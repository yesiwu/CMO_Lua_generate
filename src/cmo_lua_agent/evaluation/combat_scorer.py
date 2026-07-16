"""
CombatScorer: higher-level scoring / judgement on top of raw reward.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cmo_lua_agent.evaluation.combat_metrics import CombatMetrics
from cmo_lua_agent.evaluation.reward import RewardComputer, RewardConfig


@dataclass
class ScoreBreakdown:
    """Detailed score for human review."""

    raw_reward: float
    execution_score: float
    combat_score: float
    survival_score: float
    overall: float
    verdict: str  # "Accept", "Review", "Reject"

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_reward": self.raw_reward,
            "execution_score": self.execution_score,
            "combat_score": self.combat_score,
            "survival_score": self.survival_score,
            "overall": self.overall,
            "verdict": self.verdict,
        }


class CombatScorer:
    """
    Provides multi-dimensional scoring + a human-readable verdict.

    Compared to RewardComputer, this offers richer diagnostics suitable
    for displaying to users or logging.
    """

    def __init__(self, reward_config: RewardConfig | None = None) -> None:
        self.reward_computer = RewardComputer(reward_config)

    def score(self, metrics: CombatMetrics) -> ScoreBreakdown:
        """
        Compute a ScoreBreakdown from a CombatMetrics object.
        """
        raw = self.reward_computer.compute(metrics)

        # Execution component (±10)
        exec_score = 0.0
        status = metrics.status or ""
        if status in ("Success", "OK"):
            exec_score = 1.0
        elif status in ("Timeout", "WallTimeout"):
            exec_score = -0.5
        else:
            exec_score = -1.0

        # Combat component (hits/kills)
        hit_r = min(1.0, metrics.total_hits() / 10.0)
        kill_r = min(1.0, metrics.total_kills() / 5.0)
        combat_score = 0.6 * hit_r + 0.4 * kill_r

        # Survival (fewer own losses = higher)
        destroyed = metrics.destroyed_count()
        survival_score = max(0.0, 1.0 - destroyed * 0.2)

        # Weighted overall
        overall = 0.25 * exec_score + 0.50 * combat_score + 0.25 * survival_score

        # Verdict thresholds
        if overall >= 0.6:
            verdict = "Accept"
        elif overall >= 0.3:
            verdict = "Review"
        else:
            verdict = "Reject"

        return ScoreBreakdown(
            raw_reward=raw,
            execution_score=exec_score,
            combat_score=combat_score,
            survival_score=survival_score,
            overall=overall,
            verdict=verdict,
        )
