from __future__ import annotations

import json
from pathlib import Path

import pytest

from cmo_lua_agent.generation.manual_lua_template import (
    ManualLuaTemplateError,
    ManualLuaTemplatePackage,
)


def _write_package(tmp_path):
    (tmp_path / "manual_baseline_template.lua").write_text(
        "function baseline_fire() return '{{target}}', {{delay_seconds}} end\n",
        encoding="utf-8",
    )
    (tmp_path / "manual_template_baseline.json").write_text(
        json.dumps({"candidate_id": "baseline", "parameters": {"target": "blue_cvn70", "delay_seconds": 30}}),
        encoding="utf-8",
    )
    (tmp_path / "manual_baseline_template.json").write_text(
        json.dumps(
            {
                "template_id": "test_template",
                "template_lua": "manual_baseline_template.lua",
                "baseline_parameters": "manual_template_baseline.json",
                "slots": [
                    {"name": "target", "token": "{{target}}", "type": "lua_string", "allowed_values": ["blue_cvn70", "blue_cg59"]},
                    {"name": "delay_seconds", "token": "{{delay_seconds}}", "type": "number", "minimum": 0, "maximum": 600},
                ],
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


def test_template_renders_only_declared_slots_and_preserves_fixed_logic(tmp_path) -> None:
    package = ManualLuaTemplatePackage.load(_write_package(tmp_path))

    baseline = package.baseline_strategy()
    candidate = baseline.with_parameters(candidate_id="candidate_00", updates={"target": "blue_cg59", "delay_seconds": 45})
    rendered = package.render(candidate)

    assert rendered.content == "function baseline_fire() return 'blue_cg59', 45 end\n"
    assert rendered.changed_slots == ("delay_seconds", "target")
    assert rendered.fixed_logic_checksum == package.fixed_logic_checksum


def test_template_rejects_undeclared_or_invalid_slot_values(tmp_path) -> None:
    package = ManualLuaTemplatePackage.load(_write_package(tmp_path))

    with pytest.raises(ManualLuaTemplateError, match="manual_template_unknown_slot"):
        package.baseline_strategy().with_parameters(candidate_id="candidate_00", updates={"runtime": "unsafe"})
    with pytest.raises(ManualLuaTemplateError, match="manual_template_slot_value_invalid"):
        package.baseline_strategy().with_parameters(candidate_id="candidate_00", updates={"delay_seconds": 601})


def test_template_overlays_only_mapped_formal_strategy_differences(tmp_path) -> None:
    package_root = _write_package(tmp_path)
    config_path = package_root / "manual_baseline_template.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["slots"][0]["strategy_path"] = "/attacks/0/target_ids/0"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    package = ManualLuaTemplatePackage.load(package_root)
    baseline = {"attacks": [{"target_ids": ["blue_cvn70"]}]}
    candidate = {"attacks": [{"target_ids": ["blue_cg59"]}]}

    strategy = package.strategy_overlay(
        candidate_id="candidate_00",
        baseline_strategy=baseline,
        candidate_strategy=candidate,
        changed_paths=("/attacks/0/target_ids/0",),
    )

    assert strategy.parameters["target"] == "blue_cg59"
    with pytest.raises(ManualLuaTemplateError, match="manual_template_strategy_change_unmapped"):
        package.strategy_overlay(
            candidate_id="candidate_00",
            baseline_strategy=baseline,
            candidate_strategy=candidate,
            changed_paths=("/sorties/0/route/0/latitude",),
        )


def test_operator_authored_6v4_template_renders_its_checked_in_baseline_golden() -> None:
    root = Path(__file__).resolve().parents[4] / "baseline" / "6v4" / "manual-template"
    package = ManualLuaTemplatePackage.load(root)

    baseline = package.render(package.baseline_strategy())
    candidate = package.render(
        package.baseline_strategy().with_parameters(
            candidate_id="candidate_00",
            updates={"attack_055_target": "blue_cvn70", "attack_055_delay_seconds": 60},
        )
    )

    assert baseline.content == (root / "candidate_baseline_fixed.lua").read_text(encoding="utf-8")
    assert all(slot.token not in candidate.content for slot in package.slots.values())
    assert "target_id='blue_cvn70', delay_seconds=60" in candidate.content
    assert candidate.changed_slots == ("attack_055_delay_seconds", "attack_055_target", "candidate_id")
