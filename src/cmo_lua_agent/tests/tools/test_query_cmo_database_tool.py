from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cmo_lua_agent.integrations.cmolua import CmoDatabaseRecord
from cmo_lua_agent.tools.query_cmo_database_tool import QueryCmoDatabaseTool
from cmo_lua_agent.tools.tool_base.context import ToolContext
from cmo_lua_agent.tools.tool_base.progress import ToolProgressReporter


def _record(dbid: int, name: str, category: str) -> CmoDatabaseRecord:
    return CmoDatabaseRecord(
        dbid=dbid,
        name=name,
        category=category,
        raw={"ID": dbid, "Name": name},
    )


class FakeDatabaseRepository:
    database_path = Path("D:/CMO/DB3K_504.db3")

    def find_weapons_by_name(self, name: str) -> tuple[CmoDatabaseRecord, ...]:
        if name == "YJ-18":
            return (
                _record(2867, "YJ-18 [3M54E Klub Copy, Rocket Boosted Penetrator]", "weapon"),
                _record(2868, "YJ-18 [3M54E Klub Copy]", "weapon"),
            )
        return ()

    def get_weapon(self, dbid: int) -> CmoDatabaseRecord | None:
        return _record(2868, "YJ-18 [3M54E Klub Copy]", "weapon") if dbid == 2868 else None

    def find_platforms_by_id(
        self,
        dbid: int,
        *,
        category: str | None = None,
    ) -> tuple[CmoDatabaseRecord, ...]:
        candidates = (
            _record(3883, "TIF-25K Aerostat", "aircraft"),
            _record(3883, "Type 055 Renhai [101 Nanchang]", "ship"),
        ) if dbid == 3883 else ()
        if category is None:
            return candidates
        return tuple(item for item in candidates if item.category == category)

    def get_loadout(self, loadout_id: int) -> CmoDatabaseRecord | None:
        return _record(900, "J-15 anti-ship", "loadout") if loadout_id == 900 else None

    def find_loadouts_for_aircraft(
        self,
        aircraft_dbid: int,
    ) -> tuple[CmoDatabaseRecord, ...]:
        if aircraft_dbid != 2496:
            return ()
        return (
            _record(900, "J-15 anti-ship", "loadout"),
            _record(901, "J-15 air-defense", "loadout"),
        )

    def loadout_belongs_to_aircraft(
        self,
        *,
        aircraft_dbid: int,
        loadout_id: int,
    ) -> bool:
        return aircraft_dbid == 2496 and loadout_id == 900

    def find_loadout_weapons(
        self,
        loadout_id: int,
    ) -> tuple[dict[str, object], ...]:
        if loadout_id != 900:
            return ()
        return (
            {
                "dbid": 2137,
                "name": "YJ-83K [C-802AK]",
                "default_load": 2,
                "max_load": 2,
                "station": 3,
            },
        )


def _context(events: list[Any]) -> ToolContext:
    return ToolContext(
        tool_use_id="query-1",
        tool_name="query_cmo_database",
        progress=ToolProgressReporter(
            tool_use_id="query-1",
            tool_name="query_cmo_database",
            callback=events.append,
        ),
    )


def _payload(result: Any) -> dict[str, Any]:
    return json.loads(result.content)


def test_weapon_name_query_returns_candidates_and_progress() -> None:
    events: list[Any] = []
    tool = QueryCmoDatabaseTool(repository=FakeDatabaseRepository())

    result = tool.execute(
        {"operation": "weapon_by_name", "name": "YJ-18"},
        context=_context(events),
    )

    payload = _payload(result)
    assert result.is_error is False
    assert payload["count"] == 2
    assert payload["ambiguous"] is True
    assert [item["dbid"] for item in payload["matches"]] == [2867, 2868]
    assert "database_path" in payload["database"]
    assert [(event.event_type, event.step_id) for event in events] == [
        ("tool_started", None),
        ("step_started", "query"),
        ("step_completed", "query"),
        ("tool_completed", None),
    ]


def test_platform_query_returns_all_categories_or_the_requested_category() -> None:
    tool = QueryCmoDatabaseTool(repository=FakeDatabaseRepository())

    all_categories = _payload(
        tool.execute({"operation": "platform_by_id", "dbid": 3883})
    )
    ship_only = _payload(
        tool.execute(
            {
                "operation": "platform_by_id",
                "dbid": 3883,
                "category": "ship",
            }
        )
    )

    assert all_categories["ambiguous"] is True
    assert [item["category"] for item in all_categories["matches"]] == [
        "aircraft",
        "ship",
    ]
    assert ship_only["matches"] == [
        {
            "dbid": 3883,
            "name": "Type 055 Renhai [101 Nanchang]",
            "category": "ship",
        }
    ]


def test_loadout_query_can_check_aircraft_ownership() -> None:
    tool = QueryCmoDatabaseTool(repository=FakeDatabaseRepository())

    payload = _payload(
        tool.execute(
            {
                "operation": "loadout_by_id",
                "loadout_id": 900,
                "aircraft_dbid": 2496,
            }
        )
    )

    assert payload["matches"][0]["dbid"] == 900
    assert payload["loadout_belongs_to_aircraft"] is True


def test_loadouts_for_aircraft_lists_available_loadout_ids() -> None:
    tool = QueryCmoDatabaseTool(repository=FakeDatabaseRepository())

    payload = _payload(
        tool.execute(
            {
                "operation": "loadouts_for_aircraft",
                "aircraft_dbid": 2496,
            }
        )
    )

    assert payload["count"] == 2
    assert [item["dbid"] for item in payload["matches"]] == [900, 901]


def test_loadout_weapons_lists_the_actual_weapon_composition() -> None:
    tool = QueryCmoDatabaseTool(repository=FakeDatabaseRepository())

    payload = _payload(
        tool.execute({"operation": "loadout_weapons", "loadout_id": 900})
    )

    assert payload["count"] == 1
    assert payload["matches"] == [
        {
            "dbid": 2137,
            "name": "YJ-83K [C-802AK]",
            "default_load": 2,
            "max_load": 2,
            "station": 3,
        }
    ]


def test_invalid_operation_missing_parameters_and_unknown_inputs_are_errors() -> None:
    tool = QueryCmoDatabaseTool(repository=FakeDatabaseRepository())

    for arguments in (
        {"operation": "sql", "sql": "SELECT * FROM DataWeapon"},
        {"operation": "weapon_by_id"},
        {"operation": "weapon_by_id", "dbid": -1},
        {"operation": "weapon_by_name", "name": "YJ-18", "database_path": "x"},
    ):
        result = tool.execute(arguments)
        assert result.is_error is True
        assert _payload(result)["error"]["code"] == "invalid_database_query"


def test_repository_exceptions_are_returned_as_tool_errors() -> None:
    class BrokenRepository(FakeDatabaseRepository):
        def get_weapon(self, dbid: int) -> CmoDatabaseRecord | None:
            raise RuntimeError("database unavailable")

    result = QueryCmoDatabaseTool(repository=BrokenRepository()).execute(
        {"operation": "weapon_by_id", "dbid": 2868}
    )

    assert result.is_error is True
    assert _payload(result)["error"]["code"] == "database_query_failed"
