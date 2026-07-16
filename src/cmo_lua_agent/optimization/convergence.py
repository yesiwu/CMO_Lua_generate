"""
Convergence: detects when the optimisation loop has plateaued.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from cmo_lua_agent.orchestration.optimization_state import OptimizationState

logger = logging.getLogger(__name__)


@dataclass
class ConvergenceConfig:
    """Thresholds for convergence detection."""

    patience: int = 5          # consecutive iterations with no improvement before declaring convergence
    min_improvement: float = 0.01  # reward must improve by at least this much to count
    min_iterations: int = 3    # minimum iterations before convergence can be declared


class ConvergenceChecker:
    """
    Detects plateau in reward history.

    Convergence is declared when:
    - At least `min_iterations` have run
    - Reward has not improved by `min_improvement` for `patience` consecutive iterations
    """

    def __init__(self, config: Optional[ConvergenceConfig] = None) -> None:
        self.config = config or ConvergenceConfig()
        self._no_improve_streak: int = 0
        self._last_best: float = -1.0

    def is_converged(self, state: OptimizationState) -> bool:
        """
        Returns True if the optimisation has converged.

        Parameters
        ----------
        state : OptimizationState
            Current optimisation state.
        """
        cfg = self.config

        if len(state.history) < cfg.min_iterations:
            return False

        if state.best_reward > self._last_best + cfg.min_improvement:
            self._last_best = state.best_reward
            self._no_improve_streak = 0
            logger.debug(
                "[convergence] new best %.4f (streak reset)", state.best_reward
            )
            return False

        self._no_improve_streak += 1
        converged = self._no_improve_streak >= cfg.patience

        if converged:
            logger.info(
                "[convergence] Converged after %d iterations "
                "(best=%.4f, no improve for %d steps)",
                state.iteration,
                state.best_reward,
                self._no_improve_streak,
            )

        return converged

    def reset(self) -> None:
        """Reset internal counters. Call before a new optimisation run."""
        self._no_improve_streak = 0
        self._last_best = -1.0
