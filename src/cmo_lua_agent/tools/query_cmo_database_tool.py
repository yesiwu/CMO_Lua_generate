"""
只查询数据库，不修改，
当前只能查询数据库中的武器、平台或飞机挂载方案，似乎还不能查询其他的什么导弹，舰艇等内容
后续需要就扩展分类，
比如专门查询武器，专门查询飞机的函数，像java那样的mysql，后续可能需要扩展为skill，因为内容太多了
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from cmo_lua_agent.integrations.cmolua import CmoDatabaseRecord
from cmo_lua_agent.tools.tool_base.base import BaseTool, ToolResult
from cmo_lua_agent.tools.tool_base.context import ToolContext


class CmoDatabaseLookup(Protocol):
    """The small read-only repository surface required by this tool."""

    @property
    def database_path(self) -> Path: ...

    def get_weapon(self, dbid: int) -> CmoDatabaseRecord | None: ...

    def find_weapons_by_name(self, name: str) -> tuple[CmoDatabaseRecord, ...]: ...

    def find_platforms_by_id(
        self,
        dbid: int,
        *,
        category: str | None = None,
    ) -> tuple[CmoDatabaseRecord, ...]: ...

    def get_loadout(self, loadout_id: int) -> CmoDatabaseRecord | None: ...

    def find_loadouts_for_aircraft(
        self,
        aircraft_dbid: int,
    ) -> tuple[CmoDatabaseRecord, ...]: ...

    def loadout_belongs_to_aircraft(
        self,
        *,
        aircraft_dbid: int,
        loadout_id: int,
    ) -> bool: ...

    def find_loadout_weapons(
        self,
        loadout_id: int,
    ) -> tuple[dict[str, Any], ...]: ...


class QueryCmoDatabaseTool(BaseTool):
    """Expose fixed database lookups without accepting SQL or file paths."""

    name = "query_cmo_database"
    description = (
        "只读查询 CMO 数据库中的武器、平台或飞机挂载方案。"
        "不接受 SQL，不修改数据库，也不替用户选择作战配置。"
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": [
                    "weapon_by_id",
                    "weapon_by_name",
                    "platform_by_id",
                    "loadout_by_id",
                    "loadouts_for_aircraft",
                    "loadout_weapons",
                ],
                "description": "固定的只读查询类型。",
            },
            "dbid": {"type": "integer", "minimum": 1},
            "name": {"type": "string", "minLength": 1},
            "category": {
                "type": "string",
                "enum": ["aircraft", "ship", "submarine", "facility"],
            },
            "loadout_id": {"type": "integer", "minimum": 1},
            "aircraft_dbid": {"type": "integer", "minimum": 1},
        },
        "required": ["operation"],
        "additionalProperties": False,
    }
    toolset = "cmolua"
    requires_approval = False

    _ALLOWED_ARGUMENTS = frozenset(input_schema["properties"])

    def __init__(self, *, repository: CmoDatabaseLookup) -> None:
        self._repository = repository

    def execute(
        self,
        arguments: dict[str, Any],
        context: ToolContext | None = None,
    ) -> ToolResult:
        if context is not None:
            context.progress.tool_started("正在查询 CMO 数据库")
            context.progress.step_started("query", "正在执行受限只读查询")
        try:
            payload = self._query(arguments)
        except ValueError as exc:
            return self._failure("invalid_database_query", str(exc), context)
        except Exception as exc:
            return self._failure(
                "database_query_failed",
                str(exc) or type(exc).__name__,
                context,
            )

        if context is not None:
            context.progress.step_completed(
                "query",
                f"查询完成：{payload['count']} 条记录",
            )
            context.progress.tool_completed("CMO 数据库查询完成")
        return ToolResult(content=json.dumps(payload, ensure_ascii=False, indent=2))

    def _query(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(arguments, dict):
            raise ValueError("查询参数必须是对象")
        unknown = set(arguments).difference(self._ALLOWED_ARGUMENTS)
        if unknown:
            raise ValueError("不支持的查询参数：" + ", ".join(sorted(unknown)))

        operation = arguments.get("operation")
        if operation not in {
            "weapon_by_id",
            "weapon_by_name",
            "platform_by_id",
            "loadout_by_id",
            "loadouts_for_aircraft",
            "loadout_weapons",
        }:
            raise ValueError("operation 必须是受支持的固定查询类型")

        query: dict[str, Any] = {"operation": operation}
        extra: dict[str, Any] = {}
        if operation == "weapon_by_id":
            dbid = _positive_int(arguments.get("dbid"), "dbid")
            query["dbid"] = dbid
            record = self._repository.get_weapon(dbid)
            matches = () if record is None else (record,)
        elif operation == "weapon_by_name":
            name = _non_blank_string(arguments.get("name"), "name")
            if len(name) > 120:
                raise ValueError("name 不能超过 120 个字符")
            query["name"] = name
            matches = self._repository.find_weapons_by_name(name)
        elif operation == "platform_by_id":
            dbid = _positive_int(arguments.get("dbid"), "dbid")
            category = arguments.get("category")
            if category is not None and category not in {
                "aircraft", "ship", "submarine", "facility"
            }:
                raise ValueError("category 不受支持")
            query.update({"dbid": dbid, "category": category})
            matches = self._repository.find_platforms_by_id(
                dbid,
                category=category,
            )
        elif operation == "loadout_by_id":
            loadout_id = _positive_int(arguments.get("loadout_id"), "loadout_id")
            aircraft_dbid = arguments.get("aircraft_dbid")
            if aircraft_dbid is not None:
                aircraft_dbid = _positive_int(aircraft_dbid, "aircraft_dbid")
            query.update(
                {"loadout_id": loadout_id, "aircraft_dbid": aircraft_dbid}
            )
            record = self._repository.get_loadout(loadout_id)
            matches = () if record is None else (record,)
            if record is not None and aircraft_dbid is not None:
                extra["loadout_belongs_to_aircraft"] = (
                    self._repository.loadout_belongs_to_aircraft(
                        aircraft_dbid=aircraft_dbid,
                        loadout_id=loadout_id,
                    )
                )
        elif operation == "loadouts_for_aircraft":
            aircraft_dbid = _positive_int(
                arguments.get("aircraft_dbid"),
                "aircraft_dbid",
            )
            query["aircraft_dbid"] = aircraft_dbid
            matches = self._repository.find_loadouts_for_aircraft(
                aircraft_dbid
            )

        else:
            loadout_id = _positive_int(arguments.get("loadout_id"), "loadout_id")
            query["loadout_id"] = loadout_id
            matches = self._repository.find_loadout_weapons(loadout_id)
            return {
                "success": True,
                "operation": operation,
                "query": query,
                "count": len(matches),
                "ambiguous": False,
                "matches": list(matches),
                "database": {"database_path": str(self._repository.database_path)},
            }

        return {
            "success": True,
            "operation": operation,
            "query": query,
            "count": len(matches),
            "ambiguous": len(matches) > 1,
            "matches": [_record_payload(record) for record in matches],
            "database": {"database_path": str(self._repository.database_path)},
            **extra,
        }

    @staticmethod
    def _failure(
        code: str,
        message: str,
        context: ToolContext | None,
    ) -> ToolResult:
        if context is not None:
            context.progress.tool_failed("CMO 数据库查询失败", message)
        return ToolResult(
            content=json.dumps(
                {"success": False, "error": {"code": code, "message": message}},
                ensure_ascii=False,
                indent=2,
            ),
            is_error=True,
        )


def _record_payload(record: CmoDatabaseRecord) -> dict[str, Any]:
    return {"dbid": record.dbid, "name": record.name, "category": record.category}


def _positive_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} 必须是正整数")
    return value


def _non_blank_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} 必须是非空字符串")
    return value.strip()


__all__ = ["QueryCmoDatabaseTool"]
