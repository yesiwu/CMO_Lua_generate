"""Serializable request and scheduler state for a Training Workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class TrainingStatus(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    REPAIRING = "REPAIRING"
    WAITING_USER = "WAITING_USER"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    STOPPED = "STOPPED"


class TrainingStage(str, Enum):
    PREPARE = "PREPARE"
    EVOLUTION = "EVOLUTION"
    PHASE8 = "PHASE8"
    REPORT = "REPORT"


class TrainingAction(str, Enum):
    VALIDATE_INPUT = "VALIDATE_INPUT"
    PREPARE_CAMPAIGN = "PREPARE_CAMPAIGN"
    PREVIEW = "PREVIEW"
    EXECUTE = "EXECUTE"
    WAIT_WORKER = "WAIT_WORKER"
    SUMMARIZE = "SUMMARIZE"
    RECONCILE = "RECONCILE"
    GENERATE_REPORT = "GENERATE_REPORT"
    IDLE = "IDLE"


class Phase8Status(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class Phase8Progress:
    status: Phase8Status = Phase8Status.NOT_STARTED
    job_id: str | None = None


@dataclass(frozen=True, slots=True)
class TrainingRequest:
    schema_version: str
    workflow_id: str
    session_id: str | None
    input_path: str
    objective: str
    generation_mode: str
    generation_count: int | None
    auto_code_repair: bool
    phase8_mode: str
    execution_mode: str
    authorized_by_request: bool
    created_at: str

    @classmethod
    def create(
        cls,
        *,
        workflow_id: str,
        input_path: str,
        objective: str,
        generation_count: int,
        session_id: str | None = None,
        execution_mode: str = "PRODUCTION_CMO",
    ) -> "TrainingRequest":
        if not workflow_id or any(token in workflow_id for token in ("/", "\\", "..")):
            raise ValueError("invalid_training_workflow_id")
        if not input_path.strip():
            raise ValueError("training_input_path_required")
        if not objective.strip():
            raise ValueError("training_objective_required")
        if generation_count < 1:
            raise ValueError("training_generation_count_must_be_positive")
        if execution_mode not in {"PRODUCTION_CMO", "FAKE_FIXTURE"}:
            raise ValueError("invalid_training_execution_mode")
        return cls(
            schema_version="1.0",
            workflow_id=workflow_id,
            session_id=session_id,
            input_path=input_path,
            objective=objective,
            generation_mode="fixed_count",
            generation_count=generation_count,
            auto_code_repair=True,
            phase8_mode="after_all_generations",
            execution_mode=execution_mode,
            authorized_by_request=True,
            created_at=_utc_now(),
        )


@dataclass(frozen=True, slots=True)
class TrainingState:
    schema_version: str
    revision: int
    workflow_id: str
    campaign_id: str | None
    status: TrainingStatus
    stage: TrainingStage
    action: TrainingAction
    current_generation: int
    completed_generations: tuple[int, ...] = ()
    worker_operation_id: str | None = None
    active_failure_id: str | None = None
    last_good_commit: str | None = None
    runner: dict[str, Any] = field(default_factory=dict)
    phase8: Phase8Progress = field(default_factory=Phase8Progress)
    updated_at: str = field(default_factory=lambda: _utc_now())

    @classmethod
    def initial(cls, request: TrainingRequest) -> "TrainingState":
        return cls(
            schema_version="1.0",
            revision=0,
            workflow_id=request.workflow_id,
            campaign_id=None,
            status=TrainingStatus.CREATED,
            stage=TrainingStage.PREPARE,
            action=TrainingAction.VALIDATE_INPUT,
            current_generation=0,
        )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
