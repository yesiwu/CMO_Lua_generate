from __future__ import annotations

from cmo_lua_agent.contract.strategy_models import (
    AttackDirective,
    ScenarioDefinition,
    ScenarioUnit,
    StrategySpec,
    WeaponInventory,
)
from cmo_lua_agent.optimization.phase6_models import BootstrapSkillSnapshot, StrategyProposalContext
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
