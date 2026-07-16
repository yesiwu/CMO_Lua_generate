"""
受限文件读取工具。

只允许读取工作区内的文本文件。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cmo_lua_agent.tools.tool_base.base import BaseTool
from cmo_lua_agent.tools.tool_base.context import ToolContext


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "读取工作区中的文本文件。"

    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "相对于工作区的文件路径",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "description": "最多读取多少行",
            },
        },
        "required": ["path"],
        "additionalProperties": False,
    }

    def __init__(self, workdir: Path):
        self._workdir = workdir.resolve()

    def _safe_path(self, raw_path: str) -> Path:
        candidate = Path(raw_path).expanduser()

        if candidate.is_absolute():
            return candidate.resolve()

        return (self._workdir / candidate).resolve()

    def execute(self, arguments: dict[str, Any], context: ToolContext | None = None) -> str:
        raw_path = arguments["path"]
        limit = arguments.get("limit")

        path = self._safe_path(raw_path)
        if context is not None:
            context.progress.tool_started("读取文件")
        lines = path.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()

        if limit is not None and limit < len(lines):
            remaining = len(lines) - limit
            lines = lines[:limit]
            lines.append(f"... ({remaining} more lines)")

        result = "\n".join(lines)
        if context is not None:
            context.progress.tool_completed("文件读取完成", detail=f"{len(lines)} 行")
        return result
