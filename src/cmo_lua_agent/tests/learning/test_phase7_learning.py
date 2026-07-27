from __future__ import annotations
from pathlib import Path
import pytest
from cmo_lua_agent.agents.comparative_learning_agent import ComparativeLearningAgent
from cmo_lua_agent.learning.models import CandidateLearningView, GenerationLearningBundle, ExperienceCandidate
from cmo_lua_agent.learning.store import ExperienceKeyNormalizer, ExperienceRetriever, ExperienceStore


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
def _candidate(i="exp_o1_001", source="o1", quality=.8, confidence=.2): return ExperienceCandidate(i,"naval_air_anti_surface.salvo_timing","tactical_positive","candidate","StrategyProposalAgent",source,"h",(),{},(),{}, {"runtime_version":"2","renderer_version":"2","score_spec_checksum":"s"},("summary",),(),quality,confidence,("attacks",))
def test_agent_allows_empty_proposals_once():
    c=_Client(_response()); analysis, proposals=ComparativeLearningAgent(c).analyze(_bundle()); assert proposals==() and c.calls==1
def test_agent_rejects_facts_in_proposal():
    row={"experience_key":"salvo_timing","experience_type":"tactical_positive","hypothesis":"h","applicable_conditions":[],"recommended_pattern":{},"counter_conditions":[],"supporting_candidate_ids":[],"contradicting_candidate_ids":[],"model_confidence":.2,"status":"candidate"}
    with pytest.raises(ValueError): ComparativeLearningAgent(_Client(_response([row]))).analyze(_bundle())
def test_normalizer_and_idempotent_store(tmp_path: Path):
    assert ExperienceKeyNormalizer().normalize("salvo_timing")=="naval_air_anti_surface.salvo_timing"; assert ExperienceKeyNormalizer().normalize("free form")=="unclassified"
    store=ExperienceStore(tmp_path); item=_candidate(); store.save((item,)); store.save((item,)); assert len(list((tmp_path/"records").glob("*.json")))==1
    with pytest.raises(ValueError): store.save((_candidate(quality=.9),))
def test_retriever_excludes_current_and_prefers_quality(tmp_path: Path):
    store=ExperienceStore(tmp_path); store.save((_candidate("exp_old_low","old",.2,.9),_candidate("exp_old_high","old2",.9,.1),_candidate("exp_self","now",1,1)))
    good, _, _=ExperienceRetriever(store).retrieve(current_optimization_id="now",environment={"runtime_version":"2","renderer_version":"2","score_spec_checksum":"s"},allowed_dimensions=("attacks",)); assert [x.source_optimization_id for x in good]==["old2","old"]
