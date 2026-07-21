"""目录列表工具。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cmo_lua_agent.tools.tool_base.base import BaseTool, ToolResult
from cmo_lua_agent.tools.tool_base.context import ToolContext


class ListDirectoryTool(BaseTool):
    """列出目录的直接子项，不递归读取文件内容。"""

    name = "list_directory"
    description = "列出目录中的文件和子目录；目录不能使用 read_file 读取。"

    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "要列出的目录路径；省略时使用工作区根目录。",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 200,
                "default": 100,
                "description": "最多返回的直接子项数量。",
            },
        },
        "additionalProperties": False,
    }

    def __init__(self, workdir: Path) -> None:
        self._workdir = workdir.resolve()

    def _resolve_path(self, raw_path: str) -> Path:
        candidate = Path(raw_path).expanduser()
        if candidate.is_absolute():
            return candidate.resolve()
        return (self._workdir / candidate).resolve()

    def execute(
        self,
        arguments: dict[str, Any],
        context: ToolContext | None = None,
    ) -> ToolResult:
        raw_path = arguments.get("path", ".")
        limit = arguments.get("limit", 100)

        if not isinstance(raw_path, str) or not raw_path.strip():
            return self._failure("invalid_path", "path 必须是非空字符串。", context)
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= 200
        ):
            return self._failure(
                "invalid_limit",
                "limit 必须是 1 到 200 之间的整数。",
                context,
            )

        path = self._resolve_path(raw_path)
        if context is not None:
            context.progress.tool_started("正在列出目录")

        if not path.exists():
            return self._failure("directory_not_found", f"目录不存在：{path}", context)
        if not path.is_dir():
            return self._failure(
                "path_is_not_directory",
                f"目标路径不是目录：{path}",
                context,
                suggested_tool="read_file",
            )

        try:
            children = sorted(
                path.iterdir(),
                key=lambda item: (not item.is_dir(), item.name.casefold()),
            )
        except PermissionError as exc:
            return self._failure(
                "directory_access_denied",
                f"无法列出目录：{path} ({exc})",
                context,
            )
        except OSError as exc:
            return self._failure(
                "directory_list_failed",
                f"列出目录失败：{path} ({exc})",
                context,
            )

        entries = [
            {
                "name": item.name,
                "path": str(item),
                "type": "directory" if item.is_dir() else "file",
            }
            for item in children[:limit]
        ]
        payload = {
            "success": True,
            "path": str(path),
            "entries": entries,
            "truncated": len(children) > limit,
            "total_entries": len(children),
        }
        if context is not None:
            context.progress.tool_completed("目录列出完成", detail=f"{len(entries)} 项")
        return ToolResult(content=json.dumps(payload, ensure_ascii=False))

    @staticmethod
    def _failure(
        code: str,
        message: str,
        context: ToolContext | None,
        *,
        suggested_tool: str | None = None,
    ) -> ToolResult:
        if context is not None:
            context.progress.tool_failed("目录列出失败", detail=message)
        error: dict[str, str] = {"code": code, "message": message}
        if suggested_tool is not None:
            error["suggested_tool"] = suggested_tool
        return ToolResult(
            content=json.dumps({"success": False, "error": error}, ensure_ascii=False),
            is_error=True,
        )


__all__ = ["ListDirectoryTool"]
