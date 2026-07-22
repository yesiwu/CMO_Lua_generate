from __future__ import annotations

from pathlib import Path

from cmo_lua_agent.contract import (
    BaselineStrategy,
    StrategySpec,
    diff_initial_hint_against_baseline,
    load_baseline_strategy,
)


PROJECT_ROOT = Path(__file__).parents[4]
BASELINE_PATH = PROJECT_ROOT / "baseline" / "6v4" / "baseline_strategy.json"


def test_verified_baseline_wraps_one_strategy_spec() -> None:
    baseline = load_baseline_strategy(BASELINE_PATH)

    assert isinstance(baseline, BaselineStrategy)
    assert isinstance(baseline.strategy, StrategySpec)
    assert baseline.scenario_id == "red_blue_6v4_liaoning"
    assert baseline.verified is True
    assert baseline.source_lua == "json_data/6v4.lua"
    assert len(baseline.strategy.attacks) == 5
    assert len(baseline.strategy.sorties) == 2


def test_difference_report_is_deterministic_and_identifies_changed_fields() -> None:
    baseline = load_baseline_strategy(BASELINE_PATH)
    initial_hint = baseline.strategy.with_attack_quantity(
        attack_id="ship-055-ddg113-1",
        fire_quantity=7,
    )

    report = diff_initial_hint_against_baseline(
        initial_hint=initial_hint,
        baseline=baseline,
    )

    assert report.scenario_id == "red_blue_6v4_liaoning"
    assert report.to_dict()["differences"] == [
        {
            "baseline_value": 8,
            "initial_hint_value": 7,
            "path": "strategy.attacks[ship-055-ddg113-1].fire_quantity",
        }
    ]
