"""Approval-gated, exact text replacement tool for workspace files."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from cmo_lua_agent.tools.tool_base.base import BaseTool, ToolResult
from cmo_lua_agent.tools.tool_base.context import ToolContext
from cmo_lua_agent.tools.workspace_policy import WorkspacePathError, WorkspacePathPolicy


class EditFileTool(BaseTool):
    """Modify an existing workspace text file through verified replacements."""

    name = "edit_file"
    description = (
        "在工作区内对已存在的文本文件执行精确替换。调用前必须先读取文件、说明变更，"
        "并获得用户同意；本工具会再次请求人工审批。"
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "工作区内已有文本文件的路径。",
            },
            "replacements": {
                "type": "array",
                "minItems": 1,
                "maxItems": 20,
                "items": {
                    "type": "object",
                    "properties": {
                        "old_text": {"type": "string", "minLength": 1},
                        "new_text": {"type": "string"},
                        "expected_count": {"type": "integer", "minimum": 1},
                    },
                    "required": ["old_text", "new_text"],
                    "additionalProperties": False,
                },
                "description": "每项精确替换；未提供 expected_count 时默认必须命中一次。",
            },
        },
        "required": ["path", "replacements"],
        "additionalProperties": False,
    }
    toolset = "common"
    requires_approval = True

    _TEXT_SUFFIXES = frozenset(
        {".json", ".md", ".txt", ".lua", ".py", ".yaml", ".yml", ".toml", ".ini", ".csv"}
    )
    _MAX_BYTES = 2 * 1024 * 1024

    def __init__(self, *, workdir: Path) -> None:
        self._workdir = Path(workdir).resolve(strict=False)
        self._paths = WorkspacePathPolicy(self._workdir)

    def execute(
        self,
        arguments: dict[str, Any],
        context: ToolContext | None = None,
    ) -> ToolResult:
        if context is not None:
            context.progress.tool_started("正在修改文件")
            context.progress.step_started("validate", "正在校验替换内容和目标路径")
        try:
            path = self._resolve_target(arguments)
            replacements = self._parse_replacements(arguments)
            original = self._read_text(path)
            updated = self._apply_replacements(original, replacements)
            if context is not None:
                context.progress.step_completed("validate", "替换内容校验完成")
                context.progress.step_started("write", "正在原子写入文件")
            self._atomic_write(path, updated)
        except _EditError as exc:
            return self._failure(exc.code, exc.message, context)
        except OSError as exc:
            return self._failure("file_write_failed", f"文件修改失败：{exc}", context)

        if context is not None:
            context.progress.step_completed("write", "文件修改完成", str(path))
            context.progress.tool_completed("文件已安全修改")
        return ToolResult(
            content=json.dumps(
                {
                    "success": True,
                    "path": str(path),
                    "replacements": len(replacements),
                    "characters_before": len(original),
                    "characters_after": len(updated),
                },
                ensure_ascii=False,
                indent=2,
            )
        )

    def _resolve_target(self, arguments: dict[str, Any]) -> Path:
        self._reject_unknown_arguments(arguments)
        raw_path = arguments.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise _EditError("invalid_path", "path 必须是非空字符串")
        try:
            path = self._paths.resolve_file(raw_path)
        except WorkspacePathError as exc:
            raise _EditError(exc.code, exc.message) from exc
        if path.suffix.lower() not in self._TEXT_SUFFIXES:
            raise _EditError("unsupported_file_type", "只允许修改受支持的文本文件")
        if not path.is_file():
            raise _EditError("file_not_found", f"文件不存在：{path}")
        return path

    @staticmethod
    def _reject_unknown_arguments(arguments: dict[str, Any]) -> None:
        if not isinstance(arguments, dict):
            raise _EditError("invalid_request", "编辑参数必须是对象")
        unknown = set(arguments).difference({"path", "replacements"})
        if unknown:
            raise _EditError("invalid_request", "不支持的参数：" + ", ".join(sorted(unknown)))

    @staticmethod
    def _parse_replacements(arguments: dict[str, Any]) -> list[tuple[str, str, int]]:
        raw_replacements = arguments.get("replacements")
        if not isinstance(raw_replacements, list) or not raw_replacements:
            raise _EditError("invalid_replacements", "replacements 必须是非空数组")
        if len(raw_replacements) > 20:
            raise _EditError("invalid_replacements", "一次最多允许 20 项替换")

        parsed: list[tuple[str, str, int]] = []
        seen: set[str] = set()
        for index, item in enumerate(raw_replacements):
            if not isinstance(item, dict) or set(item).difference(
                {"old_text", "new_text", "expected_count"}
            ):
                raise _EditError("invalid_replacements", f"第 {index + 1} 项替换格式无效")
            old_text = item.get("old_text")
            new_text = item.get("new_text")
            expected_count = item.get("expected_count", 1)
            if not isinstance(old_text, str) or not old_text:
                raise _EditError("invalid_replacements", f"第 {index + 1} 项 old_text 必须非空")
            if not isinstance(new_text, str):
                raise _EditError("invalid_replacements", f"第 {index + 1} 项 new_text 必须是字符串")
            if isinstance(expected_count, bool) or not isinstance(expected_count, int) or expected_count < 1:
                raise _EditError("invalid_replacements", f"第 {index + 1} 项 expected_count 必须是正整数")
            if old_text in seen:
                raise _EditError("invalid_replacements", "同一 old_text 不能重复出现")
            seen.add(old_text)
            parsed.append((old_text, new_text, expected_count))
        return parsed

    def _read_text(self, path: Path) -> str:
        if path.stat().st_size > self._MAX_BYTES:
            raise _EditError("file_too_large", "文件超过 2 MiB，拒绝自动修改")
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise _EditError("unsupported_encoding", "只允许修改 UTF-8 文本文件") from exc

    @staticmethod
    def _apply_replacements(
        original: str,
        replacements: list[tuple[str, str, int]],
    ) -> str:
        for old_text, _new_text, expected_count in replacements:
            actual_count = original.count(old_text)
            if actual_count != expected_count:
                raise _EditError(
                    "replacement_count_mismatch",
                    f"替换目标命中 {actual_count} 次，预期 {expected_count} 次；文件未修改",
                )

        updated = original
        for old_text, new_text, _expected_count in replacements:
            updated = updated.replace(old_text, new_text)
        return updated

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        descriptor, temporary_name = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            text=True,
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _failure(code: str, message: str, context: ToolContext | None) -> ToolResult:
        if context is not None:
            context.progress.tool_failed("文件修改失败", message)
        return ToolResult(
            content=json.dumps(
                {"success": False, "error": {"code": code, "message": message}},
                ensure_ascii=False,
                indent=2,
            ),
            is_error=True,
        )


class _EditError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


__all__ = ["EditFileTool"]
