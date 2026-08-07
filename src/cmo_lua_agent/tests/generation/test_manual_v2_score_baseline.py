from pathlib import Path


def test_manual_template_keeps_native_destroyed_unit_score_rules() -> None:
    source = Path("baseline/6v4/manual-template/manual_baseline_template.lua")
    lua = source.read_text(encoding="utf-8")

    assert "local SCORE_RULES =" in lua
    assert "type='Points', name=action_name" in lua
    assert "type='UnitDestroyed'" in lua
    assert "function baseline_v2_score_poll()" not in lua
    assert "pcall(ScenEdit_SetScore, SIDE_RED, current + delta" not in lua
