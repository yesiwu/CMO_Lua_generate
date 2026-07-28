"""Deterministic pre-CMO novelty checks for Phase 9 candidate roles."""

from __future__ import annotations

from cmo_lua_agent.optimization.candidate_set_validator import strategy_leaf_diff
from cmo_lua_agent.optimization.phase6_models import StrategyCandidate


class CandidateNoveltyValidator:
    def validate(self, *, baseline, candidates: tuple[StrategyCandidate, ...], generation_context: dict[str, object]) -> None:
        allowed = tuple(generation_context.get("allowed_strategy_paths", ()))
        history = set(generation_context.get("history_fingerprints", ()))
        roles = dict(generation_context.get("candidate_roles", {}))
        fingerprints: set[str] = set()
        dimensions: set[str] = set()
        for candidate in candidates:
            if candidate.strategy_checksum in fingerprints:
                raise ValueError("novelty_duplicate_candidate")
            fingerprints.add(candidate.strategy_checksum)
            if candidate.strategy_checksum in history:
                raise ValueError("novelty_repeated_history")
            changed = strategy_leaf_diff(baseline, candidate.strategy_spec, allowed)
            if not changed:
                raise ValueError("novelty_matches_rolling_baseline")
            dimensions.update(path.split("/")[1] for path in changed if path.count("/") >= 2)
            role = roles.get(candidate.candidate_id)
            if role == "conservative_control" and len(changed) > int(generation_context.get("conservative_max_changed_leaves", 1)):
                raise ValueError("novelty_conservative_scope_exceeded")
            if role == "repair" and not generation_context.get("previous_generation_failures"):
                raise ValueError("novelty_repair_has_no_prior_failure")
        explore_id = next((candidate_id for candidate_id, role in roles.items() if role == "explore"), None)
        if explore_id and len(dimensions) < 2:
            raise ValueError("novelty_explore_dimension_missing")
