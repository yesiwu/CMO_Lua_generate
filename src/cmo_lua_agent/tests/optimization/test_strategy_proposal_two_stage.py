from __future__ import annotations

from cmo_lua_agent.contract.strategy_models import (
    AttackDirective,
    ScenarioDefinition,
    ScenarioUnit,
    StrategySpec,
    WeaponInventory,
)
from cmo_lua_agent.optimization.phase6_models import BootstrapSkillSnapshot, StrategyProposalContext
import pytest

from cmo_lua_agent.llm.json_client import JsonCompletionError
from cmo_lua_agent.optimization.candidate_intent_conformance import (
    CandidateIntentConformanceError,
    CandidateIntentConformanceValidator,
)
from cmo_lua_agent.optimization.proposal_models import CandidateIntent, CandidateProposalError, ProposalContractError
from cmo_lua_agent.optimization.strategy_proposal_agent import StrategyProposalAgent


def _context() -> StrategyProposalContext:
    scenario = ScenarioDefinition(
        "proposal-test",
        (
            ScenarioUnit("red", "red", "Red", "ship", 1, weapon_inventory=(WeaponInventory(10, "W", 12),)),
            ScenarioUnit("blue", "blue", "Blue", "ship", 2),
        ),
    )
    baseline = StrategySpec(
        "proposal-test",
        (AttackDirective("attack.red.blue", "red", ("blue",), 10, 4, 2, 0),),
    )
    return StrategyProposalContext(
        scenario,
        baseline,
        "Improve target coverage without changing scenario facts.",
        ("/attacks/0/fire_quantity", "/attacks/0/delay_seconds"),
        ("fire_quantity", "attack_timing"),
        "runtime",
        "1.0.0",
        BootstrapSkillSnapshot(
            "bootstrap", "1", "bootstrap", "human-authored", "none",
            ("StrategyProposalAgent",), "bootstrap.md", "rules", "bootstrap-checksum",
        ),
    )


class _TwoStageClient:
    def __init__(self) -> None:
        self.calls = 0
        self._responses = [
            {
                "intents": [
                    {"objective": "Increase the first attack volume.", "strategy_dimensions": ["fire_quantity"]},
                    {"objective": "Delay the repair candidate.", "strategy_dimensions": ["attack_timing"]},
                    {"objective": "Use both supported dimensions.", "strategy_dimensions": ["fire_quantity", "attack_timing"]},
                    {"objective": "Use a conservative timing adjustment.", "strategy_dimensions": ["attack_timing"]},
                ]
            },
            {"proposal_summary": "More missiles.", "changes": [{"path": "/attacks/0/fire_quantity", "value": 5}]},
            {"proposal_summary": "Delay launch.", "changes": [{"path": "/attacks/0/delay_seconds", "value": 1}]},
            {"proposal_summary": "Split the change.", "changes": [{"path": "/attacks/0/fire_quantity", "value": 3}, {"path": "/attacks/0/delay_seconds", "value": 4}]},
            {"proposal_summary": "Conservative delay.", "changes": [{"path": "/attacks/0/delay_seconds", "value": 5}]},
        ]

    def complete_json(self, **_: object) -> object:
        response = self._responses[self.calls]
        self.calls += 1
        return response


def test_proposal_agent_uses_one_intent_and_four_ordered_patch_calls() -> None:
    client = _TwoStageClient()

    candidates = StrategyProposalAgent(client).propose(_context())

    assert [candidate.candidate_id for candidate in candidates] == [
        "candidate_00", "candidate_01", "candidate_02", "candidate_03",
    ]
    assert candidates[0].strategy_spec.attacks[0].fire_quantity == 5
    assert candidates[1].strategy_spec.attacks[0].delay_seconds == 1
    assert candidates[2].intended_difference == (
        "/attacks/0/delay_seconds",
        "/attacks/0/fire_quantity",
    )
    assert client.calls == 5


def test_targeted_candidate_repair_does_not_call_the_intent_planner() -> None:
    class RepairClient:
        calls = 0

        def complete_json(self, **_kwargs: object) -> object:
            self.calls += 1
            return {
                "proposal_summary": "Explore timing and quantity.",
                "changes": [
                    {"path": "/attacks/0/fire_quantity", "value": 3},
                    {"path": "/attacks/0/delay_seconds", "value": 4},
                ],
            }

    client = RepairClient()
    agent = StrategyProposalAgent(client)
    intent = CandidateIntent(
        "candidate_02", "explore", "Explore two dimensions.",
        ("fire_quantity", "attack_timing"), 2, 3,
    )

    candidate = agent.repair_candidate(
        _context(), intent=intent, accepted=(),
        prior_error=ProposalContractError("novelty_explore_dimension_missing"),
    )

    assert client.calls == 1
    assert agent.last_usage.intent_calls == 0
    assert agent.last_usage.patch_calls == 1
    assert candidate.candidate_id == "candidate_02"


def test_invalid_patch_repair_json_is_bound_to_candidate_and_stage() -> None:
    class InvalidRepairClient(_TwoStageClient):
        def __init__(self) -> None:
            super().__init__()
            self._responses[3] = ProposalContractError("patch_path_not_offered")
            self._responses[4] = JsonCompletionError(
                {"response_type": "str", "response_length": 9, "response_checksum": "fixture"}
            )

        def complete_json(self, **_: object) -> object:
            response = self._responses[self.calls]
            self.calls += 1
            if isinstance(response, Exception):
                raise response
            return response

    agent = StrategyProposalAgent(InvalidRepairClient())

    with pytest.raises(CandidateProposalError) as raised:
        agent.propose(_context())

    assert raised.value.candidate_id == "candidate_02"
    assert raised.value.stage == "patch_repair"
    assert raised.value.code == "proposal_json_invalid"
    assert raised.value.diagnostics["response_checksum"] == "fixture"


def test_resumed_candidate_generation_skips_intent_and_is_bounded_to_one_repair() -> None:
    class ResumeClient:
        calls = 0

        def complete_json(self, **_kwargs: object) -> object:
            self.calls += 1
            if self.calls == 1:
                return {"invalid": "shape"}
            return {
                "proposal_summary": "Use a constrained timing change.",
                "changes": [{"path": "/attacks/0/delay_seconds", "value": 4}],
            }

    agent = StrategyProposalAgent(ResumeClient())
    intent = CandidateIntent(
        "candidate_03", "conservative", "Use a smaller delay.",
        ("attack_timing",), 1, 1,
    )

    candidate = agent.generate_candidate(_context(), intent=intent, accepted=())

    assert candidate.candidate_id == "candidate_03"
    assert agent.last_usage.intent_calls == 0
    assert agent.last_usage.patch_calls == 1
    assert agent.last_usage.repair_calls == 1


def test_explore_intent_requires_two_semantic_dimensions_not_two_target_leaves() -> None:
    intent = CandidateIntent(
        "candidate_02", "explore", "Cover separate targets.",
        ("target_assignment", "fire_quantity"), 2, 3,
    )

    with pytest.raises(CandidateIntentConformanceError) as raised:
        CandidateIntentConformanceValidator().validate(
            intent=intent,
            changed_paths=("/attacks/0/target_ids/0", "/attacks/1/target_ids/0"),
        )

    assert raised.value.code == "candidate_intent_dimension_missing"
    assert raised.value.required_dimensions == ("target_assignment", "fire_quantity")
    assert raised.value.actual_dimensions == ("target_assignment",)


def test_conservative_intent_must_change_exactly_one_leaf() -> None:
    intent = CandidateIntent(
        "candidate_03", "conservative", "Limit exposure.",
        ("attack_timing",), 1, 1,
    )

    CandidateIntentConformanceValidator().validate(
        intent=intent,
        changed_paths=("/attacks/0/delay_seconds",),
    )
