"""
WorkflowState: serialisable execution state for any workflow step.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional
from datetime import datetime


class WorkflowPhase(Enum):
    """High-level phases a workflow can be in."""
    INIT = auto()
    GENERATING = auto()
    EXECUTING = auto()
    EVALUATING = auto()
    OPTIMISING = auto()
    REPAIRING = auto()
    DONE = auto()
    FAILED = auto()


@dataclass
class WorkflowState:
    """Tracks progress and outputs of a workflow run."""

    # Identity
    workflow_name: str
    run_id: str

    # Phase
    phase: WorkflowPhase = WorkflowPhase.INIT

    # Timing
    started_at: datetime = field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None

    # Outputs
    lua_script: Optional[str] = None
    script_path: Optional[str] = None

    # Execution result
    execution_ok: bool = False
    execution_error: Optional[str] = None

    # Evaluation result
    reward: Optional[float] = None
    combat_metrics: dict[str, Any] = field(default_factory=dict)

    # Iteration
    iteration: int = 0
    max_iterations: int = 10

    # Flags
    cancelled: bool = False
    repair_count: int = 0

    def mark_done(self, success: bool = True, error: Optional[str] = None) -> None:
        self.finished_at = datetime.utcnow()
        self.phase = WorkflowPhase.DONE if success else WorkflowPhase.FAILED
        if error:
            self.execution_error = error

    def next_iteration(self) -> bool:
        """Advance iteration counter. Returns False if max reached."""
        self.iteration += 1
        return self.iteration <= self.max_iterations
