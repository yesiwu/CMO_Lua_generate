"""Approval-gated, field-level JSON copy tool for scenario repairs."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from cmo_lua_agent.tools.edit_file_tool import _EditError
from cmo_lua_agent.tools.tool_base.base import BaseTool, ToolResult
from cmo_lua_agent.tools.tool_base.context import ToolContext


class CreateJsonCopyTool(BaseTool):
    """Create a JSON copy and replace only existing JSON Pointer fields."""

    name = "create_json_copy"
    description = (
        "从工作区内既有 JSON 创建一个新副本，并按 JSON Pointer 精确替换已有字段。"
        "绝不覆盖原文件或目标文件；调用前必须取得用户同意，随后还会请求人工审批。"
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "source_path": {"type": "string"},
            "patches": {
                "type": "array",
                "minItems": 1,
                "maxItems": 30,
                "items": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}, "value": {}},
                    "required": ["path", "value"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["path", "source_path", "patches"],
        "additionalProperties": False,
    }
    toolset = "common"
    requires_approval = True
    _MAX_BYTES = 2 * 1024 * 1024

    def __init__(self, *, workdir: Path) -> None:
        self._workdir = Path(workdir).resolve(strict=False)

    def execute(self, arguments: dict[str, Any], context: ToolContext | None = None) -> ToolResult:
        if context is not None:
            context.progress.tool_started("正在创建 JSON 修复副本")
            context.progress.step_started("validate", "正在校验 JSON 路径和字段补丁")
        try:
            target = self._path(arguments.get("path"), must_exist=False)
            source = self._path(arguments.get("source_path"), must_exist=True)
            document = self._read_json(source)
            patches = self._patches(arguments.get("patches"))
            for pointer, value in patches:
                _replace_existing_pointer(document, pointer, value)
            self._create(target, json.dumps(document, ensure_ascii=False, indent=2) + "\n")
        except _EditError as exc:
            return self._failure(exc.code, exc.message, context)
        except (OSError, TypeError, ValueError) as exc:
            return self._failure("json_copy_failed", f"创建 JSON 副本失败：{exc}", context)

        if context is not None:
            context.progress.step_completed("validate", "JSON 补丁校验完成")
            context.progress.tool_completed("JSON 修复副本已创建")
        return ToolResult(content=json.dumps({"success": True, "path": str(target), "source_path": str(source), "mode": "copy_with_json_patches", "patches": len(patches)}, ensure_ascii=False, indent=2))

    def _path(self, raw: Any, *, must_exist: bool) -> Path:
        if not isinstance(raw, str) or not raw.strip():
            raise _EditError("invalid_path", "路径必须是非空字符串")
        candidate = Path(raw).expanduser()
        path = candidate.resolve(strict=False) if candidate.is_absolute() else (self._workdir / candidate).resolve(strict=False)
        if not path.is_relative_to(self._workdir):
            raise _EditError("path_outside_workspace", "只能访问工作区内的 JSON 文件")
        if path.suffix.lower() != ".json":
            raise _EditError("unsupported_file_type", "只允许 .json 文件")
        if must_exist and not path.is_file():
            raise _EditError("file_not_found", f"源文件不存在：{path}")
        if not must_exist and path.exists():
            raise _EditError("file_already_exists", "目标文件已存在，拒绝覆盖")
        return path

    def _read_json(self, path: Path) -> Any:
        if path.stat().st_size > self._MAX_BYTES:
            raise _EditError("file_too_large", "JSON 文件超过 2 MiB")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except UnicodeDecodeError as exc:
            raise _EditError("unsupported_encoding", "只允许 UTF-8 JSON 文件") from exc
        except json.JSONDecodeError as exc:
            raise _EditError("invalid_json", f"源文件不是合法 JSON：{exc.msg}") from exc

    @staticmethod
    def _patches(value: Any) -> list[tuple[str, Any]]:
        if not isinstance(value, list) or not value or len(value) > 30:
            raise _EditError("invalid_patches", "patches 必须是 1 至 30 项的数组")
        result: list[tuple[str, Any]] = []
        seen: set[str] = set()
        for index, patch in enumerate(value):
            if not isinstance(patch, dict) or set(patch) != {"path", "value"}:
                raise _EditError("invalid_patches", f"第 {index + 1} 项补丁格式无效")
            pointer = patch["path"]
            if not isinstance(pointer, str) or not pointer.startswith("/") or pointer in seen:
                raise _EditError("invalid_patches", f"第 {index + 1} 项 path 必须是唯一 JSON Pointer")
            seen.add(pointer)
            result.append((pointer, patch["value"]))
        return result

    @staticmethod
    def _create(path: Path, content: str) -> None:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _failure(code: str, message: str, context: ToolContext | None) -> ToolResult:
        if context is not None:
            context.progress.tool_failed("创建 JSON 修复副本失败", message)
        return ToolResult(content=json.dumps({"success": False, "error": {"code": code, "message": message}}, ensure_ascii=False, indent=2), is_error=True)


def _replace_existing_pointer(document: Any, pointer: str, value: Any) -> None:
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]
    current = document
    for part in parts[:-1]:
        current = _pointer_child(current, part, pointer)
    key = parts[-1]
    if isinstance(current, dict):
        if key not in current:
            raise _EditError("json_pointer_not_found", f"JSON 字段不存在：{pointer}")
        current[key] = value
        return
    if isinstance(current, list) and key.isdigit() and int(key) < len(current):
        current[int(key)] = value
        return
    raise _EditError("json_pointer_not_found", f"JSON 字段不存在：{pointer}")


def _pointer_child(current: Any, key: str, pointer: str) -> Any:
    if isinstance(current, dict) and key in current:
        return current[key]
    if isinstance(current, list) and key.isdigit() and int(key) < len(current):
        return current[int(key)]
    raise _EditError("json_pointer_not_found", f"JSON 字段不存在：{pointer}")


__all__ = ["CreateJsonCopyTool"]
