from __future__ import annotations

from copy import deepcopy

import pytest

from cmo_lua_agent.contract import IRBuilder, ScenarioIR


def _normalized_payload() -> dict:
    return {
        "scenario": {
            "id": "ir-test",
            "name": "IR Test",
        },
        "sides": {
            "red": {
                "name": "Red",
                "unitCount": 2,
                "units": [
                    {
                        "id": "red-carrier",
                        "name": "Red Carrier",
                        "dbid": 100,
                        "type": "CV",
                        "latitude": 20.0,
                        "longitude": 120.0,
                        "heading": 90,
                        "speed": 15,
                        "aircraftCarried": ["red-aircraft"],
                    },
                    {
                        "id": "red-aircraft",
                        "name": "Red Aircraft",
                        "dbid": 101,
                        "type": "Fighter",
                        "base": "red-carrier",
                        "loadoutId": 901,
                        "positionMode": "inherit_base",
                        "weaponLoad": [
                            {
                                "weapon": "Weapon-A",
                                "weaponDbid": 5001,
                                "loaded": 4,
                                "fired": 2,
                                "targets": ["blue-target"],
                            }
                        ],
                    },
                ],
            },
            "blue": {
                "name": "Blue",
                "unitCount": 1,
                "units": [
                    {
                        "id": "blue-target",
                        "name": "Blue Target",
                        "dbid": 200,
                        "type": "DDG",
                        "latitude": 21.0,
                        "longitude": 121.0,
                        "heading": 270,
                        "speed": 10,
                    }
                ],
            },
        },
        "strikePlan": [
            {
                "id": "strike-1",
                "shooters": ["red-aircraft"],
                "weapon": "Weapon-A",
                "weaponDbid": 5001,
                "loadoutId": 901,
                "loaded": 4,
                "fired": 2,
                "targets": ["blue-target"],
            }
        ],
        "missileSummary": {
            "Weapon-A": {"loaded": 4, "fired": 2},
            "totalLoaded": 4,
            "totalFired": 2,
        },
        "notes": ["keep this note"],
        "sourceMetadata": {"owner": "test"},
    }


def test_builder_creates_indexed_deterministic_ir() -> None:
    source = _normalized_payload()

    ir = IRBuilder().build(source)

    assert isinstance(ir, ScenarioIR)
    assert ir.data["irVersion"] == "scenario-ir-v1"
    assert ir.data["scenario"] == source["scenario"]
    assert ir.data["sides"] == {
        "red": {
            "key": "red",
            "name": "Red",
            "unitCount": 2,
            "unitIds": ["red-carrier", "red-aircraft"],
        },
        "blue": {
            "key": "blue",
            "name": "Blue",
            "unitCount": 1,
            "unitIds": ["blue-target"],
        },
    }
    assert list(ir.data["unitById"]) == [
        "red-carrier",
        "red-aircraft",
        "blue-target",
    ]
    assert ir.data["unitById"]["red-aircraft"]["sideKey"] == "red"
    assert "units" not in ir.data["sides"]["red"]
    assert ir.data["strikePlan"][0]["shooters"] == ["red-aircraft"]
    assert "shooter" not in ir.data["strikePlan"][0]
    assert ir.data["missileSummary"] == source["missileSummary"]
    assert ir.data["notes"] == ["keep this note"]
    assert ir.data["sourceMetadata"] == {"owner": "test"}


def test_builder_does_not_mutate_or_share_nested_state() -> None:
    source = _normalized_payload()
    original = deepcopy(source)

    ir = IRBuilder().build(source)
    ir.data["unitById"]["red-carrier"]["name"] = "Changed"
    ir.data["strikePlan"][0]["targets"].append("another-target")

    assert source == original


def test_builder_returns_equal_ir_for_equal_input() -> None:
    first = IRBuilder().build(_normalized_payload())
    second = IRBuilder().build(_normalized_payload())

    assert first.to_dict() == second.to_dict()


def test_builder_rejects_non_mapping_input() -> None:
    with pytest.raises(TypeError, match="normalized"):
        IRBuilder().build([])  # type: ignore[arg-type]


def test_builder_requires_semantically_normalized_shooters() -> None:
    source = _normalized_payload()
    strike = source["strikePlan"][0]
    strike["shooter"] = strike.pop("shooters")[0]

    with pytest.raises(
        ValueError,
        match="strikePlan",
    ):
        IRBuilder().build(source)
