"""Atomic persistence for Phase 9 campaign control-plane state.

The ledger is deliberately separate from a checkpoint: a checkpoint describes
where a worker should resume, while the ledger records every externally
observable operation and is the source of truth for reconciliation.
"""

from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
from threading import RLock
from typing import Any
from datetime import UTC, datetime

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


class CampaignStore:
    """A file-backed store with atomic replacement for every mutable record."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._ledger_path = self.root / "operation-ledger.jsonl"
        self._lock = RLock()

    # Campaign state -------------------------------------------------
    def save_campaign_state(self, state: CampaignState) -> None:
        self._write_json(self.root / "campaign-state.json", self._state_dict(state))

    def load_campaign_state(self) -> CampaignState:
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
        with self._lock:
            current = self.load_campaign_state()
            values = asdict(current)
            values.update(changes)
            if isinstance(values.get("status"), str):
                values["status"] = CampaignStatus(values["status"])
            if isinstance(values.get("stop_reason"), str):
                values["stop_reason"] = StopReason(values["stop_reason"])
            updated = CampaignState(**values)
            self.save_campaign_state(updated)
            return updated

    def increment_llm_calls(self, kind: str, count: int = 1) -> CampaignState:
        with self._lock:
            state = self.load_campaign_state()
            calls = dict(state.llm_call_counts)
            calls[kind] = int(calls.get(kind, 0)) + count
            return self.update_campaign_state(llm_call_counts=calls)

    # Control / checkpoint ------------------------------------------
    def request_control(self, request: ControlRequest) -> None:
        self._write_json(
            self.root / "control-request.json",
            {"action": request.action.value, "requested_at": request.requested_at, "reason": request.reason},
        )

    def get_control_request(self) -> ControlRequest | None:
        path = self.root / "control-request.json"
        if not path.is_file():
            return None
        value = self._read_json(path)
        return ControlRequest(ControlAction(value["action"]), str(value["requested_at"]), value.get("reason"))

    def clear_control_request(self) -> None:
        path = self.root / "control-request.json"
        if path.exists():
            path.unlink()

    def save_checkpoint(self, value: dict[str, Any]) -> None:
        self._write_json(self.root / "checkpoint.json", value)

    def load_checkpoint(self) -> dict[str, Any] | None:
        path = self.root / "checkpoint.json"
        return self._read_json(path) if path.is_file() else None

    # Preview --------------------------------------------------------
    def save_preview(self, preview: GenerationPreview) -> None:
        self._write_json(self._preview_path(preview.generation_index, preview.preview_revision), self._preview_dict(preview))

    def get_preview(self, generation_index: int, preview_revision: int | None = None) -> GenerationPreview | None:
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
        current = self.get_preview(generation_index)
        return 0 if current is None else current.preview_revision + 1

    # Approval -------------------------------------------------------
    def save_approval(self, approval: GenerationApproval) -> None:
        self._write_json(self._approval_path(approval.approval_id), self._approval_dict(approval))

    def get_approval(self, approval_id: str) -> GenerationApproval | None:
        path = self._approval_path(approval_id)
        return self._approval_from_dict(self._read_json(path)) if path.is_file() else None

    def get_active_approval(self, *, campaign_id: str, generation_index: int) -> GenerationApproval | None:
        directory = self.root / "approvals"
        if not directory.is_dir():
            return None
        records = [self._approval_from_dict(self._read_json(path)) for path in directory.glob("*.json")]
        matches = [item for item in records if item.valid and item.campaign_id == campaign_id and item.generation_index == generation_index]
        return sorted(matches, key=lambda item: item.approval_id)[-1] if matches else None

    def invalidate_approvals(self, *, generation_index: int | None = None, reason: str) -> None:
        directory = self.root / "approvals"
        if not directory.is_dir():
            return
        for path in directory.glob("*.json"):
            approval = self._approval_from_dict(self._read_json(path))
            if generation_index is not None and approval.generation_index != generation_index:
                continue
            if approval.valid:
                self._write_json(path, {**self._approval_dict(approval), "valid": False, "invalidated_reason": reason})

    # Worker ---------------------------------------------------------
    def save_worker(self, worker: WorkerState) -> None:
        self._write_json(self._worker_path(worker.operation_id), self._worker_dict(worker))

    def get_worker(self, operation_id: str) -> WorkerState | None:
        path = self._worker_path(operation_id)
        return self._worker_from_dict(self._read_json(path)) if path.is_file() else None

    def list_workers(self) -> tuple[WorkerState, ...]:
        directory = self.root / "workers"
        if not directory.is_dir():
            return ()
        return tuple(self._worker_from_dict(self._read_json(path)) for path in sorted(directory.glob("*.json")))

    def get_active_worker(self, *, campaign_id: str, generation_index: int) -> WorkerState | None:
        directory = self.root / "workers"
        if not directory.is_dir():
            return None
        workers = [self._worker_from_dict(self._read_json(path)) for path in directory.glob("*.json")]
        active = [item for item in workers if item.campaign_id == campaign_id and item.generation_index == generation_index and item.status == "running"]
        return active[0] if active else None

    # External operation ledger ------------------------------------
    def prepare_operation(self, *, generation_index: int, kind: OperationKind, input_checksum: str) -> OperationRecord:
        operation_id = f"g{generation_index:03d}:{kind.value}:{input_checksum[:16]}"
        with self._lock:
            existing = self.get_operation(operation_id)
            if existing is not None:
                return existing
            record = OperationRecord(operation_id, generation_index, kind, input_checksum, OperationStatus.PREPARED, updated_at=self._now())
            self._append(record)
            return record

    def get_operation(self, operation_id: str) -> OperationRecord | None:
        for data in self._ledger_rows():
            if data["operation_id"] == operation_id:
                return self._record(data)
        return None

    def list_operations(self) -> tuple[OperationRecord, ...]:
        return tuple(self._record(item) for item in self._ledger_rows())

    def mark_operation_authorized(self, operation_id: str) -> OperationRecord:
        return self._transition(operation_id, OperationStatus.AUTHORIZED)

    def mark_operation_started(self, operation_id: str) -> OperationRecord:
        return self._transition(operation_id, OperationStatus.STARTED)

    def mark_operation_unknown(self, operation_id: str, error: str | None = None) -> OperationRecord:
        return self._transition(operation_id, OperationStatus.UNKNOWN, error=error)

    def mark_operation_failed(self, operation_id: str, error: str) -> OperationRecord:
        return self._transition(operation_id, OperationStatus.FAILED, error=error)

    def mark_operation_completed(self, operation_id: str, *, output_ref: str | None = None) -> OperationRecord:
        return self._transition(operation_id, OperationStatus.COMPLETED, output_ref=output_ref)

    def reconcile_operation(self, operation_id: str, artifact: Path) -> OperationRecord:
        current = self._require(operation_id)
        artifact = Path(artifact).resolve()
        data = json.loads(artifact.read_text(encoding="utf-8"))
        if data.get("input_checksum") != current.input_checksum:
            raise ValueError("operation_artifact_checksum_mismatch")
        return self._transition(operation_id, OperationStatus.COMPLETED, output_ref=str(artifact))

    def authorize_cmo_attempt(self, *, operation_id: str, approval: GenerationApproval, max_cmo_runs: int) -> OperationRecord:
        """Atomically reserve a CMO attempt and move its ledger row to authorized."""
        with self._lock:
            current = self._require(operation_id)
            if current.status not in (OperationStatus.PREPARED, OperationStatus.AUTHORIZED):
                raise ValueError("cmo_attempt_not_prepared")
            reservations = self._load_reservations()
            used = sum(1 for item in reservations.values() if item["approval_id"] == approval.approval_id)
            if used >= approval.max_cmo_attempts:
                raise ValueError("generation_approval_cap_exhausted")
            state = self.load_campaign_state()
            if state.cmo_run_count + len(reservations) >= max_cmo_runs:
                raise ValueError("campaign_cmo_budget_exhausted")
            reservations[operation_id] = {"approval_id": approval.approval_id, "generation_index": current.generation_index}
            self._write_json(self.root / "attempt-reservations.json", reservations)
            return self._transition(operation_id, OperationStatus.AUTHORIZED)

    def mark_cmo_started(self, operation_id: str) -> OperationRecord:
        with self._lock:
            current = self._require(operation_id)
            if current.status is not OperationStatus.AUTHORIZED:
                raise ValueError("cmo_attempt_not_authorized")
            state = self.load_campaign_state()
            self.update_campaign_state(cmo_run_count=state.cmo_run_count + 1)
            return self._transition(operation_id, OperationStatus.STARTED)

    def _transition(self, operation_id: str, status: OperationStatus, *, output_ref: str | None = None, error: str | None = None) -> OperationRecord:
        current = self._require(operation_id)
        record = OperationRecord(current.operation_id, current.generation_index, current.kind, current.input_checksum, status, output_ref, error, self._now())
        self._replace(record)
        return record

    def _require(self, operation_id: str) -> OperationRecord:
        current = self.get_operation(operation_id)
        if current is None:
            raise ValueError("unknown_operation")
        return current

    def _ledger_rows(self) -> list[dict[str, Any]]:
        if not self._ledger_path.is_file():
            return []
        return [json.loads(line) for line in self._ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _append(self, record: OperationRecord) -> None:
        self._write_ledger([*self._ledger_rows(), self._asdict(record)])

    def _replace(self, record: OperationRecord) -> None:
        rows = self._ledger_rows()
        for index, row in enumerate(rows):
            if row["operation_id"] == record.operation_id:
                rows[index] = self._asdict(record)
                break
        else:
            rows.append(self._asdict(record))
        self._write_ledger(rows)

    def _write_ledger(self, rows: list[dict[str, Any]]) -> None:
        temporary = self._ledger_path.with_suffix(".tmp")
        temporary.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8", newline="\n")
        os.replace(temporary, self._ledger_path)

    def _load_reservations(self) -> dict[str, dict[str, Any]]:
        path = self.root / "attempt-reservations.json"
        return dict(self._read_json(path)) if path.is_file() else {}

    @staticmethod
    def _record(data: dict[str, Any]) -> OperationRecord:
        return OperationRecord(data["operation_id"], int(data["generation_index"]), OperationKind(data["kind"]), data["input_checksum"], OperationStatus(data["status"]), data.get("output_ref"), data.get("error"), data.get("updated_at"))

    @staticmethod
    def _asdict(record: OperationRecord) -> dict[str, Any]:
        return {"operation_id": record.operation_id, "generation_index": record.generation_index, "kind": record.kind.value, "input_checksum": record.input_checksum, "status": record.status.value, "output_ref": record.output_ref, "error": record.error, "updated_at": record.updated_at}

    def _preview_path(self, generation_index: int, preview_revision: int) -> Path:
        return self.root / "previews" / f"generation_{generation_index:03d}" / f"preview_{preview_revision:03d}.json"

    def _approval_path(self, approval_id: str) -> Path:
        return self.root / "approvals" / f"{approval_id}.json"

    def _worker_path(self, operation_id: str) -> Path:
        safe = operation_id.replace(":", "_")
        return self.root / "workers" / f"{safe}.json"

    @staticmethod
    def _state_dict(state: CampaignState) -> dict[str, Any]:
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
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8", newline="\n")
        os.replace(temporary, path)

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()
