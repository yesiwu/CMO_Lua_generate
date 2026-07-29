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


def _explore_context() -> StrategyProposalContext:
    scenario = ScenarioDefinition(
        "proposal-explore-test",
        (
            ScenarioUnit("red", "red", "Red", "ship", 1, weapon_inventory=(WeaponInventory(10, "W", 12),)),
            ScenarioUnit("blue-1", "blue", "Blue 1", "ship", 2),
            ScenarioUnit("blue-2", "blue", "Blue 2", "ship", 3),
            ScenarioUnit("blue-3", "blue", "Blue 3", "ship", 4),
        ),
    )
    baseline = StrategySpec(
        "proposal-explore-test",
        (
            AttackDirective("attack.red.blue.1", "red", ("blue-1",), 10, 4, 2, 0),
            AttackDirective("attack.red.blue.2", "red", ("blue-2",), 10, 4, 2, 0),
        ),
    )
    return StrategyProposalContext(
        scenario, baseline, "Explore supported target and fire controls.",
        (
            "/attacks/0/target_ids/0",
            "/attacks/1/target_ids/0",
            "/attacks/0/fire_quantity",
            "/attacks/0/delay_seconds",
        ),
        ("target_assignment", "fire_quantity", "attack_timing"), "runtime", "1.0.0",
        BootstrapSkillSnapshot(
            "bootstrap", "1", "bootstrap", "human-authored", "none",
            ("StrategyProposalAgent",), "bootstrap.md", "rules", "bootstrap-checksum",
        ),
    )

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
            catalog_paths=(
                "/attacks/0/target_ids/0",
                "/attacks/1/target_ids/0",
                "/attacks/0/fire_quantity",
            ),
        )

    assert raised.value.code == "candidate_intent_dimension_missing"
    assert raised.value.required_dimensions == ("minimum_distinct_dimensions=2",)
    assert raised.value.actual_dimensions == ("target_assignment",)


def test_conservative_intent_must_change_exactly_one_leaf() -> None:
    intent = CandidateIntent(
        "candidate_03", "conservative", "Limit exposure.",
        ("attack_timing",), 1, 1,
    )

    CandidateIntentConformanceValidator().validate(
        intent=intent,
        changed_paths=("/attacks/0/delay_seconds",),
        catalog_paths=("/attacks/0/delay_seconds",),
    )


@pytest.mark.parametrize(
    "paths",
    (
        ("/attacks/0/target_ids/0", "/attacks/0/fire_quantity"),
        ("/attacks/0/target_ids/0", "/attacks/0/delay_seconds"),
        ("/attacks/0/fire_quantity", "/attacks/0/reserve_quantity"),
    ),
)
def test_explore_intent_accepts_any_two_dimensions_with_a_preferred_hit(paths: tuple[str, ...]) -> None:
    intent = CandidateIntent(
        "candidate_02", "explore", "Explore safely.",
        ("target_assignment", "fire_quantity"), 2, 3,
    )
    CandidateIntentConformanceValidator().validate(
        intent=intent,
        changed_paths=paths,
        catalog_paths=(
            "/attacks/0/target_ids/0", "/attacks/0/fire_quantity",
            "/attacks/0/delay_seconds", "/attacks/0/reserve_quantity",
        ),
    )


def test_explore_intent_rejects_no_preferred_dimension_and_forbidden_path() -> None:
    intent = CandidateIntent(
        "candidate_02", "explore", "Explore safely.",
        ("target_assignment", "fire_quantity"), 2, 3,
    )
    validator = CandidateIntentConformanceValidator()
    with pytest.raises(CandidateIntentConformanceError) as no_preferred:
        validator.validate(
            intent=intent,
            changed_paths=("/attacks/0/delay_seconds", "/attacks/0/reserve_quantity"),
            catalog_paths=("/attacks/0/delay_seconds", "/attacks/0/reserve_quantity"),
        )
    assert no_preferred.value.code == "candidate_intent_dimension_missing"
    with pytest.raises(CandidateIntentConformanceError) as forbidden:
        validator.validate(
            intent=intent,
            changed_paths=("/attacks/0/target_ids/0", "/scenario_id"),
            catalog_paths=("/attacks/0/target_ids/0",),
        )
    assert forbidden.value.code == "candidate_intent_path_not_cataloged"


def test_explore_repair_adds_second_dimension_without_regenerating_other_candidates() -> None:
    class RepairClient:
        def __init__(self) -> None:
            self.calls = 0

        def complete_json(self, **_kwargs: object) -> object:
            self.calls += 1
            if self.calls == 1:
                return {
                    "proposal_summary": "Only retarget.",
                    "changes": [
                        {"path": "/attacks/0/target_ids/0", "value": "blue-2"},
                        {"path": "/attacks/1/target_ids/0", "value": "blue-1"},
                    ],
                }
            return {
                "proposal_summary": "Retarget and adjust fire volume.",
                "changes": [
                    {"path": "/attacks/0/target_ids/0", "value": "blue-3"},
                    {"path": "/attacks/0/fire_quantity", "value": 5},
                ],
            }

    client = RepairClient()
    agent = StrategyProposalAgent(client)
    candidate = agent.generate_candidate(
        _explore_context(),
        intent=CandidateIntent(
            "candidate_02", "explore", "Cover distinct targets.",
            ("target_assignment", "fire_quantity"), 2, 3,
        ),
        accepted=(),
    )

    assert client.calls == 2
    assert agent.last_usage.intent_calls == 0
    assert agent.last_usage.patch_calls == 1
    assert agent.last_usage.repair_calls == 1
    assert candidate.intended_difference == (
        "/attacks/0/fire_quantity", "/attacks/0/target_ids/0",
    )
