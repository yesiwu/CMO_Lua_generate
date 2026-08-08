"""
Phase 9 推演任务控制平面状态的原子持久化模块

账本(ledger)与检查点(checkpoint)做刻意分离设计：
- checkpoint（检查点）：记录工作节点恢复上下文，用于进程重启后继续执行任务；
- ledger（操作流水账本）：记录所有外部可见操作全生命周期，是故障对账、状态一致性修复的唯一可信数据源。
"""
from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
from threading import RLock
from typing import Any
from datetime import UTC, datetime

# 推演演化领域模型定义
from cmo_lua_agent.evolution.models import (
    CampaignState,
    CampaignStatus,
    ControlAction,
    ControlRequest,
    GenerationApproval,
    GenerationPreview,
    OperationKind,
    OperationRecord,
    OperationStatus,
    StopReason,
    WorkerState,
)
from cmo_lua_agent.evolution.production_models import GenerationApprovalGrant


class CampaignStore:
    """
    基于本地文件实现的持久化存储
    所有可变记录均采用「临时文件写入 + 原子重命名替换」，防止程序崩溃产生损坏的半写文件。
    """

    _shared_locks: dict[str, RLock] = {}
    _shared_locks_guard = RLock()

    def __init__(self, root: Path) -> None:
        # 存储根目录，该目录对应单一推演任务campaign
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        # 操作流水账本文件路径，jsonl格式保存所有操作记录
        self._ledger_path = self.root / "operation-ledger.jsonl"
        # 可重入锁：保护并发下状态更新、账本修改、配额变更，防止竞态条件
        root_key = str(self.root)
        with self._shared_locks_guard:
            self._lock = self._shared_locks.setdefault(root_key, RLock())
        self._control_state_path = self.root / "campaign-control-state.json"

    # ===================== 推演任务全局状态 CampaignState =====================
    def save_campaign_state(self, state: CampaignState) -> None:
        """持久化推演任务全局状态"""
        self._write_json(self.root / "campaign-state.json", self._state_dict(state))

    def load_campaign_state(self) -> CampaignState:
        """加载推演任务全局状态；文件不存在抛出异常"""
        path = self.root / "campaign-state.json"
        if not path.is_file():
            raise ValueError("campaign_state_not_found")
        value = self._read_json(path)
        return CampaignState(
            campaign_id=str(value["campaign_id"]),
            status=CampaignStatus(value["status"]),
            current_generation=int(value.get("current_generation", 0)),
            completed_generations=int(value.get("completed_generations", 0)),
            cmo_run_count=int(value.get("cmo_run_count", 0)),
            failed_run_count=int(value.get("failed_run_count", 0)),
            llm_call_counts=dict(value.get("llm_call_counts", {})),
            best_champion_ref=value.get("best_champion_ref"),
            best_official_score=value.get("best_official_score"),
            no_improvement_count=int(value.get("no_improvement_count", 0)),
            stop_reason=StopReason(value.get("stop_reason", StopReason.NONE.value)),
            budget_revision=int(value.get("budget_revision", 0)),
        )

    def update_campaign_state(self, **changes: Any) -> CampaignState:
        """原子更新任务全局状态：读取 -> 修改字段 -> 写回持久化文件"""
        with self._lock:
            current = self.load_campaign_state()
            values = asdict(current)
            values.update(changes)
            # 枚举字符串兼容反序列化
            if isinstance(values.get("status"), str):
                values["status"] = CampaignStatus(values["status"])
            if isinstance(values.get("stop_reason"), str):
                values["stop_reason"] = StopReason(values["stop_reason"])
            updated = CampaignState(**values)
            self.save_campaign_state(updated)
            return updated

    def increment_llm_calls(self, kind: str, count: int = 1) -> CampaignState:
        """原子累加指定类型LLM调用计数，用于统计算力开销"""
        with self._lock:
            state = self.load_campaign_state()
            calls = dict(state.llm_call_counts)
            calls[kind] = int(calls.get(kind, 0)) + count
            return self.update_campaign_state(llm_call_counts=calls)

    # ===================== 运维控制指令 & Worker恢复检查点 =====================
    def request_control(self, request: ControlRequest) -> None:
        """下发运维控制指令（暂停/终止/恢复推演）"""
        self._write_json(
            self.root / "control-request.json",
            {"action": request.action.value, "requested_at": request.requested_at, "reason": request.reason},
        )

    def get_control_request(self) -> ControlRequest | None:
        """读取当前生效的控制指令，无指令返回None"""
        path = self.root / "control-request.json"
        if not path.is_file():
            return None
        value = self._read_json(path)
        return ControlRequest(ControlAction(value["action"]), str(value["requested_at"]), value.get("reason"))

    def clear_control_request(self) -> None:
        """清除已执行完毕的控制指令文件"""
        path = self.root / "control-request.json"
        if path.exists():
            path.unlink()

    def save_checkpoint(self, value: dict[str, Any]) -> None:
        """保存Worker运行检查点，用于故障后恢复上下文继续执行"""
        self._write_json(self.root / "checkpoint.json", value)

    def load_checkpoint(self) -> dict[str, Any] | None:
        """加载检查点，不存在返回None"""
        path = self.root / "checkpoint.json"
        return self._read_json(path) if path.is_file() else None

    # ===================== 世代策略预览 GenerationPreview =====================
    def save_preview(self, preview: GenerationPreview) -> None:
        """保存单世代策略预览快照（候选策略、策略差异对比）"""
        self._write_json(self._preview_path(preview.generation_index, preview.preview_revision), self._preview_dict(preview))

    def get_preview(self, generation_index: int, preview_revision: int | None = None) -> GenerationPreview | None:
        """
        获取指定世代预览快照
        preview_revision=None：自动读取该世代最新版本预览
        """
        directory = self.root / "previews" / f"generation_{generation_index:03d}"
        if preview_revision is None:
            candidates = sorted(directory.glob("preview_*.json")) if directory.is_dir() else []
            if not candidates:
                return None
            path = candidates[-1]
        else:
            path = self._preview_path(generation_index, preview_revision)
        return self._preview_from_dict(self._read_json(path)) if path.is_file() else None

    def next_preview_revision(self, generation_index: int) -> int:
        """获取下一个预览版本号，用于迭代更新预览快照"""
        current = self.get_preview(generation_index)
        persisted = -1 if current is None else current.preview_revision
        directory = self.root / "previews" / f"generation_{generation_index:03d}"
        for path in directory.glob("revision_*") if directory.is_dir() else ():
            suffix = path.name.removeprefix("revision_")
            if suffix.isdecimal():
                persisted = max(persisted, int(suffix))
        return persisted + 1

    # ===================== 世代审批记录 GenerationApproval =====================
    def save_approval(self, approval: GenerationApproval) -> None:
        """保存一条世代仿真审批单据"""
        self._write_json(self._approval_path(approval.approval_id), self._approval_dict(approval))

    def get_approval(self, approval_id: str) -> GenerationApproval | None:
        """通过审批ID查询审批记录"""
        path = self._approval_path(approval_id)
        return self._approval_from_dict(self._read_json(path)) if path.is_file() else None

    def get_active_approval(self, *, campaign_id: str, generation_index: int) -> GenerationApproval | None:
        """查询指定世代当前有效的审批单（最新一份合法审批）"""
        directory = self.root / "approvals"
        if not directory.is_dir():
            return None
        records = [self._approval_from_dict(self._read_json(path)) for path in directory.glob("*.json")]
        matches = [item for item in records if item.valid and item.campaign_id == campaign_id and item.generation_index == generation_index]
        return sorted(matches, key=lambda item: item.approval_id)[-1] if matches else None

    def invalidate_approvals(self, *, generation_index: int | None = None, reason: str) -> None:
        """批量作废审批单据；可限定指定世代，写入失效原因"""
        directory = self.root / "approvals"
        if not directory.is_dir():
            return
        for path in directory.glob("*.json"):
            approval = self._approval_from_dict(self._read_json(path))
            if generation_index is not None and approval.generation_index != generation_index:
                continue
            if approval.valid:
                self._write_json(path, {**self._approval_dict(approval), "valid": False, "invalidated_reason": reason})

    # ===================== Worker 工作节点运行状态 =====================
    def save_worker(self, worker: WorkerState) -> None:
        """持久化单个工作节点运行状态"""
        self._write_json(self._worker_path(worker.operation_id), self._worker_dict(worker))

    def get_worker(self, operation_id: str) -> WorkerState | None:
        """根据操作ID查询工作节点状态"""
        path = self._worker_path(operation_id)
        return self._worker_from_dict(self._read_json(path)) if path.is_file() else None

    def list_workers(self) -> tuple[WorkerState, ...]:
        """列出全部已持久化的工作节点状态"""
        directory = self.root / "workers"
        if not directory.is_dir():
            return ()
        return tuple(self._worker_from_dict(self._read_json(path)) for path in sorted(directory.glob("*.json")))

    def get_active_worker(self, *, campaign_id: str, generation_index: int) -> WorkerState | None:
        """查询指定世代正在运行的工作节点，防止重复启动同一个世代的仿真任务"""
        directory = self.root / "workers"
        if not directory.is_dir():
            return None
        workers = [self._worker_from_dict(self._read_json(path)) for path in directory.glob("*.json")]
        active = [item for item in workers if item.campaign_id == campaign_id and item.generation_index == generation_index and item.status == "running"]
        return active[0] if active else None

    # ===================== OperationRecord 操作流水账本（核心可信源） =====================
    def prepare_operation(self, *, generation_index: int, kind: OperationKind, input_checksum: str) -> OperationRecord:
        """
        注册一条全新操作，初始状态置为 PREPARED
        operation_id 规则：世代编号:操作类型:输入指纹前16位，全局唯一可追溯
        若操作已存在，直接返回已有记录，避免重复创建
        """
        operation_id = f"g{generation_index:03d}:{kind.value}:{input_checksum[:16]}"
        with self._lock:
            existing = self.get_operation(operation_id)
            if existing is not None:
                return existing
            record = OperationRecord(operation_id, generation_index, kind, input_checksum, OperationStatus.PREPARED, updated_at=self._now())
            self._append(record)
            return record

    def get_operation(self, operation_id: str) -> OperationRecord | None:
        """根据operation_id查询账本内操作记录"""
        for data in self._ledger_rows():
            if data["operation_id"] == operation_id:
                return self._record(data)
        return None

    def list_operations(self) -> tuple[OperationRecord, ...]:
        """读取账本中全部操作流水记录"""
        return tuple(self._record(item) for item in self._ledger_rows())

    # 操作状态流转接口
    def mark_operation_authorized(self, operation_id: str) -> OperationRecord:
        """标记操作状态：已授权"""
        return self._transition(operation_id, OperationStatus.AUTHORIZED)

    def mark_operation_started(self, operation_id: str) -> OperationRecord:
        """标记操作状态：开始执行"""
        return self._transition(operation_id, OperationStatus.STARTED)

    def mark_operation_unknown(self, operation_id: str, error: str | None = None) -> OperationRecord:
        """标记操作状态：状态未知（worker失联、进程丢失）"""
        return self._transition(operation_id, OperationStatus.UNKNOWN, error=error)

    def mark_operation_failed(self, operation_id: str, error: str) -> OperationRecord:
        """标记操作状态：执行失败，附带错误信息"""
        return self._transition(operation_id, OperationStatus.FAILED, error=error)

    def mark_operation_completed(self, operation_id: str, *, output_ref: str | None = None) -> OperationRecord:
        """标记操作状态：正常完成，绑定仿真产物路径引用"""
        return self._transition(operation_id, OperationStatus.COMPLETED, output_ref=output_ref)

    def reconcile_operation(self, operation_id: str, artifact: Path) -> OperationRecord:
        """
        外部对账校验：使用仿真输出产物校对操作记录
        校验产物内部输入指纹与账本记录一致，防止结果与请求不匹配
        """
        current = self._require(operation_id)
        artifact = Path(artifact).resolve()
        data = json.loads(artifact.read_text(encoding="utf-8"))
        if data.get("input_checksum") != current.input_checksum:
            raise ValueError("operation_artifact_checksum_mismatch")
        return self._transition(operation_id, OperationStatus.COMPLETED, output_ref=str(artifact))

    def authorize_cmo_attempt(
        self,
        *,
        operation_id: str,
        approval: GenerationApproval,
        max_cmo_runs: int,
        enforce_count_limits: bool = True,
    ) -> OperationRecord:
        """
        原子预留一次CMO仿真运行配额，并将操作状态变更为已授权
        三重限流校验：
        1. 操作必须处于PREPARED/AUTHORIZED状态
        2. 当前审批单已占用仿真次数未达上限
        3. 推演全局CMO总运行预算未耗尽
        校验通过后写入attempt-reservations.json占用配额
        """
        with self._lock:
            current = self._require(operation_id)
            if current.status not in (OperationStatus.PREPARED, OperationStatus.AUTHORIZED):
                raise ValueError("cmo_attempt_not_prepared")
            reservations = self._load_reservations()
            used = sum(1 for item in reservations.values() if item["approval_id"] == approval.approval_id)
            if used >= approval.max_cmo_attempts:
                raise ValueError("generation_approval_cap_exhausted")
            state = self.load_campaign_state()
            if enforce_count_limits and state.cmo_run_count + len(reservations) >= max_cmo_runs:
                raise ValueError("campaign_cmo_budget_exhausted")
            reservations[operation_id] = {"approval_id": approval.approval_id, "generation_index": current.generation_index}
            self._write_json(self.root / "attempt-reservations.json", reservations)
            return self._transition(operation_id, OperationStatus.AUTHORIZED)

    def mark_cmo_started(self, operation_id: str) -> OperationRecord:
        """CMO仿真正式启动：原子递增全局仿真计数，状态切换为STARTED"""
        with self._lock:
            current = self._require(operation_id)
            if current.status is not OperationStatus.AUTHORIZED:
                raise ValueError("cmo_attempt_not_authorized")
            state = self.load_campaign_state()
            self.update_campaign_state(cmo_run_count=state.cmo_run_count + 1)
            return self._transition(operation_id, OperationStatus.STARTED)

    # Phase 9C uses this single transaction document as the authority for
    # approval usage, attempt slots, CMO budget, and operation state.
    def initialize_control_state(
        self,
        *,
        max_cmo_runs: int,
        budget_revision: int,
        enforce_count_limits: bool = True,
    ) -> None:
        with self._lock:
            if self._control_state_path.exists():
                return
            self._commit_control_state({
                "schema_version": "1.0",
                "budget": {
                    "max_cmo_runs": int(max_cmo_runs),
                    "cmo_runs_started": 0,
                    "budget_revision": int(budget_revision),
                    "enforce_count_limits": bool(enforce_count_limits),
                },
                "approvals": {},
                "approval_usage": {},
                "attempt_slots": {},
                "operations": {},
                "operation_history": [],
            })

    def load_control_state(self) -> dict[str, Any]:
        if not self._control_state_path.is_file():
            raise ValueError("campaign_control_state_not_initialized")
        return self._read_json(self._control_state_path)

    def persist_generation_approval(self, grant: GenerationApprovalGrant) -> None:
        # The grant remains an audit record. Slot ownership and the hard CMO
        # ceiling, rather than a hash of preview metadata, authorize a run.
        verified = GenerationApprovalGrant.from_dict(
            grant.to_dict(), verify_checksum=False
        )
        with self._lock:
            state = self.load_control_state()
            if state["budget"]["budget_revision"] != verified.budget_revision:
                raise ValueError("generation_approval_budget_revision_mismatch")
            state["approvals"][verified.approval_id] = verified.to_dict()
            state["approval_usage"][verified.approval_id] = {
                "authorized_attempts": 0,
                "started_attempts": 0,
            }
            for operation_id in verified.approved_operation_ids:
                existing = state["attempt_slots"].get(operation_id)
                if existing is not None and existing["status"] != "available":
                    raise ValueError("attempt_slot_conflict")
                state["attempt_slots"][operation_id] = {
                    "approval_id": verified.approval_id,
                    "status": "available",
                    "reason": None,
                }
                state["operations"].setdefault(operation_id, {
                    "status": "prepared",
                    "approval_id": None,
                })
            self._commit_control_state(state)

    def authorize_attempt_slot(
        self,
        *,
        approval_id: str,
        operation_id: str,
        expected_contract_checksum: str,
        expected_snapshot_checksum: str,
        expected_candidate_set_checksum: str,
        now: str | None = None,
    ) -> None:
        with self._lock:
            state = self.load_control_state()
            raw_grant = state["approvals"].get(approval_id)
            if raw_grant is None:
                raise ValueError("generation_approval_not_found")
            grant = GenerationApprovalGrant.from_dict(
                raw_grant, verify_checksum=False
            )
            if not grant.valid:
                raise ValueError("generation_approval_invalid")
            current_time = datetime.fromisoformat(now) if now else datetime.now(UTC)
            if datetime.fromisoformat(grant.expires_at) <= current_time:
                raise ValueError("generation_approval_expired")
            # Contract/snapshot/candidate checksums are retained in the grant
            # for audit only.  A concrete approved operation slot is the
            # execution authority.
            slot = state["attempt_slots"].get(operation_id)
            if slot is None or slot["status"] != "available":
                raise ValueError("attempt_slot_not_available")
            usage = state["approval_usage"][approval_id]
            if usage["authorized_attempts"] >= grant.maximum_cmo_attempts:
                raise ValueError("generation_approval_cap_exhausted")
            if (
                state["budget"].get("enforce_count_limits", True)
                and state["budget"]["cmo_runs_started"] >= state["budget"]["max_cmo_runs"]
            ):
                raise ValueError("campaign_cmo_budget_exhausted")
            slot.update({"status": "authorized", "approval_id": approval_id})
            usage["authorized_attempts"] += 1
            state["operations"][operation_id] = {
                "status": "authorized",
                "approval_id": approval_id,
            }
            self._append_control_transition(state, operation_id, "authorized")
            self._commit_control_state(state)

    def mark_attempt_started(self, operation_id: str) -> None:
        with self._lock:
            state = self.load_control_state()
            slot = state["attempt_slots"].get(operation_id)
            if slot is None or slot["status"] != "authorized":
                raise ValueError("attempt_slot_not_authorized")
            approval_id = slot["approval_id"]
            slot["status"] = "started"
            state["operations"][operation_id]["status"] = "started"
            state["budget"]["cmo_runs_started"] += 1
            state["approval_usage"][approval_id]["started_attempts"] += 1
            self._append_control_transition(state, operation_id, "started")
            self._commit_control_state(state)
            campaign = self.load_campaign_state()
            self.save_campaign_state(
                CampaignState(
                    **{
                        **asdict(campaign),
                        "cmo_run_count": campaign.cmo_run_count + 1,
                    }
                )
            )

    def mark_attempt_completed(self, operation_id: str, *, output_ref: str) -> None:
        self._finish_attempt(operation_id, status="completed", reason=None, output_ref=output_ref)

    def mark_attempt_failed(self, operation_id: str, *, reason: str) -> None:
        self._finish_attempt(operation_id, status="failed", reason=reason, output_ref=None)

    def mark_attempt_unknown(self, operation_id: str, *, reason: str) -> None:
        self._finish_attempt(operation_id, status="unknown", reason=reason, output_ref=None)

    def invalidate_generation_approvals(self, *, generation_index: int, reason: str) -> None:
        with self._lock:
            state = self.load_control_state()
            for approval_id, raw in state["approvals"].items():
                if int(raw["generation_index"]) == generation_index and raw.get("valid", True):
                    raw["valid"] = False
                    raw["invalidated_reason"] = reason
            self._commit_control_state(state)

    def reconcile_control_state_for_resume(self) -> dict[str, Any]:
        with self._lock:
            state = self.load_control_state()
            reconciliation_required: list[str] = []
            for operation_id, slot in state["attempt_slots"].items():
                if slot["status"] == "authorized":
                    slot.update({
                        "status": "available",
                        "approval_id": None,
                        "reason": "authorization_abandoned_before_start",
                    })
                    state["operations"][operation_id]["status"] = "prepared"
                    self._append_control_transition(
                        state,
                        operation_id,
                        "authorization_abandoned_before_start",
                    )
                elif slot["status"] == "unknown":
                    reconciliation_required.append(operation_id)
            for raw in state["approvals"].values():
                raw["valid"] = False
                raw["invalidated_reason"] = "process_resume_requires_reapproval"
            self._commit_control_state(state)
            return {"reconciliation_required": sorted(reconciliation_required)}

    def _finish_attempt(
        self,
        operation_id: str,
        *,
        status: str,
        reason: str | None,
        output_ref: str | None,
    ) -> None:
        with self._lock:
            state = self.load_control_state()
            slot = state["attempt_slots"].get(operation_id)
            if slot is None or slot["status"] != "started":
                raise ValueError("attempt_slot_not_started")
            slot.update({"status": status, "reason": reason, "output_ref": output_ref})
            state["operations"][operation_id].update({
                "status": status,
                "reason": reason,
                "output_ref": output_ref,
            })
            self._append_control_transition(state, operation_id, status)
            self._commit_control_state(state)

    def _append_control_transition(
        self,
        state: dict[str, Any],
        operation_id: str,
        status: str,
    ) -> None:
        state["operation_history"].append({
            "operation_id": operation_id,
            "status": status,
            "sequence": len(state["operation_history"]),
        })

    def _commit_control_state(self, state: dict[str, Any]) -> None:
        self._write_json(self._control_state_path, state)
        rows_by_id = {
            row["operation_id"]: row
            for row in self._ledger_rows()
            if "kind" in row and "input_checksum" in row
        }
        for operation_id, value in state.get("operations", {}).items():
            try:
                generation_index = int(operation_id[1:4])
            except (TypeError, ValueError):
                generation_index = 0
            rows_by_id[operation_id] = {
                "operation_id": operation_id,
                "generation_index": generation_index,
                "kind": OperationKind.CMO.value,
                "input_checksum": operation_id,
                "status": value["status"],
                "output_ref": value.get("output_ref"),
                "error": value.get("reason"),
                "updated_at": self._now(),
            }
        self._write_ledger([rows_by_id[key] for key in sorted(rows_by_id)])

    def _transition(self, operation_id: str, status: OperationStatus, *, output_ref: str | None = None, error: str | None = None) -> OperationRecord:
        """【内部通用方法】操作状态流转：构造新记录并更新账本"""
        current = self._require(operation_id)
        record = OperationRecord(current.operation_id, current.generation_index, current.kind, current.input_checksum, status, output_ref, error, self._now())
        self._replace(record)
        return record

    def _require(self, operation_id: str) -> OperationRecord:
        """【内部校验】确保操作记录存在，不存在则抛出异常"""
        current = self.get_operation(operation_id)
        if current is None:
            raise ValueError("unknown_operation")
        return current

    def _ledger_rows(self) -> list[dict[str, Any]]:
        """【内部工具】读取账本所有jsonl行并解析为字典列表"""
        if not self._ledger_path.is_file():
            return []
        return [json.loads(line) for line in self._ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _append(self, record: OperationRecord) -> None:
        """【内部工具】向账本追加一条全新操作记录"""
        self._write_ledger([*self._ledger_rows(), self._asdict(record)])

    def _replace(self, record: OperationRecord) -> None:
        """【内部工具】更新账本中已有operation_id记录；无匹配记录则追加"""
        rows = self._ledger_rows()
        for index, row in enumerate(rows):
            if row["operation_id"] == record.operation_id:
                rows[index] = self._asdict(record)
                break
        else:
            rows.append(self._asdict(record))
        self._write_ledger(rows)

    def _write_ledger(self, rows: list[dict[str, Any]]) -> None:
        """【内部工具】原子全量重写账本：临时文件写入后os.replace原子替换原文件，防止崩溃损坏文件"""
        temporary = self._ledger_path.with_suffix(".tmp")
        temporary.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8", newline="\n")
        os.replace(temporary, self._ledger_path)

    def _load_reservations(self) -> dict[str, dict[str, Any]]:
        """【内部工具】加载CMO仿真配额占用登记表"""
        path = self.root / "attempt-reservations.json"
        return dict(self._read_json(path)) if path.is_file() else {}

    # ===================== 模型序列化/反序列化静态工具 =====================
    @staticmethod
    def _record(data: dict[str, Any]) -> OperationRecord:
        """字典反序列化为 OperationRecord 对象"""
        return OperationRecord(data["operation_id"], int(data["generation_index"]), OperationKind(data["kind"]), data["input_checksum"], OperationStatus(data["status"]), data.get("output_ref"), data.get("error"), data.get("updated_at"))

    @staticmethod
    def _asdict(record: OperationRecord) -> dict[str, Any]:
        """OperationRecord 对象序列化为可存储字典，枚举转为字符串"""
        return {"operation_id": record.operation_id, "generation_index": record.generation_index, "kind": record.kind.value, "input_checksum": record.input_checksum, "status": record.status.value, "output_ref": record.output_ref, "error": record.error, "updated_at": record.updated_at}

    def _preview_path(self, generation_index: int, preview_revision: int) -> Path:
        """构造预览快照文件路径"""
        return self.root / "previews" / f"generation_{generation_index:03d}" / f"preview_{preview_revision:03d}.json"

    def write_input_package_manifest(self, value: dict[str, Any]) -> Path:
        path = self.root / "controlled-input-package.json"
        self._write_json(path, value)
        return path

    def _approval_path(self, approval_id: str) -> Path:
        """构造审批单据文件路径"""
        return self.root / "approvals" / f"{approval_id}.json"

    def _worker_path(self, operation_id: str) -> Path:
        """构造Worker状态文件路径，替换冒号规避操作系统文件名非法字符限制"""
        safe = operation_id.replace(":", "_")
        return self.root / "workers" / f"{safe}.json"

    @staticmethod
    def _state_dict(state: CampaignState) -> dict[str, Any]:
        """CampaignState 序列化为字典，枚举转为字符串"""
        return {**asdict(state), "status": state.status.value, "stop_reason": state.stop_reason.value}

    @staticmethod
    def _preview_dict(preview: GenerationPreview) -> dict[str, Any]:
        return asdict(preview)

    @staticmethod
    def _preview_from_dict(value: dict[str, Any]) -> GenerationPreview:
        return GenerationPreview(**{**value, "strategy_diffs": tuple(dict(item) for item in value["strategy_diffs"])})

    @staticmethod
    def _approval_dict(approval: GenerationApproval) -> dict[str, Any]:
        return asdict(approval)

    @staticmethod
    def _approval_from_dict(value: dict[str, Any]) -> GenerationApproval:
        allowed = {field: value[field] for field in GenerationApproval.__dataclass_fields__ if field in value}
        return GenerationApproval(**allowed)

    @staticmethod
    def _worker_dict(worker: WorkerState) -> dict[str, Any]:
        return asdict(worker)

    @staticmethod
    def _worker_from_dict(value: dict[str, Any]) -> WorkerState:
        return WorkerState(**value)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        """通用读取JSON文件"""
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json(path: Path, value: dict[str, Any]) -> None:
        """
        通用原子写入JSON
        先写入 .tmp 临时文件，成功后原子替换原文件，避免程序异常产生损坏的半写JSON
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8", newline="\n")
        os.replace(temporary, path)

    @staticmethod
    def _now() -> str:
        """获取UTC标准时间ISO格式字符串，统一时间基准"""
        return datetime.now(UTC).isoformat()
