from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from cmo_lua_agent.contract import (
    ScenarioInput,
    ScenarioSchemaValidator,
    ValidationSeverity,
)


def _golden_payload() -> dict:
    fixture = (
        Path(__file__).parents[1]
        / "fixtures"
        / "cmolua"
        / "golden"
        / "source.json"
    )
    return json.loads(fixture.read_text(encoding="utf-8"))


def _scenario(payload: dict) -> ScenarioInput:
    return ScenarioInput(
        source_path=Path("scenario.json"),
        raw=payload,
    )


def _minimal_valid_payload() -> dict:
    return {
        "scenario": {
            "id": "scenario-001",
            "name": "测试场景",
        },
        "sides": {
            "red": {
                "name": "红方",
                "units": [
                    {
                        "id": "red-1",
                        "name": "Red-1",
                        "dbid": 1001,
                        "type": "ship",
                        "latitude": 20.0,
                        "longitude": 120.0,
                        "heading": 90,
                        "speed": 15,
                    }
                ],
            },
            "blue": {
                "name": "蓝方",
                "units": [
                    {
                        "id": "blue-1",
                        "name": "Blue-1",
                        "dbid": 2001,
                        "type": "ship",
                        "latitude": 21.0,
                        "longitude": 121.0,
                        "heading": 270,
                        "speed": 0,
                    }
                ],
            },
        },
        "strikePlan": [
            {
                "shooter": "red-1",
                "weapon": "Weapon-A",
                "loaded": 2,
                "fired": 1,
                "targets": ["blue-1"],
            }
        ],
    }


def _issues_by_code(result, code: str):
    return [issue for issue in result.issues if issue.code == code]


def test_golden_scenario_passes_schema_validation() -> None:
    result = ScenarioSchemaValidator().validate(
        _scenario(_golden_payload())
    )

    assert result.valid is True
    assert result.issues == ()


def test_unknown_extension_fields_are_allowed() -> None:
    payload = _minimal_valid_payload()
    payload["customMetadata"] = {"owner": "test"}
    payload["scenario"]["customFlag"] = True
    payload["sides"]["red"]["units"][0]["customField"] = "value"

    result = ScenarioSchemaValidator().validate(_scenario(payload))

    assert result.valid is True


def test_missing_top_level_fields_are_reported_in_stable_order() -> None:
    result = ScenarioSchemaValidator().validate(_scenario({}))

    assert [issue.code for issue in result.issues] == [
        "schema.missing_field",
        "schema.missing_field",
        "schema.missing_field",
    ]
    assert [issue.path for issue in result.issues] == [
        "$.scenario",
        "$.sides",
        "$.strikePlan",
    ]


def test_scenario_requires_non_blank_id_and_name() -> None:
    payload = _minimal_valid_payload()
    payload["scenario"] = {"id": " ", "name": 42}

    result = ScenarioSchemaValidator().validate(_scenario(payload))

    assert [(issue.code, issue.path) for issue in result.issues] == [
        ("schema.invalid_type", "$.scenario.id"),
        ("schema.invalid_type", "$.scenario.name"),
    ]


def test_sides_require_red_and_blue_objects() -> None:
    payload = _minimal_valid_payload()
    payload["sides"] = {"red": []}

    result = ScenarioSchemaValidator().validate(_scenario(payload))

    assert [(issue.code, issue.path) for issue in result.issues] == [
        ("schema.invalid_side", "$.sides.red"),
        ("schema.side_missing", "$.sides.blue"),
    ]


def test_side_requires_name_and_units_array() -> None:
    payload = _minimal_valid_payload()
    payload["sides"]["red"] = {
        "name": "",
        "units": {},
    }

    result = ScenarioSchemaValidator().validate(_scenario(payload))

    assert [(issue.code, issue.path) for issue in result.issues] == [
        ("schema.invalid_type", "$.sides.red.name"),
        ("schema.invalid_type", "$.sides.red.units"),
    ]


def test_unit_count_must_be_non_negative_integer_and_match_units() -> None:
    payload = _minimal_valid_payload()
    payload["sides"]["red"]["unitCount"] = 2
    payload["sides"]["blue"]["unitCount"] = True

    result = ScenarioSchemaValidator().validate(_scenario(payload))

    assert [(issue.code, issue.path) for issue in result.issues] == [
        ("schema.unit_count_mismatch", "$.sides.red.unitCount"),
        ("schema.invalid_type", "$.sides.blue.unitCount"),
    ]


def test_unit_requires_id_name_dbid_and_type() -> None:
    payload = _minimal_valid_payload()
    payload["sides"]["red"]["units"] = [
        {
            "latitude": 20,
            "longitude": 120,
            "heading": 90,
            "speed": 10,
        }
    ]

    result = ScenarioSchemaValidator().validate(_scenario(payload))

    assert [issue.path for issue in result.issues] == [
        "$.sides.red.units[0].id",
        "$.sides.red.units[0].name",
        "$.sides.red.units[0].dbid",
        "$.sides.red.units[0].type",
    ]
    assert all(
        issue.code == "schema.missing_unit_field"
        for issue in result.issues
    )


@pytest.mark.parametrize("invalid_dbid", [0, -1, "1001", 1.5, True])
def test_unit_dbid_must_be_positive_integer(invalid_dbid) -> None:
    payload = _minimal_valid_payload()
    payload["sides"]["red"]["units"][0]["dbid"] = invalid_dbid

    result = ScenarioSchemaValidator().validate(_scenario(payload))

    assert [(issue.code, issue.path) for issue in result.issues] == [
        ("schema.invalid_dbid", "$.sides.red.units[0].dbid")
    ]


def test_fixed_unit_requires_all_four_numeric_position_fields() -> None:
    payload = _minimal_valid_payload()
    del payload["sides"]["red"]["units"][0]["speed"]
    payload["sides"]["blue"]["units"][0]["latitude"] = "21.0"

    result = ScenarioSchemaValidator().validate(_scenario(payload))

    assert [(issue.code, issue.path) for issue in result.issues] == [
        ("schema.missing_position", "$.sides.red.units[0].speed"),
        (
            "schema.invalid_coordinate_type",
            "$.sides.blue.units[0].latitude",
        ),
    ]


@pytest.mark.parametrize("invalid_number", [True, float("nan"), float("inf")])
def test_position_rejects_bool_nan_and_infinity(invalid_number) -> None:
    payload = _minimal_valid_payload()
    payload["sides"]["red"]["units"][0]["heading"] = invalid_number

    result = ScenarioSchemaValidator().validate(_scenario(payload))

    assert [(issue.code, issue.path) for issue in result.issues] == [
        (
            "schema.invalid_coordinate_type",
            "$.sides.red.units[0].heading",
        )
    ]


def test_based_unit_accepts_all_missing_position_fields() -> None:
    payload = _minimal_valid_payload()
    aircraft = payload["sides"]["red"]["units"][0]
    aircraft["base"] = "carrier-1"
    for field in ("latitude", "longitude", "heading", "speed"):
        aircraft.pop(field)

    result = ScenarioSchemaValidator().validate(_scenario(payload))

    assert result.valid is True


def test_based_unit_accepts_all_non_blank_descriptive_position_fields() -> None:
    payload = _minimal_valid_payload()
    aircraft = payload["sides"]["red"]["units"][0]
    aircraft.update(
        {
            "base": "carrier-1",
            "latitude": "随母舰",
            "longitude": "随母舰",
            "heading": "起飞后设定",
            "speed": "起飞后设定",
        }
    )

    result = ScenarioSchemaValidator().validate(_scenario(payload))

    assert result.valid is True


def test_based_unit_accepts_all_numeric_position_fields() -> None:
    payload = _minimal_valid_payload()
    payload["sides"]["red"]["units"][0]["base"] = "carrier-1"

    result = ScenarioSchemaValidator().validate(_scenario(payload))

    assert result.valid is True


def test_descriptive_position_without_base_is_rejected() -> None:
    payload = _minimal_valid_payload()
    unit = payload["sides"]["red"]["units"][0]
    unit.update(
        {
            "latitude": "随母舰",
            "longitude": "随母舰",
            "heading": "起飞后设定",
            "speed": "起飞后设定",
        }
    )

    result = ScenarioSchemaValidator().validate(_scenario(payload))

    assert _issues_by_code(result, "schema.invalid_coordinate_type")


def test_based_unit_rejects_mixed_position_mode() -> None:
    payload = _minimal_valid_payload()
    unit = payload["sides"]["red"]["units"][0]
    unit.update(
        {
            "base": "carrier-1",
            "latitude": 20.0,
            "longitude": "随母舰",
            "heading": 90,
            "speed": "起飞后设定",
        }
    )

    result = ScenarioSchemaValidator().validate(_scenario(payload))

    assert [(issue.code, issue.path) for issue in result.issues] == [
        ("schema.mixed_position_mode", "$.sides.red.units[0]")
    ]


def test_weapon_load_allows_missing_weapon_dbid() -> None:
    payload = _minimal_valid_payload()
    payload["sides"]["red"]["units"][0]["weaponLoad"] = [
        {
            "weapon": "YJ-18",
            "loaded": 8,
            "fired": 4,
            "targets": ["blue-1"],
        }
    ]

    result = ScenarioSchemaValidator().validate(_scenario(payload))

    assert result.valid is True


@pytest.mark.parametrize("invalid_quantity", [-1, 1.5, "2", True])
def test_weapon_load_quantities_must_be_non_negative_integers(
    invalid_quantity,
) -> None:
    payload = _minimal_valid_payload()
    payload["sides"]["red"]["units"][0]["weaponLoad"] = [
        {
            "weapon": "YJ-18",
            "loaded": invalid_quantity,
            "fired": 0,
        }
    ]

    result = ScenarioSchemaValidator().validate(_scenario(payload))

    assert [(issue.code, issue.path) for issue in result.issues] == [
        (
            "schema.invalid_ammo_quantity",
            "$.sides.red.units[0].weaponLoad[0].loaded",
        )
    ]


def test_weapon_load_optional_targets_must_be_non_empty_string_array() -> None:
    payload = _minimal_valid_payload()
    payload["sides"]["red"]["units"][0]["weaponLoad"] = [
        {
            "weapon": "YJ-18",
            "loaded": 4,
            "fired": 2,
            "targets": [],
        }
    ]

    result = ScenarioSchemaValidator().validate(_scenario(payload))

    assert [(issue.code, issue.path) for issue in result.issues] == [
        (
            "schema.invalid_targets",
            "$.sides.red.units[0].weaponLoad[0].targets",
        )
    ]


def test_strike_requires_exactly_one_shooter_shape() -> None:
    payload = _minimal_valid_payload()
    payload["strikePlan"] = [
        {
            "weapon": "Weapon-A",
            "loaded": 1,
            "fired": 1,
            "targets": ["blue-1"],
        },
        {
            "shooter": "red-1",
            "shooters": ["red-1"],
            "weapon": "Weapon-A",
            "loaded": 1,
            "fired": 1,
            "targets": ["blue-1"],
        },
    ]

    result = ScenarioSchemaValidator().validate(_scenario(payload))

    assert [(issue.code, issue.path) for issue in result.issues] == [
        ("schema.invalid_shooter_shape", "$.strikePlan[0]"),
        ("schema.invalid_shooter_shape", "$.strikePlan[1]"),
    ]


def test_strike_shooters_and_targets_must_be_non_empty_string_arrays() -> None:
    payload = _minimal_valid_payload()
    payload["strikePlan"] = [
        {
            "shooters": [],
            "weapon": "Weapon-A",
            "loaded": 1,
            "fired": 1,
            "targets": [""],
        }
    ]

    result = ScenarioSchemaValidator().validate(_scenario(payload))

    assert [(issue.code, issue.path) for issue in result.issues] == [
        ("schema.invalid_shooters", "$.strikePlan[0].shooters"),
        ("schema.invalid_targets", "$.strikePlan[0].targets"),
    ]


def test_strike_requires_weapon_loaded_fired_and_targets() -> None:
    payload = _minimal_valid_payload()
    payload["strikePlan"] = [{"shooter": "red-1"}]

    result = ScenarioSchemaValidator().validate(_scenario(payload))

    assert [issue.path for issue in result.issues] == [
        "$.strikePlan[0].weapon",
        "$.strikePlan[0].loaded",
        "$.strikePlan[0].fired",
        "$.strikePlan[0].targets",
    ]


def test_optional_weapon_dbid_and_loadout_id_must_be_positive_integers() -> None:
    payload = _minimal_valid_payload()
    payload["strikePlan"][0]["weaponDbid"] = 0
    payload["strikePlan"][0]["loadoutId"] = True

    result = ScenarioSchemaValidator().validate(_scenario(payload))

    assert [(issue.code, issue.path) for issue in result.issues] == [
        ("schema.invalid_weapon_dbid", "$.strikePlan[0].weaponDbid"),
        ("schema.invalid_loadout_id", "$.strikePlan[0].loadoutId"),
    ]


def test_missile_summary_quantities_must_be_non_negative_integers() -> None:
    payload = _minimal_valid_payload()
    payload["missileSummary"] = {
        "Weapon-A": {"loaded": 2, "fired": -1},
        "totalLoaded": "2",
        "totalFired": 1,
    }

    result = ScenarioSchemaValidator().validate(_scenario(payload))

    assert [(issue.code, issue.path) for issue in result.issues] == [
        (
            "schema.invalid_ammo_quantity",
            "$.missileSummary.Weapon-A.fired",
        ),
        (
            "schema.invalid_ammo_quantity",
            "$.missileSummary.totalLoaded",
        ),
    ]


def test_notes_must_be_array_of_strings() -> None:
    payload = _minimal_valid_payload()
    payload["notes"] = ["ok", 42]

    result = ScenarioSchemaValidator().validate(_scenario(payload))

    assert [(issue.code, issue.path) for issue in result.issues] == [
        ("schema.invalid_type", "$.notes[1]")
    ]


def test_validator_collects_independent_errors_without_mutating_input() -> None:
    payload = _minimal_valid_payload()
    payload["scenario"]["name"] = ""
    payload["sides"]["red"]["units"][0]["dbid"] = 0
    payload["strikePlan"][0]["loaded"] = -1
    original = deepcopy(payload)

    result = ScenarioSchemaValidator().validate(_scenario(payload))

    assert result.valid is False
    assert len(result.errors) == 3
    assert all(
        issue.severity is ValidationSeverity.ERROR
        for issue in result.issues
    )
    assert payload == original