from pathlib import Path


def test_v2_score_baseline_replaces_v1_destroy_only_section() -> None:
    from cmo_lua_agent.generation.manual_v2_score import build_v2_score_baseline

    source = Path(
        "baseline/6v4/manual-template/reference/"
        "candidate_baseline_fixed.reference.lua"
    )
    lua = build_v2_score_baseline(source.read_text(encoding="utf-8"))

    assert "-- score_spec_version: 2.0.0" in lua
    assert "function baseline_v2_score_poll()" in lua
    assert "damage_threshold_percent" in lua
    assert "ScenEdit_SetKeyValue" in lua
    assert "pcall(ScenEdit_SetScore, SIDE_RED, current + delta" in lua
    assert "local SCORE_RULES =" not in lua
    assert "type='Points', name=action_name" in lua
    assert "PointChange=rule.total" in lua
    assert "-- SCHEDULE ACTIVE ATTACKS" in lua
    assert "baseline_ship_attack_poll" in lua
    assert "baseline_air_launch_poll" in lua
    assert "phase3_collect_final_state()" in lua
    assert "destroyed_unit_poll" in lua
    assert "destroyed_missing_from_wrapper" in lua
    assert "baseline_v2_score_once()" in lua
    assert "baseline_v2_score_poll_" in lua
