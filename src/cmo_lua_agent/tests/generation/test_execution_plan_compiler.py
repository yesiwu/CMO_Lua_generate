from __future__ import annotations

from cmo_lua_agent.contract.strategy_models import (
    AttackDirective,
    RouteWaypoint,
    ScenarioDefinition,
    ScenarioUnit,
    SortieDirective,
    StrategySpec,
    WeaponInventory,
)
from cmo_lua_agent.generation.execution_plan_compiler import ExecutionPlanCompiler
from cmo_lua_agent.generation.runtime_models import LuaRuntimeProfile


def test_compiler_lowers_ship_attack_into_plan_operations() -> None:
    scenario = ScenarioDefinition(units=(
        ScenarioUnit("red_ship", "red", "Red Ship", "ship", 1, weapon_inventory=(WeaponInventory(2868, "YJ-18", 16),)),
        ScenarioUnit("blue_ship", "blue", "Blue Ship", "ship", 2),
    ), scenario_id="golden")
    strategy = StrategySpec(scenario_id="golden", attacks=(AttackDirective("ship-attack", "red_ship", ("blue_ship",), 2868, 8, 30, 8),))

    result = ExecutionPlanCompiler().compile(
        scenario=scenario, strategy=strategy,
        runtime=LuaRuntimeProfile("cmo_naval_air_anti_surface", "1.0.0"),
    )

    assert result.capability_gaps == ()
    assert [item.primitive_type for item in result.plan.operations] == [
        "ensure_sides",
        "configure_side_state",
        "ensure_ship",
        "ensure_ship",
        "prepare_target_contact",
        "configure_ship_inventory",
        "schedule_ship_attack",
    ]
    attack = result.plan.operations[-1]
    assert attack.source_strategy_path == "/strategy/attacks/0"
    assert attack.depends_on == ("inventory.red_ship", "contact.blue_ship")


def test_compiler_preserves_auto_weapon_selection_in_the_execution_plan() -> None:
    scenario = ScenarioDefinition(units=(
        ScenarioUnit("red_ship", "red", "Red Ship", "ship", 1, weapon_inventory=(WeaponInventory(2868, "YJ-18", 16),)),
        ScenarioUnit("blue_ship", "blue", "Blue Ship", "ship", 2),
    ), scenario_id="golden")
    strategy = StrategySpec(
        scenario_id="golden",
        attacks=(AttackDirective("ship-attack", "red_ship", ("blue_ship",), None, 8, 30, weapon_selection="auto"),),
    )

    result = ExecutionPlanCompiler().compile(
        scenario=scenario, strategy=strategy,
        runtime=LuaRuntimeProfile("cmo_naval_air_anti_surface", "1.0.0"),
    )

    assert result.capability_gaps == ()
    assert result.plan.operations[-1].parameters["weapon_selection"] == "auto"
    assert result.plan.operations[-1].parameters["weapon_dbid"] is None


def test_compiler_returns_gap_for_submarine_attack() -> None:
    scenario = ScenarioDefinition(units=(
        ScenarioUnit("red_sub", "red", "Red Sub", "submarine", 1, weapon_inventory=(WeaponInventory(2868, "YJ-18", 8),)),
        ScenarioUnit("blue_ship", "blue", "Blue Ship", "ship", 2),
    ), scenario_id="golden")
    strategy = StrategySpec(scenario_id="golden", attacks=(AttackDirective("sub-attack", "red_sub", ("blue_ship",), 2868, 4, 30),))

    result = ExecutionPlanCompiler().compile(
        scenario=scenario, strategy=strategy,
        runtime=LuaRuntimeProfile("cmo_naval_air_anti_surface", "1.0.0"),
    )

    assert result.plan is None
    assert result.capability_gaps[0].capability == "submarine_operations"


def test_compiler_lowers_air_sortie_without_runtime_helpers_as_operations() -> None:
    scenario = ScenarioDefinition(
        scenario_id="golden",
        units=(
            ScenarioUnit("red_carrier", "red", "Carrier", "ship", 2007),
            ScenarioUnit(
                "red_j15",
                "red",
                "J-15",
                "aircraft",
                2496,
                loadout_id=9682,
                base_unit_id="red_carrier",
                weapon_inventory=(WeaponInventory(2137, "YJ-83K", 4),),
            ),
            ScenarioUnit("blue_target", "blue", "Target", "ship", 3551),
        ),
    )
    strategy = StrategySpec(
        scenario_id="golden",
        attacks=(
            AttackDirective("air-attack", "red_j15", ("blue_target",), 2137, 4, 0),
        ),
        sorties=(
            SortieDirective(
                sortie_id="j15-sortie",
                aircraft_id="red_j15",
                target_id="blue_target",
                base_unit_id="red_carrier",
                route=(RouteWaypoint(23.6, 129.98), RouteWaypoint(22.3, 129.95)),
                altitude_meters=8000,
                throttle="Cruise",
                fire_delay_seconds=30,
                return_delay_seconds=600,
            ),
        ),
    )

    result = ExecutionPlanCompiler().compile(
        scenario=scenario,
        strategy=strategy,
        runtime=LuaRuntimeProfile("cmo_naval_air_anti_surface", "1.0.0"),
    )

    primitive_types = [item.primitive_type for item in result.plan.operations]
    assert result.capability_gaps == ()
    assert primitive_types[-7:] == [
        "configure_aircraft",
        "request_aircraft_launch",
        "wait_aircraft_airborne",
        "set_aircraft_route",
        "wait_aircraft_attack_range",
        "aircraft_attack",
        "return_aircraft_to_base",
    ]
    assert "lookup_unit" not in primitive_types
    assert "schedule_lua" not in primitive_types
    assert "runtime_log" not in primitive_types

    air_attack = result.plan.operations[-2]
    assert air_attack.depends_on == ("air_range.j15-sortie",)
    assert air_attack.source_strategy_path == "/strategy/attacks/0"
