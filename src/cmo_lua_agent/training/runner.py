"""Training Workflow 的持久化调度循环。

调用链：``TrainingService -> 后台 runtime -> TrainingRunner -> CampaignDriver``。
本模块只根据 ``runs/training/<workflow_id>/state.json`` 推进下一项动作；
候选生成、CMO 执行、排名和 Phase 7 仍属于 Campaign。这样进程重启后只需读取
状态即可继续，而不依赖聊天上下文或内存中的执行进度。
"""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
import subprocess
from typing import Protocol

from cmo_lua_agent.training.models import (
    Phase8Progress,
    Phase8Status,
    TrainingAction,
    TrainingStage,
    TrainingState,
    TrainingStatus,
)
from cmo_lua_agent.training.store import TrainingStore
from cmo_lua_agent.training.failures import FailureClassifier, FailureKind, FailureRecord
from cmo_lua_agent.training.reporting import TrainingReportWriter
from cmo_lua_agent.training.recovery import (
    ErrorEnvelope,
    RecoveryDecision,
    RecoveryRouter,
    RepairContextBuilder,
    append_known_issue,
    append_recovery_report,
)
from cmo_lua_agent.training.repair import RepairSnapshot


class CampaignDriver(Protocol):
    """TrainingRunner 使用的最小 Campaign 适配面。

Runner 只能调用这组调度动作，不能访问 Campaign 的私有 Store 或内部服务，避免
训练层再次实现一套 Campaign 状态机。
    """

    def prepare(self, request) -> str: ...
    def preview(self, campaign_id: str, generation_index: int) -> None: ...
    def execute(self, campaign_id: str, generation_index: int) -> None: ...
    def inspect_generation(self, campaign_id: str, generation_index: int) -> dict[str, object]: ...
    def pause(self, campaign_id: str) -> None: ...
    def resume(self, campaign_id: str) -> None: ...
    def stop(self, campaign_id: str) -> None: ...
    def reconcile(self, campaign_id: str) -> dict[str, object]: ...
    def run_phase8(self, campaign_id: str, completed_generations: tuple[int, ...]) -> dict[str, object]: ...


class TrainingRunner:
    """按持久化状态推进训练，并把失败分流到重试或代码修复。

负责：读取/写入 TrainingStore、驱动 Campaign、在所有代结束后统一触发 Phase 8。
不负责：生成策略、执行 CMO、选择 Champion。

每一次状态推进都会落盘，因此 ``run`` 可以在后台循环中反复调用；进程异常退出后
新的 runtime 会从同一 action 恢复，不会把已完成的 Generation 当作未开始。
    """

    def __init__(
        self,
        store: TrainingStore,
        driver: CampaignDriver,
        *,
        repair_coordinator: object | None = None,
        recovery_router: RecoveryRouter | None = None,
        context_builder: RepairContextBuilder | None = None,
    ) -> None:
        self._store = store
        self._driver = driver
        self._repair = repair_coordinator
        self._failures = FailureClassifier()
        self._recovery_router = recovery_router or RecoveryRouter()
        self._context_builder = context_builder or RepairContextBuilder(
            project_root=self._store.root.parents[2]
        )

    def run(self) -> TrainingState:
        """在独占锁内连续执行无需等待外部结果的动作。

返回时要么到达 ``IDLE``/终态，要么等待 CMO Worker，要么保留 retry 退避信息。
锁只保护本 Workflow，多个 Workflow 仍可独立运行。
        """
        with self._store.lock():
            while True:
                before = self._store.load_state()
                after = self.run_once()
                if after.action is TrainingAction.IDLE or after == before or self._retry_pending(after):
                    return after

    def run_once(self) -> TrainingState:
        """执行一个可恢复动作，并按错误类别决定重试、代码修复或向上抛出。

短暂端点/进程失败保留原 action 和退避时间，下一次后台轮询会重试同一动作；
Python 系统错误交给 CodeRepairCoordinator。业务执行结果不会在这里被伪造为成功。
        """
        pending = self._pending_code_repair(self._store.load_state())
        if pending is not None:
            return self._resume_code_repair(pending)
        try:
            state = self._run_once()
            # 动作成功并已持久化，说明此前可重试的外部结果已被替换；清理退避信息，
            # 防止下一阶段无故沿用前一阶段的等待时间。
            if self._retry_pending(state) or isinstance(state.runner.get("recovery"), dict):
                runner = {
                    key: value
                    for key, value in state.runner.items()
                    if key not in {"retry", "recovery"}
                }
                runner["recovery"] = {"status": "IDLE"}
                return self._store.transition(runner=runner)
            return state
        except Exception as exc:
            state = self._store.load_state()
            record = self._failures.classify(exc)
            envelope = ErrorEnvelope.capture(
                workflow_id=state.workflow_id,
                stage=state.stage.value,
                generation=state.current_generation,
                task=state.action.value,
                subtask=getattr(exc, "candidate_id", None),
                error=exc,
                stderr_path=self._store.root / "runner.log",
            )
            decision = self._recovery_router.decide(envelope)
            if decision.relevant_files:
                envelope = replace(
                    envelope,
                    related_files=list(
                        dict.fromkeys((*envelope.related_files, *decision.relevant_files))
                    ),
                )
            recovery = self._next_recovery(state, envelope, decision)
            self._store.append_event({
                "event": "recovery_incident",
                "kind": record.kind.value,
                "error_type": record.error_type,
                "message": record.message,
                "stage": envelope.stage,
                "action": envelope.task,
                "generation": envelope.generation,
                "recovery_category": decision.category,
                "recovery_action": decision.action,
                "attempt": recovery["attempts"],
            })
            if int(recovery["attempts"]) >= 3 and decision.action != "CODE_REPAIR":
                self._append_recovery_report(envelope, decision, recovery, "三次恢复失败，Workflow 已停止")
                return self._store.transition(
                    status=TrainingStatus.STOPPED,
                    action=TrainingAction.IDLE,
                    runner={**state.runner, "recovery": recovery},
                )
            if decision.action == "RETRY":
                # 保留当前已持久化 action，后台 Runtime 在短暂等待后即可无人工介入地
                # 重试同一步骤。CandidateProposalError 表示模型给出了无效候选方案，
                # 下一次 Preview 会重新生成该提案，而非要求用户处理。
                runner = self._next_retry(state, record)
                runner["recovery"] = recovery
                self._append_recovery_report(envelope, decision, recovery, "等待重试原 action")
                return self._store.transition(runner=runner)
            if decision.action == "DOMAIN_REPAIR":
                repair_current = getattr(self._driver, "repair_current", None)
                if callable(repair_current):
                    repair_current(state.campaign_id, state.current_generation, envelope)
                elif record.error_type != "CandidateProposalError":
                    self._append_recovery_report(
                        envelope, decision, recovery, "Driver 没有领域修复入口，Workflow 已停止"
                    )
                    return self._store.transition(
                        status=TrainingStatus.STOPPED,
                        action=TrainingAction.IDLE,
                        runner={**state.runner, "recovery": recovery},
                    )
                runner = self._next_retry(state, record)
                runner["recovery"] = recovery
                self._append_recovery_report(
                    envelope, decision, recovery, "已进入既有领域修复/Preview 再生路径"
                )
                return self._store.transition(runner=runner)
            if decision.action == "CODE_REPAIR" and self._repair is not None:
                return self._execute_code_repair(
                    state=state,
                    record=record,
                    envelope=envelope,
                    decision=decision,
                    recovery=recovery,
                )
            self._append_recovery_report(
                envelope, decision, recovery, "没有可执行的恢复路径，Workflow 已停止"
            )
            return self._store.transition(
                status=TrainingStatus.STOPPED,
                action=TrainingAction.IDLE,
                runner={**state.runner, "recovery": recovery},
            )

    def _execute_code_repair(
        self,
        *,
        state: TrainingState,
        record: FailureRecord,
        envelope: ErrorEnvelope,
        decision: RecoveryDecision,
        recovery: dict[str, object],
    ) -> TrainingState:
        """执行一次 CODE_REPAIR，并把 Coordinator 进度原子写回 recovery 状态。"""

        request = self._store.load_request()
        repair_context = self._context_builder.build(
            original_task=asdict(request),
            training_state=asdict(state),
            envelope=envelope,
            last_good_commit=state.last_good_commit,
        )

        def progress(status: str, metadata: dict[str, object]) -> None:
            current = self._store.load_state()
            current_recovery = current.runner.get("recovery")
            persisted = dict(current_recovery) if isinstance(current_recovery, dict) else dict(recovery)
            persisted.update(metadata)
            persisted["status"] = status
            runner = {**current.runner, "recovery": persisted}
            top_status = (
                TrainingStatus.REPAIRING
                if status in {"REPAIRING", "VERIFYING", "COMMITTED"}
                else TrainingStatus.RUNNING
            )
            self._store.transition(status=top_status, runner=runner)
            self._store.append_event(
                {
                    "event": "code_repair_progress",
                    "status": status,
                    "attempt": persisted.get("attempts"),
                    **metadata,
                }
            )

        result = self._repair.repair(
            workflow_id=state.workflow_id,
            record=record,
            envelope=envelope,
            repair_context=repair_context,
            test_command="python -m pytest src/cmo_lua_agent/tests/training -q",
            replay_task=lambda: self._reconcile_failed_action(envelope),
            attempt=int(recovery["attempts"]),
            progress_callback=progress,
        )
        current = self._store.load_state()
        current_recovery = current.runner.get("recovery")
        persisted = dict(current_recovery) if isinstance(current_recovery, dict) else dict(recovery)
        if getattr(result, "succeeded", False):
            runner = {key: value for key, value in current.runner.items() if key not in {"retry", "recovery"}}
            runner["recovery"] = {"status": "IDLE"}
            self._append_recovery_report(
                envelope,
                decision,
                recovery,
                "代码修复、验证、失败 action 对账及提交成功",
                getattr(result, "summary", ""),
            )
            commit_id = getattr(result, "commit_id", None)
            if commit_id and decision.category in {"CODE", "UNKNOWN"}:
                append_known_issue(
                    project_root=self._store.root.parents[2],
                    envelope=envelope,
                    decision=decision,
                    root_cause=getattr(result, "summary", decision.reason),
                    changed_files=getattr(result, "changed_files", ()),
                    verification=getattr(result, "verification", ()),
                    commit_id=commit_id,
                )
            return self._store.transition(
                status=TrainingStatus.RUNNING,
                last_good_commit=commit_id,
                runner=runner,
            )
        if getattr(result, "push_failed", False) or getattr(result, "commit_failed_after_replay", False):
            self._append_recovery_report(
                envelope,
                decision,
                recovery,
                "Git 收口失败，保留已验证源码/提交并停止",
                getattr(result, "summary", ""),
            )
            return self._store.transition(
                status=TrainingStatus.STOPPED,
                action=TrainingAction.IDLE,
                runner={**current.runner, "recovery": persisted},
            )
        if not self._head_matches(state.last_good_commit):
            self._append_recovery_report(
                envelope,
                decision,
                recovery,
                "修复失败后 HEAD 与 last_good_commit 不一致；Workflow 已停止",
            )
            return self._store.transition(
                status=TrainingStatus.STOPPED,
                action=TrainingAction.IDLE,
                runner={**current.runner, "recovery": persisted},
            )
        if int(recovery["attempts"]) >= 3:
            persisted["status"] = "FAILED"
            self._append_recovery_report(envelope, decision, recovery, "三次代码修复失败，Workflow 已停止")
            return self._store.transition(
                status=TrainingStatus.STOPPED,
                action=TrainingAction.IDLE,
                runner={**current.runner, "recovery": persisted},
            )
        runner = self._next_retry(current, record)
        persisted["status"] = "FAILED"
        persisted["stop_reason"] = getattr(result, "summary", "repair_failed")
        runner["recovery"] = persisted
        self._append_recovery_report(
            envelope,
            decision,
            recovery,
            "代码修复失败，源码已恢复并等待下一次修复",
            getattr(result, "summary", ""),
        )
        return self._store.transition(status=TrainingStatus.RUNNING, runner=runner)

    def _pending_code_repair(self, state: TrainingState) -> dict[str, object] | None:
        recovery = state.runner.get("recovery")
        if not isinstance(recovery, dict):
            return None
        if recovery.get("action") != "CODE_REPAIR" or recovery.get("status") != "FAILED":
            return None
        if int(recovery.get("attempts", 0)) >= 3 and not recovery.get("resume_ready"):
            return None
        return recovery

    def _resume_code_repair(self, recovery: dict[str, object]) -> TrainingState:
        """从持久化 ErrorEnvelope 重新开始 Agent，不恢复旧对话或重新触发失败 action。"""

        state = self._store.load_state()
        raw_envelope = recovery.get("envelope")
        if not isinstance(raw_envelope, dict):
            return self._store.transition(status=TrainingStatus.STOPPED, action=TrainingAction.IDLE)
        envelope = ErrorEnvelope(**raw_envelope)
        attempts = int(recovery.get("attempts", 0))
        if recovery.get("resume_ready"):
            recovery = {**recovery, "resume_ready": False}
        else:
            attempts += 1
            recovery = {**recovery, "attempts": attempts}
        if attempts > 3:
            return self._store.transition(
                status=TrainingStatus.STOPPED,
                action=TrainingAction.IDLE,
                runner={**state.runner, "recovery": recovery},
            )
        self._store.transition(
            status=TrainingStatus.RUNNING,
            runner={key: value for key, value in state.runner.items() if key != "retry"} | {"recovery": recovery},
        )
        record = FailureRecord(FailureKind.CODE, envelope.error_type, envelope.message)
        decision = RecoveryDecision(
            str(recovery.get("category", "CODE")),
            "CODE_REPAIR",
            str(recovery.get("reason", "持久化代码故障恢复")),
            list(recovery.get("relevant_files", [])),
        )
        return self._execute_code_repair(
            state=state,
            record=record,
            envelope=envelope,
            decision=decision,
            recovery=recovery,
        )

    def _reconcile_failed_action(self, envelope: ErrorEnvelope) -> TrainingState:
        """复用 Campaign 持久化事实，只推进原失败 action 的未完成最小步骤。"""

        state = self._store.load_state()
        request = self._store.load_request()
        try:
            action = TrainingAction(envelope.task)
        except ValueError as exc:
            raise RuntimeError(f"unknown failed training action: {envelope.task}") from exc
        if state.campaign_id is None:
            if action not in {TrainingAction.VALIDATE_INPUT, TrainingAction.PREPARE_CAMPAIGN}:
                raise RuntimeError("failed action has no campaign to reconcile")
            campaign_id = self._driver.prepare(request)
            return self._store.transition(
                campaign_id=campaign_id,
                status=TrainingStatus.REPAIRING,
                stage=TrainingStage.EVOLUTION,
                action=TrainingAction.PREVIEW,
            )

        self._driver.reconcile(state.campaign_id)
        inspected = self._driver.inspect_generation(state.campaign_id, state.current_generation)
        if action is TrainingAction.PREVIEW:
            if inspected.get("preview") is None:
                self._driver.preview(state.campaign_id, state.current_generation)
            return self._store.transition(action=TrainingAction.EXECUTE)
        if action is TrainingAction.EXECUTE:
            worker_status = str(inspected.get("status", "")).lower()
            if worker_status == "completed":
                return self._store.transition(action=TrainingAction.SUMMARIZE)
            if worker_status in {"running", "started", "authorized", "queued"}:
                return self._store.transition(action=TrainingAction.WAIT_WORKER)
            if worker_status in {"unknown", "cancelled_incomplete"}:
                raise RuntimeError("worker execution is unknown; refusing duplicate CMO start")
            if worker_status == "ready" and not inspected.get("operation_id"):
                self._driver.execute(state.campaign_id, state.current_generation)
                return self._store.transition(action=TrainingAction.SUMMARIZE)
            raise RuntimeError(f"worker status cannot be safely replayed: {worker_status}")
        if action in {TrainingAction.WAIT_WORKER, TrainingAction.SUMMARIZE}:
            next_action = (
                TrainingAction.SUMMARIZE
                if str(inspected.get("status", "")).lower() == "completed"
                else TrainingAction.WAIT_WORKER
            )
            return self._store.transition(action=next_action)
        raise RuntimeError(f"failed action is not replayable: {action.value}")

    @staticmethod
    def _is_retryable_generation_failure(record) -> bool:
        return record.kind is FailureKind.TRANSIENT or (
            record.kind is FailureKind.BUSINESS
            and record.error_type == "CandidateProposalError"
        )

    @staticmethod
    def _retry_pending(state: TrainingState) -> bool:
        return isinstance(state.runner.get("retry"), dict)

    @staticmethod
    def _next_retry(state: TrainingState, record) -> dict[str, object]:
        """为同一持久化动作计算有上限的指数退避信息。

        此处只更新 ``state.runner.retry``，不改变 action 或代索引；进程重启后仍会继续
        失败前的精确步骤，而不会跳过 CMO 执行或重复已完成的代。
        """
        previous = state.runner.get("retry")
        prior_count = previous.get("consecutive_failures", 0) if isinstance(previous, dict) else 0
        count = int(prior_count) + 1
        delay_seconds = min(5 * (2 ** (count - 1)), 60)
        next_retry_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)
        return {
            **state.runner,
            "retry": {
                "kind": record.kind.value,
                "error_type": record.error_type,
                "message": record.message,
                "consecutive_failures": count,
                "next_retry_at": next_retry_at.isoformat(),
            },
        }

    @staticmethod
    def _next_recovery(state: TrainingState, envelope, decision) -> dict[str, object]:
        """按持久化 stage/action/generation 识别同一事故并累加恢复次数。"""

        previous = state.runner.get("recovery")
        same_action = isinstance(previous, dict) and (
            previous.get("stage") == envelope.stage
            and previous.get("task") == envelope.task
            and previous.get("generation") == envelope.generation
        )
        attempts = int(previous.get("attempts", 0)) + 1 if same_action else 1
        return {
            "status": "FAILED",
            "stage": envelope.stage,
            "task": envelope.task,
            "generation": envelope.generation,
            "attempts": attempts,
            "category": decision.category,
            "action": decision.action,
            "error_type": envelope.error_type,
            "message": envelope.message,
            "reason": decision.reason,
            "relevant_files": list(decision.relevant_files),
            "envelope": envelope.to_dict(),
        }

    def _append_recovery_report(
        self,
        envelope,
        decision,
        recovery: dict[str, object],
        result: str,
        details: str = "",
    ) -> None:
        append_recovery_report(
            self._store.root / "recovery-report.md",
            envelope=envelope,
            decision=decision,
            attempt=int(recovery["attempts"]),
            result=result,
            details=details,
        )

    def _head_matches(self, last_good_commit: str | None) -> bool:
        """只读检查源码恢复边界；不使用 reset 覆盖用户工作区。"""

        if not last_good_commit:
            return True
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self._store.root.parents[2],
            text=True,
            capture_output=True,
        )
        return completed.returncode == 0 and completed.stdout.strip() == last_good_commit

    def _run_once(self) -> TrainingState:
        """依据 ``state.json`` 的 action 执行唯一的下一步状态转换。"""
        request = self._store.load_request()
        state = self._store.load_state()
        if state.status in {TrainingStatus.PAUSED, TrainingStatus.STOPPED, TrainingStatus.FAILED}:
            return state
        if state.campaign_id is None:
            campaign_id = self._driver.prepare(request)
            self._store.append_event({"event": "campaign_prepared", "campaign_id": campaign_id})
            return self._store.transition(
                campaign_id=campaign_id,
                status=TrainingStatus.RUNNING,
                stage=TrainingStage.EVOLUTION,
                action=TrainingAction.PREVIEW,
            )

        if request.generation_count is None:
            raise ValueError("fixed_generation_count_required")
        if len(state.completed_generations) >= request.generation_count:
            # Phase 8 只在全部 Generation 的正式结果已落盘后运行一次，避免聚合过程
            # 与新的经验写入并发，从而让 Skill 证据集合保持本轮训练结束时的边界。
            if state.phase8.status is Phase8Status.NOT_STARTED:
                result = self._driver.run_phase8(
                    state.campaign_id,
                    state.completed_generations,
                )
                phase8_job_id = str(result.get("job_id") or result.get("phase8_run_id") or "")
                if not self._phase8_finished(result):
                    return self._store.transition(
                        status=TrainingStatus.FAILED,
                        stage=TrainingStage.PHASE8,
                        action=TrainingAction.IDLE,
                        phase8=Phase8Progress(Phase8Status.FAILED, phase8_job_id),
                    )
                self._store.append_event({"event": "phase8_completed", "campaign_id": state.campaign_id})
                completed = self._store.transition(
                    status=TrainingStatus.COMPLETED,
                    stage=TrainingStage.REPORT,
                    action=TrainingAction.IDLE,
                    phase8=Phase8Progress(Phase8Status.COMPLETED, phase8_job_id),
                )
                self._write_reports(completed)
                return completed
            completed = self._store.transition(
                status=TrainingStatus.COMPLETED,
                stage=TrainingStage.REPORT,
                action=TrainingAction.IDLE,
            )
            self._write_reports(completed)
            return completed

        generation_index = state.current_generation
        if state.action in {TrainingAction.VALIDATE_INPUT, TrainingAction.PREVIEW}:
            self._driver.preview(state.campaign_id, generation_index)
            self._store.append_event({"event": "generation_previewed", "generation_index": generation_index})
            return self._store.transition(
                status=TrainingStatus.RUNNING,
                stage=TrainingStage.EVOLUTION,
                action=TrainingAction.EXECUTE,
            )
        if state.action is TrainingAction.EXECUTE:
            self._driver.execute(state.campaign_id, generation_index)
            self._store.append_event({"event": "generation_executed", "generation_index": generation_index})
            return self._store.transition(action=TrainingAction.SUMMARIZE)
        if state.action is TrainingAction.SUMMARIZE:
            inspected = self._driver.inspect_generation(state.campaign_id, generation_index)
            if self._worker_failed(inspected):
                return self._mark_worker_failed(state, generation_index, inspected)
            if inspected.get("status") != "completed":
                return self._store.transition(action=TrainingAction.WAIT_WORKER)
            # completed_generations 是恢复时判断“哪一代已有正式结果”的唯一调度事实；
            # 只有 Worker 明确 completed 后才推进，不能用内存中的 execute 调用代替。
            completed = tuple(sorted((*state.completed_generations, generation_index)))
            self._store.append_event({"event": "generation_completed", "generation_index": generation_index})
            return self._store.transition(
                completed_generations=completed,
                current_generation=generation_index + 1,
                action=TrainingAction.PREVIEW,
            )
        if state.action is TrainingAction.WAIT_WORKER:
            inspected = self._driver.inspect_generation(state.campaign_id, generation_index)
            if self._worker_failed(inspected):
                return self._mark_worker_failed(state, generation_index, inspected)
            if inspected.get("status") == "completed":
                return self._store.transition(action=TrainingAction.SUMMARIZE)
            return state
        return state

    def _write_reports(self, state: TrainingState) -> None:
        """在终态后从持久化状态生成报告；该操作不改变训练状态。"""
        TrainingReportWriter(self._store).write(state)

    @staticmethod
    def _phase8_finished(result: dict[str, object]) -> bool:
        return result.get("status") in {"completed", "NO_PROMOTABLE_EXPERIENCE", "pending_review"}

    @staticmethod
    def _worker_failed(inspected: dict[str, object]) -> bool:
        return str(inspected.get("status", "")).lower() in {
            "failed",
            "cancelled_incomplete",
        }

    def _mark_worker_failed(
        self,
        state: TrainingState,
        generation_index: int,
        inspected: dict[str, object],
    ) -> TrainingState:
        """记录 Worker 已确认的失败，并将 Workflow 置为终态。

        Runner 不猜测失败原因或伪造完成结果；更细的 CMO/候选方案恢复由 Campaign 在
        执行阶段处理，从而避免训练层与 Campaign 状态机承担重复职责。
        """
        self._store.append_event({
            "event": "generation_worker_failed",
            "generation_index": generation_index,
            "worker_status": inspected.get("status"),
        })
        return self._store.transition(
            status=TrainingStatus.FAILED,
            action=TrainingAction.IDLE,
        )

    def reconcile(self) -> TrainingState:
        """启动或恢复前先收口中断修复，再让 Campaign 对账持久化业务事实。"""
        state = self._store.load_state()
        recovery = state.runner.get("recovery")
        if isinstance(recovery, dict) and recovery.get("status") == "COMMITTED":
            commit_id = recovery.get("commit_id")
            if not isinstance(commit_id, str) or not commit_id:
                return self._store.transition(
                    status=TrainingStatus.STOPPED,
                    action=TrainingAction.IDLE,
                    runner={**state.runner, "recovery": {**recovery, "status": "FAILED", "stop_reason": "commit_id_missing"}},
                )
            if recovery.get("push_completed") is True:
                result = None
                succeeded = True
            else:
                resume = getattr(self._repair, "resume_committed", None)
                result = resume(workflow_id=state.workflow_id, commit_id=commit_id) if callable(resume) else None
                succeeded = bool(getattr(result, "succeeded", False))
            if not succeeded:
                return self._store.transition(
                    status=TrainingStatus.STOPPED,
                    action=TrainingAction.IDLE,
                    runner={**state.runner, "recovery": {**recovery, "status": "FAILED", "stop_reason": "committed_push_failed"}},
                )
            snapshot_path = recovery.get("snapshot_path")
            if isinstance(snapshot_path, str):
                try:
                    RepairSnapshot(
                        project_root=self._store.root.parents[2],
                        archive_path=Path(snapshot_path),
                    ).discard()
                except (OSError, ValueError):
                    pass
            state = self._store.transition(
                status=TrainingStatus.RUNNING,
                last_good_commit=commit_id,
                runner={
                    **{key: value for key, value in state.runner.items() if key not in {"retry", "recovery"}},
                    "recovery": {"status": "IDLE"},
                },
            )
            self._store.append_event(
                {"event": "committed_code_repair_resumed", "commit_id": commit_id}
            )
            recovery = state.runner.get("recovery")
        if isinstance(recovery, dict) and recovery.get("status") in {"REPAIRING", "VERIFYING"}:
            snapshot_path = recovery.get("snapshot_path")
            if not isinstance(snapshot_path, str):
                recovery = {**recovery, "status": "FAILED", "stop_reason": "snapshot_missing"}
                return self._store.transition(
                    status=TrainingStatus.STOPPED,
                    action=TrainingAction.IDLE,
                    runner={**state.runner, "recovery": recovery},
                )
            try:
                snapshot = RepairSnapshot(
                    project_root=self._store.root.parents[2],
                    archive_path=Path(snapshot_path),
                )
                snapshot.restore()
                snapshot.discard()
            except Exception as exc:
                recovery = {
                    **recovery,
                    "status": "FAILED",
                    "stop_reason": f"snapshot_restore_failed:{type(exc).__name__}",
                }
                return self._store.transition(
                    status=TrainingStatus.STOPPED,
                    action=TrainingAction.IDLE,
                    runner={**state.runner, "recovery": recovery},
                )
            attempts = int(recovery.get("attempts", 0)) + 1
            recovery = {
                **recovery,
                "status": "FAILED",
                "attempts": attempts,
                "resume_ready": True,
                "stop_reason": "repair_process_interrupted",
                "snapshot_path": None,
            }
            state = self._store.transition(
                status=TrainingStatus.RUNNING,
                runner={**state.runner, "recovery": recovery},
            )
            self._store.append_event(
                {
                    "event": "interrupted_code_repair_restored",
                    "attempt": attempts,
                    "action": recovery.get("task"),
                }
            )
            if attempts > 3:
                return self._store.transition(
                    status=TrainingStatus.STOPPED,
                    action=TrainingAction.IDLE,
                    runner={**state.runner, "recovery": recovery},
                )
        if state.campaign_id is not None:
            self._driver.reconcile(state.campaign_id)
            self._store.append_event({"event": "campaign_reconciled", "campaign_id": state.campaign_id})
        return self._store.load_state()

    def pause(self) -> TrainingState:
        """请求 Campaign 在安全边界暂停，并持久化 Training 的暂停意图。"""
        state = self._store.load_state()
        if state.campaign_id is not None and state.status is not TrainingStatus.PAUSED:
            self._driver.pause(state.campaign_id)
            self._store.append_event({"event": "workflow_paused", "campaign_id": state.campaign_id})
        return self._store.transition(status=TrainingStatus.PAUSED)

    def resume(self) -> TrainingState:
        """对账后恢复已暂停的 Workflow，避免用旧内存状态覆盖 Campaign 真实进度。"""
        state = self._store.load_state()
        if state.status is not TrainingStatus.PAUSED:
            return state
        if state.campaign_id is not None:
            self._driver.reconcile(state.campaign_id)
            self._driver.resume(state.campaign_id)
            self._store.append_event({"event": "workflow_resumed", "campaign_id": state.campaign_id})
        return self._store.transition(status=TrainingStatus.RUNNING)

    def stop(self) -> TrainingState:
        """请求停止并使 Workflow 进入终态；不再触发后续 Generation 或 Phase 8。"""
        state = self._store.load_state()
        if state.status is TrainingStatus.STOPPED:
            return state
        if state.campaign_id is not None:
            self._driver.stop(state.campaign_id)
            self._store.append_event({"event": "workflow_stopped", "campaign_id": state.campaign_id})
        return self._store.transition(status=TrainingStatus.STOPPED, action=TrainingAction.IDLE)
