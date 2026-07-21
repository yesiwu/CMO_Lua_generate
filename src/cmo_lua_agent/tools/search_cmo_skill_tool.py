"""CMOLua Skill 仓库检索工具适配器。"""

from __future__ import annotations

import json
from typing import Any

from cmo_lua_agent.integrations.cmolua import (
    CmoSkillAccessError,
    CmoSkillInfrastructureError,
    CmoSkillRepository,
)
from cmo_lua_agent.tools.tool_base.base import BaseTool, ToolResult
from cmo_lua_agent.tools.tool_base.context import ToolContext


_ALLOWED_AREAS = frozenset(
    {"skill", "templates", "references", "errors", "examples"}
)
_DEFAULT_LIMIT = 10
_MAX_LIMIT = 20


class SearchCmoSkillTool(BaseTool):
    """通过通用 Agent 工具协议暴露受限的 Skill 检索能力。"""

    name = "search_cmo_skill"
    description = (
        "在允许读取的 CMOLua Skill 文档中检索，返回相对路径、"
        "区域、行号和摘要。"
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "要在 CMOLua Skill 中检索的文本。",
            },
            "area": {
                "type": "string",
                "enum": sorted(_ALLOWED_AREAS),
                "description": "可选的 Skill 文档区域。",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": _MAX_LIMIT,
                "default": _DEFAULT_LIMIT,
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    }
    toolset = "cmolua"
    requires_approval = False

    def __init__(self, *, skill_repository: CmoSkillRepository) -> None:
        if not isinstance(skill_repository, CmoSkillRepository):
            raise TypeError("skill_repository 必须是 CmoSkillRepository")
        self._skill_repository = skill_repository

    def execute(
        self,
        arguments: dict[str, Any],
        context: ToolContext | None = None,
    ) -> ToolResult:
        if context is not None:
            context.progress.tool_started("正在检索 CMOLua Skill")

        try:
            query = self._read_non_blank_string(arguments, "query")
            area = self._read_area(arguments)
            limit = self._read_limit(arguments)
            if context is not None:
                context.progress.step_started(
                    "search",
                    "正在检索 Skill 文档",
                    query,
                )

            hits = self._skill_repository.search(
                query,
                area=area,
                limit=limit,
            )
            payload = {
                "success": True,
                "query": query,
                "count": len(hits),
                "hits": [
                    {
                        "relative_path": hit.relative_path,
                        "area": hit.area,
                        "line_number": hit.line_number,
                        "snippet": hit.snippet,
                    }
                    for hit in hits
                ],
            }
            if context is not None:
                context.progress.step_completed(
                    "search",
                    f"找到 {len(hits)} 条 Skill 结果",
                )
                context.progress.tool_completed("CMOLua Skill 检索完成")
            return self._result(payload)

        except (ValueError, CmoSkillAccessError) as exc:
            return self._failure(
                code="invalid_skill_search_request",
                message=str(exc),
                context=context,
            )
        except CmoSkillInfrastructureError as exc:
            return self._failure(
                code="skill_repository_unavailable",
                message=str(exc),
                context=context,
            )
        except Exception as exc:
            return self._failure(
                code="skill_search_failed",
                message=str(exc) or type(exc).__name__,
                context=context,
                error_type=type(exc).__name__,
            )

    @staticmethod
    def _read_non_blank_string(arguments: dict[str, Any], field_name: str) -> str:
        value = arguments.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} 必须是非空字符串")
        return value.strip()

    def _read_area(self, arguments: dict[str, Any]) -> str | None:
        value = arguments.get("area")
        if value is None:
            return None
        area = self._read_non_blank_string(arguments, "area")
        if area not in _ALLOWED_AREAS:
            raise ValueError(f"不支持的 Skill 区域：{area}")
        return area

    @staticmethod
    def _read_limit(arguments: dict[str, Any]) -> int:
        value = arguments.get("limit", _DEFAULT_LIMIT)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("limit 必须是整数")
        if not 1 <= value <= _MAX_LIMIT:
            raise ValueError(f"limit 必须位于 1..{_MAX_LIMIT} 范围内")
        return value

    @staticmethod
    def _result(payload: dict[str, Any], *, is_error: bool = False) -> ToolResult:
        return ToolResult(
            content=json.dumps(payload, ensure_ascii=False, indent=2),
            is_error=is_error,
        )

    def _failure(
        self,
        *,
        code: str,
        message: str,
        context: ToolContext | None,
        error_type: str | None = None,
    ) -> ToolResult:
        if context is not None:
            context.progress.tool_failed("CMOLua Skill 检索失败", message)
        error: dict[str, str] = {"code": code, "message": message}
        if error_type is not None:
            error["type"] = error_type
        return self._result({"success": False, "error": error}, is_error=True)


__all__ = ["SearchCmoSkillTool"]
