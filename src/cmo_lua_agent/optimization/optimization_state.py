"""
OptimizationState: persistent state across optimisation iterations.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional

from cmo_lua_agent.evaluation.combat_metrics import CombatMetrics


@dataclass
class OptimizationState:
    """
    Carries the current optimisation state between calls.

    Attributes
    ----------
    run_id : str
        Unique identifier for this optimisation run.
    iteration : int
        Current 0-based iteration counter.
    best_reward : float
        Best reward observed so far.
    best_script : str
        Lua script that achieved best_reward.
    best_metrics : CombatMetrics
        Metrics for the best run.
    last_reward : float
        Reward from the most recent iteration.
    history : list[float]
        Reward history across iterations.
    candidate_scores : dict[str, float]
        Map from script hash → reward.  Used by CandidateSelector.
    """

    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    iteration: int = 0
    best_reward: float = -1.0
    best_script: str = ""
    best_metrics: Optional[CombatMetrics] = None
    last_reward: float = -1.0
    history: list[float] = field(default_factory=list)
    candidate_scores: dict[str, str] = field(default_factory=dict)  # hash → script

    def update(self, script: str, reward: float, metrics: CombatMetrics) -> bool:
        """
        Record a new result. Returns True if this is the new best.
        """
        import hashlib

        self.iteration += 1
        self.last_reward = reward
        self.history.append(reward)

        script_hash = hashlib.md5(script.encode()).hexdigest()
        self.candidate_scores[script_hash] = script

        if reward > self.best_reward:
            self.best_reward = reward
            self.best_script = script
            self.best_metrics = metrics
            return True
        return False

    def reward_trend(self) -> list[float]:
        """Return reward history."""
        return list(self.history)
