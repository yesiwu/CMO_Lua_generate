from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cmo_lua_agent.evolution.models import CampaignBudget, CampaignExecutionMode, CandidateScore, EvolutionCampaignSpec
from cmo_lua_agent.evolution.workflow import EvolutionWorkflow


def _spec() -> EvolutionCampaignSpec:
    return EvolutionCampaignSpec(
        campaign_id="fixture_campaign", scenario_id="six_v_four", scenario_ref="scenario.json",
        scenario_checksum="scenario", initial_strategy_ref="strategy.json", runtime_contract_checksum="runtime",
        renderer_contract_checksum="renderer", score_contract_checksum="score", semantic_contract_checksum="semantic",
        code_revision="revision", allowed_strategy_paths=("/attacks/0/fire_quantity",), generation_objective="improve",
        execution_mode=CampaignExecutionMode.FAKE_FIXTURE,
        budget=CampaignBudget(3, 15, 1, 1, 0, 4, 20, 4, 0, 0, 3, 0, 3600, 1200, 600),
        minimum_improvement_delta=5,
    )


def _score(candidate_id: str, value: int | None, **changes: object) -> CandidateScore:
    values = dict(candidate_id=candidate_id, official_score=value, execution_success=True, scoreable=True,
                  semantic_valid=True, artifact_provenance="formal_renderer",
                  score_source="execution-summary.json#/official_score/final", execution_fidelity="verified")
    values.update(changes)
    return CandidateScore(**values)


@dataclass
class _Phase6:
    generations: list[tuple[CandidateScore, tuple[CandidateScore, ...]]]
    calls: list[int]

    def run(self, *, generation_index: int, rolling_baseline_id: str, **_: object):
        self.calls.append(generation_index)
        return self.generations[generation_index]


class _Phase7:
    def __init__(self) -> None:
        self.calls: list[int] = []

    def run(self, *, generation_index: int, **_: object) -> tuple[dict[str, object], ...]:
        self.calls.append(generation_index)
        return ({"experience_id": f"exp-{generation_index}", "source_generation_index": generation_index},)


class _Phase8:
    def __init__(self) -> None:
        self.calls: list[int] = []

    def run(self, *, generation_index: int, **_: object) -> str:
        self.calls.append(generation_index)
        return "no_eligible_experience"


def test_three_generation_fake_campaign_reexecutes_rolling_baseline_and_isolates_learning(tmp_path: Path) -> None:
    phase6 = _Phase6([
        (_score("baseline", 0), (_score("candidate_00", 10), _score("candidate_01", 20), _score("candidate_02", None, semantic_valid=False), _score("candidate_03", -5))),
        (_score("candidate_01", 20), (_score("candidate_00", 22), _score("candidate_01", 35), _score("candidate_02", 18), _score("candidate_03", None, scoreable=False))),
        (_score("candidate_01", 35), (_score("candidate_00", 36), _score("candidate_01", 34), _score("candidate_02", 30), _score("candidate_03", None, semantic_valid=False))),
    ], [])
    phase7, phase8 = _Phase7(), _Phase8()
    result = EvolutionWorkflow(phase6=phase6, phase7=phase7, phase8=phase8).run(_spec(), root=tmp_path / "campaign")

    assert phase6.calls == [0, 1, 2]
    assert result.anchor_score == 0
    assert result.rolling_scores == (20, 35, 35)
    assert result.global_best_score == 35
    assert phase7.calls == [0, 1, 2]
    assert phase8.calls == [0, 1, 2]
    assert (tmp_path / "campaign" / "lineage.jsonl").is_file()


def test_manual_stop_after_phase6_keeps_auditable_partial_generation_without_learning(tmp_path: Path) -> None:
    phase6 = _Phase6([(_score("baseline", 0), (_score("candidate_00", 10),) * 4)], [])
    phase7, phase8 = _Phase7(), _Phase8()
    calls = 0

    def stop() -> bool:
        nonlocal calls
        calls += 1
        return calls >= 2

    result = EvolutionWorkflow(phase6=phase6, phase7=phase7, phase8=phase8, stop_requested=stop).run(
        _spec(), root=tmp_path / "stopped"
    )

    assert result.stopped_early
    assert phase6.calls == [0]
    assert phase7.calls == []
    assert phase8.calls == []
