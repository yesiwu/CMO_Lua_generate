"""Deterministic gate for generation-wide side effects."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


_TERMINAL_STATES = frozenset(
    {
        "completed",
        "semantic_invalid",
        "unscorable",
        "execution_failed",
        "failed",
        "runtime_defect",
        "repair_budget_exhausted",
        "cancelled_after_start",
    }
)


@dataclass(frozen=True, slots=True)
class GenerationCompletionDecision:
    complete: bool
    code: str
    pending_candidate_ids: tuple[str, ...]


class GenerationCompletionGate:
    """Allow ranking and learning only after every expected object is terminal."""

    def evaluate(
        self,
        *,
        expected_candidate_ids: Sequence[str],
        outcomes: Sequence[Mapping[str, object]],
    ) -> GenerationCompletionDecision:
        state_by_id = {
            str(item.get("candidate_id")): self._state(item)
            for item in outcomes
        }
        pending = tuple(
            candidate_id
            for candidate_id in expected_candidate_ids
            if state_by_id.get(candidate_id, "not_started") not in _TERMINAL_STATES
        )
        return GenerationCompletionDecision(
            complete=not pending,
            code="generation_complete" if not pending else "generation_incomplete",
            pending_candidate_ids=pending,
        )

    @staticmethod
    def _state(outcome: Mapping[str, object]) -> str:
        state = outcome.get("final_state")
        if isinstance(state, str) and state:
            return state.lower()
        # Compatibility for pre-gate Phase 6 adapters.  A false or absent
        # success flag remains non-terminal and therefore blocks side effects.
        return "completed" if outcome.get("success") is True else "not_started"
