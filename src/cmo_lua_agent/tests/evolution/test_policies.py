from __future__ import annotations

from cmo_lua_agent.evolution.champion_selection import ChampionSelectionPolicy
from cmo_lua_agent.evolution.models import CandidateScore, CampaignBudget, StopReason
from cmo_lua_agent.evolution.stop_policy import StopPolicy


def _candidate(candidate_id: str, score: int | None, **changes: object) -> CandidateScore:
    values = {
        "candidate_id": candidate_id,
        "official_score": score,
        "execution_success": True,
        "scoreable": True,
        "semantic_valid": True,
        "artifact_provenance": "formal_renderer",
        "score_source": "execution-summary.json#/official_score/final",
        "execution_fidelity": "verified",
    }
    values.update(changes)
    return CandidateScore(**values)


def test_champion_keeps_rolling_baseline_when_best_candidate_does_not_clear_delta() -> None:
    decision = ChampionSelectionPolicy(minimum_improvement_delta=5).select(
        rolling_baseline=_candidate("baseline", 35),
        candidates=(_candidate("candidate_00", 36), _candidate("candidate_01", 34)),
    )
    assert decision.best_candidate_id == "candidate_00"
    assert decision.selected_champion_id == "baseline"
    assert decision.improved is False


def test_negative_scores_are_ranked_normally() -> None:
    decision = ChampionSelectionPolicy(minimum_improvement_delta=1).select(
        rolling_baseline=_candidate("baseline", -50),
        candidates=(_candidate("candidate_00", -10), _candidate("candidate_01", -30)),
    )
    assert decision.best_candidate_id == "candidate_00"
    assert decision.selected_champion_id == "candidate_00"


def test_champion_allows_completed_scoreable_result_with_partial_process_evidence() -> None:
    decision = ChampionSelectionPolicy(minimum_improvement_delta=1).select(
        rolling_baseline=_candidate("baseline", -40, execution_fidelity="unknown"),
        candidates=(_candidate("candidate_00", 160, execution_fidelity="unknown"),),
    )

    assert decision.selected_champion_id == "candidate_00"


def test_stop_policy_stops_on_exact_contract_change() -> None:
    decision = StopPolicy().evaluate(contract_changed=True, manual_stop_requested=False)
    assert decision.should_stop
    assert decision.reason is StopReason.CONTRACT_CHANGED
