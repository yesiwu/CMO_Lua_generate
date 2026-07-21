"""Immutable state model for one JSON-to-Lua workflow run."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any

from cmo_lua_agent.artifacts import RunArtifactPaths


class WorkflowTransitionError(ValueError):
    """A requested workflow transition violates the state machine."""


class WorkflowStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    NEEDS_USER_INPUT = "needs_user_input"
    FAILED = "failed"


class WorkflowStage(str, Enum):
    CREATED = "created"
    INPUT = "input"
    SCHEMA = "schema"
    SEMANTIC = "semantic"
    IR = "ir"
    DATABASE = "database"
    MANIFEST = "manifest"
    GENERATION = "generation"
    COMPLETED = "completed"


_ALLOWED_TRANSITIONS: dict[WorkflowStage, frozenset[WorkflowStage]] = {
    WorkflowStage.CREATED: frozenset(
        {WorkflowStage.INPUT, WorkflowStage.MANIFEST}
    ),
    WorkflowStage.INPUT: frozenset({WorkflowStage.SCHEMA}),
    WorkflowStage.SCHEMA: frozenset({WorkflowStage.SEMANTIC}),
    WorkflowStage.SEMANTIC: frozenset({WorkflowStage.IR}),
    WorkflowStage.IR: frozenset({WorkflowStage.DATABASE}),
    WorkflowStage.DATABASE: frozenset({WorkflowStage.MANIFEST}),
    WorkflowStage.MANIFEST: frozenset({WorkflowStage.GENERATION}),
}
_TERMINAL_STATUSES = {
    WorkflowStatus.COMPLETED,
    WorkflowStatus.NEEDS_USER_INPUT,
    WorkflowStatus.FAILED,
}
_RUNNING_STAGES = {
    WorkflowStage.INPUT,
    WorkflowStage.SCHEMA,
    WorkflowStage.SEMANTIC,
    WorkflowStage.IR,
    WorkflowStage.DATABASE,
    WorkflowStage.MANIFEST,
    WorkflowStage.GENERATION,
}


@dataclass(frozen=True, slots=True)
class WorkflowState:
    """Serializable workflow status linked to canonical artifact paths."""

    run_id: str
    status: WorkflowStatus
    stage: WorkflowStage
    artifact_paths: Mapping[str, str]
    error_code: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        run_id = _require_non_blank(self.run_id, field_name="run_id")
        if not isinstance(self.status, WorkflowStatus):
            raise TypeError("status must be a WorkflowStatus")
        if not isinstance(self.stage, WorkflowStage):
            raise TypeError("stage must be a WorkflowStage")
        if not isinstance(self.artifact_paths, Mapping):
            raise TypeError("artifact_paths must be a mapping")

        normalized_paths: dict[str, str] = {}
        for key, value in self.artifact_paths.items():
            normalized_key = _require_non_blank(
                key,
                field_name="artifact_paths key",
            )
            normalized_value = _require_non_blank(
                value,
                field_name=f"artifact_paths[{normalized_key!r}]",
            )
            normalized_paths[normalized_key] = normalized_value

        error_code = _normalize_optional_string(
            self.error_code,
            field_name="error_code",
        )
        error_message = _normalize_optional_string(
            self.error_message,
            field_name="error_message",
        )

        if self.status in {
            WorkflowStatus.FAILED,
            WorkflowStatus.NEEDS_USER_INPUT,
        }:
            if error_code is None:
                raise ValueError("failed state requires error_code")
            if error_message is None:
                raise ValueError("failed state requires error_message")
        elif error_code is not None or error_message is not None:
            raise ValueError(
                "non-terminal state cannot contain error metadata"
            )

        if self.status is WorkflowStatus.CREATED:
            if self.stage is not WorkflowStage.CREATED:
                raise ValueError(
                    "created status requires created stage"
                )
        elif self.status is WorkflowStatus.RUNNING:
            if self.stage not in _RUNNING_STAGES:
                raise ValueError(
                    "running status requires an active workflow stage"
                )
        elif self.status is WorkflowStatus.COMPLETED:
            if self.stage is not WorkflowStage.COMPLETED:
                raise ValueError(
                    "completed status requires completed stage"
                )
        elif self.stage is WorkflowStage.COMPLETED:
            raise ValueError(
                "terminal non-success status cannot use completed stage"
            )

        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(
            self,
            "artifact_paths",
            MappingProxyType(normalized_paths),
        )
        object.__setattr__(self, "error_code", error_code)
        object.__setattr__(self, "error_message", error_message)

    @classmethod
    def initial(cls, paths: RunArtifactPaths) -> "WorkflowState":
        if not isinstance(paths, RunArtifactPaths):
            raise TypeError("paths must be a RunArtifactPaths")
        return cls(
            run_id=paths.run_id,
            status=WorkflowStatus.CREATED,
            stage=WorkflowStage.CREATED,
            artifact_paths=paths.to_dict(),
        )

    def advance(self, stage: WorkflowStage) -> "WorkflowState":
        self._require_non_terminal()
        if not isinstance(stage, WorkflowStage):
            raise TypeError("stage must be a WorkflowStage")

        allowed = _ALLOWED_TRANSITIONS.get(self.stage, frozenset())
        if stage not in allowed:
            raise WorkflowTransitionError(
                "illegal workflow stage transition: "
                f"{self.stage.value} -> {stage.value}"
            )

        return WorkflowState(
            run_id=self.run_id,
            status=WorkflowStatus.RUNNING,
            stage=stage,
            artifact_paths=self.artifact_paths,
        )

    def complete(self) -> "WorkflowState":
        self._require_non_terminal()
        if (
            self.status is not WorkflowStatus.RUNNING
            or self.stage is not WorkflowStage.GENERATION
        ):
            raise WorkflowTransitionError(
                "workflow can complete only after generation"
            )
        return WorkflowState(
            run_id=self.run_id,
            status=WorkflowStatus.COMPLETED,
            stage=WorkflowStage.COMPLETED,
            artifact_paths=self.artifact_paths,
        )

    def fail(self, code: str, message: str) -> "WorkflowState":
        self._require_non_terminal()
        normalized_code = _require_non_blank(code, field_name="code")
        normalized_message = _require_non_blank(
            message,
            field_name="message",
        )
        return WorkflowState(
            run_id=self.run_id,
            status=WorkflowStatus.FAILED,
            stage=self.stage,
            artifact_paths=self.artifact_paths,
            error_code=normalized_code,
            error_message=normalized_message,
        )

    def needs_user_input(self, code: str, message: str) -> "WorkflowState":
        """Finish without guessing when a user-owned decision is required."""
        self._require_non_terminal()
        return WorkflowState(
            run_id=self.run_id,
            status=WorkflowStatus.NEEDS_USER_INPUT,
            stage=self.stage,
            artifact_paths=self.artifact_paths,
            error_code=_require_non_blank(code, field_name="code"),
            error_message=_require_non_blank(message, field_name="message"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status.value,
            "stage": self.stage.value,
            "artifact_paths": dict(self.artifact_paths),
            "error_code": self.error_code,
            "error_message": self.error_message,
        }

    def _require_non_terminal(self) -> None:
        if self.status in _TERMINAL_STATUSES:
            raise WorkflowTransitionError(
                f"workflow is already terminal: {self.status.value}"
            )


def _require_non_blank(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    return normalized


def _normalize_optional_string(
    value: str | None,
    *,
    field_name: str,
) -> str | None:
    if value is None:
        return None
    return _require_non_blank(value, field_name=field_name)
