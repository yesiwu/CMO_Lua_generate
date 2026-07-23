from __future__ import annotations

from pathlib import Path
import hashlib
import json

from cmo_lua_agent.generation.phase2_golden_baseline import (
    Phase2GoldenBaselineService,
)


PROJECT_ROOT = Path(__file__).parents[4]
BASELINE_ROOT = PROJECT_ROOT / "baseline" / "6v4"


def test_phase2_golden_baseline_compiles_validates_and_renders_deterministically() -> None:
    service = Phase2GoldenBaselineService()

    first = service.render(
        scenario_definition_path=BASELINE_ROOT / "scenario_definition.json",
        baseline_strategy_path=BASELINE_ROOT / "baseline_strategy.json",
    )
    second = service.render(
        scenario_definition_path=BASELINE_ROOT / "scenario_definition.json",
        baseline_strategy_path=BASELINE_ROOT / "baseline_strategy.json",
    )

    assert first.validation.is_valid
    assert first.plan.checksum == second.plan.checksum
    assert first.rendered.content == second.rendered.content
    assert first.rendered.lua_checksum == second.rendered.lua_checksum
    assert len(first.plan.operations) >= 30

    primitive_types = {operation.primitive_type for operation in first.plan.operations}
    assert {
        "ensure_sides",
        "configure_side_state",
        "ensure_ship",
        "ensure_aircraft",
        "configure_aircraft",
        "configure_ship_inventory",
        "prepare_target_contact",
        "schedule_ship_attack",
        "request_aircraft_launch",
        "wait_aircraft_airborne",
        "set_aircraft_route",
        "wait_aircraft_attack_range",
        "aircraft_attack",
        "return_aircraft_to_base",
    } <= primitive_types


def test_phase2_golden_generation_manifest_records_audit_checksums() -> None:
    result = Phase2GoldenBaselineService().render(
        scenario_definition_path=BASELINE_ROOT / "scenario_definition.json",
        baseline_strategy_path=BASELINE_ROOT / "baseline_strategy.json",
    )

    manifest = result.generation_manifest

    assert manifest["scenario_id"] == "red_blue_6v4_liaoning"
    assert manifest["scenario_checksum"]
    assert manifest["strategy_checksum"]
    assert manifest["plan_checksum"] == result.plan.checksum
    assert manifest["lua_checksum"] == result.rendered.lua_checksum
    assert "source_map" in manifest


def test_phase2_golden_outputs_match_checked_in_snapshots() -> None:
    result = Phase2GoldenBaselineService().render(
        scenario_definition_path=BASELINE_ROOT / "scenario_definition.json",
        baseline_strategy_path=BASELINE_ROOT / "baseline_strategy.json",
    )

    assert result.rendered.content == (BASELINE_ROOT / "rendered_baseline.lua").read_text(
        encoding="utf-8"
    )
    assert result.plan.to_dict() == json.loads(
        (BASELINE_ROOT / "expected_execution_plan.json").read_text(encoding="utf-8")
    )
    assert result.generation_manifest == json.loads(
        (BASELINE_ROOT / "generation_manifest.json").read_text(encoding="utf-8")
    )


def test_phase2_golden_manifest_records_source_audit_inputs() -> None:
    manifest = json.loads((BASELINE_ROOT / "golden_manifest.json").read_text(encoding="utf-8"))

    assert manifest["scenario_id"] == "red_blue_6v4_liaoning"
    assert manifest["database_version"] == "DB3K_504"
    assert manifest["cmo_version"] in {"unknown", "unavailable"}
    assert manifest["plan_schema_version"] == "1.0.0"
    assert manifest["compiler_version"] == "1.0.0"
    assert manifest["renderer_version"] == "1.0.0"
    assert manifest["runtime_id"] == "cmo_naval_air_anti_surface"
    assert manifest["runtime_version"] == "1.0.0"
    assert manifest["scenario_checksum"]
    assert manifest["strategy_checksum"]
    assert manifest["execution_plan_checksum"]
    assert manifest["lua_checksum"]
    assert manifest["successful_run_id"]
    assert manifest["verification_status"] == "verified"
    assert manifest["input_sources"]["source_lua"] == "json_data/6v4.lua"

    for key, source in manifest["input_sources"].items():
        digest = hashlib.sha256((PROJECT_ROOT / source).read_bytes()).hexdigest()
        assert manifest["input_checksums"][key] == digest
