"""主 Agent 的通用工作区文本搜索工具。

它用于先定位定义和调用关系，再把命中的文件交给 ``read_file`` 精读。搜索范围
与所有主 Agent 文件工具共享 ``WorkspacePathPolicy``，因此不会扫描点号目录、
工作区外路径或符号链接，也不会把二进制文件误送入模型上下文。
"""

from __future__ import annotations

import fnmatch
import json
import os
from pathlib import Path
from typing import Any, Iterator

from cmo_lua_agent.tools.tool_base.base import BaseTool, ToolResult
from cmo_lua_agent.tools.tool_base.context import ToolContext
from cmo_lua_agent.tools.workspace_artifacts import WorkspaceArtifactStore
from cmo_lua_agent.tools.workspace_policy import WorkspacePathError, WorkspacePathPolicy


class SearchWorkspaceTool(BaseTool):
    """在一个或多个可见目录中执行纯文本搜索。"""

    name = "search_workspace"
    description = "在工作区文本文件中搜索字符串，返回文件、行号和命中行。"
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "要查找的非空文本。"},
            "paths": {
                "type": "array",
                "items": {"type": "string"},
                "default": ["."],
                "description": "要搜索的文件或目录，相对于工作区。",
            },
            "glob": {
                "type": "string",
                "description": "可选文件名模式，例如 *.py 或 *.json。",
            },
            "max_results": {
                "type": "integer",
                "minimum": 1,
                "maximum": 1000,
                "default": 200,
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def __init__(self, workdir: Path, *, max_inline_chars: int = 12_000) -> None:
        self._workdir = Path(workdir).resolve()
        self._paths = WorkspacePathPolicy(self._workdir)
        self._artifacts = WorkspaceArtifactStore(
            self._workdir, max_inline_chars=max_inline_chars
        )

    def execute(
        self,
        arguments: dict[str, Any],
        context: ToolContext | None = None,
    ) -> str | ToolResult:
        query = arguments.get("query")
        raw_paths = arguments.get("paths", ["."])
        glob = arguments.get("glob")
        max_results = arguments.get("max_results", 200)
        if not isinstance(query, str) or not query:
            return self._failure("invalid_query", "query 必须是非空字符串。", context)
        if not isinstance(raw_paths, list) or not raw_paths or not all(
            isinstance(item, str) for item in raw_paths
        ):
            return self._failure("invalid_paths", "paths 必须是非空字符串数组。", context)
        if glob is not None and (not isinstance(glob, str) or not glob):
            return self._failure("invalid_glob", "glob 必须是非空字符串。", context)
        if (
            not isinstance(max_results, int)
            or isinstance(max_results, bool)
            or not 1 <= max_results <= 1000
        ):
            return self._failure(
                "invalid_max_results", "max_results 必须是 1 到 1000 的整数。", context
            )

        try:
            roots = [self._resolve_search_root(item) for item in raw_paths]
        except WorkspacePathError as exc:
            return self._failure(exc.code, exc.message, context)
        if context is not None:
            context.progress.tool_started("正在搜索工作区")

        results: list[str] = []
        try:
            for root in roots:
                for path in self._iter_files(root, glob):
                    if self._is_binary(path):
                        continue
                    try:
                        lines = path.read_text(encoding="utf-8").splitlines()
                    except (UnicodeDecodeError, OSError):
                        continue
                    relative = path.relative_to(self._workdir).as_posix()
                    for line_number, line in enumerate(lines, start=1):
                        if query in line:
                            results.append(f"{relative}:{line_number}:{line}")
                            if len(results) >= max_results:
                                break
                    if len(results) >= max_results:
                        break
                if len(results) >= max_results:
                    break
        except OSError as exc:
            return self._failure("workspace_search_failed", f"搜索失败：{exc}", context)

        content = "\n".join(results)
        if not content:
            content = "未找到匹配内容。"
        output = self._artifacts.inline_or_store(content, kind="search")
        if context is not None:
            context.progress.tool_completed("搜索完成", detail=f"{len(results)} 条命中")
        return output

    def _resolve_search_root(self, raw_path: str) -> Path:
        path = self._paths.resolve_file(raw_path)
        if not path.exists():
            raise WorkspacePathError("path_not_found", f"搜索路径不存在：{path}")
        return path

    def _iter_files(self, root: Path, glob: str | None) -> Iterator[Path]:
        if root.is_file():
            if glob is None or fnmatch.fnmatch(root.name, glob):
                yield root
            return
        for directory, directory_names, file_names in os.walk(root, followlinks=False):
            directory_names[:] = sorted(
                name
                for name in directory_names
                if not name.startswith(".")
                and not (Path(directory) / name).is_symlink()
            )
            for name in sorted(file_names):
                path = Path(directory) / name
                if name.startswith(".") or path.is_symlink():
                    continue
                if glob is not None and not fnmatch.fnmatch(name, glob):
                    continue
                yield path

    @staticmethod
    def _is_binary(path: Path) -> bool:
        try:
            with path.open("rb") as stream:
                return b"\x00" in stream.read(8192)
        except OSError:
            return True

    @staticmethod
    def _failure(code: str, message: str, context: ToolContext | None) -> ToolResult:
        if context is not None:
            context.progress.tool_failed("工作区搜索失败", detail=message)
        return ToolResult(
            content=json.dumps(
                {"success": False, "error": {"code": code, "message": message}},
                ensure_ascii=False,
            ),
            is_error=True,
        )


__all__ = ["SearchWorkspaceTool"]
