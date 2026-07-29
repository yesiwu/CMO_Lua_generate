from __future__ import annotations

import pytest

from cmo_lua_agent.evolution.models import CampaignBudget, CampaignExecutionMode, EvolutionCampaignSpec


def _budget(**changes: int) -> CampaignBudget:
    values = {
        "max_generations": 3,
        "max_cmo_runs": 30,
        "max_cmo_attempts_per_candidate": 2,
        "max_cmo_attempts_for_baseline": 2,
        "max_repair_attempts_per_candidate": 1,
        "max_failed_runs": 8,
        "max_llm_total_calls": 20,
        "max_strategy_proposal_calls": 9,
        "max_lua_generation_calls": 0,
        "max_lua_repair_calls": 8,
        "max_comparative_learning_calls": 3,
        "max_skill_author_calls": 3,
        "max_wall_clock_seconds": 3600,
        "per_generation_timeout_seconds": 1200,
        "per_candidate_timeout_seconds": 600,
    }
    values.update(changes)
    return CampaignBudget(**values)


def _spec(**changes: object) -> EvolutionCampaignSpec:
    values = {
        "campaign_id": "campaign_001",
        "scenario_id": "scenario_6v4",
        "scenario_ref": "baseline/6v4/scenario_definition.json",
        "scenario_checksum": "scenario-sha",
        "initial_strategy_ref": "json_data/6v4ScenarioIR.json#derived-baseline",
        "runtime_contract_checksum": "runtime-sha",
        "renderer_contract_checksum": "renderer-sha",
        "score_contract_checksum": "score-sha",
        "semantic_contract_checksum": "semantic-sha",
        "code_revision": "abc123",
        "allowed_strategy_paths": ("/attacks/0/fire_quantity",),
        "generation_objective": "improve score",
        "budget": _budget(),
        "execution_mode": CampaignExecutionMode.FAKE_FIXTURE,
    }
    values.update(changes)
    return EvolutionCampaignSpec(**values)


def test_campaign_requires_four_candidates_and_explicit_budget() -> None:
    spec = _spec()
    assert spec.candidates_per_generation == 4
    assert spec.checksum
    with pytest.raises(ValueError, match="candidates_per_generation"):
        _spec(candidates_per_generation=3)


def test_generation_reservation_accounts_for_baseline_and_all_candidates() -> None:
    budget = _budget(max_cmo_attempts_for_baseline=2, max_cmo_attempts_per_candidate=3)
    assert budget.required_cmo_attempts_per_generation == 14
    assert budget.can_reserve_generation(available_cmo_runs=14)
    assert not budget.can_reserve_generation(available_cmo_runs=13)


def test_contract_fingerprint_changes_when_any_exact_contract_changes() -> None:
    spec = _spec()
    changed = _spec(renderer_contract_checksum="different")
    assert spec.contract_checksum != changed.contract_checksum
