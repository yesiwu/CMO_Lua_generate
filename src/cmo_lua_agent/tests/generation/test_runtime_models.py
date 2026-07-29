from __future__ import annotations

import pytest

from cmo_lua_agent.generation.runtime_models import (
    ExecutionPlan,
    GoldenManifest,
    LuaRuntimeProfile,
    Operation,
    canonical_sha256,
)


def test_operation_parameters_are_deeply_immutable_and_detached() -> None:
    source = {"nested": {"items": ["a", {"quantity": 2}]}}

    operation = Operation(
        operation_id="attack.ship.red-055.blue-ddg-113-1",
        primitive_type="schedule_ship_attack",
        parameters=source,
        depends_on=("inventory.red-055",),
        source_strategy_path="/strategy/attacks/0",
    )
    source["nested"]["items"][1]["quantity"] = 99

    assert operation.parameters["nested"]["items"][1]["quantity"] == 2
    with pytest.raises(TypeError):
        operation.parameters["nested"]["items"] = ()
    with pytest.raises(TypeError):
        operation.parameters["nested"]["items"][1]["quantity"] = 3


def test_operation_rejects_non_pointer_source_path() -> None:
    with pytest.raises(ValueError, match="JSON Pointer"):
        Operation(
            operation_id="setup.sides",
            primitive_type="ensure_sides",
            parameters={},
            depends_on=(),
            source_strategy_path="strategy.attacks[0]",
        )


def test_runtime_event_name_is_deterministic_without_scenario_specific_profile_field() -> None:
    runtime = LuaRuntimeProfile(
        runtime_id="cmo_naval_air_anti_surface",
        runtime_version="1.0.0",
    )

    first = runtime.event_name(
        scenario_id="red_blue_6v4_liaoning",
        operation_id="attack.ship.red-055.blue-ddg-113-1",
        phase="fire",
        attempt=1,
    )
    second = runtime.event_name(
        scenario_id="red_blue_6v4_liaoning",
        operation_id="attack.ship.red-055.blue-ddg-113-1",
        phase="fire",
        attempt=1,
    )

    assert first == second
    assert "p2_6v4" not in first
    assert "red_blue_6v4_liaoning" not in first


def test_execution_plan_checksum_is_stable_when_parameter_key_order_differs() -> None:
    first = ExecutionPlan(
        plan_schema_version="1.0.0",
        compiler_version="1.0.0",
        scenario_id="red_blue_6v4_liaoning",
        runtime_id="cmo_naval_air_anti_surface",
        runtime_version="1.0.0",
        operations=(
            Operation(
                operation_id="setup.sides",
                primitive_type="ensure_sides",
                parameters={"red_side": "Red", "blue_side": "Blue"},
                depends_on=(),
                source_strategy_path=None,
            ),
        ),
    )
    second = ExecutionPlan(
        plan_schema_version="1.0.0",
        compiler_version="1.0.0",
        scenario_id="red_blue_6v4_liaoning",
        runtime_id="cmo_naval_air_anti_surface",
        runtime_version="1.0.0",
        operations=(
            Operation(
                operation_id="setup.sides",
                primitive_type="ensure_sides",
                parameters={"blue_side": "Blue", "red_side": "Red"},
                depends_on=(),
                source_strategy_path=None,
            ),
        ),
    )

    assert first.checksum == second.checksum
    assert canonical_sha256(first.to_dict()) == first.checksum


def test_golden_manifest_requires_pinned_input_checksums() -> None:
    with pytest.raises(ValueError, match="checksum"):
        GoldenManifest(
            scenario_id="red_blue_6v4_liaoning",
            scenario_definition_source="baseline/6v4/scenario_definition.json",
            baseline_strategy_source="baseline/6v4/legacy/baseline_strategy.pre-scenario-ir.json",
            source_lua="json_data/6v4.lua",
            cmo_version="CMO-unknown",
            database_version="DB3K_504",
            runtime_id="cmo_naval_air_anti_surface",
            runtime_version="1.0.0",
            successful_run_id="",
            input_checksums={},
        )
