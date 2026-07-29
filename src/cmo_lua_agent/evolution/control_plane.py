"""
面向单条Phase 9迭代世代的异步持久化控制平面

本模块刻意隔离CMO底层、Phase6内部实现，不向对话LLM暴露底层细节。
世代工作节点仅能获取：持久化推演任务配置、固化世代预览快照、权限鉴权代理。
规则约束：每次发起真实CMO仿真尝试前，Worker必须主动调用权限代理完成准入校验
（实例互斥锁、无暂停 / 停止信号、Worker 合法运行、审批单未过期且哈希匹配预览 + 契约 + 预算、算力配额未耗尽、输入指纹结果对照是一致的。）。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import getpass
import json
import os
from pathlib import Path
import socket
from threading import Event, RLock, Thread
from typing import Any, Protocol
from uuid import uuid4

# 内部模块导入
from cmo_lua_agent.evolution.campaign_store import CampaignStore
from cmo_lua_agent.evolution.cmo_lock import CmoInstanceLock
from cmo_lua_agent.evolution.models import (
    CampaignState,
    CampaignStatus,
    ControlAction,
    ControlRequest,
    EvolutionCampaignSpec,
    GenerationApproval,
    GenerationPreview,
    OperationKind,
    OperationStatus,
    WorkerState,
)
from cmo_lua_agent.evolution.production_models import GenerationApprovalGrant


def _checksum(value: object) -> str:
    """对对象序列化后计算sha256哈希，用于契约、快照完整性校验"""
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return sha256(payload).hexdigest()


def _utc_now() -> datetime:
    """获取UTC标准当前时间，统一全系统时间基准"""
    return datetime.now(UTC)


class ApprovalMode:
    """仿真审批模式枚举常量"""
    PER_ATTEMPT = "per_attempt"      # 单次仿真尝试授权
    GENERATION_CAP = "generation_cap"# 世代最大仿真总量授权


@dataclass(frozen=True, slots=True)
class CampaignPermissionReceipt:
    """
    权限凭证：由权限拦截钩子生成，禁止由模型入参直接构造
    执行高危工具(execute_evolution_generation)时必须携带有效凭证
    时间防止：凭证长期泄露，隔几小时之后被重复滥用。
    """
    receipt_id: str
    tool_name: str
    issued_at: str
    expires_at: str
    issuer: str = "permission_hook"

    @classmethod
    def issue(cls, tool_name: str, *, lifetime_seconds: int = 300) -> "CampaignPermissionReceipt":
        """签发一张新权限凭证，默认5分钟有效期"""
        now = _utc_now()
        return cls(uuid4().hex, tool_name, now.isoformat(), (now + timedelta(seconds=lifetime_seconds)).isoformat())

    @classmethod
    def trusted_for_tests(cls, tool_name: str) -> "CampaignPermissionReceipt":
        """测试专用长时效凭证（1小时），生产环境禁止滥用"""
        return cls.issue(tool_name, lifetime_seconds=3600)

    @classmethod
    def from_hook_receipt(cls, value: object) -> "CampaignPermissionReceipt | None":
        """从钩子上下文对象解析凭证，字段不全返回None"""
        required = ("receipt_id", "tool_name", "issued_at", "expires_at", "issuer")
        if not all(hasattr(value, field) for field in required):
            return None
        return cls(
            receipt_id=str(getattr(value, "receipt_id")),
            tool_name=str(getattr(value, "tool_name")),
            issued_at=str(getattr(value, "issued_at")),
            expires_at=str(getattr(value, "expires_at")),
            issuer=str(getattr(value, "issuer")),
        )

    def is_valid_for(self, tool_name: str, *, now: datetime | None = None) -> bool:
        """校验凭证：签发主体匹配、目标工具匹配、未过期"""
        if self.issuer != "permission_hook" or self.tool_name != tool_name:
            return False
        try:
            return datetime.fromisoformat(self.expires_at) > (now or _utc_now())
        except ValueError:
            return False


@dataclass(frozen=True, slots=True)
class GenerationPreviewPayload:
    """预览构建器输出载荷，用于生成GenerationPreview快照"""
    knowledge_snapshot_checksum: str    # 知识库快照哈希
    candidate_set_checksum: str         # 候选策略集合哈希
    strategy_diffs: tuple[dict[str, Any], ...] # 策略差异对比信息
    proposal_llm_calls: int             # 本次预览消耗的LLM调用次数
    baseline_checksum: str = ""
    frozen_candidate_set_ref: str = ""
    strategy_diff_ref: str = ""


@dataclass(frozen=True, slots=True)
class GenerationExecutionResult:
    """世代执行最终结果载体"""
    status: str
    result: dict[str, Any]
    reason: str | None = None

    @classmethod
    def completed(cls, result: dict[str, Any]) -> "GenerationExecutionResult":
        """正常完成构造器"""
        return cls("completed", dict(result))

    @classmethod
    def paused(cls, reason: str) -> "GenerationExecutionResult":
        """任务暂停构造器"""
        return cls("paused", {}, reason)

    @classmethod
    def cancelled_incomplete(cls, reason: str) -> "GenerationExecutionResult":
        """任务提前终止、未跑完构造器"""
        return cls("cancelled_incomplete", {}, reason)


class PreviewBuilder(Protocol):
    """预览构建器协议，外部注入实现类（解耦业务逻辑）"""
    def build(self, *, spec: EvolutionCampaignSpec, generation_index: int, preview_revision: int) -> GenerationPreviewPayload: ...


class GenerationExecutor(Protocol):
    """世代执行器协议，负责执行一代完整仿真推演流程，外部注入实现"""
    def run(self, context: "GenerationWorkerContext") -> GenerationExecutionResult: ...


@dataclass(frozen=True, slots=True)
class GenerationWorkerContext:
    """世代Worker运行上下文，传递给执行器"""
    spec: EvolutionCampaignSpec                 # 推演任务规约
    preview: GenerationPreview                 # 当前世代预览快照
    campaign_root: Path                        # 任务持久化根目录
    permission_broker: "CampaignPermissionBroker" # 权限鉴权代理
    control_action: Any                        # 外部控制指令查询回调


class CampaignPermissionBroker:
    """
    CMO仿真尝试唯一准入网关
    所有CMO启动请求必须经过本代理校验，统一实施多层安全与配额限制
    """
    def __init__(self, *, store: CampaignStore, spec: EvolutionCampaignSpec, generation_index: int, worker_operation_id: str, production_lock_held: bool = True) -> None:
        self._store = store
        self._spec = spec
        self._generation_index = generation_index
        self._worker_operation_id = worker_operation_id
        self._production_lock_held = production_lock_held

    def authorize_cmo_attempt(self, *, attempt_input_checksum: str) -> str:
        """
        授权单次CMO仿真尝试，全部校验通过后在账本注册操作并占用算力配额
        :return: operation_id 本次CMO操作唯一标识
        """
        # 生产模式下必须持有CMO实例独占锁
        if self._spec.execution_mode.value == "production_cmo" and not self._production_lock_held:
            raise ValueError("campaign_cmo_lock_not_held")
        # 存在暂停/停止控制指令，禁止启动新仿真
        control = self._store.get_control_request()
        if control is not None:
            raise ValueError("campaign_control_request_pending")
        # 所属世代Worker必须处于运行状态
        worker = self._store.get_worker(self._worker_operation_id)
        if worker is None or worker.status != "running":
            raise ValueError("generation_worker_not_active")
        # 获取当前世代有效审批单
        approval = self._store.get_active_approval(campaign_id=self._spec.campaign_id, generation_index=self._generation_index)
        if approval is None or not approval.valid or not self._approval_matches(approval):
            raise ValueError("generation_approval_required")
        # 在操作账本注册一条CMO类型操作记录
        operation = self._store.prepare_operation(generation_index=self._generation_index, kind=OperationKind.CMO, input_checksum=attempt_input_checksum)
        # 原子预留CMO仿真配额，校验单审批上限、全局算力预算
        self._store.authorize_cmo_attempt(operation_id=operation.operation_id, approval=approval, max_cmo_runs=self._spec.budget.max_cmo_runs)
        return operation.operation_id

    def mark_cmo_started(self, operation_id: str) -> None:
        """标记CMO仿真正式启动，递增全局CMO运行计数"""
        self._store.mark_cmo_started(operation_id)

    def authorize_attempt_slot(
        self,
        *,
        operation_id: str,
        snapshot_checksum: str,
        candidate_set_checksum: str,
    ) -> None:
        if self._spec.execution_mode.value == "production_cmo" and not self._production_lock_held:
            raise ValueError("campaign_cmo_lock_not_held")
        if self._store.get_control_request() is not None:
            raise ValueError("campaign_control_request_pending")
        worker = self._store.get_worker(self._worker_operation_id)
        if worker is None or worker.status != "running":
            raise ValueError("generation_worker_not_active")
        control = self._store.load_control_state()
        slot = control.get("attempt_slots", {}).get(operation_id)
        if slot is None:
            raise ValueError("attempt_slot_not_found")
        approval_id = slot.get("approval_id")
        if not approval_id:
            raise ValueError("generation_approval_required")
        self._store.authorize_attempt_slot(
            approval_id=approval_id,
            operation_id=operation_id,
            expected_contract_checksum=self._spec.contract_checksum,
            expected_snapshot_checksum=snapshot_checksum,
            expected_candidate_set_checksum=candidate_set_checksum,
        )

    def mark_attempt_started(self, operation_id: str) -> None:
        self._store.mark_attempt_started(operation_id)

    def mark_attempt_completed(self, operation_id: str, *, output_ref: str) -> None:
        self._store.mark_attempt_completed(operation_id, output_ref=output_ref)

    def mark_attempt_failed(self, operation_id: str, *, reason: str) -> None:
        self._store.mark_attempt_failed(operation_id, reason=reason)

    def mark_attempt_unknown(self, operation_id: str, *, reason: str) -> None:
        self._store.mark_attempt_unknown(operation_id, reason=reason)

    def _approval_matches(self, approval: GenerationApproval) -> bool:
        """
        完整性校验：审批单是否与当前环境完全匹配
        防止预览更新、契约变更、预算版本变动后使用旧审批单
        """
        preview = self._store.get_preview(self._generation_index, approval.preview_revision)
        if preview is None:
            return False
        state = self._store.load_campaign_state()
        return (
            approval.contract_checksum == self._spec.contract_checksum
            and approval.snapshot_checksum == preview.snapshot_checksum
            and approval.candidate_set_checksum == preview.candidate_set_checksum
            and approval.budget_revision == state.budget_revision
            and datetime.fromisoformat(approval.expires_at) > _utc_now()
        )


class GenerationWorkerManager:
    """
    进程内世代Worker线程管理器
    线程运行时内存状态由本类持有；权威持久化状态始终保存在CampaignStore
    """
    def __init__(self, *, synchronous_fake_workers: bool) -> None:
        self._synchronous_fake_workers = synchronous_fake_workers # 测试模式：同步执行，不新开线程
        self._threads: dict[str, Thread] = {} # 内存维护活跃线程映射
        self._lock = RLock()
        self._production_locks: dict[str, CmoInstanceLock] = {} # 持有CMO独占锁缓存

    def start_or_get(self, *, store: CampaignStore, spec: EvolutionCampaignSpec, preview: GenerationPreview, executor: GenerationExecutor) -> WorkerState:
        """
        启动世代Worker；如果已有运行/历史完成Worker，直接返回，避免重复启动
        """
        # 查询是否存在正在运行的Worker
        existing = store.get_active_worker(campaign_id=spec.campaign_id, generation_index=preview.generation_index)
        if existing is not None:
            return existing
        # 查询是否存在已经结束的历史Worker
        previous = next((item for item in store.list_workers() if item.campaign_id == spec.campaign_id and item.generation_index == preview.generation_index), None)
        if previous is not None and previous.status in {"completed", "paused", "cancelled_incomplete", "reconciliation_required"}:
            return previous
        # 创建世代顶层操作记录（PHASE6 = 世代整体执行操作）
        op_checksum = _checksum({"preview": preview.checksum, "contract": spec.contract_checksum})
        operation = store.prepare_operation(generation_index=preview.generation_index, kind=OperationKind.PHASE6, input_checksum=op_checksum)
        # 操作处于启动/未知状态，代表进程崩溃遗留任务，需要外部对账
        if operation.status in (OperationStatus.STARTED, OperationStatus.UNKNOWN):
            return WorkerState(operation.operation_id, spec.campaign_id, preview.generation_index, "reconciliation_required", "recovered")
        # 生产模式抢占CMO实例独占锁
        lock: CmoInstanceLock | None = None
        if spec.execution_mode.value == "production_cmo":
            lock = CmoInstanceLock(store.root.parent / ".cmo-instance.lock", campaign_id=spec.campaign_id)
            lock.acquire()
            self._production_locks[operation.operation_id] = lock
        # 初始化Worker状态并持久化
        worker = WorkerState(operation.operation_id, spec.campaign_id, preview.generation_index, "running", uuid4().hex)
        store.mark_operation_started(operation.operation_id)
        store.save_worker(worker)
        # 定义线程执行入口
        target = lambda: self._run(store=store, spec=spec, preview=preview, worker=worker, executor=executor, production_lock_held=lock is not None or spec.execution_mode.value != "production_cmo")
        # 测试模式同步执行；生产模式后台守护线程
        if self._synchronous_fake_workers and spec.execution_mode.value == "fake_fixture":
            target()
        else:
            thread = Thread(target=target, name=f"campaign-{spec.campaign_id}-{preview.generation_index}", daemon=True)
            with self._lock:
                self._threads[worker.operation_id] = thread
            thread.start()
        return store.get_worker(worker.operation_id) or worker

    def wait(self, operation_id: str, timeout_seconds: float) -> None:
        """阻塞等待指定Worker线程结束，支持超时"""
        with self._lock:
            thread = self._threads.get(operation_id)
        if thread is not None:
            thread.join(timeout_seconds)

    def _run(self, *, store: CampaignStore, spec: EvolutionCampaignSpec, preview: GenerationPreview, worker: WorkerState, executor: GenerationExecutor, production_lock_held: bool) -> None:
        """Worker线程主逻辑：构建上下文、调用执行器、统一收尾持久化"""
        broker = CampaignPermissionBroker(store=store, spec=spec, generation_index=preview.generation_index, worker_operation_id=worker.operation_id, production_lock_held=production_lock_held)
        context = GenerationWorkerContext(spec, preview, store.root, broker, lambda: self._control_name(store))
        try:
            result = executor.run(context)
            self._finalize(store, spec, preview, worker, result)
        except Exception as exc:
            # 线程内异常不直接抛出，持久化失败状态，防止进程静默丢失错误
            store.mark_operation_failed(worker.operation_id, f"{type(exc).__name__}: {exc}")
            store.save_worker(WorkerState(worker.operation_id, spec.campaign_id, preview.generation_index, "failed", worker.worker_id, error=str(exc)))
            store.update_campaign_state(status=CampaignStatus.FAILED)
        finally:
            # 无论成功失败，释放CMO独占锁
            lock = self._production_locks.pop(worker.operation_id, None)
            if lock is not None:
                lock.release()

    @staticmethod
    def _control_name(store: CampaignStore) -> str | None:
        """查询当前生效控制指令类型，供执行器感知暂停/停止信号"""
        request = store.get_control_request()
        return request.action.value if request is not None else None

    @staticmethod
    def _finalize(store: CampaignStore, spec: EvolutionCampaignSpec, preview: GenerationPreview, worker: WorkerState, result: GenerationExecutionResult) -> None:
        """
        世代执行收尾统一处理：根据结果更新持久化状态、审批单、任务全局状态
        分支：暂停 / 强制终止 / 正常完成
        """
        if result.status == "paused":
            # 暂停：写入断点检查点，作废审批单，任务状态置PAUSED
            store.save_checkpoint({"generation_index": preview.generation_index, "worker_operation_id": worker.operation_id, "reason": result.reason})
            store.invalidate_approvals(generation_index=preview.generation_index, reason="campaign_paused")
            store.save_worker(WorkerState(worker.operation_id, spec.campaign_id, preview.generation_index, "paused", worker.worker_id, result.result, result.reason))
            store.update_campaign_state(status=CampaignStatus.PAUSED)
        elif result.status == "cancelled_incomplete":
            # 提前终止：保存断点，作废审批，任务置CANCELLED
            store.save_checkpoint({"generation_index": preview.generation_index, "worker_operation_id": worker.operation_id, "status": "cancelled_incomplete", "reason": result.reason})
            store.invalidate_approvals(generation_index=preview.generation_index, reason="campaign_stopped")
            store.save_worker(WorkerState(worker.operation_id, spec.campaign_id, preview.generation_index, "cancelled_incomplete", worker.worker_id, {}, result.reason))
            store.update_campaign_state(status=CampaignStatus.CANCELLED)
        else:
            # 正常完成：标记操作完成，世代编号+1，等待下一轮预览
            store.mark_operation_completed(worker.operation_id)
            store.save_worker(WorkerState(worker.operation_id, spec.campaign_id, preview.generation_index, "completed", worker.worker_id, result.result))
            store.update_campaign_state(status=CampaignStatus.RUNNING, current_generation=preview.generation_index + 1)
        # 清除已经处理完毕的控制指令
        store.clear_control_request()


class EvolutionCampaignService:
    """
    推演演化顶层服务
    对话侧6个campaign工具唯一调用边界，对外暴露最小可控API
    """
    def __init__(self, *, campaigns_root: Path, preview_builder: PreviewBuilder, generation_executor: GenerationExecutor, synchronous_fake_workers: bool = False) -> None:
        self._campaigns_root = Path(campaigns_root).resolve()
        self._preview_builder = preview_builder      # 预览生成实现（外部注入）
        self._generation_executor = generation_executor # 世代执行实现（外部注入）
        self._workers = GenerationWorkerManager(synchronous_fake_workers=synchronous_fake_workers)

    def prepare_campaign(self, spec: EvolutionCampaignSpec) -> dict[str, Any]:
        """新建一套推演任务，初始化持久化目录与状态，对应工具 prepare_evolution_campaign"""
        root = self._campaign_root(spec.campaign_id)
        if root.exists():
            raise ValueError("campaign_already_exists")
        root.mkdir(parents=True, exist_ok=False)
        store = CampaignStore(root)
        # 持久化推演规约
        self._write_json(root / "campaign-spec.json", self._spec_dict(spec))
        # 初始化任务全局状态
        store.save_campaign_state(CampaignState(campaign_id=spec.campaign_id, status=CampaignStatus.CREATED))
        return self.inspect_campaign(spec.campaign_id)

    def preview_generation(self, *, campaign_id: str, generation_index: int, regenerate_preview: bool = False) -> GenerationPreview:
        """
        生成/读取世代预览快照，对应工具 preview_evolution_generation
        包含候选策略、策略差异快照；预览重新生成时自动作废旧审批单
        """
        store, spec = self._load(campaign_id)
        current = store.get_preview(generation_index)
        if current is not None and not regenerate_preview:
            return current
        if not regenerate_preview and any(
            operation.generation_index == generation_index
            and operation.kind is OperationKind.STRATEGY_PROPOSAL
            and operation.status is OperationStatus.FAILED
            for operation in store.list_operations()
        ):
            raise ValueError("preview_regeneration_required")
        revision = store.next_preview_revision(generation_index)
        # 强制重生成预览 → 旧审批失效
        if regenerate_preview:
            store.invalidate_approvals(generation_index=generation_index, reason="preview_regenerated")
        state = store.load_campaign_state()
        # LLM算力预算校验
        proposal_reservation = 9
        calls = int(state.llm_call_counts.get("strategy_proposal", 0))
        if calls + proposal_reservation > spec.budget.max_strategy_proposal_calls or sum(state.llm_call_counts.values()) + proposal_reservation > spec.budget.max_llm_total_calls:
            raise ValueError("strategy_proposal_llm_budget_exhausted")
        # 创建策略生成操作记录
        operation = store.prepare_operation(generation_index=generation_index, kind=OperationKind.STRATEGY_PROPOSAL, input_checksum=_checksum({"contract": spec.contract_checksum, "revision": revision}))
        if operation.status in (OperationStatus.STARTED, OperationStatus.UNKNOWN):
            raise ValueError("preview_operation_reconciliation_required")
        store.mark_operation_started(operation.operation_id)
        try:
            payload = self._preview_builder.build(spec=spec, generation_index=generation_index, preview_revision=revision)
        except Exception as exc:
            actual_calls = int(getattr(self._preview_builder, "proposal_calls", 0))
            if actual_calls:
                store.increment_llm_calls("strategy_proposal", actual_calls)
            store.mark_operation_failed(operation.operation_id, f"{type(exc).__name__}: {exc}")
            raise
        # 组装预览快照并持久化
        body = {
            "campaign_id": campaign_id,
            "generation_index": generation_index,
            "preview_revision": revision,
            "snapshot_checksum": payload.knowledge_snapshot_checksum,
            "candidate_set_checksum": payload.candidate_set_checksum,
            "strategy_diffs": payload.strategy_diffs,
            "proposal_operation_id": operation.operation_id,
            "baseline_checksum": payload.baseline_checksum,
            "frozen_candidate_set_ref": payload.frozen_candidate_set_ref,
            "strategy_diff_ref": payload.strategy_diff_ref,
        }
        preview = GenerationPreview(**body, checksum=_checksum(body))
        store.save_preview(preview)
        store.mark_operation_completed(operation.operation_id, output_ref=str(store.root / "previews" / f"generation_{generation_index:03d}"))
        # 累加LLM调用计数
        store.increment_llm_calls("strategy_proposal", payload.proposal_llm_calls)
        store.update_campaign_state(status=CampaignStatus.AWAITING_APPROVAL, current_generation=generation_index)
        return preview

    def repair_preview_candidate(
        self,
        *,
        campaign_id: str,
        generation_index: int,
        source_revision: int,
        candidate_id: str,
    ) -> GenerationPreview:
        """Resume a novelty-rejected preview by regenerating exactly one candidate."""
        store, spec = self._load(campaign_id)
        state = store.load_campaign_state()
        required_calls = 2
        used_calls = int(state.llm_call_counts.get("strategy_proposal", 0))
        if (
            used_calls + required_calls > spec.budget.max_strategy_proposal_calls
            or sum(state.llm_call_counts.values()) + required_calls > spec.budget.max_llm_total_calls
        ):
            raise ValueError("proposal_budget_insufficient_for_candidate_repair")
        revision = source_revision + 1
        operation = store.prepare_operation(
            generation_index=generation_index,
            kind=OperationKind.STRATEGY_PROPOSAL,
            input_checksum=_checksum({
                "contract": spec.contract_checksum,
                "parent_revision": source_revision,
                "candidate_id": candidate_id,
                "revision": revision,
            }),
        )
        if operation.status in (OperationStatus.STARTED, OperationStatus.UNKNOWN):
            raise ValueError("preview_operation_reconciliation_required")
        store.mark_operation_started(operation.operation_id)
        repair = getattr(self._preview_builder, "repair_candidate", None)
        if repair is None:
            store.mark_operation_failed(operation.operation_id, "awaiting_operator_action")
            raise ValueError("awaiting_operator_action")
        try:
            payload = repair(
                spec=spec,
                generation_index=generation_index,
                source_revision=source_revision,
                preview_revision=revision,
                candidate_id=candidate_id,
            )
        except Exception as exc:
            actual_calls = int(getattr(self._preview_builder, "proposal_calls", 0))
            if actual_calls:
                store.increment_llm_calls("strategy_proposal", actual_calls)
            store.mark_operation_failed(operation.operation_id, f"{type(exc).__name__}: {exc}")
            raise
        body = {
            "campaign_id": campaign_id,
            "generation_index": generation_index,
            "preview_revision": revision,
            "snapshot_checksum": payload.knowledge_snapshot_checksum,
            "candidate_set_checksum": payload.candidate_set_checksum,
            "strategy_diffs": payload.strategy_diffs,
            "proposal_operation_id": operation.operation_id,
            "baseline_checksum": payload.baseline_checksum,
            "frozen_candidate_set_ref": payload.frozen_candidate_set_ref,
            "strategy_diff_ref": payload.strategy_diff_ref,
        }
        preview = GenerationPreview(**body, checksum=_checksum(body))
        store.save_preview(preview)
        store.mark_operation_completed(operation.operation_id, output_ref=str(store.root / "previews" / f"generation_{generation_index:03d}"))
        store.increment_llm_calls("strategy_proposal", payload.proposal_llm_calls)
        store.update_campaign_state(status=CampaignStatus.AWAITING_APPROVAL, current_generation=generation_index)
        return preview

    def authorize_generation(self, *, campaign_id: str, generation_index: int, receipt: CampaignPermissionReceipt | None, authorization_mode: str = ApprovalMode.PER_ATTEMPT, max_cmo_attempts: int | None = None, expires_in_seconds: int = 300) -> GenerationApproval:
        """
        创建世代仿真审批单
        必须携带合法权限凭证；审批单绑定预览哈希、契约哈希，防止配置篡改
        """
        if receipt is None or not receipt.is_valid_for("execute_evolution_generation"):
            raise ValueError("trusted_permission_receipt_required")
        if authorization_mode not in (ApprovalMode.PER_ATTEMPT, ApprovalMode.GENERATION_CAP):
            raise ValueError("invalid_generation_authorization_mode")
        store, spec = self._load(campaign_id)
        preview = store.get_preview(generation_index)
        if preview is None:
            raise ValueError("generation_preview_required")
        maximum = 1 if authorization_mode == ApprovalMode.PER_ATTEMPT else max_cmo_attempts
        if not isinstance(maximum, int) or maximum < 1:
            raise ValueError("invalid_generation_attempt_cap")
        now = _utc_now()
        state = store.load_campaign_state()
        approval_body = {
            "campaign_id": campaign_id,
            "generation_index": generation_index,
            "preview_revision": preview.preview_revision,
            "snapshot_checksum": preview.snapshot_checksum,
            "candidate_set_checksum": preview.candidate_set_checksum,
            "contract_checksum": spec.contract_checksum,
            "budget_revision": state.budget_revision,
            "authorization_mode": authorization_mode,
            "max_cmo_attempts": maximum,
            "expires_at": (now + timedelta(seconds=expires_in_seconds)).isoformat(),
            "receipt_summary": receipt.receipt_id
        }
        # 用内容哈希生成审批ID，保证相同条件不会重复生成
        approval = GenerationApproval(approval_id=_checksum(approval_body)[:24], **approval_body)
        store.save_approval(approval)
        return approval

    def execute_generation(
        self,
        *,
        campaign_id: str,
        generation_index: int,
        approval_id: str | None = None,
    ) -> WorkerState:
        """启动世代Worker，对应工具 execute_evolution_generation；要求存在有效审批单"""
        store, spec = self._load(campaign_id)
        active = store.get_active_worker(campaign_id=campaign_id, generation_index=generation_index)
        if active is not None:
            return active
        preview = store.get_preview(generation_index)
        if preview is None:
            raise ValueError("generation_preview_required")
        if approval_id is not None:
            control = store.load_control_state()
            raw_grant = control.get("approvals", {}).get(approval_id)
            if raw_grant is None or not raw_grant.get("valid", False):
                raise ValueError("generation_approval_required")
            grant = GenerationApprovalGrant.from_dict(raw_grant)
            state = store.load_campaign_state()
            if (
                grant.campaign_id != campaign_id
                or grant.generation_index != generation_index
                or grant.preview_revision != preview.preview_revision
                or grant.snapshot_checksum != preview.snapshot_checksum
                or grant.candidate_set_checksum != preview.candidate_set_checksum
                or grant.baseline_checksum != preview.baseline_checksum
                or grant.contract_checksum != spec.contract_checksum
                or grant.budget_revision != state.budget_revision
            ):
                raise ValueError("generation_approval_required")
            return self._workers.start_or_get(
                store=store,
                spec=spec,
                preview=preview,
                executor=self._generation_executor,
            )
        approval = store.get_active_approval(campaign_id=campaign_id, generation_index=generation_index)
        # 校验预览、审批单完整性与时效性
        if preview is None or approval is None or not self._approval_is_current(store, spec, preview, approval):
            raise ValueError("generation_approval_required")
        return self._workers.start_or_get(store=store, spec=spec, preview=preview, executor=self._generation_executor)

    def persist_permission_grant(
        self,
        receipt: object,
        hook_context: dict[str, Any],
    ) -> str:
        arguments = dict(hook_context.get("arguments", {}))
        campaign_id = str(arguments["campaign_id"])
        generation_index = int(arguments["generation_index"])
        store, spec = self._load(campaign_id)
        preview = store.get_preview(generation_index)
        if preview is None:
            raise ValueError("generation_preview_required")
        try:
            store.load_control_state()
        except ValueError:
            store.initialize_control_state(
                max_cmo_runs=spec.budget.max_cmo_runs,
                budget_revision=store.load_campaign_state().budget_revision,
            )
        operation_ids = self._attempt_slot_ids(spec, generation_index)
        issued_at = str(getattr(receipt, "issued_at"))
        expires_at = str(getattr(receipt, "expires_at"))
        grant = GenerationApprovalGrant.issue(
            campaign_id=campaign_id,
            generation_index=generation_index,
            preview_revision=preview.preview_revision,
            snapshot_checksum=preview.snapshot_checksum,
            candidate_set_checksum=preview.candidate_set_checksum,
            baseline_checksum=preview.baseline_checksum,
            contract_checksum=spec.contract_checksum,
            budget_revision=store.load_campaign_state().budget_revision,
            approved_operation_ids=operation_ids,
            maximum_cmo_attempts=len(operation_ids),
            actor=getpass.getuser(),
            hostname=socket.gethostname(),
            process_id=os.getpid(),
            approved_at=issued_at,
            expires_at=expires_at,
            receipt_checksum=_checksum({
                "receipt_id": getattr(receipt, "receipt_id"),
                "tool_name": getattr(receipt, "tool_name"),
                "issued_at": issued_at,
                "expires_at": expires_at,
            }),
        )
        store.persist_generation_approval(grant)
        return grant.approval_id

    @staticmethod
    def _attempt_slot_ids(
        spec: EvolutionCampaignSpec,
        generation_index: int,
    ) -> tuple[str, ...]:
        values = [
            f"g{generation_index:03d}:cmo:baseline:a{attempt:02d}"
            for attempt in range(spec.budget.max_cmo_attempts_for_baseline)
        ]
        values.extend(
            f"g{generation_index:03d}:cmo:candidate_{candidate:02d}:a{attempt:02d}"
            for candidate in range(4)
            for attempt in range(spec.budget.max_cmo_attempts_per_candidate)
        )
        return tuple(values)

    def inspect_campaign(self, campaign_id: str) -> dict[str, Any]:
        """查询推演任务全局信息，对应工具 inspect_evolution_campaign"""
        store, spec = self._load(campaign_id)
        state = store.load_campaign_state()
        return {
            "campaign_id": campaign_id,
            "status": state.status.value,
            "current_generation": state.current_generation,
            "budget": {
                "cmo_run_count": state.cmo_run_count,
                "max_cmo_runs": spec.budget.max_cmo_runs,
                "llm_call_counts": state.llm_call_counts
            },
            "contract_checksum": spec.contract_checksum,
            "control_request": self._control_dict(store.get_control_request())
        }

    def inspect_generation(self, campaign_id: str, generation_index: int) -> dict[str, Any]:
        """查询单世代详情：预览、Worker状态、执行结果，对应工具 inspect_evolution_generation"""
        store, _ = self._load(campaign_id)
        preview = store.get_preview(generation_index)
        worker = store.get_active_worker(campaign_id=campaign_id, generation_index=generation_index)
        if worker is None:
            worker = next((item for item in store.list_workers() if item.generation_index == generation_index), None)
        return {
            "campaign_id": campaign_id,
            "generation_index": generation_index,
            "preview": self._preview_dict(preview),
            "status": worker.status if worker else "ready",
            "operation_id": worker.operation_id if worker else None,
            "result": self._generation_result_summary(worker.result) if worker else {}
        }

    def pause_campaign(self, campaign_id: str) -> dict[str, Any]:
        """下发暂停控制指令，对应工具 control_evolution_campaign pause"""
        store, _ = self._load(campaign_id)
        store.request_control(ControlRequest(ControlAction.PAUSE, _utc_now().isoformat()))
        try:
            generation = store.load_campaign_state().current_generation
            store.invalidate_generation_approvals(
                generation_index=generation,
                reason="campaign_paused",
            )
        except ValueError:
            pass
        return self.inspect_campaign(campaign_id)

    def stop_campaign(self, campaign_id: str) -> dict[str, Any]:
        """下发终止指令，对应工具 control_evolution_campaign stop"""
        store, _ = self._load(campaign_id)
        store.request_control(ControlRequest(ControlAction.STOP, _utc_now().isoformat()))
        try:
            generation = store.load_campaign_state().current_generation
            store.invalidate_generation_approvals(
                generation_index=generation,
                reason="campaign_stopped",
            )
        except ValueError:
            pass
        store.update_campaign_state(status=CampaignStatus.STOPPING)
        return self.inspect_campaign(campaign_id)

    def resume_campaign(self, campaign_id: str) -> dict[str, Any]:
        """恢复推演任务，清理旧审批、清除控制指令，扫描未对账操作"""
        store, _ = self._load(campaign_id)
        store.invalidate_approvals(reason="worker_process_restart")
        try:
            control_reconciliation = store.reconcile_control_state_for_resume()
        except ValueError:
            control_reconciliation = {"reconciliation_required": []}
        store.clear_control_request()
        # 读取断点，恢复到断点世代
        checkpoint = store.load_checkpoint()
        state = store.load_campaign_state()
        generation = int(checkpoint.get("generation_index", state.current_generation)) if checkpoint else state.current_generation
        # 找出所有处于STARTED / UNKNOWN 待对账操作
        unresolved = [item.operation_id for item in store.list_operations() if item.status in (OperationStatus.STARTED, OperationStatus.UNKNOWN)]
        store.update_campaign_state(status=CampaignStatus.AWAITING_APPROVAL, current_generation=generation)
        result = self.inspect_campaign(campaign_id)
        result["reconciliation_required_operations"] = sorted(set(
            unresolved + control_reconciliation["reconciliation_required"]
        ))
        result["process_restart_recovery"] = "not_validated"
        return result

    def is_approval_valid(self, approval_id: str) -> bool:
        """跨任务检索审批单是否有效（运维接口）"""
        for root in self._campaigns_root.glob("*") if self._campaigns_root.is_dir() else ():
            approval = CampaignStore(root).get_approval(approval_id)
            if approval is not None:
                return approval.valid and datetime.fromisoformat(approval.expires_at) > _utc_now()
        return False

    def wait_for_worker(self, operation_id: str, timeout_seconds: float) -> None:
        """阻塞等待指定Worker线程结束（外部调度使用）"""
        self._workers.wait(operation_id, timeout_seconds)

    def _load(self, campaign_id: str) -> tuple[CampaignStore, EvolutionCampaignSpec]:
        """加载任务持久化存储与推演规约"""
        root = self._campaign_root(campaign_id)
        if not root.is_dir():
            raise ValueError("campaign_not_found")
        store = CampaignStore(root)
        spec_data = json.loads((root / "campaign-spec.json").read_text(encoding="utf-8"))
        return store, self._spec_from_dict(spec_data)

    def _campaign_root(self, campaign_id: str) -> Path:
        """构造任务存储目录，防御路径穿越攻击"""
        if not campaign_id or any(char in campaign_id for char in ("/", "\\", "..")):
            raise ValueError("invalid_campaign_id")
        return self._campaigns_root / campaign_id

    @staticmethod
    def _approval_is_current(store: CampaignStore, spec: EvolutionCampaignSpec, preview: GenerationPreview, approval: GenerationApproval) -> bool:
        """校验审批单是否匹配当前预览、契约、预算版本且未过期"""
        state = store.load_campaign_state()
        return (
            approval.valid
            and approval.preview_revision == preview.preview_revision
            and approval.snapshot_checksum == preview.snapshot_checksum
            and approval.candidate_set_checksum == preview.candidate_set_checksum
            and approval.contract_checksum == spec.contract_checksum
            and approval.budget_revision == state.budget_revision
            and datetime.fromisoformat(approval.expires_at) > _utc_now()
        )

    @staticmethod
    def _spec_dict(spec: EvolutionCampaignSpec) -> dict[str, Any]:
        """规约对象序列化为可存储字典，枚举转为字符串"""
        data = asdict(spec)
        data["execution_mode"] = spec.execution_mode.value
        data["budget"] = asdict(spec.budget)
        return data

    @staticmethod
    def _spec_from_dict(data: dict[str, Any]) -> EvolutionCampaignSpec:
        """字典反序列化为强类型推演规约对象"""
        from cmo_lua_agent.evolution.models import CampaignBudget, CampaignExecutionMode
        return EvolutionCampaignSpec(**{
            **data,
            "execution_mode": CampaignExecutionMode(data["execution_mode"]),
            "budget": CampaignBudget(**data["budget"]),
            "allowed_strategy_paths": tuple(data["allowed_strategy_paths"])
        })

    @staticmethod
    def _write_json(path: Path, value: dict[str, Any]) -> None:
        """简单持久化JSON（非原子写入，仅用于静态spec配置文件）"""
        path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8", newline="\n")

    @staticmethod
    def _preview_dict(preview: GenerationPreview | None) -> dict[str, Any] | None:
        """预览快照转为字典"""
        if preview is None:
            return None
        return {
            "campaign_id": preview.campaign_id,
            "generation_index": preview.generation_index,
            "preview_revision": preview.preview_revision,
            "snapshot_checksum": preview.snapshot_checksum,
            "candidate_set_checksum": preview.candidate_set_checksum,
            "baseline_checksum": preview.baseline_checksum,
            "strategy_diffs": [dict(item) for item in preview.strategy_diffs],
            "proposal_operation_id": preview.proposal_operation_id,
            "checksum": preview.checksum,
        }

    @staticmethod
    def _control_dict(control: ControlRequest | None) -> dict[str, Any] | None:
        """控制指令转为对外返回字典"""
        if control is None:
            return None
        return {
            "action": control.action.value,
            "requested_at": control.requested_at,
            "reason": control.reason
        }

    @staticmethod
    def _generation_result_summary(value: dict[str, Any]) -> dict[str, Any]:
        outcomes = []
        for item in value.get("outcomes", ()):
            if not isinstance(item, dict):
                continue
            outcomes.append({
                "candidate_id": item.get("candidate_id"),
                "execution_success": item.get("execution_success"),
                "executable": item.get("executable"),
                "semantic_valid": item.get("semantic_valid"),
                "scoreable": item.get("scoreable"),
                "native_score": item.get("native_score"),
                "score_source": item.get("score_source"),
                "rank": item.get("rank"),
                "execution_attempts": item.get("execution_attempts"),
                "repair_invocations": item.get("repair_invocations"),
                "failure_reason": item.get("failure_reason"),
            })
        phase7 = value.get("phase7", {})
        phase8 = value.get("phase8", {})
        result: dict[str, Any] = {}
        if "artifact_provenance" in value:
            result["artifact_provenance"] = value["artifact_provenance"]
        if "candidate_order" in value:
            result["candidate_order"] = list(value["candidate_order"])
        if "outcomes" in value:
            result["outcomes"] = outcomes
        if "leaderboard" in value:
            result["leaderboard"] = list(value["leaderboard"])
        if "champion_decision" in value:
            result["champion_decision"] = value["champion_decision"]
        if "phase7" in value:
            result["phase7"] = {
                key: phase7.get(key)
                for key in (
                    "status",
                    "optimization_id",
                    "experience_candidate_count",
                    "experience_ids",
                )
                if isinstance(phase7, dict) and key in phase7
            }
        if "phase8" in value:
            result["phase8"] = {
                key: phase8.get(key)
                for key in ("status", "pending_count", "decision_count")
                if isinstance(phase8, dict) and key in phase8
            }
        if "stop_decision" in value:
            result["stop_decision"] = value["stop_decision"]
        if "process_restart_recovery" in value:
            result["process_restart_recovery"] = value[
                "process_restart_recovery"
            ]
        return result
