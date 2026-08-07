from __future__ import annotations
from dataclasses import replace
from pathlib import Path
import pytest
from cmo_lua_agent.agents.comparative_learning_agent import ComparativeLearningAgent
from cmo_lua_agent.learning.models import (
    CandidateLearningView,
    EvidenceStance,
    ExperienceCandidate,
    ExperienceProposal,
    GenerationLearningBundle,
)
from cmo_lua_agent.learning.store import ExperienceKeyNormalizer, ExperienceRetriever, ExperienceStore
from cmo_lua_agent.learning.workflow import ExperienceCandidateAssembler
from cmo_lua_agent.learning.evidence_reconstruction import ResultEvidenceReconstructor


def test_comparative_learning_agent_has_a_single_official_import_path():
    import importlib

    from cmo_lua_agent.agents import ComparativeLearningAgent as exported_agent

    assert exported_agent is ComparativeLearningAgent
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("cmo_lua_agent.learning.agent")

def _view(cid: str, baseline=False) -> CandidateLearningView:
    return CandidateLearningView(cid, baseline, {}, (), {}, 0, "execution-summary.json#/official_score/final", True, True, True, {}, [], [], {}, "verified", {"results_complete":True}, {"runtime_version":"2","renderer_version":"2","score_spec_checksum":"s"}, ("summary",), "COMPLETE")
def _bundle() -> GenerationLearningBundle:
    return GenerationLearningBundle("o1",(),{"runtime_version":"2","renderer_version":"2","score_spec_checksum":"s"},_view("baseline",True),(_view("candidate_00"),),(),{},("candidate_00",),(),("summary",))
class _Client:
    def __init__(self, data): self.data=data; self.calls=0
    def complete_json(self, **_): self.calls+=1; return self.data
def _response(proposals=[]):
    analysis = {k: [] for k in ("observed_strategy_differences","observed_execution_differences","observed_outcome_differences","evidence_limitations","possible_random_factors","next_testable_hypotheses")}
    return {"candidate_comparisons": [{"candidate_id": "candidate_00", "analysis": analysis}], "cross_candidate_analysis": analysis, "proposals": proposals}
def _candidate(i="exp_o1_001", source="o1", quality=.8, confidence=.2):
    return ExperienceCandidate(
        experience_id=i,
        experience_key="naval_air_anti_surface.salvo_timing",
        experience_type="tactical_positive",
        evidence_stance=EvidenceStance.SUPPORT,
        status="candidate",
        consumer="StrategyProposalAgent",
        source_optimization_id=source,
        hypothesis="h",
        applicable_conditions=(),
        recommended_pattern={},
        counter_conditions=(),
        observed_effect={},
        environment={
            "runtime_version": "2",
            "renderer_version": "2",
            "score_spec_checksum": "s",
        },
        evidence_refs=("summary",),
        created_from=(),
        evidence_quality=quality,
        model_confidence=confidence,
        strategy_dimensions=("attacks",),
    )
def test_agent_allows_empty_proposals_once():
    c=_Client(_response()); response=ComparativeLearningAgent(c).analyze(_bundle()); assert response.proposals==() and c.calls==1


def test_agent_binds_ordered_comparisons_to_frozen_candidate_ids() -> None:
    analysis = {k: [] for k in (
        "observed_strategy_differences", "observed_execution_differences",
        "observed_outcome_differences", "evidence_limitations",
        "possible_random_factors", "next_testable_hypotheses",
    )}
    response = ComparativeLearningAgent(_Client({
        "candidate_comparisons": [analysis],
        "cross_candidate_analysis": analysis,
        "proposals": [],
    })).analyze(_bundle())

    assert [item.candidate_id for item in response.candidate_comparisons] == ["candidate_00"]


def test_agent_repairs_invalid_batch_response_up_to_three_times() -> None:
    analysis = {k: [] for k in (
        "observed_strategy_differences", "observed_execution_differences",
        "observed_outcome_differences", "evidence_limitations",
        "possible_random_factors", "next_testable_hypotheses",
    )}

    class RetryClient:
        def __init__(self) -> None:
            self.calls = 0
            self.responses = [
                {"candidate_comparisons": [], "proposals": []},
                {"candidate_comparisons": [analysis], "cross_candidate_analysis": analysis, "proposals": []},
            ]

        def complete_json(self, **_: object) -> object:
            value = self.responses[self.calls]
            self.calls += 1
            return value

    client = RetryClient()
    agent = ComparativeLearningAgent(client)
    response = agent.analyze(_bundle())

    assert response.proposals == ()
    assert client.calls == 2
    assert [item["status"] for item in agent.last_attempts] == ["invalid", "accepted"]
def test_agent_rejects_facts_in_proposal():
    row={"experience_key":"salvo_timing","experience_type":"tactical_positive","evidence_stance":"support","hypothesis":"h","applicable_conditions":[],"recommended_pattern":{},"counter_conditions":[],"supporting_candidate_ids":[],"contradicting_candidate_ids":[],"model_confidence":.2,"status":"candidate"}
    with pytest.raises(ValueError): ComparativeLearningAgent(_Client(_response([row]))).analyze(_bundle())


@pytest.mark.parametrize("field", [
    "applicable_conditions", "counter_conditions", "supporting_candidate_ids",
    "contradicting_candidate_ids",
])
def test_agent_rejects_scalar_where_string_array_is_required(field: str):
    row = {
        "experience_key": "salvo_timing", "experience_type": "tactical_positive",
        "evidence_stance": "support", "hypothesis": "h",
        "applicable_conditions": [], "recommended_pattern": {},
        "counter_conditions": [], "supporting_candidate_ids": ["candidate_00"],
        "contradicting_candidate_ids": [], "model_confidence": .2,
    }
    row[field] = "not-an-array"
    with pytest.raises(ValueError, match="must be an array of strings"):
        ComparativeLearningAgent(_Client(_response([row]))).analyze(_bundle())


def _proposal(
    *,
    stance: EvidenceStance = EvidenceStance.SUPPORT,
    supporting: tuple[str, ...] = ("candidate_00",),
    contradicting: tuple[str, ...] = (),
    counter_conditions: tuple[str, ...] = (),
) -> ExperienceProposal:
    return ExperienceProposal(
        experience_key="salvo_timing",
        experience_type="tactical_positive",
        evidence_stance=stance,
        hypothesis="h",
        applicable_conditions=(),
        recommended_pattern={},
        counter_conditions=counter_conditions,
        supporting_candidate_ids=supporting,
        contradicting_candidate_ids=contradicting,
        model_confidence=0.5,
    )


def test_agent_rejects_invalid_evidence_stance():
    row = {
        "experience_key": "salvo_timing",
        "experience_type": "tactical_positive",
        "evidence_stance": "inferred",
        "hypothesis": "h",
        "applicable_conditions": [],
        "recommended_pattern": {},
        "counter_conditions": [],
        "supporting_candidate_ids": ["candidate_00"],
        "contradicting_candidate_ids": [],
        "model_confidence": 0.2,
    }
    with pytest.raises(ValueError):
        ComparativeLearningAgent(_Client(_response([row]))).analyze(_bundle())


def test_assembler_validates_candidate_references_and_stance_gates():
    assembler = ExperienceCandidateAssembler()
    candidate = assembler.assemble(
        bundle=_bundle(),
        proposals=(_proposal(),),
    )[0]
    assert candidate.evidence_stance is EvidenceStance.SUPPORT
    assert candidate.schema_version == "2"

    with pytest.raises(ValueError):
        assembler.assemble(
            bundle=_bundle(),
            proposals=(_proposal(supporting=("unknown",)),),
        )
    with pytest.raises(ValueError):
        assembler.assemble(
            bundle=_bundle(),
            proposals=(_proposal(
                supporting=("candidate_00",),
                contradicting=("candidate_00",),
            ),),
        )
    with pytest.raises(ValueError):
        assembler.assemble(
            bundle=_bundle(),
            proposals=(_proposal(
                stance=EvidenceStance.QUALIFY,
                counter_conditions=(),
            ),),
        )


def test_missing_score_chain_becomes_low_confidence_blackbox_diagnostic() -> None:
    baseline = _view("baseline", True)
    candidate = replace(_view("candidate_00"), scoring_evidence_status="MISSING")
    bundle = GenerationLearningBundle(
        "blackbox", (), {"runtime_version": "2"}, baseline, (candidate,),
        (), {}, ("candidate_00",), (), ("summary",),
    )
    experience = ExperienceCandidateAssembler().assemble(
        bundle=bundle,
        proposals=(_proposal(),),
    )[0]

    assert experience.experience_type == "evidence_limitation"
    assert experience.evidence_quality == 0.4
    assert experience.model_confidence == 0.4
    assert experience.skill_promotion_eligible is False
    assert experience.observed_effect["black_box_outcome_only"] is True
def test_normalizer_and_idempotent_store(tmp_path: Path):
    assert ExperienceKeyNormalizer().normalize("salvo_timing")=="naval_air_anti_surface.salvo_timing"; assert ExperienceKeyNormalizer().normalize("free form")=="unclassified"
    store=ExperienceStore(tmp_path); item=_candidate(); store.save((item,)); store.save((item,)); assert len(list((tmp_path/"records").glob("*.json")))==1
    with pytest.raises(ValueError): store.save((_candidate(quality=.9),))
def test_retriever_excludes_current_and_prefers_quality(tmp_path: Path):
    store=ExperienceStore(tmp_path); store.save((_candidate("exp_old_low","old",.2,.9),_candidate("exp_old_high","old2",.9,.1),_candidate("exp_self","now",1,1)))
    good, _, _=ExperienceRetriever(store).retrieve(current_optimization_id="now",environment={"runtime_version":"2","renderer_version":"2","score_spec_checksum":"s"},allowed_dimensions=("attacks",)); assert [x.source_optimization_id for x in good]==["old2","old"]


def test_retriever_uses_experience_id_tiebreaker_without_comparing_record_dicts(tmp_path: Path):
    store = ExperienceStore(tmp_path)
    store.save((_candidate("exp_b", "old_b", .8, .8), _candidate("exp_a", "old_a", .8, .8)))

    positive, _, _ = ExperienceRetriever(store).retrieve(
        current_optimization_id="now",
        environment={"runtime_version":"2", "renderer_version":"2", "score_spec_checksum":"s"},
        allowed_dimensions=("attacks",),
    )

    assert [card.source_optimization_id for card in positive] == ["old_a", "old_b"]


def test_retriever_keeps_related_experience_when_environment_metadata_changes(tmp_path: Path):
    """Runtime metadata ranks evidence; it must not hide a related tactic."""
    store = ExperienceStore(tmp_path)
    item = _candidate("exp_other_runtime", "older", .8, .4)
    payload = item.to_dict()
    payload["environment"] = {
        "runtime_version": "3",
        "renderer_version": "9",
        "score_spec_checksum": "different-score-spec",
        "mission_type": "naval_air_anti_surface",
    }
    store.records.mkdir(parents=True)
    (store.records / "exp_other_runtime.json").write_text(
        __import__("json").dumps(payload), encoding="utf-8"
    )
    store.save(())

    positive, _, _ = ExperienceRetriever(store).retrieve(
        current_optimization_id="now",
        environment={
            "runtime_version": "2",
            "renderer_version": "2",
            "score_spec_checksum": "s",
            "mission_type": "naval_air_anti_surface",
        },
        allowed_dimensions=("attacks",),
    )

    assert [item.source_optimization_id for item in positive] == ["older"]


def test_retriever_keeps_related_experience_when_environment_metadata_changes(tmp_path: Path):
    """Runtime metadata ranks evidence; it must not hide a related tactic."""
    store = ExperienceStore(tmp_path)
    item = _candidate("exp_other_runtime", "older", .8, .4)
    payload = item.to_dict()
    payload["environment"] = {
        "runtime_version": "3",
        "renderer_version": "9",
        "score_spec_checksum": "different-score-spec",
        "mission_type": "naval_air_anti_surface",
    }
    store.records.mkdir(parents=True)
    (store.records / "exp_other_runtime.json").write_text(
        __import__("json").dumps(payload), encoding="utf-8"
    )
    store.save(())

    positive, _, _ = ExperienceRetriever(store).retrieve(
        current_optimization_id="now",
        environment={
            "runtime_version": "2",
            "renderer_version": "2",
            "score_spec_checksum": "s",
            "mission_type": "naval_air_anti_surface",
        },
        allowed_dimensions=("attacks",),
    )

    assert [item.source_optimization_id for item in positive] == ["older"]


def test_retriever_honors_immutable_record_exclusions(tmp_path: Path):
    store = ExperienceStore(tmp_path)
    item = _candidate("exp_excluded", "old", 1, 1)
    store.save((item,))
    store.record_exclusions(({"experience_id": item.experience_id, "reason": "malformed_condition_array"},))
    positive, negative, diagnostic = ExperienceRetriever(store).retrieve(
        current_optimization_id="now", environment={"runtime_version":"2","renderer_version":"2","score_spec_checksum":"s"}, allowed_dimensions=("attacks",)
    )
    assert (positive, negative, diagnostic) == ((), (), ())
    assert (tmp_path / "records" / "exp_excluded.json").is_file()


def test_legacy_unclassified_character_conditions_are_excluded_not_rewritten(tmp_path: Path):
    store = ExperienceStore(tmp_path)
    item = _candidate("exp_bad", "old")
    payload = item.to_dict() | {"experience_key": "unclassified", "applicable_conditions": ["b", "a", "d"]}
    store.records.mkdir(parents=True)
    record = store.records / "exp_bad.json"
    record.write_text(__import__("json").dumps(payload), encoding="utf-8")
    exclusions = store.exclude_non_retrievable_records()
    assert exclusions == ({"experience_id": "exp_bad", "reason": "malformed_condition_array"},)
    assert __import__("json").loads(record.read_text(encoding="utf-8"))["experience_key"] == "unclassified"


def test_result_evidence_reconstruction_uses_csv_without_reading_sqlite(tmp_path: Path):
    result_dir = tmp_path / "results"
    result_dir.mkdir()
    summary = {
        "official_score": {"initial": 0, "final": 160, "delta": 160, "status": "VALID"},
        "score_events": [],
        "losses": {"red": [], "blue": []},
        "target_damage": [],
        "evidence_integrity": {"status": "DEGRADED", "results_complete": False},
    }
    (result_dir / "execution-summary.json").write_text(__import__("json").dumps(summary), encoding="utf-8")
    (result_dir / "combat-summary.csv").write_text(
        "指标,阵营,武器或单位,结果,数量或损伤百分比\n"
        "单位战损,red,J-15-1 [J-15],被毁,1\n"
        "单位战损,red,J-15-2 [J-15],被毁,1\n"
        "单位战损,blue,蓝方CVN-70卡尔文森 [CVN],被毁,1\n",
        encoding="utf-8",
    )
    rules = (
        {"rule_id": "native_score/red_j15_1", "target_unit_name": "J-15-1", "point_change": -20},
        {"rule_id": "native_score/red_j15_2", "target_unit_name": "J-15-2", "point_change": -20},
        {"rule_id": "native_score/blue_cvn70", "target_unit_name": "蓝方CVN-70卡尔文森", "point_change": 200},
    )

    rebuilt = ResultEvidenceReconstructor(score_rules=rules).reconstruct(result_dir)

    assert [row["unit_name"] for row in rebuilt["losses"]["red"]] == ["J-15-1", "J-15-2"]
    assert [row["point_delta"] for row in rebuilt["score_events"]] == [-20, -20, 200]
    assert rebuilt["scoring_evidence_status"] == "DERIVED"
    assert rebuilt["score_event_chain_status"] == "DERIVED_VALID"


def test_result_evidence_reconstruction_preserves_original_summary_before_apply(tmp_path: Path):
    result_dir = tmp_path / "results"
    result_dir.mkdir()
    original = {
        "official_score": {"initial": 0, "final": -20, "delta": -20, "status": "VALID"},
        "score_events": [], "losses": {"red": [], "blue": []}, "target_damage": [],
    }
    (result_dir / "execution-summary.json").write_text(__import__("json").dumps(original), encoding="utf-8")
    (result_dir / "combat-summary.csv").write_text(
        "指标,阵营,武器或单位,结果,数量或损伤百分比\n单位战损,red,J-15-1 [J-15],被毁,1\n",
        encoding="utf-8",
    )
    updated = ResultEvidenceReconstructor(score_rules=(
        {"rule_id": "native_score/red_j15_1", "target_unit_name": "J-15-1", "point_change": -20},
    )).apply(result_dir)

    assert (result_dir / "execution-summary.pre-phase7-reconstruction.json").is_file()
    assert updated["scoring_evidence_status"] == "DERIVED"
