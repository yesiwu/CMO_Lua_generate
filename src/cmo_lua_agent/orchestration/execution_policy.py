"""
ExecutionPolicy: rules for when to execute, repair, or stop.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExecutionPolicy:
    """
    Defines thresholds and limits for the agent loop.

    Attributes
    ----------
    reward_threshold : float
        Minimum reward to accept a generated script without repair.
    max_repair_attempts : int
        How many repair cycles to attempt before giving up.
    max_iterations_per_workflow : int
        Hard cap on total generation attempts per workflow run.
    require_combat : bool
        If True, reject runs where no combat events were recorded.
    min_combat_events : int
        Minimum weapon/engagement events to consider the run valid.
    """

    reward_threshold: float = 0.6
    max_repair_attempts: int = 3
    max_iterations_per_workflow: int = 10
    require_combat: bool = True
    min_combat_events: int = 1

    def should_repair(self, reward: float, repair_count: int) -> bool:
        """Decide whether another repair attempt is worthwhile."""
        if repair_count >= self.max_repair_attempts:
            return False
        return reward < self.reward_threshold

    def is_acceptable(self, reward: float, combat_events: int) -> bool:
        """Check if current result meets acceptance criteria."""
        if self.require_combat and combat_events < self.min_combat_events:
            return False
        return reward >= self.reward_threshold

    @classmethod
    def from_dict(cls, d: dict) -> ExecutionPolicy:
        return cls(
            reward_threshold=d.get("reward_threshold", 0.6),
            max_repair_attempts=d.get("max_repair_attempts", 3),
            max_iterations_per_workflow=d.get("max_iterations", 10),
            require_combat=d.get("require_combat", True),
            min_combat_events=d.get("min_combat_events", 1),
        )
