"""Asynchronous, persisted control plane for one Phase 9 generation.

This module deliberately does not expose CMO or Phase 6 internals to chat.  A
worker receives only a persisted campaign, frozen preview, and a permission
broker.  It remains the worker's responsibility to call the broker immediately
before every real CMO attempt.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path
from threading import Event, RLock, Thread
from typing import Any, Protocol
from uuid import uuid4

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


def _checksum(value: object) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ApprovalMode:
    PER_ATTEMPT = "per_attempt"
    GENERATION_CAP = "generation_cap"


@dataclass(frozen=True, slots=True)
class CampaignPermissionReceipt:
    """A receipt created inside PermissionHook, never from model arguments."""

    receipt_id: str
    tool_name: str
    issued_at: str
    expires_at: str
    issuer: str = "permission_hook"

    @classmethod
    def issue(cls, tool_name: str, *, lifetime_seconds: int = 300) -> "CampaignPermissionReceipt":
        now = _utc_now()
        return cls(uuid4().hex, tool_name, now.isoformat(), (now + timedelta(seconds=lifetime_seconds)).isoformat())

    @classmethod
    def trusted_for_tests(cls, tool_name: str) -> "CampaignPermissionReceipt":
        return cls.issue(tool_name, lifetime_seconds=3600)

    @classmethod
    def from_hook_receipt(cls, value: object) -> "CampaignPermissionReceipt | None":
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
        if self.issuer != "permission_hook" or self.tool_name != tool_name:
            return False
        try:
            return datetime.fromisoformat(self.expires_at) > (now or _utc_now())
        except ValueError:
            return False


@dataclass(frozen=True, slots=True)
class GenerationPreviewPayload:
    knowledge_snapshot_checksum: str
    candidate_set_checksum: str
    strategy_diffs: tuple[dict[str, Any], ...]
    proposal_llm_calls: int


@dataclass(frozen=True, slots=True)
class GenerationExecutionResult:
    status: str
    result: dict[str, Any]
    reason: str | None = None

    @classmethod
    def completed(cls, result: dict[str, Any]) -> "GenerationExecutionResult":
        return cls("completed", dict(result))

    @classmethod
    def paused(cls, reason: str) -> "GenerationExecutionResult":
        return cls("paused", {}, reason)

    @classmethod
    def cancelled_incomplete(cls, reason: str) -> "GenerationExecutionResult":
        return cls("cancelled_incomplete", {}, reason)


class PreviewBuilder(Protocol):
    def build(self, *, spec: EvolutionCampaignSpec, generation_index: int, preview_revision: int) -> GenerationPreviewPayload: ...


class GenerationExecutor(Protocol):
    def run(self, context: "GenerationWorkerContext") -> GenerationExecutionResult: ...


@dataclass(frozen=True, slots=True)
class GenerationWorkerContext:
    spec: EvolutionCampaignSpec
    preview: GenerationPreview
    campaign_root: Path
    permission_broker: "CampaignPermissionBroker"
    control_action: Any


class CampaignPermissionBroker:
    """The only admission point for a CMO attempt in campaign execution."""

    def __init__(self, *, store: CampaignStore, spec: EvolutionCampaignSpec, generation_index: int, worker_operation_id: str, production_lock_held: bool = True) -> None:
        self._store = store
        self._spec = spec
        self._generation_index = generation_index
        self._worker_operation_id = worker_operation_id
        self._production_lock_held = production_lock_held

    def authorize_cmo_attempt(self, *, attempt_input_checksum: str) -> str:
        if self._spec.execution_mode.value == "production_cmo" and not self._production_lock_held:
            raise ValueError("campaign_cmo_lock_not_held")
        control = self._store.get_control_request()
        if control is not None:
            raise ValueError("campaign_control_request_pending")
        worker = self._store.get_worker(self._worker_operation_id)
        if worker is None or worker.status != "running":
            raise ValueError("generation_worker_not_active")
        approval = self._store.get_active_approval(campaign_id=self._spec.campaign_id, generation_index=self._generation_index)
        if approval is None or not approval.valid or not self._approval_matches(approval):
            raise ValueError("generation_approval_required")
        operation = self._store.prepare_operation(generation_index=self._generation_index, kind=OperationKind.CMO, input_checksum=attempt_input_checksum)
        self._store.authorize_cmo_attempt(operation_id=operation.operation_id, approval=approval, max_cmo_runs=self._spec.budget.max_cmo_runs)
        return operation.operation_id

    def mark_cmo_started(self, operation_id: str) -> None:
        self._store.mark_cmo_started(operation_id)

    def _approval_matches(self, approval: GenerationApproval) -> bool:
        preview = self._store.get_preview(self._generation_index, approval.preview_revision)
        if preview is None:
            return False
        return (
            approval.contract_checksum == self._spec.contract_checksum
            and approval.snapshot_checksum == preview.snapshot_checksum
            and approval.candidate_set_checksum == preview.candidate_set_checksum
            and approval.budget_revision == self._store.load_campaign_state().budget_revision
            and datetime.fromisoformat(approval.expires_at) > _utc_now()
        )


class GenerationWorkerManager:
    """Owns process-local workers; durable state always remains in CampaignStore."""

    def __init__(self, *, synchronous_fake_workers: bool) -> None:
        self._synchronous_fake_workers = synchronous_fake_workers
        self._threads: dict[str, Thread] = {}
        self._lock = RLock()
        self._production_locks: dict[str, CmoInstanceLock] = {}

    def start_or_get(self, *, store: CampaignStore, spec: EvolutionCampaignSpec, preview: GenerationPreview, executor: GenerationExecutor) -> WorkerState:
        existing = store.get_active_worker(campaign_id=spec.campaign_id, generation_index=preview.generation_index)
        if existing is not None:
            return existing
        previous = next((item for item in store.list_workers() if item.campaign_id == spec.campaign_id and item.generation_index == preview.generation_index), None)
        if previous is not None and previous.status in {"completed", "paused", "cancelled_incomplete", "reconciliation_required"}:
            return previous
        operation = store.prepare_operation(generation_index=preview.generation_index, kind=OperationKind.PHASE6, input_checksum=_checksum({"preview": preview.checksum, "contract": spec.contract_checksum}))
        if operation.status in (OperationStatus.STARTED, OperationStatus.UNKNOWN):
            # A process restart never guesses whether a previous external call finished.
            return WorkerState(operation.operation_id, spec.campaign_id, preview.generation_index, "reconciliation_required", "recovered")
        lock: CmoInstanceLock | None = None
        if spec.execution_mode.value == "production_cmo":
            lock = CmoInstanceLock(store.root.parent / ".cmo-instance.lock", campaign_id=spec.campaign_id)
            lock.acquire()
            self._production_locks[operation.operation_id] = lock
        worker = WorkerState(operation.operation_id, spec.campaign_id, preview.generation_index, "running", uuid4().hex)
        store.mark_operation_started(operation.operation_id)
        store.save_worker(worker)
        target = lambda: self._run(store=store, spec=spec, preview=preview, worker=worker, executor=executor, production_lock_held=lock is not None or spec.execution_mode.value != "production_cmo")
        if self._synchronous_fake_workers and spec.execution_mode.value == "fake_fixture":
            target()
        else:
            thread = Thread(target=target, name=f"campaign-{spec.campaign_id}-{preview.generation_index}", daemon=True)
            with self._lock:
                self._threads[worker.operation_id] = thread
            thread.start()
        return store.get_worker(worker.operation_id) or worker

    def wait(self, operation_id: str, timeout_seconds: float) -> None:
        with self._lock:
            thread = self._threads.get(operation_id)
        if thread is not None:
            thread.join(timeout_seconds)

    def _run(self, *, store: CampaignStore, spec: EvolutionCampaignSpec, preview: GenerationPreview, worker: WorkerState, executor: GenerationExecutor, production_lock_held: bool) -> None:
        broker = CampaignPermissionBroker(store=store, spec=spec, generation_index=preview.generation_index, worker_operation_id=worker.operation_id, production_lock_held=production_lock_held)
        context = GenerationWorkerContext(spec, preview, store.root, broker, lambda: self._control_name(store))
        try:
            result = executor.run(context)
            self._finalize(store, spec, preview, worker, result)
        except Exception as exc:  # Worker errors are persisted rather than escaping a detached thread.
            store.mark_operation_failed(worker.operation_id, f"{type(exc).__name__}: {exc}")
            store.save_worker(WorkerState(worker.operation_id, spec.campaign_id, preview.generation_index, "failed", worker.worker_id, error=str(exc)))
            store.update_campaign_state(status=CampaignStatus.FAILED)
        finally:
            lock = self._production_locks.pop(worker.operation_id, None)
            if lock is not None:
                lock.release()

    @staticmethod
    def _control_name(store: CampaignStore) -> str | None:
        request = store.get_control_request()
        return request.action.value if request is not None else None

    @staticmethod
    def _finalize(store: CampaignStore, spec: EvolutionCampaignSpec, preview: GenerationPreview, worker: WorkerState, result: GenerationExecutionResult) -> None:
        if result.status == "paused":
            store.save_checkpoint({"generation_index": preview.generation_index, "worker_operation_id": worker.operation_id, "reason": result.reason})
            store.invalidate_approvals(generation_index=preview.generation_index, reason="campaign_paused")
            store.save_worker(WorkerState(worker.operation_id, spec.campaign_id, preview.generation_index, "paused", worker.worker_id, result.result, result.reason))
            store.update_campaign_state(status=CampaignStatus.PAUSED)
        elif result.status == "cancelled_incomplete":
            store.save_checkpoint({"generation_index": preview.generation_index, "worker_operation_id": worker.operation_id, "status": "cancelled_incomplete", "reason": result.reason})
            store.invalidate_approvals(generation_index=preview.generation_index, reason="campaign_stopped")
            store.save_worker(WorkerState(worker.operation_id, spec.campaign_id, preview.generation_index, "cancelled_incomplete", worker.worker_id, {}, result.reason))
            store.update_campaign_state(status=CampaignStatus.CANCELLED)
        else:
            store.mark_operation_completed(worker.operation_id)
            store.save_worker(WorkerState(worker.operation_id, spec.campaign_id, preview.generation_index, "completed", worker.worker_id, result.result))
            store.update_campaign_state(status=CampaignStatus.RUNNING, current_generation=preview.generation_index + 1)
        store.clear_control_request()


class EvolutionCampaignService:
    """The only public boundary used by campaign Chat tools."""

    def __init__(self, *, campaigns_root: Path, preview_builder: PreviewBuilder, generation_executor: GenerationExecutor, synchronous_fake_workers: bool = False) -> None:
        self._campaigns_root = Path(campaigns_root).resolve()
        self._preview_builder = preview_builder
        self._generation_executor = generation_executor
        self._workers = GenerationWorkerManager(synchronous_fake_workers=synchronous_fake_workers)

    def prepare_campaign(self, spec: EvolutionCampaignSpec) -> dict[str, Any]:
        root = self._campaign_root(spec.campaign_id)
        if root.exists():
            raise ValueError("campaign_already_exists")
        root.mkdir(parents=True, exist_ok=False)
        store = CampaignStore(root)
        self._write_json(root / "campaign-spec.json", self._spec_dict(spec))
        store.save_campaign_state(CampaignState(campaign_id=spec.campaign_id, status=CampaignStatus.CREATED))
        return self.inspect_campaign(spec.campaign_id)

    def preview_generation(self, *, campaign_id: str, generation_index: int, regenerate_preview: bool = False) -> GenerationPreview:
        store, spec = self._load(campaign_id)
        current = store.get_preview(generation_index)
        if current is not None and not regenerate_preview:
            return current
        revision = store.next_preview_revision(generation_index)
        if regenerate_preview:
            store.invalidate_approvals(generation_index=generation_index, reason="preview_regenerated")
        state = store.load_campaign_state()
        calls = int(state.llm_call_counts.get("strategy_proposal", 0))
        if calls >= spec.budget.max_strategy_proposal_calls or sum(state.llm_call_counts.values()) >= spec.budget.max_llm_total_calls:
            raise ValueError("strategy_proposal_llm_budget_exhausted")
        operation = store.prepare_operation(generation_index=generation_index, kind=OperationKind.STRATEGY_PROPOSAL, input_checksum=_checksum({"contract": spec.contract_checksum, "revision": revision}))
        if operation.status in (OperationStatus.STARTED, OperationStatus.UNKNOWN):
            raise ValueError("preview_operation_reconciliation_required")
        store.mark_operation_started(operation.operation_id)
        try:
            payload = self._preview_builder.build(spec=spec, generation_index=generation_index, preview_revision=revision)
        except Exception as exc:
            store.mark_operation_failed(operation.operation_id, f"{type(exc).__name__}: {exc}")
            raise
        body = {"campaign_id": campaign_id, "generation_index": generation_index, "preview_revision": revision, "snapshot_checksum": payload.knowledge_snapshot_checksum, "candidate_set_checksum": payload.candidate_set_checksum, "strategy_diffs": payload.strategy_diffs, "proposal_operation_id": operation.operation_id}
        preview = GenerationPreview(**body, checksum=_checksum(body))
        store.save_preview(preview)
        store.mark_operation_completed(operation.operation_id, output_ref=str(store.root / "previews" / f"generation_{generation_index:03d}"))
        store.increment_llm_calls("strategy_proposal", payload.proposal_llm_calls)
        store.update_campaign_state(status=CampaignStatus.AWAITING_APPROVAL, current_generation=generation_index)
        return preview

    def authorize_generation(self, *, campaign_id: str, generation_index: int, receipt: CampaignPermissionReceipt | None, authorization_mode: str = ApprovalMode.PER_ATTEMPT, max_cmo_attempts: int | None = None, expires_in_seconds: int = 300) -> GenerationApproval:
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
        approval_body = {"campaign_id": campaign_id, "generation_index": generation_index, "preview_revision": preview.preview_revision, "snapshot_checksum": preview.snapshot_checksum, "candidate_set_checksum": preview.candidate_set_checksum, "contract_checksum": spec.contract_checksum, "budget_revision": state.budget_revision, "authorization_mode": authorization_mode, "max_cmo_attempts": maximum, "expires_at": (now + timedelta(seconds=expires_in_seconds)).isoformat(), "receipt_summary": receipt.receipt_id}
        approval = GenerationApproval(approval_id=_checksum(approval_body)[:24], **approval_body)
        store.save_approval(approval)
        return approval

    def execute_generation(self, *, campaign_id: str, generation_index: int) -> WorkerState:
        store, spec = self._load(campaign_id)
        active = store.get_active_worker(campaign_id=campaign_id, generation_index=generation_index)
        if active is not None:
            return active
        preview = store.get_preview(generation_index)
        approval = store.get_active_approval(campaign_id=campaign_id, generation_index=generation_index)
        if preview is None or approval is None or not self._approval_is_current(store, spec, preview, approval):
            raise ValueError("generation_approval_required")
        return self._workers.start_or_get(store=store, spec=spec, preview=preview, executor=self._generation_executor)

    def inspect_campaign(self, campaign_id: str) -> dict[str, Any]:
        store, spec = self._load(campaign_id)
        state = store.load_campaign_state()
        return {"campaign_id": campaign_id, "status": state.status.value, "current_generation": state.current_generation, "budget": {"cmo_run_count": state.cmo_run_count, "max_cmo_runs": spec.budget.max_cmo_runs, "llm_call_counts": state.llm_call_counts}, "contract_checksum": spec.contract_checksum, "control_request": self._control_dict(store.get_control_request())}

    def inspect_generation(self, campaign_id: str, generation_index: int) -> dict[str, Any]:
        store, _ = self._load(campaign_id)
        preview = store.get_preview(generation_index)
        worker = store.get_active_worker(campaign_id=campaign_id, generation_index=generation_index)
        if worker is None:
            worker = next((item for item in store.list_workers() if item.generation_index == generation_index), None)
        return {"campaign_id": campaign_id, "generation_index": generation_index, "preview": self._preview_dict(preview), "status": worker.status if worker else "ready", "operation_id": worker.operation_id if worker else None, "result": dict(worker.result) if worker else {}}

    def pause_campaign(self, campaign_id: str) -> dict[str, Any]:
        store, _ = self._load(campaign_id)
        store.request_control(ControlRequest(ControlAction.PAUSE, _utc_now().isoformat()))
        return self.inspect_campaign(campaign_id)

    def stop_campaign(self, campaign_id: str) -> dict[str, Any]:
        store, _ = self._load(campaign_id)
        store.request_control(ControlRequest(ControlAction.STOP, _utc_now().isoformat()))
        store.update_campaign_state(status=CampaignStatus.STOPPING)
        return self.inspect_campaign(campaign_id)

    def resume_campaign(self, campaign_id: str) -> dict[str, Any]:
        store, _ = self._load(campaign_id)
        # Resume is reconciliation only. Started/unknown operations are never replayed here.
        store.invalidate_approvals(reason="worker_process_restart")
        store.clear_control_request()
        checkpoint = store.load_checkpoint()
        generation = int(checkpoint.get("generation_index", store.load_campaign_state().current_generation)) if checkpoint else store.load_campaign_state().current_generation
        unresolved = [item.operation_id for item in store.list_operations() if item.status in (OperationStatus.STARTED, OperationStatus.UNKNOWN)]
        store.update_campaign_state(status=CampaignStatus.AWAITING_APPROVAL, current_generation=generation)
        result = self.inspect_campaign(campaign_id)
        result["reconciliation_required_operations"] = unresolved
        return result

    def is_approval_valid(self, approval_id: str) -> bool:
        for root in self._campaigns_root.glob("*") if self._campaigns_root.is_dir() else ():
            approval = CampaignStore(root).get_approval(approval_id)
            if approval is not None:
                return approval.valid and datetime.fromisoformat(approval.expires_at) > _utc_now()
        return False

    def wait_for_worker(self, operation_id: str, timeout_seconds: float) -> None:
        self._workers.wait(operation_id, timeout_seconds)

    def _load(self, campaign_id: str) -> tuple[CampaignStore, EvolutionCampaignSpec]:
        root = self._campaign_root(campaign_id)
        if not root.is_dir():
            raise ValueError("campaign_not_found")
        return CampaignStore(root), self._spec_from_dict(json.loads((root / "campaign-spec.json").read_text(encoding="utf-8")))

    def _campaign_root(self, campaign_id: str) -> Path:
        if not campaign_id or any(value in campaign_id for value in ("/", "\\", "..")):
            raise ValueError("invalid_campaign_id")
        return self._campaigns_root / campaign_id

    @staticmethod
    def _approval_is_current(store: CampaignStore, spec: EvolutionCampaignSpec, preview: GenerationPreview, approval: GenerationApproval) -> bool:
        return approval.valid and approval.preview_revision == preview.preview_revision and approval.snapshot_checksum == preview.snapshot_checksum and approval.candidate_set_checksum == preview.candidate_set_checksum and approval.contract_checksum == spec.contract_checksum and approval.budget_revision == store.load_campaign_state().budget_revision and datetime.fromisoformat(approval.expires_at) > _utc_now()

    @staticmethod
    def _spec_dict(spec: EvolutionCampaignSpec) -> dict[str, Any]:
        data = asdict(spec)
        data["execution_mode"] = spec.execution_mode.value
        data["budget"] = asdict(spec.budget)
        return data

    @staticmethod
    def _spec_from_dict(data: dict[str, Any]) -> EvolutionCampaignSpec:
        from cmo_lua_agent.evolution.models import CampaignBudget, CampaignExecutionMode
        return EvolutionCampaignSpec(**{**data, "execution_mode": CampaignExecutionMode(data["execution_mode"]), "budget": CampaignBudget(**data["budget"]), "allowed_strategy_paths": tuple(data["allowed_strategy_paths"])})

    @staticmethod
    def _write_json(path: Path, value: dict[str, Any]) -> None:
        path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8", newline="\n")

    @staticmethod
    def _preview_dict(preview: GenerationPreview | None) -> dict[str, Any] | None:
        return asdict(preview) if preview is not None else None

    @staticmethod
    def _control_dict(control: ControlRequest | None) -> dict[str, Any] | None:
        return {"action": control.action.value, "requested_at": control.requested_at, "reason": control.reason} if control else None
