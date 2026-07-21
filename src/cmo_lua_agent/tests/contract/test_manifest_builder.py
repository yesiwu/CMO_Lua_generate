from __future__ import annotations

import json
from copy import deepcopy

import pytest

from cmo_lua_agent.contract import (
    ManifestBuilder,
    ResolvedScenarioManifest,
    ScenarioContract,
    ScenarioIR,
)


def _resolved_ir() -> ScenarioIR:
    return ScenarioIR(
        data={
            "irVersion": "scenario-ir-v1",
            "scenario": {
                "id": "carrier-demo",
                "name": "航母协同场景",
            },
            "sides": {
                "red": {
                    "key": "red",
                    "name": "红方",
                    "unitCount": 2,
                    "unitIds": [
                        "red_carrier",
                        "red_aircraft",
                    ],
                },
                "blue": {
                    "key": "blue",
                    "name": "蓝方",
                    "unitCount": 1,
                    "unitIds": ["blue_target"],
                },
            },
            "unitById": {
                "red_carrier": {
                    "id": "red_carrier",
                    "name": "Red Carrier",
                    "dbid": 100,
                    "type": "carrier",
                    "latitude": 20.0,
                    "longitude": 120.0,
                    "heading": 90,
                    "speed": 20,
                    "sideKey": "red",
                    "databaseName": "Database Carrier",
                    "platformCategory": "ship",
                    "aircraftCarried": ["red_aircraft"],
                    "weaponLoad": [
                        {
                            "weapon": "Weapon-A",
                            "weaponDbid": 500,
                            "loaded": 8,
                            "fired": 4,
                            "targets": ["blue_target"],
                            "databaseName": "Weapon-A",
                            "resolutionSource": "explicit_dbid",
                        }
                    ],
                },
                "red_aircraft": {
                    "id": "red_aircraft",
                    "name": "Red Aircraft",
                    "dbid": 200,
                    "type": "aircraft",
                    "base": "red_carrier",
                    "positionMode": "inherit_base",
                    "loadoutId": 900,
                    "sideKey": "red",
                    "databaseName": "Database Aircraft",
                    "platformCategory": "aircraft",
                    "loadoutDatabaseName": "Strike Loadout",
                    "weaponLoad": [],
                },
                "blue_target": {
                    "id": "blue_target",
                    "name": "Blue Target",
                    "dbid": 300,
                    "type": "ship",
                    "latitude": 21.0,
                    "longitude": 121.0,
                    "heading": 270,
                    "speed": 18,
                    "sideKey": "blue",
                    "databaseName": "Database Target",
                    "platformCategory": "ship",
                    "weaponLoad": [],
                },
            },
            "strikePlan": [
                {
                    "id": "strike-1",
                    "shooters": [
                        "red_carrier",
                        "red_aircraft",
                    ],
                    "weapon": "Weapon-A",
                    "weaponDbid": 500,
                    "loaded": 8,
                    "fired": 4,
                    "targets": ["blue_target"],
                    "databaseName": "Weapon-A",
                    "resolutionSource": "explicit_dbid",
                },
                {
                    "id": "strike-2",
                    "shooters": ["red_carrier"],
                    "weapon": "Weapon-A",
                    "weaponDbid": 500,
                    "loaded": 4,
                    "fired": 2,
                    "targets": ["blue_target"],
                    "databaseName": "Weapon-A",
                    "resolutionSource": "explicit_dbid",
                },
            ],
            "missileSummary": {
                "Weapon-A": {
                    "loaded": 12,
                    "fired": 6,
                },
                "totalLoaded": 12,
                "totalFired": 6,
            },
            "settle": {
                "ship": 30,
                "air": 150,
            },
            "notes": ["测试"],
        }
    )


def test_build_returns_manifest_contract_and_valid_result() -> None:
    output = ManifestBuilder().build(_resolved_ir())

    assert isinstance(output.manifest, ResolvedScenarioManifest)
    assert isinstance(output.contract, ScenarioContract)
    assert output.validation.valid is True


def test_build_reconstructs_generator_compatible_sides_and_units() -> None:
    output = ManifestBuilder().build(_resolved_ir())
    manifest = output.manifest.to_dict()

    assert manifest["manifestVersion"] == (
        "resolved-scenario-manifest-v1"
    )
    assert "irVersion" not in manifest
    assert "unitById" not in manifest

    red = manifest["sides"]["red"]
    assert red["name"] == "红方"
    assert red["unitCount"] == 2
    assert [unit["id"] for unit in red["units"]] == [
        "red_carrier",
        "red_aircraft",
    ]
    assert "key" not in red
    assert "unitIds" not in red
    assert "sideKey" not in red["units"][0]

    assert manifest["sides"]["blue"]["units"][0]["id"] == (
        "blue_target"
    )
    assert manifest["strikePlan"][0]["shooters"] == [
        "red_carrier",
        "red_aircraft",
    ]
    assert "shooter" not in manifest["strikePlan"][0]


def test_build_preserves_resolved_database_metadata_and_extensions() -> None:
    manifest = ManifestBuilder().build(
        _resolved_ir()
    ).manifest.to_dict()

    carrier = manifest["sides"]["red"]["units"][0]
    aircraft = manifest["sides"]["red"]["units"][1]

    assert carrier["databaseName"] == "Database Carrier"
    assert carrier["platformCategory"] == "ship"
    assert aircraft["loadoutDatabaseName"] == "Strike Loadout"
    assert carrier["weaponLoad"][0]["resolutionSource"] == (
        "explicit_dbid"
    )
    assert manifest["settle"] == {
        "ship": 30,
        "air": 150,
    }


def test_build_creates_stable_deduplicated_contract() -> None:
    contract = ManifestBuilder().build(
        _resolved_ir()
    ).contract

    assert contract.scenario_id == "carrier-demo"
    assert contract.unit_ids == (
        "red_carrier",
        "red_aircraft",
        "blue_target",
    )
    assert contract.unit_names == (
        "Red Carrier",
        "Red Aircraft",
        "Blue Target",
    )
    assert contract.shooter_ids == (
        "red_carrier",
        "red_aircraft",
    )
    assert contract.target_ids == ("blue_target",)


def test_build_reports_missing_weapon_dbid_in_unit_weapon_load() -> None:
    data = _resolved_ir().to_dict()
    del data["unitById"]["red_carrier"]["weaponLoad"][0][
        "weaponDbid"
    ]

    output = ManifestBuilder().build(
        ScenarioIR(data=data)
    )

    assert output.validation.valid is False
    assert [
        (issue.code, issue.path)
        for issue in output.validation.errors
    ] == [
        (
            "manifest.missing_weapon_dbid",
            "$.sides.red.units[0].weaponLoad[0].weaponDbid",
        )
    ]


def test_build_reports_missing_weapon_dbid_in_strike_plan() -> None:
    data = _resolved_ir().to_dict()
    del data["strikePlan"][0]["weaponDbid"]

    output = ManifestBuilder().build(
        ScenarioIR(data=data)
    )

    assert output.validation.valid is False
    assert output.validation.errors[0].code == (
        "manifest.missing_weapon_dbid"
    )
    assert output.validation.errors[0].path == (
        "$.strikePlan[0].weaponDbid"
    )


def test_build_reports_unresolved_platform_and_loadout() -> None:
    data = _resolved_ir().to_dict()
    del data["unitById"]["red_aircraft"]["platformCategory"]
    del data["unitById"]["red_aircraft"]["databaseName"]
    del data["unitById"]["red_aircraft"][
        "loadoutDatabaseName"
    ]

    output = ManifestBuilder().build(
        ScenarioIR(data=data)
    )

    assert [
        issue.code
        for issue in output.validation.errors
    ] == [
        "manifest.unresolved_platform",
        "manifest.unresolved_loadout",
    ]


def test_build_omits_runtime_fields_and_reports_them() -> None:
    data = _resolved_ir().to_dict()
    data["runRoot"] = "runs/run-001"
    data["workflowState"] = {"stage": "generated"}

    output = ManifestBuilder().build(
        ScenarioIR(data=data)
    )
    manifest = output.manifest.to_dict()

    assert "runRoot" not in manifest
    assert "workflowState" not in manifest
    assert [
        issue.code
        for issue in output.validation.errors
    ] == [
        "manifest.runtime_field_forbidden",
        "manifest.runtime_field_forbidden",
    ]


def test_build_is_deterministic_json_serializable_and_does_not_mutate() -> None:
    ir = _resolved_ir()
    before = deepcopy(ir.to_dict())

    first = ManifestBuilder().build(ir)
    second = ManifestBuilder().build(ir)

    assert first.manifest.to_dict() == second.manifest.to_dict()
    assert first.contract.to_dict() == second.contract.to_dict()
    assert ir.to_dict() == before

    serialized = json.dumps(
        first.manifest.to_dict(),
        ensure_ascii=False,
        sort_keys=True,
    )
    assert "carrier-demo" in serialized


def test_build_rejects_non_scenario_ir() -> None:
    with pytest.raises(TypeError, match="ScenarioIR"):
        ManifestBuilder().build({})  # type: ignore[arg-type]