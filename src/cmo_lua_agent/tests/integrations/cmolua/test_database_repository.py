"""
参数化武器名称查询
零命中与多命中
JSON 包装查询结果解析
武器 DBID 查询
平台 DBID 查询
Loadout 查询
飞机与 Loadout 归属校验
缺少 query.py
缺少 read_query
外部查询异常包装
禁止通用写数据库接口
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cmo_lua_agent.integrations.cmolua.config import CmoLuaIntegrationConfig
from cmo_lua_agent.integrations.cmolua.database_repository import (
    CmoDatabaseInfrastructureError,
    CmoDatabaseRecord,
    CmoDatabaseRepository,
)


def _build_config(project_root: Path, *, query_source: str | None = None) -> CmoLuaIntegrationConfig:
    skill_root = project_root / "CMOLua-main"
    generator_path = skill_root / "tools" / "json_to_lua.py"
    database_path = skill_root / "mcp" / "db" / "DB3K_504.db3"
    outputs_dir = project_root / "outputs" / "lua"

    generator_path.parent.mkdir(parents=True)
    database_path.parent.mkdir(parents=True)
    outputs_dir.mkdir(parents=True)

    (skill_root / "SKILL.md").write_text("# CMOLua\n", encoding="utf-8")
    generator_path.write_text(
        "def generate_cmo_lua(path):\n    return '-- lua'\n",
        encoding="utf-8",
    )
    database_path.write_bytes(b"SQLite fixture")

    if query_source is not None:
        (skill_root / "mcp" / "query.py").write_text(
            query_source,
            encoding="utf-8",
        )

    return CmoLuaIntegrationConfig(
        skill_root=skill_root,
        generator_path=generator_path,
        database_path=database_path,
        outputs_dir=outputs_dir,
    ).validate()


_QUERY_STUB = r'''
import json
import os

IMPORTED_DATABASE_PATH = os.environ.get("SQLITE_DB_PATH")


def read_query(sql, *, params=None, fetch_all=True, row_limit=1000):
    parameters = tuple(params or ())

    if "DROP TABLE" in sql or "YJ-18';" in sql:
        raise AssertionError("user value was interpolated into SQL")

    if "FROM DataWeapon" in sql and "WHERE Name" in sql:
        name = parameters[0]
        if name == "YJ-18":
            return [{
                "ID": 2137,
                "Name": "YJ-18",
                "Type": "Guided Weapon",
                "ImportedPath": IMPORTED_DATABASE_PATH,
            }]
        if name == "DUPLICATE":
            return [
                {"ID": 1, "Name": "DUPLICATE"},
                {"ID": 2, "Name": "DUPLICATE"},
            ]
        if name == "JSON-WEAPON":
            return json.dumps({
                "rows": [{"ID": 3001, "Name": "JSON-WEAPON"}]
            })
        if name == "BROKEN":
            raise RuntimeError("database unavailable")
        return []

    if "FROM DataWeapon" in sql and "WHERE ID" in sql:
        if parameters[0] == 2137:
            return [{"ID": 2137, "Name": "YJ-18"}]
        return []

    if "FROM DataAircraftLoadouts" in sql and "AND ComponentID" in sql:
        aircraft_dbid, loadout_id = parameters
        if aircraft_dbid == 2496 and loadout_id == 9682:
            return [{"ID": 2496, "ComponentID": 9682}]
        return []

    if "FROM DataAircraftLoadouts" in sql and "WHERE ComponentID" in sql:
        if parameters[0] == 9682:
            return [{
                "ID": 2496,
                "Name": "J-15 Strike Loadout",
                "ComponentID": 9682,
            }]
        return []

    if "FROM DataAircraftLoadouts" in sql and "WHERE ID" in sql:
        if parameters[0] == 2496:
            return [
                {"ID": 2496, "ComponentID": 9681},
                {"ID": 2496, "ComponentID": 9682},
            ]
        return []

    if "FROM DataAircraft" in sql:
        if parameters[0] in (2496, 777):
            return [{"ID": parameters[0], "Name": "J-15"}]
        return []

    if "FROM DataShip" in sql:
        if parameters[0] == 100:
            return [{"ID": 100, "Name": "Type 055"}]
        if parameters[0] == 777:
            return [{"ID": 777, "Name": "Ambiguous Ship"}]
        return []

    if "FROM DataSubmarine" in sql or "FROM DataFacility" in sql:
        return []

    raise AssertionError(f"unexpected SQL: {sql}")
'''


def test_find_weapon_exact_uses_parameterized_query_and_maps_record(
    tmp_path: Path,
) -> None:
    config = _build_config(tmp_path, query_source=_QUERY_STUB)
    repository = CmoDatabaseRepository(config)

    records = repository.find_weapon_exact("YJ-18'; DROP TABLE DataWeapon; --")
    assert records == ()

    records = repository.find_weapon_exact("YJ-18")

    assert records == (
        CmoDatabaseRecord(
            dbid=2137,
            name="YJ-18",
            category="weapon",
            raw={
                "ID": 2137,
                "Name": "YJ-18",
                "Type": "Guided Weapon",
                "ImportedPath": str(config.database_path),
            },
        ),
    )


def test_find_weapon_exact_preserves_zero_and_multiple_matches(
    tmp_path: Path,
) -> None:
    repository = CmoDatabaseRepository(
        _build_config(tmp_path, query_source=_QUERY_STUB)
    )

    assert repository.find_weapon_exact("UNKNOWN") == ()
    assert [record.dbid for record in repository.find_weapon_exact("DUPLICATE")] == [1, 2]


def test_repository_normalizes_json_wrapped_query_results(tmp_path: Path) -> None:
    repository = CmoDatabaseRepository(
        _build_config(tmp_path, query_source=_QUERY_STUB)
    )

    records = repository.find_weapon_exact("JSON-WEAPON")

    assert len(records) == 1
    assert records[0].dbid == 3001
    assert records[0].name == "JSON-WEAPON"


def test_get_weapon_platform_and_loadout(tmp_path: Path) -> None:
    repository = CmoDatabaseRepository(
        _build_config(tmp_path, query_source=_QUERY_STUB)
    )

    weapon = repository.get_weapon(2137)
    aircraft = repository.get_platform(2496)
    ship = repository.get_platform(100, category="ship")
    loadout = repository.get_loadout(9682)

    assert weapon is not None and weapon.category == "weapon"
    assert aircraft is not None and aircraft.category == "aircraft"
    assert ship is not None and ship.category == "ship"
    assert loadout is not None and loadout.category == "loadout"
    assert loadout.dbid == 9682
    assert loadout.raw["ComponentID"] == 9682


def test_find_loadouts_for_aircraft_uses_aircraft_as_owner_id(
    tmp_path: Path,
) -> None:
    repository = CmoDatabaseRepository(
        _build_config(tmp_path, query_source=_QUERY_STUB)
    )

    loadouts = repository.find_loadouts_for_aircraft(2496)

    assert [item.dbid for item in loadouts] == [9681, 9682]


def test_get_loadout_allows_a_loadout_shared_by_multiple_aircraft(
    tmp_path: Path,
) -> None:
    shared_query = _QUERY_STUB.replace(
        'return [{\n                "ID": 2496,',
        'return [{"ID": 2496, "ComponentID": 9682}, {\n                "ID": 3311,',
        1,
    )
    repository = CmoDatabaseRepository(
        _build_config(tmp_path, query_source=shared_query)
    )

    loadout = repository.get_loadout(9682)

    assert loadout is not None
    assert loadout.dbid == 9682


def test_get_platform_rejects_unknown_category_and_ambiguous_dbid(
    tmp_path: Path,
) -> None:
    repository = CmoDatabaseRepository(
        _build_config(tmp_path, query_source=_QUERY_STUB)
    )

    with pytest.raises(ValueError, match="不支持的平台类别"):
        repository.get_platform(2496, category="tank")

    with pytest.raises(CmoDatabaseInfrastructureError, match="多个平台表"):
        repository.get_platform(777)


def test_loadout_belongs_to_aircraft_returns_boolean(tmp_path: Path) -> None:
    repository = CmoDatabaseRepository(
        _build_config(tmp_path, query_source=_QUERY_STUB)
    )

    assert repository.loadout_belongs_to_aircraft(
        aircraft_dbid=2496,
        loadout_id=9682,
    )
    assert not repository.loadout_belongs_to_aircraft(
        aircraft_dbid=9999,
        loadout_id=9682,
    )


def test_repository_rejects_missing_query_module(tmp_path: Path) -> None:
    config = _build_config(tmp_path, query_source=None)

    with pytest.raises(CmoDatabaseInfrastructureError, match="query.py 不存在"):
        CmoDatabaseRepository(config).find_weapon_exact("YJ-18")


def test_repository_rejects_query_module_without_read_query(
    tmp_path: Path,
) -> None:
    config = _build_config(
        tmp_path,
        query_source="VALUE = 1\n",
    )

    with pytest.raises(CmoDatabaseInfrastructureError, match="read_query"):
        CmoDatabaseRepository(config).find_weapon_exact("YJ-18")


def test_repository_wraps_external_query_failures(tmp_path: Path) -> None:
    repository = CmoDatabaseRepository(
        _build_config(tmp_path, query_source=_QUERY_STUB)
    )

    with pytest.raises(CmoDatabaseInfrastructureError, match="database unavailable"):
        repository.find_weapon_exact("BROKEN")


def test_repository_exposes_no_generic_sql_or_write_api(tmp_path: Path) -> None:
    repository = CmoDatabaseRepository(
        _build_config(tmp_path, query_source=_QUERY_STUB)
    )

    assert not hasattr(repository, "execute")
    assert not hasattr(repository, "execute_sql")
    assert not hasattr(repository, "write")
    assert not hasattr(repository, "insert")
    assert not hasattr(repository, "update")
    assert not hasattr(repository, "delete")
