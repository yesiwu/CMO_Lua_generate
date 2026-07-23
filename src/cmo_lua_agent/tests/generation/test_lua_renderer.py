from __future__ import annotations

from cmo_lua_agent.generation.lua_renderer import LuaRenderer
from cmo_lua_agent.generation.runtime_models import (
    ExecutionPlan,
    LuaRuntimeProfile,
    Operation,
)


def _plan() -> ExecutionPlan:
    return ExecutionPlan(
        plan_schema_version="1.0.0",
        compiler_version="1.0.0",
        scenario_id="red_blue_6v4_liaoning",
        runtime_id="cmo_naval_air_anti_surface",
        runtime_version="1.0.0",
        operations=(
            Operation(
                "setup.sides",
                "ensure_sides",
                {"side_ids": ["red", "blue"]},
                (),
                "/scenario_definition",
            ),
            Operation(
                "unit.red_ship",
                "ensure_ship",
                {
                    "unit_id": "red_ship",
                    "side_id": "red",
                    "name": "Red Ship",
                    "dbid": 3883,
                    "latitude": 24.0,
                    "longitude": 128.0,
                    "heading": 135,
                    "speed": 20,
                },
                ("setup.sides",),
                "/scenario_definition/units/0",
            ),
        ),
    )


def test_renderer_returns_deterministic_lua_metadata_and_source_map() -> None:
    runtime = LuaRuntimeProfile("cmo_naval_air_anti_surface", "1.0.0")
    first = LuaRenderer().render(plan=_plan(), runtime=runtime)
    second = LuaRenderer().render(plan=_plan(), runtime=runtime)

    assert first.content == second.content
    assert first.lua_checksum == second.lua_checksum
    assert first.metadata["plan_schema_version"] == "1.0.0"
    assert first.metadata["renderer_version"] == "1.0.0"
    assert first.metadata["runtime_id"] == "cmo_naval_air_anti_surface"
    assert "setup.sides" in first.source_map
    assert first.source_map["setup.sides"].start_line < first.source_map["setup.sides"].end_line


def test_renderer_keeps_runtime_helpers_inside_lua_not_as_plan_operations() -> None:
    rendered = LuaRenderer().render(
        plan=_plan(),
        runtime=LuaRuntimeProfile("cmo_naval_air_anti_surface", "1.0.0"),
    )

    assert "local function lookup_unit" in rendered.content
    assert "local function schedule_lua" in rendered.content
    assert "local function runtime_log" in rendered.content
    assert "-- BEGIN OP lookup_unit" not in rendered.content
    assert "-- BEGIN OP schedule_lua" not in rendered.content
    assert "-- BEGIN OP runtime_log" not in rendered.content


def test_renderer_event_names_are_deterministic_and_not_time_based() -> None:
    rendered = LuaRenderer().render(
        plan=_plan(),
        runtime=LuaRuntimeProfile("cmo_naval_air_anti_surface", "1.0.0"),
    )

    assert "tostring(ScenEdit_CurrentTime())" not in rendered.content
    assert "p2_6v4" not in rendered.content
    assert "evt_" in rendered.content
