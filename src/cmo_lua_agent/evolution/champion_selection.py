"""Deterministic champion selection for one completed generation."""

from __future__ import annotations

from cmo_lua_agent.evolution.models import CandidateScore, ChampionDecision


class ChampionSelectionPolicy:
    def __init__(self, *, minimum_improvement_delta: int) -> None:
        self._delta = minimum_improvement_delta

    def select(self, *, rolling_baseline: CandidateScore, candidates: tuple[CandidateScore, ...]) -> ChampionDecision:
        if not rolling_baseline.eligible:
            raise ValueError("rolling_baseline_ineligible")
        exclusions = {item.candidate_id: "ineligible" for item in candidates if not item.eligible}
        eligible = [item for item in candidates if item.eligible]
        if not eligible:
            return ChampionDecision(None, rolling_baseline.candidate_id, rolling_baseline.official_score or 0, False, exclusions)
        best = sorted(eligible, key=lambda item: (
            -(item.official_score or 0), item.own_loss_count, -item.high_value_enemy_damage,
            item.unexpected_weapon_activity_count, -int(item.execution_fidelity == "verified"),
            item.weapon_expenditure, item.candidate_id,
        ))[0]
        baseline_score = rolling_baseline.official_score or 0
        improved = (best.official_score or 0) >= baseline_score + self._delta
        return ChampionDecision(best.candidate_id, best.candidate_id if improved else rolling_baseline.candidate_id,
                                (best.official_score or 0) if improved else baseline_score, improved, exclusions)
