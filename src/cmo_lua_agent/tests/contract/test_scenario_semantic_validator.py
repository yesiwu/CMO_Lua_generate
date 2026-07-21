from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from cmo_lua_agent.contract import (
    ScenarioInput,
    ScenarioSemanticValidator,
)


def _scenario(payload: dict) -> ScenarioInput:
    return ScenarioInput(
        source_path=Path("scenario.json"),
        raw=payload,
    )


def _valid_payload() -> dict:
    return {
        "scenario": {
            "id": "semantic-test",
            "name": "Semantic Test",
        },
        "sides": {
            "red": {
                "name": "Red",
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
                        "latitude": "随母舰",
                        "longitude": "随母舰",
                        "heading": "起飞后设定",
                        "speed": "起飞后设定",
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
                "shooter": "red-aircraft",
                "weapon": "Weapon-A",
                "weaponDbid": 5001,
                "loadoutId": 901,
                "loaded": 4,
                "fired": 2,
                "targets": ["blue-target"],
            }
        ],
        "missileSummary": {
            "Weapon-A": {
                "loaded": 4,
                "fired": 2,
            },
            "totalLoaded": 4,
            "totalFired": 2,
        },
    }


def _issue_pairs(output) -> list[tuple[str, str]]:
    return [
        (issue.code, issue.path)
        for issue in output.validation.issues
    ]


def test_valid_scenario_is_normalized_without_mutating_input() -> None:
    payload = _valid_payload()
    original = deepcopy(payload)

    output = ScenarioSemanticValidator().validate_and_normalize(
        _scenario(payload)
    )

    assert output.validation.valid is True
    assert output.validation.issues == ()
    assert payload == original

    normalized_aircraft = output.normalized["sides"]["red"]["units"][1]
    assert normalized_aircraft["positionMode"] == "inherit_base"
    for field in ("latitude", "longitude", "heading", "speed"):
        assert field not in normalized_aircraft

    strike = output.normalized["strikePlan"][0]
    assert strike["shooters"] == ["red-aircraft"]
    assert "shooter" not in strike


def test_numeric_position_with_base_is_not_converted_to_inherit_base() -> None:
    payload = _valid_payload()
    aircraft = payload["sides"]["red"]["units"][1]
    aircraft.update(
        {
            "latitude": 20.5,
            "longitude": 120.5,
            "heading": 100,
            "speed": 300,
        }
    )

    output = ScenarioSemanticValidator().validate_and_normalize(
        _scenario(payload)
    )

    normalized = output.normalized["sides"]["red"]["units"][1]
    assert "positionMode" not in normalized
    assert normalized["latitude"] == 20.5


def test_duplicate_unit_ids_and_names_are_reported_at_later_occurrence() -> None:
    payload = _valid_payload()
    duplicate = {
        "id": "red-carrier",
        "name": "Red Aircraft",
        "dbid": 201,
        "type": "DDG",
        "latitude": 22.0,
        "longitude": 122.0,
        "heading": 270,
        "speed": 10,
    }
    payload["sides"]["blue"]["units"].append(duplicate)

    output = ScenarioSemanticValidator().validate_and_normalize(
        _scenario(payload)
    )

    assert _issue_pairs(output) == [
        (
            "semantic.duplicate_unit_id",
            "$.sides.blue.units[1].id",
        ),
        (
            "semantic.duplicate_unit_name",
            "$.sides.blue.units[1].name",
        ),
    ]


def test_unknown_and_cross_side_base_references_are_rejected() -> None:
    payload = _valid_payload()
    red_aircraft = payload["sides"]["red"]["units"][1]
    red_aircraft["base"] = "missing-carrier"

    blue_aircraft = {
        "id": "blue-aircraft",
        "name": "Blue Aircraft",
        "dbid": 201,
        "type": "Fighter",
        "base": "red-carrier",
        "loadoutId": 902,
    }
    payload["sides"]["blue"]["units"].append(blue_aircraft)

    output = ScenarioSemanticValidator().validate_and_normalize(
        _scenario(payload)
    )

    assert (
        "semantic.unknown_base",
        "$.sides.red.units[1].base",
    ) in _issue_pairs(output)
    assert (
        "semantic.cross_side_base",
        "$.sides.blue.units[1].base",
    ) in _issue_pairs(output)


def test_aircraft_carried_references_must_exist_on_same_side() -> None:
    payload = _valid_payload()
    carrier = payload["sides"]["red"]["units"][0]
    carrier["aircraftCarried"] = ["missing", "blue-target"]

    output = ScenarioSemanticValidator().validate_and_normalize(
        _scenario(payload)
    )

    assert _issue_pairs(output)[:2] == [
        (
            "semantic.unknown_aircraft",
            "$.sides.red.units[0].aircraftCarried[0]",
        ),
        (
            "semantic.cross_side_aircraft",
            "$.sides.red.units[0].aircraftCarried[1]",
        ),
    ]


def test_unknown_shooter_and_target_are_reported() -> None:
    payload = _valid_payload()
    strike = payload["strikePlan"][0]
    strike["shooter"] = "missing-shooter"
    strike["targets"] = ["missing-target"]

    output = ScenarioSemanticValidator().validate_and_normalize(
        _scenario(payload)
    )

    assert (
        "semantic.unknown_shooter",
        "$.strikePlan[0].shooters[0]",
    ) in _issue_pairs(output)
    assert (
        "semantic.unknown_target",
        "$.strikePlan[0].targets[0]",
    ) in _issue_pairs(output)


def test_friendly_target_is_rejected_for_strike_and_weapon_load() -> None:
    payload = _valid_payload()
    payload["strikePlan"][0]["targets"] = ["red-carrier"]
    payload["sides"]["red"]["units"][1]["weaponLoad"][0][
        "targets"
    ] = ["red-carrier"]

    output = ScenarioSemanticValidator().validate_and_normalize(
        _scenario(payload)
    )

    assert (
        "semantic.friendly_target",
        "$.sides.red.units[1].weaponLoad[0].targets[0]",
    ) in _issue_pairs(output)
    assert (
        "semantic.friendly_target",
        "$.strikePlan[0].targets[0]",
    ) in _issue_pairs(output)


def test_shooters_must_belong_to_one_side() -> None:
    payload = _valid_payload()
    payload["strikePlan"][0].pop("shooter")
    payload["strikePlan"][0]["shooters"] = [
        "red-aircraft",
        "blue-target",
    ]

    output = ScenarioSemanticValidator().validate_and_normalize(
        _scenario(payload)
    )

    assert (
        "semantic.mixed_shooter_sides",
        "$.strikePlan[0].shooters",
    ) in _issue_pairs(output)


def test_fired_cannot_exceed_loaded_in_inventory_or_strike() -> None:
    payload = _valid_payload()
    payload["sides"]["red"]["units"][1]["weaponLoad"][0][
        "fired"
    ] = 5
    payload["strikePlan"][0]["fired"] = 5

    output = ScenarioSemanticValidator().validate_and_normalize(
        _scenario(payload)
    )

    assert (
        "semantic.ammo_exceeded",
        "$.sides.red.units[1].weaponLoad[0].fired",
    ) in _issue_pairs(output)
    assert (
        "semantic.ammo_exceeded",
        "$.strikePlan[0].fired",
    ) in _issue_pairs(output)


def test_strike_cannot_exceed_explicit_matching_shooter_inventory() -> None:
    payload = _valid_payload()
    payload["strikePlan"][0]["loaded"] = 6
    payload["strikePlan"][0]["fired"] = 5
    payload["missileSummary"]["Weapon-A"] = {
        "loaded": 6,
        "fired": 5,
    }
    payload["missileSummary"]["totalLoaded"] = 6
    payload["missileSummary"]["totalFired"] = 5

    output = ScenarioSemanticValidator().validate_and_normalize(
        _scenario(payload)
    )

    assert (
        "semantic.ammo_inventory_exceeded",
        "$.strikePlan[0].loaded",
    ) in _issue_pairs(output)
    assert (
        "semantic.ammo_inventory_exceeded",
        "$.strikePlan[0].fired",
    ) in _issue_pairs(output)


def test_group_strike_uses_sum_of_all_explicit_shooter_inventories() -> None:
    payload = _valid_payload()
    second_aircraft = deepcopy(
        payload["sides"]["red"]["units"][1]
    )
    second_aircraft.update(
        {
            "id": "red-aircraft-2",
            "name": "Red Aircraft 2",
        }
    )
    second_aircraft["weaponLoad"][0]["loaded"] = 3
    second_aircraft["weaponLoad"][0]["fired"] = 3
    payload["sides"]["red"]["units"].append(second_aircraft)
    payload["sides"]["red"]["units"][0]["aircraftCarried"].append(
        "red-aircraft-2"
    )

    strike = payload["strikePlan"][0]
    strike.pop("shooter")
    strike["shooters"] = ["red-aircraft", "red-aircraft-2"]
    strike["loaded"] = 7
    strike["fired"] = 5
    payload["missileSummary"]["Weapon-A"] = {
        "loaded": 7,
        "fired": 5,
    }
    payload["missileSummary"]["totalLoaded"] = 7
    payload["missileSummary"]["totalFired"] = 5

    output = ScenarioSemanticValidator().validate_and_normalize(
        _scenario(payload)
    )

    assert output.validation.valid is True


def test_missing_inventory_for_group_skips_capacity_check() -> None:
    payload = _valid_payload()
    payload["sides"]["red"]["units"][1]["weaponLoad"] = []
    payload["strikePlan"][0]["loaded"] = 100
    payload["strikePlan"][0]["fired"] = 100
    payload["missileSummary"]["Weapon-A"] = {
        "loaded": 100,
        "fired": 100,
    }
    payload["missileSummary"]["totalLoaded"] = 100
    payload["missileSummary"]["totalFired"] = 100

    output = ScenarioSemanticValidator().validate_and_normalize(
        _scenario(payload)
    )

    assert not any(
        issue.code == "semantic.ammo_inventory_exceeded"
        for issue in output.validation.issues
    )


def test_missile_summary_must_match_strike_plan() -> None:
    payload = _valid_payload()
    payload["missileSummary"]["Weapon-A"]["fired"] = 3
    payload["missileSummary"]["totalLoaded"] = 9

    output = ScenarioSemanticValidator().validate_and_normalize(
        _scenario(payload)
    )

    assert (
        "semantic.missile_summary_mismatch",
        "$.missileSummary.Weapon-A.fired",
    ) in _issue_pairs(output)
    assert (
        "semantic.missile_total_mismatch",
        "$.missileSummary.totalLoaded",
    ) in _issue_pairs(output)


def test_issue_order_is_deterministic() -> None:
    payload = _valid_payload()
    payload["sides"]["blue"]["units"][0]["id"] = "red-carrier"
    payload["strikePlan"][0]["targets"] = ["missing-target"]

    validator = ScenarioSemanticValidator()
    first = validator.validate_and_normalize(_scenario(payload))
    second = validator.validate_and_normalize(_scenario(payload))

    assert first.validation.to_dict() == second.validation.to_dict()
    assert first.normalized == second.normalized


def test_golden_scenario_passes_and_normalizes_j15_units() -> None:
    import json

    source = (
        Path(__file__).parents[1]
        / "fixtures"
        / "cmolua"
        / "golden"
        / "source.json"
    )
    payload = json.loads(source.read_text(encoding="utf-8"))

    output = ScenarioSemanticValidator().validate_and_normalize(
        ScenarioInput(source_path=source, raw=payload)
    )

    assert output.validation.valid is True
    assert output.validation.issues == ()

    red_units = output.normalized["sides"]["red"]["units"]
    j15_units = [unit for unit in red_units if unit["type"] == "J-15"]
    assert len(j15_units) == 2
    assert all(
        unit["positionMode"] == "inherit_base"
        for unit in j15_units
    )
    assert all(
        field not in unit
        for unit in j15_units
        for field in ("latitude", "longitude", "heading", "speed")
    )
    assert all(
        "shooter" not in strike and isinstance(strike["shooters"], list)
        for strike in output.normalized["strikePlan"]
    )