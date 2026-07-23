from __future__ import annotations

from cmo_lua_agent.generation.capability_validator import CapabilityValidator
from cmo_lua_agent.generation.runtime_models import (
    ExecutionPlan,
    LuaRuntimeProfile,
    Operation,
)
from cmo_lua_agent.generation.runtime_primitives import (
    default_runtime_primitive_registry,
)


def _plan(*operations: Operation, runtime_version: str = "1.0.0") -> ExecutionPlan:
    return ExecutionPlan(
        plan_schema_version="1.0.0",
        compiler_version="1.0.0",
        scenario_id="golden",
        runtime_id="cmo_naval_air_anti_surface",
        runtime_version=runtime_version,
        operations=operations,
    )


def test_validator_accepts_registered_primitives_with_valid_dependencies() -> None:
    plan = _plan(
        Operation("setup.sides", "ensure_sides", {"side_ids": ["red", "blue"]}, (), "/scenario_definition"),
        Operation(
            "unit.red_ship",
            "ensure_ship",
            {"unit_id": "red_ship", "side_id": "red", "name": "Red Ship", "dbid": 1},
            ("setup.sides",),
            "/scenario_definition/units/0",
        ),
    )

    result = CapabilityValidator(default_runtime_primitive_registry()).validate(
        plan=plan,
        runtime=LuaRuntimeProfile("cmo_naval_air_anti_surface", "1.0.0"),
    )

    assert result.is_valid
    assert result.issues == ()


def test_validator_rejects_unknown_primitive() -> None:
    plan = _plan(
        Operation("unknown", "free_lua", {}, (), "/strategy"),
    )

    result = CapabilityValidator(default_runtime_primitive_registry()).validate(
        plan=plan,
        runtime=LuaRuntimeProfile("cmo_naval_air_anti_surface", "1.0.0"),
    )

    assert not result.is_valid
    assert result.issues[0].code == "unknown_primitive"


def test_validator_rejects_missing_dependency_and_cycles() -> None:
    registry = default_runtime_primitive_registry()
    runtime = LuaRuntimeProfile("cmo_naval_air_anti_surface", "1.0.0")
    missing = CapabilityValidator(registry).validate(
        plan=_plan(
            Operation(
                "attack",
                "schedule_ship_attack",
                {
                    "attack_id": "a",
                    "shooter_id": "red_ship",
                    "target_ids": ["blue_ship"],
                    "weapon_dbid": 2868,
                    "fire_quantity": 1,
                },
                ("missing",),
                "/strategy/attacks/0",
            ),
        ),
        runtime=runtime,
    )
    cyclic = CapabilityValidator(registry).validate(
        plan=_plan(
            Operation("a", "ensure_sides", {"side_ids": ["red"]}, ("b",), "/scenario_definition"),
            Operation("b", "ensure_sides", {"side_ids": ["blue"]}, ("a",), "/scenario_definition"),
        ),
        runtime=runtime,
    )

    assert missing.issues[0].code == "missing_dependency"
    assert cyclic.issues[0].code == "cyclic_dependency"


def test_validator_rejects_runtime_version_and_invalid_parameters() -> None:
    registry = default_runtime_primitive_registry()
    runtime = LuaRuntimeProfile("cmo_naval_air_anti_surface", "1.0.0")

    version_result = CapabilityValidator(registry).validate(
        plan=_plan(
            Operation("setup.sides", "ensure_sides", {"side_ids": ["red"]}, (), "/scenario_definition"),
            runtime_version="9.9.9",
        ),
        runtime=runtime,
    )
    parameter_result = CapabilityValidator(registry).validate(
        plan=_plan(
            Operation("setup.sides", "ensure_sides", {"side_ids": []}, (), "/scenario_definition"),
        ),
        runtime=runtime,
    )

    assert version_result.issues[0].code == "runtime_version_mismatch"
    assert parameter_result.issues[0].code == "invalid_parameters"
