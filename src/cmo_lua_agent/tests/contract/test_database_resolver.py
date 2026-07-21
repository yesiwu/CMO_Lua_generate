from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from cmo_lua_agent.contract import ScenarioIR
from cmo_lua_agent.contract.database_resolver import (
    DatabaseResolutionOutput,
    DatabaseResolver,
)
from cmo_lua_agent.integrations.cmolua.database_repository import (
    CmoDatabaseInfrastructureError,
    CmoDatabaseRecord,
)


def _record(
    dbid: int,
    name: str,
    category: str,
    **raw: Any,
) -> CmoDatabaseRecord:
    return CmoDatabaseRecord(
        dbid=dbid,
        name=name,
        category=category,
        raw={"ID": dbid, "Name": name, **raw},
    )


class FakeRepository:
    def __init__(self) -> None:
        self.platforms: dict[int, CmoDatabaseRecord] = {
            100: _record(100, "Test Aircraft", "aircraft"),
            200: _record(200, "Test Target", "ship"),
        }
        self.weapons: dict[int, CmoDatabaseRecord] = {
            500: _record(500, "Weapon-A", "weapon"),
            501: _record(501, "Weapon-B", "weapon"),
        }
        self.weapon_matches: dict[str, tuple[CmoDatabaseRecord, ...]] = {
            "Weapon-A": (self.weapons[500],),
            "Weapon-B": (self.weapons[501],),
        }
        self.loadouts: dict[int, CmoDatabaseRecord] = {
            900: _record(
                900,
                "Air-to-Surface Loadout",
                "loadout",
                ComponentID=100,
            )
        }
        self.belongs: set[tuple[int, int]] = {(100, 900)}
        self.exact_name_calls: list[str] = []

    def get_platform(
        self,
        dbid: int,
        *,
        category: str | None = None,
    ) -> CmoDatabaseRecord | None:
        del category
        return self.platforms.get(dbid)

    def get_weapon(self, dbid: int) -> CmoDatabaseRecord | None:
        return self.weapons.get(dbid)

    def find_weapon_exact(
        self,
        name: str,
    ) -> tuple[CmoDatabaseRecord, ...]:
        self.exact_name_calls.append(name)
        return self.weapon_matches.get(name, ())

    def get_loadout(
        self,
        loadout_id: int,
    ) -> CmoDatabaseRecord | None:
        return self.loadouts.get(loadout_id)

    def loadout_belongs_to_aircraft(
        self,
        *,
        aircraft_dbid: int,
        loadout_id: int,
    ) -> bool:
        return (aircraft_dbid, loadout_id) in self.belongs


def _valid_ir() -> ScenarioIR:
    return ScenarioIR(
        data={
            "irVersion": "scenario-ir-v1",
            "scenario": {
                "id": "scenario-001",
                "name": "Database resolver test",
            },
            "sides": {
                "red": {
                    "key": "red",
                    "name": "Red",
                    "unitCount": 1,
                    "unitIds": ["red-aircraft"],
                },
                "blue": {
                    "key": "blue",
                    "name": "Blue",
                    "unitCount": 1,
                    "unitIds": ["blue-target"],
                },
            },
            "unitById": {
                "red-aircraft": {
                    "id": "red-aircraft",
                    "name": "Red Aircraft",
                    "dbid": 100,
                    "type": "Fighter",
                    "sideKey": "red",
                    "base": "red-carrier",
                    "positionMode": "inherit_base",
                    "loadoutId": 900,
                    "weaponLoad": [
                        {
                            "weapon": "Weapon-A",
                            "loaded": 4,
                            "fired": 2,
                            "targets": ["blue-target"],
                        }
                    ],
                },
                "blue-target": {
                    "id": "blue-target",
                    "name": "Blue Target",
                    "dbid": 200,
                    "type": "DDG",
                    "sideKey": "blue",
                    "latitude": 20.0,
                    "longitude": 120.0,
                    "heading": 270,
                    "speed": 10,
                },
            },
            "strikePlan": [
                {
                    "id": "strike-1",
                    "shooters": ["red-aircraft"],
                    "weapon": "Weapon-A",
                    "loaded": 4,
                    "fired": 2,
                    "targets": ["blue-target"],
                },
                {
                    "id": "strike-2",
                    "shooters": ["red-aircraft"],
                    "weapon": "Weapon-B",
                    "weaponDbid": 501,
                    "loadoutId": 900,
                    "loaded": 2,
                    "fired": 1,
                    "targets": ["blue-target"],
                },
            ],
        }
    )


def _issue_pairs(output: DatabaseResolutionOutput) -> list[tuple[str, str]]:
    return [
        (issue.code, issue.path)
        for issue in output.validation.issues
    ]


def test_resolve_validates_platforms_loadout_and_resolves_weapons() -> None:
    repository = FakeRepository()

    output = DatabaseResolver(repository).resolve(_valid_ir())

    assert output.validation.valid is True
    assert output.validation.issues == ()

    resolved = output.resolved_ir.data
    inventory = resolved["unitById"]["red-aircraft"]["weaponLoad"][0]
    assert inventory["weaponDbid"] == 500
    assert inventory["resolutionSource"] == "database_exact_name"
    assert inventory["databaseName"] == "Weapon-A"

    first_strike = resolved["strikePlan"][0]
    assert first_strike["weaponDbid"] == 500
    assert first_strike["resolutionSource"] == "database_exact_name"

    explicit_strike = resolved["strikePlan"][1]
    assert explicit_strike["weaponDbid"] == 501
    assert explicit_strike["resolutionSource"] == "explicit_dbid"
    assert explicit_strike["databaseName"] == "Weapon-B"

    assert repository.exact_name_calls == ["Weapon-A"]
    assert output.report["summary"] == {
        "platformsChecked": 2,
        "loadoutsChecked": 1,
        "weaponOccurrencesChecked": 3,
        "weaponNamesResolved": 1,
        "errors": 0,
    }


def test_resolve_does_not_mutate_source_ir() -> None:
    ir = _valid_ir()
    original = ir.to_dict()

    DatabaseResolver(FakeRepository()).resolve(ir)

    assert ir.to_dict() == original


def test_unknown_platform_dbid_is_reported() -> None:
    ir = _valid_ir()
    ir.data["unitById"]["blue-target"]["dbid"] = 999

    output = DatabaseResolver(FakeRepository()).resolve(ir)

    assert (
        "database.platform_not_found",
        "$.unitById.blue-target.dbid",
    ) in _issue_pairs(output)


def test_missing_loadout_is_reported() -> None:
    repository = FakeRepository()
    repository.loadouts.clear()

    output = DatabaseResolver(repository).resolve(_valid_ir())

    assert (
        "database.loadout_not_found",
        "$.unitById.red-aircraft.loadoutId",
    ) in _issue_pairs(output)


def test_loadout_must_belong_to_aircraft() -> None:
    repository = FakeRepository()
    repository.belongs.clear()

    output = DatabaseResolver(repository).resolve(_valid_ir())

    assert (
        "database.loadout_mismatch",
        "$.unitById.red-aircraft.loadoutId",
    ) in _issue_pairs(output)


def test_loadout_on_non_aircraft_platform_is_rejected() -> None:
    repository = FakeRepository()
    repository.platforms[100] = _record(100, "Surface Ship", "ship")

    output = DatabaseResolver(repository).resolve(_valid_ir())

    assert (
        "database.loadout_requires_aircraft",
        "$.unitById.red-aircraft.loadoutId",
    ) in _issue_pairs(output)


def test_explicit_weapon_dbid_must_exist() -> None:
    repository = FakeRepository()
    repository.weapons.pop(501)

    output = DatabaseResolver(repository).resolve(_valid_ir())

    assert (
        "database.weapon_not_found",
        "$.strikePlan[1].weaponDbid",
    ) in _issue_pairs(output)


def test_explicit_weapon_name_must_match_database_name() -> None:
    ir = _valid_ir()
    ir.data["strikePlan"][1]["weapon"] = "Different Name"

    output = DatabaseResolver(FakeRepository()).resolve(ir)

    assert (
        "database.weapon_name_mismatch",
        "$.strikePlan[1].weapon",
    ) in _issue_pairs(output)


def test_missing_weapon_dbid_with_zero_exact_matches_is_rejected() -> None:
    repository = FakeRepository()
    repository.weapon_matches["Weapon-A"] = ()

    output = DatabaseResolver(repository).resolve(_valid_ir())

    paths = [
        path
        for code, path in _issue_pairs(output)
        if code == "database.weapon_not_found"
    ]
    assert paths == [
        "$.unitById.red-aircraft.weaponLoad[0].weapon",
        "$.strikePlan[0].weapon",
    ]


def test_missing_weapon_dbid_with_multiple_exact_matches_is_rejected() -> None:
    repository = FakeRepository()
    repository.weapon_matches["Weapon-A"] = (
        repository.weapons[500],
        _record(502, "Weapon-A", "weapon"),
    )

    output = DatabaseResolver(repository).resolve(_valid_ir())

    assert (
        "database.weapon_ambiguous",
        "$.unitById.red-aircraft.weaponLoad[0].weapon",
    ) in _issue_pairs(output)
    assert (
        "database.weapon_ambiguous",
        "$.strikePlan[0].weapon",
    ) in _issue_pairs(output)


def test_database_infrastructure_errors_are_not_misreported_as_validation() -> None:
    class BrokenRepository(FakeRepository):
        def get_platform(
            self,
            dbid: int,
            *,
            category: str | None = None,
        ) -> CmoDatabaseRecord | None:
            del dbid, category
            raise CmoDatabaseInfrastructureError("database unavailable")

    with pytest.raises(
        CmoDatabaseInfrastructureError,
        match="database unavailable",
    ):
        DatabaseResolver(BrokenRepository()).resolve(_valid_ir())


def test_explicit_platform_resolution_overrides_only_the_selected_unit() -> None:
    ir = _valid_ir()
    ir.data["unitById"]["red-aircraft"]["dbid"] = 999

    output = DatabaseResolver(FakeRepository()).resolve(
        ir,
        platform_resolutions={
            "red-aircraft": {"category": "aircraft", "dbid": 100}
        },
    )

    resolved = output.resolved_ir.data["unitById"]["red-aircraft"]
    assert resolved["dbid"] == 100
    assert resolved["platformCategory"] == "aircraft"
    assert output.report["platformResolutions"] == [
        {
            "unitId": "red-aircraft",
            "category": "aircraft",
            "dbid": 100,
            "source": "explicit_resolution",
        }
    ]


def test_ambiguous_platform_dbid_requires_explicit_user_resolution() -> None:
    class AmbiguousRepository(FakeRepository):
        def get_platform(
            self,
            dbid: int,
            *,
            category: str | None = None,
        ) -> CmoDatabaseRecord | None:
            if dbid != 100:
                return super().get_platform(dbid, category=category)
            if category == "aircraft":
                return _record(100, "Test Aircraft", "aircraft")
            if category == "ship":
                return _record(100, "Unrelated Ship", "ship")
            return None

    output = DatabaseResolver(AmbiguousRepository()).resolve(_valid_ir())

    assert (
        "database.platform_resolution_required",
        "$.unitById.red-aircraft.dbid",
    ) in _issue_pairs(output)
    report = output.report["platforms"][0]
    assert report["status"] == "resolution_required"
    assert report["candidates"] == [
        {
            "category": "aircraft",
            "dbid": 100,
            "databaseName": "Test Aircraft",
        },
        {
            "category": "ship",
            "dbid": 100,
            "databaseName": "Unrelated Ship",
        },
    ]
