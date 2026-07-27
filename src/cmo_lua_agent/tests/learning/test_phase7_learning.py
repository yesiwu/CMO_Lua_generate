from __future__ import annotations
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


def test_comparative_learning_agent_has_a_single_official_import_path():
    import importlib

    from cmo_lua_agent.agents import ComparativeLearningAgent as exported_agent

    assert exported_agent is ComparativeLearningAgent
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("cmo_lua_agent.learning.agent")

def _view(cid: str, baseline=False) -> CandidateLearningView:
    return CandidateLearningView(cid, baseline, {}, (), {}, 0, "execution-summary.json#/official_score/final", True, True, True, {}, [], [], {}, "verified", {"results_complete":True}, {"runtime_version":"2","renderer_version":"2","score_spec_checksum":"s"}, ("summary",))
def _bundle() -> GenerationLearningBundle:
    return GenerationLearningBundle("o1",(),{"runtime_version":"2","renderer_version":"2","score_spec_checksum":"s"},_view("baseline",True),(_view("candidate_00"),),(),{},("candidate_00",),(),("summary",))
class _Client:
    def __init__(self, data): self.data=data; self.calls=0
    def complete_json(self, **_): self.calls+=1; return self.data
def _response(proposals=[]): return {"analysis": {k: [] for k in ("observed_strategy_differences","observed_execution_differences","observed_outcome_differences","evidence_limitations","possible_random_factors","next_testable_hypotheses")}, "proposals": proposals}
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
    c=_Client(_response()); analysis, proposals=ComparativeLearningAgent(c).analyze(_bundle()); assert proposals==() and c.calls==1
def test_agent_rejects_facts_in_proposal():
    row={"experience_key":"salvo_timing","experience_type":"tactical_positive","evidence_stance":"support","hypothesis":"h","applicable_conditions":[],"recommended_pattern":{},"counter_conditions":[],"supporting_candidate_ids":[],"contradicting_candidate_ids":[],"model_confidence":.2,"status":"candidate"}
    with pytest.raises(ValueError): ComparativeLearningAgent(_Client(_response([row]))).analyze(_bundle())


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
def test_normalizer_and_idempotent_store(tmp_path: Path):
    assert ExperienceKeyNormalizer().normalize("salvo_timing")=="naval_air_anti_surface.salvo_timing"; assert ExperienceKeyNormalizer().normalize("free form")=="unclassified"
    store=ExperienceStore(tmp_path); item=_candidate(); store.save((item,)); store.save((item,)); assert len(list((tmp_path/"records").glob("*.json")))==1
    with pytest.raises(ValueError): store.save((_candidate(quality=.9),))
def test_retriever_excludes_current_and_prefers_quality(tmp_path: Path):
    store=ExperienceStore(tmp_path); store.save((_candidate("exp_old_low","old",.2,.9),_candidate("exp_old_high","old2",.9,.1),_candidate("exp_self","now",1,1)))
    good, _, _=ExperienceRetriever(store).retrieve(current_optimization_id="now",environment={"runtime_version":"2","renderer_version":"2","score_spec_checksum":"s"},allowed_dimensions=("attacks",)); assert [x.source_optimization_id for x in good]==["old2","old"]
