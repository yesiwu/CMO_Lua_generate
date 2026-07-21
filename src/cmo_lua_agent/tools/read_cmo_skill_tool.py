"""CMOLua Skill 仓库受限读取工具适配器。"""

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


_DEFAULT_MAX_RESPONSE_CHARS = 24_000
_DEFAULT_LINE_LIMIT = 120
_MAX_LINE_LIMIT = 200


class ReadCmoSkillTool(BaseTool):
    """将仓库的安全按行读取能力暴露为 Agent 工具。"""

    name = "read_cmo_skill"
    description = (
        "读取受允许的 CMOLua Skill 文档中限定行范围的内容。"
        "应先使用 search_cmo_skill 获取相对路径。"
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "relative_path": {
                "type": "string",
                "description": "由 search_cmo_skill 返回的相对路径。",
            },
            "start_line": {
                "type": "integer",
                "minimum": 1,
                "default": 1,
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": _MAX_LINE_LIMIT,
                "default": _DEFAULT_LINE_LIMIT,
            },
        },
        "required": ["relative_path"],
        "additionalProperties": False,
    }
    toolset = "cmolua"
    requires_approval = False

    def __init__(
        self,
        *,
        skill_repository: CmoSkillRepository,
        max_response_chars: int = _DEFAULT_MAX_RESPONSE_CHARS,
    ) -> None:
        if not isinstance(skill_repository, CmoSkillRepository):
            raise TypeError("skill_repository 必须是 CmoSkillRepository")
        if isinstance(max_response_chars, bool) or max_response_chars < 1:
            raise ValueError("max_response_chars 必须是正整数")

        self._skill_repository = skill_repository
        self._max_response_chars = max_response_chars

    def execute(
        self,
        arguments: dict[str, Any],
        context: ToolContext | None = None,
    ) -> ToolResult:
        """读取允许范围内的 Skill 文档并返回结构化工具结果。"""
        if context is not None:
            context.progress.tool_started("正在加载 CMOLua Skill 文档")

        try:
            relative_path = self._read_non_blank_string(arguments, "relative_path")
            start_line = self._read_integer(
                arguments, "start_line", default=1, minimum=1
            )
            line_limit = self._read_integer(
                arguments,
                "limit",
                default=_DEFAULT_LINE_LIMIT,
                minimum=1,
                maximum=_MAX_LINE_LIMIT,
            )
            if context is not None:
                context.progress.step_started(
                    "read",
                    "正在读取 Skill 文档行范围",
                    f"{relative_path}:{start_line}+{line_limit}",
                )

            read_result = self._skill_repository.read(
                relative_path,
                start_line=start_line,
                limit=line_limit,
            )
            text, content_truncated = self._truncate_text(read_result.text)
            payload = {
                "success": True,
                "relative_path": read_result.relative_path,
                "start_line": read_result.start_line,
                "end_line": read_result.end_line,
                "text": text,
                "truncated": read_result.truncated or content_truncated,
                "content_truncated": content_truncated,
            }

            if context is not None:
                context.progress.step_completed(
                    "read",
                    "Skill 文档读取完成",
                    f"{read_result.relative_path}:"
                    f"{read_result.start_line}-{read_result.end_line}",
                )
                context.progress.tool_completed("CMOLua Skill 文档加载完成")
            return self._result(payload)

        except (ValueError, CmoSkillAccessError) as exc:
            return self._failure(
                code="invalid_skill_read_request",
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
                code="skill_read_failed",
                message=str(exc) or type(exc).__name__,
                context=context,
                error_type=type(exc).__name__,
            )

    def _truncate_text(self, text: str) -> tuple[str, bool]:
        if len(text) <= self._max_response_chars:
            return text, False
        return text[: self._max_response_chars], True

    @staticmethod
    def _read_non_blank_string(arguments: dict[str, Any], field_name: str) -> str:
        value = arguments.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} 必须是非空字符串")
        return value.strip()

    @staticmethod
    def _read_integer(
        arguments: dict[str, Any],
        field_name: str,
        *,
        default: int,
        minimum: int,
        maximum: int | None = None,
    ) -> int:
        value = arguments.get(field_name, default)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{field_name} 必须是整数")
        if value < minimum or (maximum is not None and value > maximum):
            upper = f"..{maximum}" if maximum is not None else "+"
            raise ValueError(f"{field_name} 必须位于 {minimum}{upper} 范围内")
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
            context.progress.tool_failed("CMOLua Skill 文档读取失败", message)
        error: dict[str, str] = {"code": code, "message": message}
        if error_type is not None:
            error["type"] = error_type
        return self._result({"success": False, "error": error}, is_error=True)


__all__ = ["ReadCmoSkillTool"]
