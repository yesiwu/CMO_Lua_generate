"""受限文本文件读取工具。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cmo_lua_agent.tools.tool_base.base import BaseTool, ToolResult
from cmo_lua_agent.tools.tool_base.context import ToolContext


class ReadFileTool(BaseTool):
    """读取文本文件；目录应由 ``list_directory`` 处理。"""

    name = "read_file"
    description = "读取文本文件。目录请使用 list_directory 列出内容。"

    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "要读取的文件路径，可为绝对路径。",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "description": "最多读取的行数。",
            },
        },
        "required": ["path"],
        "additionalProperties": False,
    }

    def __init__(self, workdir: Path) -> None:
        self._workdir = workdir.resolve()

    def _safe_path(self, raw_path: str) -> Path:
        candidate = Path(raw_path).expanduser()
        if candidate.is_absolute():
            return candidate.resolve()
        return (self._workdir / candidate).resolve()

    def execute(
        self,
        arguments: dict[str, Any],
        context: ToolContext | None = None,
    ) -> str | ToolResult:
        raw_path = arguments.get("path")
        limit = arguments.get("limit")

        if not isinstance(raw_path, str) or not raw_path.strip():
            return self._failure(
                code="invalid_path",
                message="path 必须是非空字符串。",
                context=context,
            )

        if limit is not None and (
            not isinstance(limit, int) or isinstance(limit, bool) or limit < 1
        ):
            return self._failure(
                code="invalid_limit",
                message="limit 必须是大于 0 的整数。",
                context=context,
            )

        path = self._safe_path(raw_path)
        if context is not None:
            context.progress.tool_started("正在读取文件")

        if path.is_dir():
            return self._failure(
                code="path_is_directory",
                message=f"目标路径是目录，不能使用 read_file：{path}",
                context=context,
                suggested_tool="list_directory",
            )

        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except FileNotFoundError:
            return self._failure(
                code="file_not_found",
                message=f"文件不存在：{path}",
                context=context,
            )
        except PermissionError as exc:
            return self._failure(
                code="file_access_denied",
                message=f"无法读取文件：{path} ({exc})",
                context=context,
            )
        except OSError as exc:
            return self._failure(
                code="file_read_failed",
                message=f"读取文件失败：{path} ({exc})",
                context=context,
            )

        if limit is not None and limit < len(lines):
            remaining = len(lines) - limit
            lines = lines[:limit]
            lines.append(f"... ({remaining} more lines)")

        result = "\n".join(lines)
        if context is not None:
            context.progress.tool_completed("文件读取完成", detail=f"{len(lines)} 行")
        return result

    @staticmethod
    def _failure(
        *,
        code: str,
        message: str,
        context: ToolContext | None,
        suggested_tool: str | None = None,
    ) -> ToolResult:
        if context is not None:
            context.progress.tool_failed("文件读取失败", detail=message)

        error: dict[str, str] = {"code": code, "message": message}
        if suggested_tool is not None:
            error["suggested_tool"] = suggested_tool
        return ToolResult(
            content=json.dumps({"success": False, "error": error}, ensure_ascii=False),
            is_error=True,
        )


__all__ = ["ReadFileTool"]
