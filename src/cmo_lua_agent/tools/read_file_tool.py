"""受限文本文件读取工具。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cmo_lua_agent.tools.tool_base.base import BaseTool, ToolResult
from cmo_lua_agent.tools.tool_base.context import ToolContext
from cmo_lua_agent.tools.workspace_artifacts import WorkspaceArtifactStore
from cmo_lua_agent.tools.workspace_policy import WorkspacePathError, WorkspacePathPolicy


class ReadFileTool(BaseTool):
    """读取文本文件；目录应由 ``list_directory`` 处理。"""

    name = "read_file"
    description = "读取文本文件。目录请使用 list_directory 列出内容。"
    _BINARY_SUFFIXES = frozenset(
        {
            ".7z", ".avi", ".bin", ".bmp", ".db", ".dll", ".doc",
            ".docx", ".exe", ".gif", ".gz", ".ico", ".jpeg", ".jpg",
            ".mp3", ".mp4", ".pdf", ".png", ".pyc", ".sqlite", ".tar",
            ".wav", ".webp", ".xls", ".xlsx", ".zip",
        }
    )

    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "工作区内要读取的文件路径；不得包含隐藏路径组成部分。",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "description": "最多读取的行数。",
            },
            "start_line": {
                "type": "integer",
                "minimum": 1,
                "description": "开始行号，从 1 开始。",
            },
            "end_line": {
                "type": "integer",
                "minimum": 1,
                "description": "结束行号（含该行）。",
            },
        },
        "required": ["path"],
        "additionalProperties": False,
    }

    def __init__(self, workdir: Path, *, max_inline_chars: int = 12_000) -> None:
        self._workdir = workdir.resolve()
        self._paths = WorkspacePathPolicy(self._workdir)
        self._artifacts = WorkspaceArtifactStore(
            self._workdir, max_inline_chars=max_inline_chars
        )

    def _safe_path(self, raw_path: str) -> Path:
        return self._paths.resolve_file(raw_path)

    def execute(
        self,
        arguments: dict[str, Any],
        context: ToolContext | None = None,
    ) -> str | ToolResult:
        raw_path = arguments.get("path")
        limit = arguments.get("limit")
        start_line = arguments.get("start_line", 1)
        end_line = arguments.get("end_line")

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
        if (
            not isinstance(start_line, int)
            or isinstance(start_line, bool)
            or start_line < 1
            or (
                end_line is not None
                and (
                    not isinstance(end_line, int)
                    or isinstance(end_line, bool)
                    or end_line < start_line
                )
            )
        ):
            return self._failure(
                code="invalid_line_range",
                message="start_line 和 end_line 必须组成从 1 开始的有效行区间。",
                context=context,
            )
        if limit is not None and end_line is not None:
            return self._failure(
                code="conflicting_line_range",
                message="limit 与 end_line 不能同时提供。",
                context=context,
            )

        try:
            path = self._safe_path(raw_path)
        except WorkspacePathError as exc:
            return self._failure(code=exc.code, message=exc.message, context=context)
        if context is not None:
            context.progress.tool_started("正在读取文件")

        if path.is_dir():
            return self._failure(
                code="path_is_directory",
                message=f"目标路径是目录，不能使用 read_file：{path}",
                context=context,
                suggested_tool="list_directory",
            )
        if path.suffix.casefold() in self._BINARY_SUFFIXES:
            return self._failure(
                code="binary_file_not_supported",
                message=f"不支持读取二进制文件：{path}",
                context=context,
            )

        try:
            raw = path.read_bytes()
            if b"\x00" in raw[:8192]:
                return self._failure(
                    code="binary_file_not_supported",
                    message=f"不支持读取二进制文件：{path}",
                    context=context,
                )
            lines = raw.decode("utf-8").splitlines()
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
        except UnicodeDecodeError:
            return self._failure(
                code="binary_file_not_supported",
                message=f"文件不是 UTF-8 文本，不能作为文本读取：{path}",
                context=context,
            )
        except OSError as exc:
            return self._failure(
                code="file_read_failed",
                message=f"读取文件失败：{path} ({exc})",
                context=context,
            )

        start_index = start_line - 1
        if limit is not None:
            end_index = start_index + limit
        elif end_line is not None:
            end_index = end_line
        else:
            end_index = len(lines)
        lines = lines[start_index:end_index]

        result = "\n".join(lines)
        if context is not None:
            context.progress.tool_completed("文件读取完成", detail=f"{len(lines)} 行")
        return self._artifacts.inline_or_store(result, kind="read")

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
