from __future__ import annotations

import json

from cmo_lua_agent.contract import (
    ScenarioDefinitionBuilder,
    ScenarioIR,
)


def _scenario_ir():
    return ScenarioIR(
        data={
            "scenario": {"id": "stable-scenario"},
            "unitById": {
                "red-j15-1": {
                    "sideKey": "red",
                    "name": "Red J-15",
                    "type": "aircraft",
                    "dbid": 2496,
                    "base": "red-carrier",
                    "loadoutId": 9682,
                    "weaponLoad": [
                        {
                            "weapon": "YJ-83K",
                            "weaponDbid": 2137,
                            "loaded": 4,
                            "fired": 3,
                            "targets": ["blue-ship"],
                        }
                    ],
                },
                "blue-ship": {
                    "sideKey": "blue",
                    "name": "Blue ship",
                    "type": "ship",
                    "dbid": 3000,
                    "weaponLoad": [],
                },
            },
            "strikePlan": [
                {
                    "shooters": ["red-j15-1"],
                    "weaponDbid": 2137,
                    "loaded": 4,
                    "fired": 3,
                    "targets": ["blue-ship"],
                    "delaySeconds": 30,
                }
            ],
        }
    )


def test_builder_separates_weapon_inventory_from_initial_strategy() -> None:
    output = ScenarioDefinitionBuilder().build(_scenario_ir())

    definition = output.scenario_definition.to_dict()
    hint = output.initial_strategy_hint.to_dict()
    red_aircraft = next(
        unit
        for unit in definition["units"]
        if unit["unit_id"] == "red-j15-1"
    )

    assert red_aircraft["weapon_inventory"] == [
        {
            "max_quantity": 4,
            "weapon_dbid": 2137,
            "weapon_name": "YJ-83K",
        }
    ]
    assert "targets" not in red_aircraft
    assert "fired" not in red_aircraft
    assert hint["strategy"]["attacks"][0]["target_ids"] == ["blue-ship"]
    assert hint["strategy"]["attacks"][0]["fire_quantity"] == 3


def test_builder_does_not_put_strategy_fields_in_scenario_definition() -> None:
    output = ScenarioDefinitionBuilder().build(_scenario_ir())
    definition = output.scenario_definition.to_dict()

    rendered = json.dumps(definition, ensure_ascii=False, sort_keys=True)

    assert "strikePlan" not in rendered
    assert "target_ids" not in rendered
    assert "fire_quantity" not in rendered
    assert "delay_seconds" not in rendered
    assert "route" not in rendered
