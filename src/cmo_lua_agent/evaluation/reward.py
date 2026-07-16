"""
Reward: computes a scalar reward from CombatMetrics.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cmo_lua_agent.evaluation.combat_metrics import CombatMetrics


@dataclass
class RewardConfig:
    """Weights for the reward function."""

    hit_weight: float = 1.0
    kill_weight: float = 5.0
    intercept_kill_weight: float = 2.0
    own_loss_penalty: float = -3.0
    execution_bonus: float = 10.0
    execution_penalty: float = -10.0
    timeout_penalty: float = -5.0

    # Normalisation divisors (to keep reward in [-1, 1] roughly)
    hits_norm: float = 10.0
    kills_norm: float = 5.0


class RewardComputer:
    """
    Maps a CombatMetrics object to a scalar reward in roughly [-1, 1].

    Components
    ----------
    - Combat success (hits, kills, intercepts)
    - Own losses (penalty)
    - Execution outcome (bonus / penalty)
    """

    def __init__(self, config: RewardConfig | None = None) -> None:
        self.config = config or RewardConfig()

    def compute(self, combat_metrics: dict[str, Any] | CombatMetrics) -> float:
        """
        Compute scalar reward.

        Parameters
        ----------
        combat_metrics : CombatMetrics or dict
            Parsed metrics from a run. Accepts raw dict for convenience.

        Returns
        -------
        float
            Reward in [-1, 1] approximately.
        """
        if isinstance(combat_metrics, dict):
            return self._compute_from_dict(combat_metrics)

        cfg = self.config
        total = 0.0

        # Execution outcome
        status = getattr(combat_metrics, "status", "") or ""
        if status in ("Success", "OK"):
            total += cfg.execution_bonus
        elif status in ("Timeout", "WallTimeout"):
            total += cfg.timeout_penalty
        else:
            total += cfg.execution_penalty

        # Hits
        hits = combat_metrics.total_hits()
        total += cfg.hit_weight * (hits / cfg.hits_norm)

        # Kills
        kills = combat_metrics.total_kills()
        total += cfg.kill_weight * (kills / cfg.kills_norm)

        # Intercepts
        intercepts = combat_metrics.total_intercept_kills()
        total += cfg.intercept_kill_weight * (intercepts / cfg.kills_norm)

        # Own losses penalty
        destroyed = combat_metrics.destroyed_count()
        total += cfg.own_loss_penalty * destroyed

        # Clamp to [-1, 1]
        return max(-1.0, min(1.0, total))

    def _compute_from_dict(self, d: dict) -> float:
        """Compute reward from a raw dict (e.g. from JSON)."""
        cfg = self.config
        total = 0.0
        status = d.get("status", "")
        if status in ("Success", "OK"):
            total += cfg.execution_bonus
        elif status in ("Timeout", "WallTimeout"):
            total += cfg.timeout_penalty
        else:
            total += cfg.execution_penalty

        hits = d.get("total_hits", 0)
        total += cfg.hit_weight * (hits / cfg.hits_norm)
        kills = d.get("total_kills", 0)
        total += cfg.kill_weight * (kills / cfg.kills_norm)
        intercepts = d.get("intercept_kills", 0)
        total += cfg.intercept_kill_weight * (intercepts / cfg.kills_norm)
        destroyed = d.get("destroyed_units", 0)
        total += cfg.own_loss_penalty * destroyed

        return max(-1.0, min(1.0, total))
