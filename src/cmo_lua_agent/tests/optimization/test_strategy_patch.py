from __future__ import annotations

import pytest

from cmo_lua_agent.contract.strategy_models import AttackDirective, ScenarioDefinition, ScenarioUnit, StrategySpec, WeaponInventory
from cmo_lua_agent.optimization.proposal_models import CandidatePatch, ProposalContractError, StrategyPatchOperation
from cmo_lua_agent.optimization.strategy_patch import StrategyPatchAssembler, build_patchable_leaf_catalog


def _scenario() -> ScenarioDefinition:
    return ScenarioDefinition("s", (
        ScenarioUnit("red", "red", "Red", "ship", 1, weapon_inventory=(WeaponInventory(7, "W", 8),)),
        ScenarioUnit("blue_a", "blue", "Blue A", "ship", 2),
        ScenarioUnit("blue_b", "blue", "Blue B", "ship", 3),
    ))


def _baseline() -> StrategySpec:
    return StrategySpec("s", (AttackDirective("attack.red", "red", ("blue_a",), 7, 4, 0, 1),))


def _assembler() -> StrategyPatchAssembler:
    baseline = _baseline()
    catalog = build_patchable_leaf_catalog(
        baseline=baseline,
        scenario=_scenario(),
        allowed_paths=(
            "/attacks/0/target_ids/0",
            "/attacks/0/fire_quantity",
            "/attacks/0/delay_seconds",
        ),
    )
    return StrategyPatchAssembler(baseline=baseline, catalog=catalog)


def test_assembler_applies_only_catalogued_scalar_paths_and_reports_actual_diff() -> None:
    result = _assembler().assemble(CandidatePatch(
        "candidate_00", "Retarget and reduce volume.", (
            StrategyPatchOperation("/attacks/0/target_ids/0", "blue_b"),
            StrategyPatchOperation("/attacks/0/fire_quantity", 3),
        ),
    ))
    assert result.strategy.attacks[0].target_ids == ("blue_b",)
    assert result.changed_paths == ("/attacks/0/fire_quantity", "/attacks/0/target_ids/0")


@pytest.mark.parametrize("operation, code", [
    (StrategyPatchOperation("/attacks/0/attack_id", "renamed"), "path_not_catalogued"),
    (StrategyPatchOperation("/attacks/0/fire_quantity", "five"), "scalar_type_mismatch"),
    (StrategyPatchOperation("/attacks/0/fire_quantity", 4), "no_effective_change"),
])
def test_assembler_rejects_stable_fields_wrong_types_and_noops(operation: StrategyPatchOperation, code: str) -> None:
    with pytest.raises(ProposalContractError) as raised:
        _assembler().assemble(CandidatePatch("candidate_00", "x", (operation,)))
    assert raised.value.code == code


def test_assembler_rejects_duplicate_patch_paths() -> None:
    with pytest.raises(ProposalContractError) as raised:
        CandidatePatch("candidate_00", "x", (
            StrategyPatchOperation("/attacks/0/fire_quantity", 3),
            StrategyPatchOperation("/attacks/0/fire_quantity", 2),
        ))
    assert raised.value.code == "duplicate_patch_path"
