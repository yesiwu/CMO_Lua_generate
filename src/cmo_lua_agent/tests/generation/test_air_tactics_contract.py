from __future__ import annotations

import json
from pathlib import Path

from cmo_lua_agent.contract.baseline_strategy_builder import BaselineStrategyBuilder
from cmo_lua_agent.contract.strategy_models import AirTactics
from cmo_lua_agent.generation.execution_plan_compiler import ExecutionPlanCompiler
from cmo_lua_agent.generation.runtime_models import LuaRuntimeProfile
from cmo_lua_agent.optimization.tactical_capability_registry import TacticalCapabilityRegistry


def test_default_air_tactics_are_preserved_in_air_operations():
    scenario_ir_payload = json.loads(
        (Path(__file__).resolve().parents[4] / "json_data" / "6v4ScenarioIR.json").read_text(encoding="utf-8")
    )
    derived = BaselineStrategyBuilder().build(scenario_ir_payload)
    scenario = derived.scenario
    baseline = derived.strategy
    plan = ExecutionPlanCompiler().compile(
        scenario=scenario,
        strategy=baseline,
        runtime=LuaRuntimeProfile("test", "1.0.0"),
    ).plan
    assert plan is not None
    launch = next(operation for operation in plan.operations if operation.operation_id.startswith("air_launch."))
    attack_range = next(operation for operation in plan.operations if operation.operation_id.startswith("air_range."))
    assert launch.parameters["air_tactics"]["launch_delay_seconds"] == 5
    assert attack_range.parameters["air_tactics"] == {
        "launch_delay_seconds": 5,
        "ingress_altitude_m": 200,
        "popup_altitude_m": 9500,
        "popup_range_nm": 95,
        "attack_range_nm": 80,
    }


def test_registry_exposes_only_bounded_role_specific_air_tactics_paths():
    registry = TacticalCapabilityRegistry.default()
    assert registry.paths_for_role(role="exploit", sortie_count=2) == (
        "/sorties/0/air_tactics/ingress_altitude_m",
        "/sorties/1/air_tactics/ingress_altitude_m",
    )
    attack_range = registry.capability_for_path("/sorties/1/air_tactics/attack_range_nm")
    assert attack_range is not None and (attack_range.minimum, attack_range.maximum) == (30, 140)


def test_air_tactics_rejects_attack_range_at_or_beyond_popup_range():
    try:
        AirTactics(popup_range_nm=95, attack_range_nm=100)
    except ValueError as exc:
        assert str(exc) == "attack_range_nm must be lower than popup_range_nm"
    else:
        raise AssertionError("invalid air tactic ordering must be rejected before Lua rendering")
