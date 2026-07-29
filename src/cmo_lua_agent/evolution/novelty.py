"""Deterministic Phase 9 candidate novelty validation."""

from __future__ import annotations

from cmo_lua_agent.optimization.candidate_set_validator import strategy_leaf_diff
from cmo_lua_agent.optimization.phase6_models import StrategyCandidate
from cmo_lua_agent.optimization.strategy_dimensions import semantic_dimensions


class CandidateNoveltyError(ValueError):
    """A deterministic novelty rejection with bounded repair context."""

    def __init__(
        self,
        *,
        code: str,
        failed_candidate_ids: tuple[str, ...],
        required_dimensions: tuple[str, ...],
        actual_dimensions: tuple[str, ...],
        related_changed_paths: tuple[str, ...],
    ) -> None:
        self.code = code
        self.failed_candidate_ids = failed_candidate_ids
        self.required_dimensions = required_dimensions
        self.actual_dimensions = actual_dimensions
        self.related_changed_paths = related_changed_paths
        super().__init__(code)


class CandidateNoveltyValidator:
    """Reject duplicate, historical, unchanged, or role-incompatible candidates."""

    def validate(
        self,
        *,
        baseline,
        candidates: tuple[StrategyCandidate, ...],
        generation_context: dict[str, object],
    ) -> None:
        allowed = tuple(generation_context.get("allowed_strategy_paths", ()))
        history = set(generation_context.get("history_fingerprints", ()))
        roles = dict(generation_context.get("candidate_roles", {}))
        fingerprints: set[str] = set()

        for candidate in candidates:
            if candidate.strategy_checksum in fingerprints:
                raise ValueError("novelty_duplicate_candidate")
            fingerprints.add(candidate.strategy_checksum)
            if candidate.strategy_checksum in history:
                raise ValueError("novelty_repeated_history")

            changed = strategy_leaf_diff(baseline, candidate.strategy_spec, allowed)
            if not changed:
                raise ValueError("novelty_matches_rolling_baseline")
            semantic_dimensions(changed)

            role = roles.get(candidate.candidate_id)
            if role == "conservative_control" and len(changed) > int(
                generation_context.get("conservative_max_changed_leaves", 1)
            ):
                raise ValueError("novelty_conservative_scope_exceeded")
            if role == "repair" and not generation_context.get(
                "previous_generation_failures"
            ):
                raise ValueError("novelty_repair_has_no_prior_failure")
