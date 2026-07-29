from __future__ import annotations

import json
from pathlib import Path

from cmo_lua_agent.generation.derived_baseline_golden import DerivedBaselineGoldenService


PROJECT_ROOT = Path(__file__).parents[4]


def test_scenario_ir_derived_baseline_golden_is_deterministic_and_uses_auto_weapons(tmp_path: Path) -> None:
    service = DerivedBaselineGoldenService(project_root=PROJECT_ROOT)

    first = service.build()
    second = service.build()
    service.write(first, output_dir=tmp_path / "generated")

    assert len(first.strategy.attacks) == 5
    assert len(first.strategy.sorties) == 2
    assert [(attack.shooter_id, attack.target_ids[0], attack.fire_quantity, attack.delay_seconds) for attack in first.strategy.attacks] == [
        ("red_055_nanchang", "blue_ddg113_1", 8, 30),
        ("red_052d_1", "blue_cg59", 8, 30),
        ("red_052d_2", "blue_cg59", 5, 33),
        ("red_j15_1", "blue_cvn70", 4, 0),
        ("red_j15_2", "blue_ddg113_2", 4, 0),
    ]
    assert [(sortie.aircraft_id, sortie.target_id, sortie.fire_delay_seconds, sortie.return_delay_seconds,
             [(point.latitude, point.longitude) for point in sortie.route]) for sortie in first.strategy.sorties] == [
        ("red_j15_1", "blue_cvn70", 30, 600, [(23.6, 129.98), (22.3, 129.95)]),
        ("red_j15_2", "blue_ddg113_2", 30, 600, [(23.65, 130.1), (22.45, 130.18)]),
    ]
    assert all(attack.weapon_selection == "auto" and attack.weapon_dbid is None for attack in first.strategy.attacks)
    assert first.plan.checksum == second.plan.checksum
    assert first.strategy_checksum == second.strategy_checksum
    assert first.rendered.lua_checksum == second.rendered.lua_checksum
    plan_attacks = [
        operation for operation in first.plan.operations
        if operation.primitive_type in {"schedule_ship_attack", "aircraft_attack"}
    ]
    assert len(plan_attacks) == 5
    assert all(
        operation.parameters.get("weapon_selection") == "auto"
        and operation.parameters.get("weapon_dbid") is None
        for operation in plan_attacks
    )
    assert "nil,4" in first.rendered.content
    assert "weapon=tonumber(weapon_dbid)" not in first.rendered.content
    assert "if weapon_dbid ~= nil then opts.weapon = tonumber(weapon_dbid) end" in first.rendered.content
    assert first.derivation_manifest["defaulted_fields"]
    assert first.generation_manifest["score_spec_checksum"]
    assert first.generation_manifest["native_score_fragment_checksum"]
    assert json.loads((tmp_path / "generated" / "derived-baseline-strategy.json").read_text(encoding="utf-8"))["scenario_id"] == "red_blue_6v4_liaoning"
    assert (tmp_path / "generated" / "baseline.lua").is_file()
