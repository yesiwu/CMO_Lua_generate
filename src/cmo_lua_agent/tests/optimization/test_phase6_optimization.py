from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from cmo_lua_agent.contract.strategy_models import BaselineStrategy, ScenarioDefinition, ScenarioUnit, StrategySpec, WeaponInventory
from cmo_lua_agent.generation.runtime_models import LuaRuntimeProfile
from cmo_lua_agent.optimization.bootstrap_skill_loader import BootstrapSkillLoader
from cmo_lua_agent.optimization.candidate_comparator import CandidateComparator
from cmo_lua_agent.optimization.candidate_models import CandidateFailureReason, CandidateOutcome, CandidateState
from cmo_lua_agent.optimization.candidate_set_validator import CandidateSetValidator
from cmo_lua_agent.optimization.optimization_generation_workflow import OptimizationGenerationWorkflow
from cmo_lua_agent.optimization.phase6_models import BootstrapSkillSnapshot, EvaluationIdentity, PlanningRequest, StrategyProposalContext
from cmo_lua_agent.optimization.strategy_proposal_agent import StrategyProposalAgent
from cmo_lua_agent.scoring.native_score_compiler import CmoNativeScoreCompilation


def _scenario() -> ScenarioDefinition:
    return ScenarioDefinition("s", (
        ScenarioUnit("red", "red", "Red", "ship", 1, weapon_inventory=(WeaponInventory(10, "W", 12),)),
        ScenarioUnit("blue", "blue", "Blue", "ship", 2),
    ))


def _strategy(quantity: int = 4) -> StrategySpec:
    from cmo_lua_agent.contract.strategy_models import AttackDirective
    return StrategySpec("s", (AttackDirective("a", "red", ("blue",), 10, quantity, 2, 0),))


def _score(scenario: ScenarioDefinition) -> CmoNativeScoreCompilation:
    rule = SimpleNamespace(score_side_id="red")
    spec = SimpleNamespace(scenario_id="s", rules=(rule,))
    return CmoNativeScoreCompilation(spec, SimpleNamespace(checksum="fragment"), "scenario", "role", "profile", "obj", "score", "fragment", "v")


class _Client:
    def __init__(self) -> None:
        self.calls = 0

    def complete_json(self, **_: object) -> object:
        responses = (
            {"intents": [
                {"objective": "Reduce volume.", "strategy_dimensions": ["fire_quantity"]},
                {"objective": "Delay attack.", "strategy_dimensions": ["attack_timing"]},
                {"objective": "Change two dimensions.", "strategy_dimensions": ["fire_quantity", "attack_timing"]},
                {"objective": "Conservative delay.", "strategy_dimensions": ["attack_timing"]},
            ]},
            {"proposal_summary": "x", "changes": [{"path": "/attacks/0/fire_quantity", "value": 1}]},
            {"proposal_summary": "x", "changes": [{"path": "/attacks/0/delay_seconds", "value": 1}]},
            {"proposal_summary": "x", "changes": [{"path": "/attacks/0/fire_quantity", "value": 3}, {"path": "/attacks/0/delay_seconds", "value": 3}]},
            {"proposal_summary": "x", "changes": [{"path": "/attacks/0/delay_seconds", "value": 4}]},
        )
        response = responses[self.calls]
        self.calls += 1
        return response


def test_bootstrap_loader_freezes_project_relative_skill(tmp_path: Path) -> None:
    skill = tmp_path / "src/cmo_lua_agent/skills/bootstrap/x.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nskill_id: x\nversion: 1\nstatus: bootstrap\nsource: human-authored\nevidence_level: none\nconsumer:\n  - StrategyProposalAgent\n---\nbody", encoding="utf-8")
    first = BootstrapSkillLoader(tmp_path).load("src/cmo_lua_agent/skills/bootstrap/x.md")
    second = BootstrapSkillLoader(tmp_path).load("src/cmo_lua_agent/skills/bootstrap/x.md")
    assert first.checksum == second.checksum
    with pytest.raises(ValueError):
        BootstrapSkillLoader(tmp_path).load("../x.md")


def test_proposal_agent_rejects_extra_fields() -> None:
    class Bad:
        def complete_json(self, **_: object) -> object: return {"lua": "bad"}
    context = StrategyProposalContext(
        _scenario(), _strategy(), "objective", ("/attacks/0/fire_quantity", "/attacks/0/delay_seconds"), ("fire_quantity", "attack_timing"),
        "runtime", "v", BootstrapSkillSnapshot("skill", "1", "bootstrap", "human-authored", "none", ("StrategyProposalAgent",), "x.md", "body", "checksum"),
    )
    with pytest.raises(ValueError):
        StrategyProposalAgent(Bad()).propose(context)


def test_proposal_agent_prompts_for_intents_then_scalar_patches() -> None:
    class CapturingClient:
        def __init__(self) -> None:
            self.systems: list[str] = []
            self._delegate = _Client()

        def complete_json(self, **kwargs: object) -> object:
            self.systems.append(str(kwargs["system"]))
            return self._delegate.complete_json()

    client = CapturingClient()
    context = StrategyProposalContext(
        _scenario(), _strategy(), "objective", ("/attacks/0/fire_quantity", "/attacks/0/delay_seconds"), ("fire_quantity", "attack_timing"),
        "runtime", "v", BootstrapSkillSnapshot("skill", "1", "bootstrap", "human-authored", "none", ("StrategyProposalAgent",), "x.md", "body", "checksum"),
    )

    StrategyProposalAgent(client).propose(context)

    assert len(client.systems) == 5
    assert "CandidateIntentPlanner" in client.systems[0]
    assert "CandidatePatchGenerator" in client.systems[1]
    assert "full strategy" in client.systems[1]


def test_candidate_set_rejects_reordered_or_forbidden_changes() -> None:
    from cmo_lua_agent.optimization.phase6_models import StrategyCandidate
    scenario, baseline = _scenario(), _strategy()
    bad = StrategySpec("s", ())
    candidate = StrategyCandidate("candidate_00", bad, "x", ())
    with pytest.raises(ValueError):
        CandidateSetValidator().validate(scenario=scenario, baseline=baseline, candidates=(candidate,) * 4, allowed_paths=("/attacks/0/fire_quantity",), diversity_dimensions=("fire_quantity",))


def _outcome(candidate_id: str, *, score: int | None, success: bool = True, executable: bool | None = None, semantic: bool = True, scoreable: bool = True) -> CandidateOutcome:
    return CandidateOutcome(candidate_id, 0, _strategy(), success, success if executable is None else executable, semantic, scoreable, None, None, 0, 1, 0, 0, None, SimpleNamespace(raw_score=score) if score is not None else None, None, CandidateFailureReason.COMPLETED, CandidateState.COMPLETED, Path("/tmp") / f"candidate_{candidate_id}", Path("/tmp/x"), native_score=score, score_source="execution-summary.json#/official_score/final")


def test_comparator_ranks_negative_scores_and_excludes_contract_mismatch() -> None:
    identity = EvaluationIdentity("s", "spec", "frag", "v", "red")
    mismatch = EvaluationIdentity("other", "spec", "frag", "v", "red")
    result = CandidateComparator().compare(outcomes=((_outcome("candidate_00", score=-10), identity, False), (_outcome("candidate_01", score=-5), identity, False), (_outcome("candidate_02", score=1), mismatch, False)))
    assert [entry.rank for entry in result] == [2, 1, None]
    assert result[2].category == "execution_failed"


def test_comparator_keeps_semantic_and_scoring_failures_distinct() -> None:
    identity = EvaluationIdentity("s", "spec", "frag", "v", "red")
    result = CandidateComparator().compare(outcomes=(
        (_outcome("candidate_00", score=260, success=False, executable=True, semantic=False), identity, False),
        (_outcome("candidate_01", score=None, success=False, executable=True, semantic=True, scoreable=False), identity, False),
    ))
    assert [entry.category for entry in result] == ["semantic_invalid", "unscorable"]
    assert result[0].raw_score == 260
    assert result[0].rank is None


class _Evaluator:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def evaluate(self, request):
        self.calls.append(request.candidate_id)
        return _outcome(request.candidate_id, score=-1)


def test_workflow_serializes_baseline_then_four_candidates(tmp_path: Path) -> None:
    scenario = _scenario()
    request = PlanningRequest(
        "generation", scenario, BaselineStrategy(_strategy(), "baseline.lua", True), "objective",
        ("/attacks/0/fire_quantity", "/attacks/0/delay_seconds"), ("fire_quantity", "attack_timing"),
        LuaRuntimeProfile("runtime", "v"), _score(scenario), 10, tmp_path / "generation",
    )
    evaluator = _Evaluator()
    workflow = OptimizationGenerationWorkflow(
        project_root=Path(__file__).resolve().parents[4], proposal_agent=StrategyProposalAgent(_Client()),
        candidate_evaluator=evaluator,
    )
    result = workflow.run(request)
    assert result.workflow_completed
    assert evaluator.calls == ["baseline", "candidate_00", "candidate_01", "candidate_02", "candidate_03"]
    assert (tmp_path / "generation" / "generation_manifest.json").read_text(encoding="utf-8").find('"completed"') > 0
    assert (tmp_path / "generation" / "leaderboard.json").is_file()
    with pytest.raises(ValueError, match="already exists"):
        workflow.run(request)
