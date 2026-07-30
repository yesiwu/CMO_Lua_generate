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


def test_explore_intent_dimension_preference_does_not_block_hard_valid_patch() -> None:
    intent = CandidateIntent(
        "candidate_02", "explore", "Cover separate targets.",
        ("target_assignment", "fire_quantity"), 2, 3,
    )

    report = CandidateIntentConformanceValidator().validate(
        intent=intent,
        changed_paths=("/attacks/0/target_ids/0", "/attacks/1/target_ids/0"),
        catalog_paths=(
            "/attacks/0/target_ids/0", "/attacks/1/target_ids/0",
            "/attacks/0/fire_quantity",
        ),
    )
    assert report.role_adherence == "partial"


def test_explicit_required_dimension_remains_a_hard_gate() -> None:
    intent = CandidateIntent(
        "candidate_00", "exploit", "Use timing.",
        ("target_assignment", "attack_timing"), 3, 5,
        required_dimensions=("attack_timing",),
    )
    with pytest.raises(CandidateIntentConformanceError) as raised:
        CandidateIntentConformanceValidator().validate(
            intent=intent,
            changed_paths=("/attacks/0/target_ids/0",),
            catalog_paths=("/attacks/0/target_ids/0",),
        )
    assert raised.value.code == "candidate_intent_required_dimension_missing"


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


def test_intent_preferred_dimensions_do_not_become_a_hard_requirement() -> None:
    intent = CandidateIntent(
        "candidate_02", "explore", "Explore safely.",
        ("target_assignment", "fire_quantity"), 2, 3,
    )
    validator = CandidateIntentConformanceValidator()

    validator.validate(
        intent=intent,
        changed_paths=("/attacks/0/delay_seconds", "/attacks/0/reserve_quantity"),
        catalog_paths=("/attacks/0/delay_seconds", "/attacks/0/reserve_quantity"),
    )
    with pytest.raises(CandidateIntentConformanceError) as forbidden:
        validator.validate(
            intent=intent,
            changed_paths=("/attacks/0/target_ids/0", "/scenario_id"),
            catalog_paths=("/attacks/0/target_ids/0",),
        )
    assert forbidden.value.code == "candidate_intent_path_not_cataloged"


def _conformance_repair_context() -> StrategyProposalContext:
    scenario = ScenarioDefinition(
        "proposal-conformance-repair",
        (
            ScenarioUnit("red", "red", "Red", "ship", 1, weapon_inventory=(WeaponInventory(10, "W", 40),)),
            ScenarioUnit("blue-1", "blue", "Blue 1", "ship", 2),
            ScenarioUnit("blue-2", "blue", "Blue 2", "ship", 3),
            ScenarioUnit("blue-3", "blue", "Blue 3", "ship", 4),
            ScenarioUnit("blue-4", "blue", "Blue 4", "ship", 5),
        ),
    )
    baseline = StrategySpec(
        "proposal-conformance-repair",
        (
            AttackDirective("attack.red.blue.1", "red", ("blue-1",), 10, 4, 2, 0),
            AttackDirective("attack.red.blue.2", "red", ("blue-2",), 10, 4, 2, 0),
            AttackDirective("attack.red.blue.3", "red", ("blue-3",), 10, 4, 2, 0),
            AttackDirective("attack.red.blue.4", "red", ("blue-4",), 10, 4, 2, 0),
        ),
    )
    return StrategyProposalContext(
        scenario, baseline, "Repair a bounded candidate patch.",
        (
            "/attacks/0/target_ids/0", "/attacks/1/target_ids/0",
            "/attacks/2/target_ids/0", "/attacks/3/target_ids/0",
            "/attacks/0/delay_seconds", "/attacks/0/fire_quantity",
            "/attacks/1/delay_seconds",
        ),
        ("target_assignment", "attack_timing"), "runtime", "1.0.0",
        BootstrapSkillSnapshot(
            "bootstrap", "1", "bootstrap", "human-authored", "none",
            ("StrategyProposalAgent",), "bootstrap.md", "rules", "bootstrap-checksum",
        ),
    )


class _ConformanceRepairClient:
    def __init__(
        self,
        repair_changes: list[dict[str, object]],
        initial_changes: list[dict[str, object]] | None = None,
    ) -> None:
        self.calls = 0
        self.prompts: list[dict[str, object]] = []
        self._repair_changes = repair_changes
        self._initial_changes = initial_changes or [
            {"path": "/attacks/0/target_ids/0", "value": "blue-2"},
            {"path": "/attacks/1/target_ids/0", "value": "blue-3"},
            {"path": "/attacks/2/target_ids/0", "value": "blue-4"},
            {"path": "/attacks/3/target_ids/0", "value": "blue-1"},
        ]

    def complete_json(self, *, prompt: str, **_kwargs: object) -> object:
        self.prompts.append(__import__("json").loads(prompt))
        self.calls += 1
        if self.calls == 1:
            return {
                "proposal_summary": "Retarget four attacks.",
                "changes": self._initial_changes,
            }
        return {"proposal_summary": "Retarget and stagger.", "changes": self._repair_changes}


def _candidate_01_intent() -> CandidateIntent:
    return CandidateIntent(
        "candidate_01", "robust_repair", "Bounded repair.",
        ("target_assignment", "attack_timing", "fire_quantity"), 3, 5,
        min_operations=2, min_dimensions=2,
    )


def test_conformance_repair_preserves_complete_initial_patch_and_needs_only_two_dimensions() -> None:
    client = _ConformanceRepairClient([
        {"path": "/attacks/0/target_ids/0", "value": "blue-2"},
        {"path": "/attacks/1/target_ids/0", "value": "blue-3"},
        {"path": "/attacks/2/target_ids/0", "value": "blue-4"},
        {"path": "/attacks/0/delay_seconds", "value": 9},
    ])
    agent = StrategyProposalAgent(client)

    candidate = agent.generate_candidate(
        _conformance_repair_context(), intent=_candidate_01_intent(), accepted=(),
    )

    assert client.calls == 1
    assert len(candidate.intended_difference) == 4


def test_hard_valid_patch_is_not_rejected_only_for_role_quality() -> None:
    client = _ConformanceRepairClient([
        {"path": "/attacks/0/target_ids/0", "value": "blue-2"},
        {"path": "/attacks/1/target_ids/0", "value": "blue-3"},
        {"path": "/attacks/2/target_ids/0", "value": "blue-4"},
        {"path": "/attacks/3/target_ids/0", "value": "blue-1"},
        {"path": "/attacks/0/delay_seconds", "value": 9},
        {"path": "/attacks/1/delay_seconds", "value": 10},
    ])
    agent = StrategyProposalAgent(client)

    candidate = agent.generate_candidate(
        _conformance_repair_context(), intent=_candidate_01_intent(), accepted=(),
    )
    assert candidate.intended_difference


def test_conservative_partial_quality_does_not_force_repair() -> None:
    client = _ConformanceRepairClient(
        [{"path": "/attacks/0/fire_quantity", "value": 5}],
        initial_changes=[
            {"path": "/attacks/0/fire_quantity", "value": 5},
            {"path": "/attacks/1/delay_seconds", "value": 9},
        ],
    )
    agent = StrategyProposalAgent(client)
    intent = CandidateIntent(
        "candidate_03", "conservative_control", "Bounded conservative change.",
        ("fire_quantity",), 1, 2,
        min_operations=1, min_dimensions=1,
        max_operations=1, max_dimensions=1,
    )

    candidate = agent.generate_candidate(
        _conformance_repair_context(), intent=intent, accepted=(),
    )

    assert candidate.intended_difference == ("/attacks/0/fire_quantity",)
    assert client.calls == 2


def test_explore_partial_quality_is_accepted_without_repair() -> None:
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

    assert client.calls == 1
    assert agent.last_usage.intent_calls == 0
    assert agent.last_usage.patch_calls == 1
    assert agent.last_usage.repair_calls == 0
    assert candidate.intended_difference == (
        "/attacks/0/target_ids/0", "/attacks/1/target_ids/0",
    )
