"""Pure stop decisions for controlled campaign execution."""

from __future__ import annotations

from cmo_lua_agent.evolution.models import StopDecision, StopReason


class StopPolicy:
    def evaluate(self, *, contract_changed: bool = False, manual_stop_requested: bool = False,
                 cmo_lock_unavailable: bool = False, require_human_review: bool = False,
                 max_generations_reached: bool = False, budget_exhausted: bool = False,
                 no_improvement_exhausted: bool = False) -> StopDecision:
        checks = (
            (contract_changed, StopReason.CONTRACT_CHANGED),
            (manual_stop_requested, StopReason.MANUAL_STOP_REQUESTED),
            (cmo_lock_unavailable, StopReason.CMO_LOCK_UNAVAILABLE),
            (require_human_review, StopReason.REQUIRE_HUMAN_REVIEW),
            (budget_exhausted, StopReason.MAX_CMO_RUNS_REACHED),
            (no_improvement_exhausted, StopReason.NO_IMPROVEMENT_PATIENCE_EXHAUSTED),
            (max_generations_reached, StopReason.MAX_GENERATIONS_REACHED),
        )
        for enabled, reason in checks:
            if enabled:
                return StopDecision(True, reason)
        return StopDecision(False, StopReason.NONE)
