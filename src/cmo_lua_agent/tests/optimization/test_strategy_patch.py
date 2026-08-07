from __future__ import annotations

import json
from pathlib import Path

import pytest

from cmo_lua_agent.contract.baseline_strategy_builder import BaselineStrategyBuilder
from cmo_lua_agent.contract.strategy_models import AttackDirective, ScenarioDefinition, ScenarioUnit, StrategySpec, WeaponInventory, strategy_spec_from_dict
from cmo_lua_agent.generation.execution_plan_compiler import ExecutionPlanCompiler
from cmo_lua_agent.generation.runtime_models import LuaRuntimeProfile
from cmo_lua_agent.optimization.candidate_set_validator import CandidateSetValidator
from cmo_lua_agent.optimization.phase6_models import StrategyCandidate
from cmo_lua_agent.optimization.phase6_models import BootstrapSkillSnapshot, StrategyProposalContext
from cmo_lua_agent.optimization.proposal_models import CandidateIntent, CandidatePatch, CandidateProposalError, ProposalContractError, StrategyPatchOperation
from cmo_lua_agent.optimization.strategy_proposal_agent import StrategyProposalAgent
from cmo_lua_agent.optimization.strategy_patch import StrategyPatchAssembler, build_patchable_leaf_catalog
from cmo_lua_agent.optimization.candidate_patch_generator import _repair_alternatives


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


def test_assembler_noop_diagnostic_exposes_baseline_and_proposed_values() -> None:
    with pytest.raises(ProposalContractError) as raised:
        _assembler().assemble(CandidatePatch("candidate_00", "x", (
            StrategyPatchOperation("/attacks/0/fire_quantity", 4),
        )))

    assert raised.value.code == "no_effective_change"
    assert raised.value.diagnostics == {
        "path": "/attacks/0/fire_quantity",
        "baseline_value": 4,
        "proposed_value": 4,
        "no_effective_changes": [
            {
                "path": "/attacks/0/fire_quantity",
                "baseline_value": 4,
                "proposed_value": 4,
            }
        ],
    }


def test_assembler_reports_all_noop_changes_for_one_repair() -> None:
    with pytest.raises(ProposalContractError) as raised:
        _assembler().assemble(CandidatePatch("candidate_00", "x", (
            StrategyPatchOperation("/attacks/0/fire_quantity", 4),
            StrategyPatchOperation("/attacks/0/delay_seconds", 0),
        )))

    assert raised.value.code == "no_effective_change"
    assert raised.value.diagnostics["no_effective_changes"] == [
        {
            "path": "/attacks/0/fire_quantity",
            "baseline_value": 4,
            "proposed_value": 4,
        },
        {
            "path": "/attacks/0/delay_seconds",
            "baseline_value": 0,
            "proposed_value": 0,
        },
    ]
    assert _repair_alternatives(_assembler().catalog, raised.value) == [
        {
            "path": "/attacks/0/fire_quantity",
            "baseline_value": 4,
            "allowed_alternatives": [3, 5],
        },
        {
            "path": "/attacks/0/delay_seconds",
            "baseline_value": 0,
            "allowed_alternatives": [1, 86400],
        },
    ]


def test_assembler_rejects_duplicate_patch_paths() -> None:
    with pytest.raises(ProposalContractError) as raised:
        CandidatePatch("candidate_00", "x", (
            StrategyPatchOperation("/attacks/0/fire_quantity", 3),
            StrategyPatchOperation("/attacks/0/fire_quantity", 2),
        ))
    assert raised.value.code == "duplicate_patch_path"


def test_fire_quantity_catalog_reserves_existing_ammunition_before_strategy_validation() -> None:
    baseline = StrategySpec("s", (
        AttackDirective("attack.red", "red", ("blue_a",), 7, 3, 1, 5),
    ))
    catalog = build_patchable_leaf_catalog(
        baseline=baseline,
        scenario=_scenario(),
        allowed_paths=("/attacks/0/fire_quantity",),
    )

    assert catalog[0].maximum == 3


def test_repair_patch_cannot_exceed_available_inventory_after_reserve() -> None:
    baseline = StrategySpec("s", (
        AttackDirective("attack.red", "red", ("blue_a",), 7, 3, 1, 5),
    ))
    catalog = build_patchable_leaf_catalog(
        baseline=baseline,
        scenario=_scenario(),
        allowed_paths=("/attacks/0/fire_quantity",),
    )
    assembler = StrategyPatchAssembler(baseline=baseline, catalog=catalog)

    with pytest.raises(ProposalContractError) as raised:
        assembler.assemble(CandidatePatch("candidate_02", "Increase fire volume.", (
            StrategyPatchOperation("/attacks/0/fire_quantity", 4),
        )))

    assert raised.value.code == "value_above_maximum"


def _derived_sortie_context() -> tuple[ScenarioDefinition, StrategySpec]:
    root = Path(__file__).resolve().parents[4]
    scenario_ir = json.loads(
        (root / "json_data" / "6v4ScenarioIR.json").read_text(encoding="utf-8")
    )
    derived = BaselineStrategyBuilder().build(scenario_ir)
    return derived.scenario, derived.strategy


def test_fire_delay_is_hidden_from_catalog_and_rejected_before_assembly() -> None:
    scenario, baseline = _derived_sortie_context()
    fire_delay_path = "/sorties/0/fire_delay_seconds"
    route_path = "/sorties/0/route/0/latitude"
    catalog = build_patchable_leaf_catalog(
        baseline=baseline,
        scenario=scenario,
        allowed_paths=(fire_delay_path, route_path),
    )

    assert [leaf.path for leaf in catalog] == [route_path]

    assembler = StrategyPatchAssembler(baseline=baseline, catalog=catalog)
    with pytest.raises(ProposalContractError) as raised:
        assembler.assemble(
            CandidatePatch(
                "candidate_03",
                "Delay the aircraft launch.",
                (StrategyPatchOperation(fire_delay_path, 45),),
            )
        )

    assert raised.value.code == "patch_path_not_executable"
    assert raised.value.diagnostics == {
        "candidate_id": "candidate_03",
        "path": fire_delay_path,
        "strategy_field": "fire_delay_seconds",
        "reason": "not_preserved_by_execution_plan",
        "supported_alternatives": [
            "/sorties/0/route/0/latitude",
            "/sorties/0/route/0/longitude",
        ],
    }


def test_baseline_fire_delay_remains_valid_while_route_is_executable() -> None:
    scenario, baseline = _derived_sortie_context()
    assert baseline.sorties[0].fire_delay_seconds == 30
    assert ExecutionPlanCompiler().compile(
        scenario=scenario,
        strategy=baseline,
        runtime=LuaRuntimeProfile("cmo_naval_air_anti_surface_scored", "2.0.0"),
    ).plan is not None


def test_fake_proposal_cannot_repair_a_hand_forged_fire_delay_patch() -> None:
    scenario, baseline = _derived_sortie_context()
    fire_delay_path = "/sorties/0/fire_delay_seconds"
    route_path = "/sorties/0/route/0/latitude"

    class ForgedPatchClient:
        calls = 0
        prompt: dict[str, object] | None = None

        def complete_json(self, *, prompt: str, **_: object) -> object:
            self.calls += 1
            self.prompt = json.loads(prompt)
            return {
                "proposal_summary": "Delay the aircraft launch.",
                "changes": [{"path": fire_delay_path, "value": 45}],
            }

    client = ForgedPatchClient()
    context = StrategyProposalContext(
        scenario,
        baseline,
        "Adjust only executable aircraft behavior.",
        (fire_delay_path, route_path),
        ("air_route",),
        "runtime",
        "2.0.0",
        BootstrapSkillSnapshot(
            "bootstrap", "1", "bootstrap", "human-authored", "none",
            ("StrategyProposalAgent",), "bootstrap.md", "rules", "checksum",
        ),
    )
    agent = StrategyProposalAgent(client)
    intent = CandidateIntent(
        "candidate_03", "conservative", "Use a route adjustment.",
        ("air_route",), 1, 1,
    )

    with pytest.raises(CandidateProposalError) as raised:
        agent.generate_candidate(context, intent=intent, accepted=())

    assert raised.value.code == "patch_path_not_executable"
    assert raised.value.stage == "patch_generation"
    assert client.calls == 1
    assert agent.last_usage.repair_calls == 0
    assert client.prompt is not None
    assert "different from its current_value" in client.prompt["candidate_instruction"]  # type: ignore[index]
    paths = {
        item["path"] for item in client.prompt["patchable_leaves"]  # type: ignore[index]
    }
    assert fire_delay_path not in paths
    assert route_path in paths


def test_candidate_set_does_not_count_a_non_executable_fire_delay_change() -> None:
    scenario, baseline = _derived_sortie_context()
    payload = baseline.to_dict()
    payload["sorties"][0]["fire_delay_seconds"] = 45
    changed = strategy_spec_from_dict(payload)
    candidates = tuple(
        StrategyCandidate(
            f"candidate_{index:02d}",
            changed if index == 0 else baseline,
            "fixture",
            (),
        )
        for index in range(4)
    )

    result = CandidateSetValidator().validate(
        scenario=scenario,
        baseline=baseline,
        candidates=candidates,
        allowed_paths=("/sorties/0/fire_delay_seconds",),
        diversity_dimensions=("attack_timing",),
    )

    assert "candidate_00:patch_path_not_executable" in result.diversity_report.violations
    assert result.diversity_report.candidate_diffs["candidate_00"] == ()
    assert "attack_timing" not in result.diversity_report.dimensions_covered
