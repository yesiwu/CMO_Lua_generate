"""
Trajectory: a single optimisation episode (one script → execution → reward).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class TrajectoryStep:
    """One step in a trajectory (here, one script evaluation)."""

    iteration: int
    lua_script: str
    script_path: str
    reward: float
    combat_metrics: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "iteration": self.iteration,
            "reward": self.reward,
            "script_length": len(self.lua_script),
            "combat_metrics": self.combat_metrics,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class Trajectory:
    """
    A complete optimisation run: a sequence of TrajectorySteps.

    In this project a "trajectory" is a single run with potentially
    multiple script attempts (iterations).  Each attempt is a step.
    """

    run_id: str
    steps: list[TrajectoryStep] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def add_step(self, step: TrajectoryStep) -> None:
        self.steps.append(step)

    @property
    def best_reward(self) -> float:
        if not self.steps:
            return -1.0
        return max(s.reward for s in self.steps)

    @property
    def best_step(self) -> Optional[TrajectoryStep]:
        if not self.steps:
            return None
        return max(self.steps, key=lambda s: s.reward)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "created_at": self.created_at.isoformat(),
            "num_steps": len(self.steps),
            "best_reward": self.best_reward,
            "steps": [s.to_dict() for s in self.steps],
        }
