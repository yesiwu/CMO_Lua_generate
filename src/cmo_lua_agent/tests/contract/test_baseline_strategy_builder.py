from __future__ import annotations

import json
from pathlib import Path

import pytest

from cmo_lua_agent.contract.baseline_strategy_builder import (
    BaselineStrategyBuilder,
    BaselineDerivationError,
)
from cmo_lua_agent.contract.strategy_validator import StrategyValidator


PROJECT_ROOT = Path(__file__).parents[4]


def test_builder_derives_the_formal_6v4_baseline_from_scenario_ir() -> None:
    payload = json.loads((PROJECT_ROOT / "json_data" / "6v4ScenarioIR.json").read_text(encoding="utf-8"))

    derived = BaselineStrategyBuilder().build(payload)

    assert derived.scenario.scenario_id == "red_blue_6v4_liaoning"
    assert len(derived.strategy.attacks) == 5
    assert len(derived.strategy.sorties) == 2
    assert all(attack.weapon_selection == "auto" for attack in derived.strategy.attacks)
    assert derived.manifest.defaulted_fields == (
        "missions/red_052d_1_attack_cg59/reserveQuantity",
        "missions/red_052d_2_attack_cg59/reserveQuantity",
        "missions/red_055_attack_ddg113_1/reserveQuantity",
        "missions/red_j15_1_attack_cvn70/reserveQuantity",
        "missions/red_j15_2_attack_ddg113_2/reserveQuantity",
    )
    assert StrategyValidator().validate(derived.strategy, derived.scenario).valid is True


def test_builder_rejects_a_duplicate_mission_id_and_does_not_guess_reserve(tmp_path: Path) -> None:
    payload = {
        "version": "1.0",
        "scenario": {"id": "fixture"},
        "units": [
            {"id": "red_ship", "sideId": "red", "name": "Red", "type": "ship", "dbid": 1},
            {"id": "blue_ship", "sideId": "blue", "name": "Blue", "type": "ship", "dbid": 2},
        ],
        "weapons": [],
        "missions": [
            {"id": "duplicate", "type": "ship_attack", "unitId": "red_ship", "targetId": "blue_ship", "weaponSelection": "auto", "weaponDbid": None, "fireQuantity": 1, "delaySeconds": 0},
            {"id": "duplicate", "type": "ship_attack", "unitId": "red_ship", "targetId": "blue_ship", "weaponSelection": "auto", "weaponDbid": None, "fireQuantity": 1, "delaySeconds": 0},
        ],
    }

    with pytest.raises(BaselineDerivationError, match="baseline_derivation_duplicate_mission_id"):
        BaselineStrategyBuilder().build(payload)
