"""Approval-gated new text-file creation with optional safe source copying."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from cmo_lua_agent.tools.edit_file_tool import EditFileTool, _EditError
from cmo_lua_agent.tools.tool_base.base import BaseTool, ToolResult
from cmo_lua_agent.tools.tool_base.context import ToolContext
from cmo_lua_agent.tools.workspace_policy import WorkspacePathError, WorkspacePathPolicy


class CreateFileTool(BaseTool):
    """Create a new workspace text file and never overwrite an existing path."""

    name = "create_file"
    description = (
        "在工作区内新建一个文本文件，绝不覆盖已有文件。"
        "可提供完整 content，或从 source_path 复制后执行精确 replacements。"
        "调用前必须说明变更并获得用户同意；本工具会请求人工审批。"
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "工作区内的新文件路径，必须不存在。"},
            "content": {"type": "string", "description": "新文件完整 UTF-8 文本。"},
            "source_path": {"type": "string", "description": "复制模式下的工作区源文本文件。"},
            "replacements": EditFileTool.input_schema["properties"]["replacements"],
        },
        "required": ["path"],
        "additionalProperties": False,
    }
    toolset = "common"
    requires_approval = True

    _MAX_BYTES = EditFileTool._MAX_BYTES
    _TEXT_SUFFIXES = EditFileTool._TEXT_SUFFIXES

    def __init__(self, *, workdir: Path) -> None:
        self._workdir = Path(workdir).resolve(strict=False)
        self._paths = WorkspacePathPolicy(self._workdir)

    def execute(
        self,
        arguments: dict[str, Any],
        context: ToolContext | None = None,
    ) -> ToolResult:
        if context is not None:
            context.progress.tool_started("正在新建文件")
            context.progress.step_started("validate", "正在校验新文件路径和内容")
        try:
            target = self._resolve_new_path(arguments.get("path"), field_name="path")
            content, mode, replacement_count = self._build_content(arguments)
            if context is not None:
                context.progress.step_completed("validate", "新文件内容校验完成")
                context.progress.step_started("write", "正在原子创建文件")
            self._create_exclusive(target, content)
        except _EditError as exc:
            return self._failure(exc.code, exc.message, context)
        except FileExistsError:
            return self._failure("file_already_exists", "目标文件已存在，拒绝覆盖", context)
        except OSError as exc:
            return self._failure("file_create_failed", f"创建文件失败：{exc}", context)

        if context is not None:
            context.progress.step_completed("write", "新文件创建完成", str(target))
            context.progress.tool_completed("新文件已创建")
        return ToolResult(
            content=json.dumps(
                {
                    "success": True,
                    "path": str(target),
                    "mode": mode,
                    "replacements": replacement_count,
                    "characters": len(content),
                },
                ensure_ascii=False,
                indent=2,
            )
        )

    def _build_content(self, arguments: dict[str, Any]) -> tuple[str, str, int]:
        if not isinstance(arguments, dict):
            raise _EditError("invalid_request", "创建参数必须是对象")
        unknown = set(arguments).difference({"path", "content", "source_path", "replacements"})
        if unknown:
            raise _EditError("invalid_request", "不支持的参数：" + ", ".join(sorted(unknown)))

        has_content = "content" in arguments
        has_source = "source_path" in arguments or "replacements" in arguments
        if has_content == has_source:
            raise _EditError("invalid_request", "必须且只能选择 content 或 source_path 加 replacements")

        if has_content:
            content = arguments["content"]
            if not isinstance(content, str):
                raise _EditError("invalid_content", "content 必须是字符串")
            if len(content.encode("utf-8")) > self._MAX_BYTES:
                raise _EditError("file_too_large", "新文件内容超过 2 MiB")
            return content, "content", 0

        source_path = self._resolve_new_path(
            arguments.get("source_path"),
            field_name="source_path",
            must_exist=True,
        )
        replacements = EditFileTool._parse_replacements(arguments)
        try:
            source = source_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise _EditError("unsupported_encoding", "只允许复制 UTF-8 文本文件") from exc
        if len(source.encode("utf-8")) > self._MAX_BYTES:
            raise _EditError("file_too_large", "源文件超过 2 MiB")
        content = EditFileTool._apply_replacements(source, replacements)
        return content, "copy_with_replacements", len(replacements)

    def _resolve_new_path(
        self,
        raw_path: Any,
        *,
        field_name: str,
        must_exist: bool = False,
    ) -> Path:
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise _EditError("invalid_path", f"{field_name} 必须是非空字符串")
        try:
            path = self._paths.resolve_file(raw_path)
        except WorkspacePathError as exc:
            raise _EditError(exc.code, exc.message) from exc
        if path.suffix.lower() not in self._TEXT_SUFFIXES:
            raise _EditError("unsupported_file_type", "只允许受支持的文本文件")
        if must_exist:
            if not path.is_file():
                raise _EditError("file_not_found", f"源文件不存在：{path}")
        elif path.exists():
            raise _EditError("file_already_exists", "目标文件已存在，拒绝覆盖")
        return path

    @staticmethod
    def _create_exclusive(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _failure(code: str, message: str, context: ToolContext | None) -> ToolResult:
        if context is not None:
            context.progress.tool_failed("新建文件失败", message)
        return ToolResult(
            content=json.dumps(
                {"success": False, "error": {"code": code, "message": message}},
                ensure_ascii=False,
                indent=2,
            ),
            is_error=True,
        )


__all__ = ["CreateFileTool"]
