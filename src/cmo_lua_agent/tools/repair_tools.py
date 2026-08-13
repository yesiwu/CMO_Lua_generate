"""CodeRepairAgent 专用的受限文件与诊断工具。

上游 ``CodeRepairAgent`` 为每次修复创建独立会话并注册本模块的六个工具；下游只会
访问 ``src/``、``scripts/``、``tests/`` 和本次 Workflow 的诊断 Artifact。模块不提供
Git 写操作、CMO 控制、Workflow 状态修改或删除能力，这些副作用始终由外层 Harness 管理。
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable
from uuid import uuid4

from cmo_lua_agent.tools.tool_base.base import BaseTool, ToolResult
from cmo_lua_agent.tools.tool_base.context import ToolContext
from cmo_lua_agent.tools.tool_base.registry import ToolRegistry


_REPAIR_ROOTS = (Path("src"), Path("scripts"), Path("tests"))
_SHELL_CONTROL_TOKENS = frozenset({"&&", "||", "|", ">", ">>", "<", ";"})


@dataclass(frozen=True, slots=True)
class RepairCommandRecord:
    """记录 Agent 内部执行过的诊断命令，供外层判断是否观察过测试结果。"""

    argv: tuple[str, ...]
    succeeded: bool
    exit_code: int
    artifact_path: str | None = None


@dataclass(slots=True)
class RepairToolSession:
    """保存一次修复工具循环的有限运行信息，不承担 Workflow 状态持久化。"""

    project_root: Path
    workflow_id: str
    attempt: int
    max_inline_chars: int = 12_000
    default_timeout_seconds: int = 300
    maximum_timeout_seconds: int = 900
    command_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None
    tests_run: list[RepairCommandRecord] = field(default_factory=list)
    _artifact_sequence: int = 0

    def __post_init__(self) -> None:
        self.project_root = Path(self.project_root).resolve()
        if not self.workflow_id or any(token in self.workflow_id for token in ("/", "\\", "..")):
            raise ValueError("invalid_repair_workflow_id")

    @property
    def artifact_root(self) -> Path:
        return self.project_root / "runs" / "training" / self.workflow_id / "repair-artifacts"

    def render_output(self, *, kind: str, content: str, extra: dict[str, Any] | None = None) -> str:
        """小结果直接返回；大结果完整落盘，只把摘要和可分页读取路径送回模型。"""

        payload: dict[str, Any] = dict(extra or {})
        if len(content) <= self.max_inline_chars:
            payload.update({"summary": content, "truncated": False, "artifact_path": None})
            return json.dumps(payload, ensure_ascii=False)
        self._artifact_sequence += 1
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        name = f"a{self.attempt:02d}-{self._artifact_sequence:04d}-{kind}.log"
        path = self.artifact_root / name
        path.write_text(content, encoding="utf-8", newline="\n")
        relative = path.relative_to(self.project_root).as_posix()
        half = max(1, self.max_inline_chars // 2)
        payload.update(
            {
                "summary": f"{content[:half]}\n\n……完整输出已保存……\n\n{content[-half:]}",
                "truncated": True,
                "artifact_path": relative,
            }
        )
        return json.dumps(payload, ensure_ascii=False)


class _RepairPathResolver:
    """集中执行路径边界检查，避免六个工具形成不同的安全口径。"""

    def __init__(self, session: RepairToolSession) -> None:
        self._session = session
        self._root = session.project_root

    def source(self, raw_path: object, *, must_exist: bool = False) -> Path:
        relative = self._relative(raw_path)
        candidate = self._root / relative
        resolved = candidate.resolve(strict=False)
        allowed = tuple((self._root / root).resolve(strict=False) for root in _REPAIR_ROOTS)
        if not any(resolved == root or resolved.is_relative_to(root) for root in allowed):
            raise PermissionError("路径不在 src/、scripts/ 或 tests/ 修复范围内")
        self._reject_symlink_components(candidate)
        if must_exist and not candidate.is_file():
            raise FileNotFoundError(f"修复文件不存在：{relative.as_posix()}")
        return candidate

    def readable(self, raw_path: object) -> Path:
        try:
            return self.source(raw_path, must_exist=True)
        except PermissionError:
            relative = self._relative(raw_path)
            candidate = self._root / relative
            resolved = candidate.resolve(strict=False)
            artifact_root = self._session.artifact_root.resolve(strict=False)
            if not (resolved == artifact_root or resolved.is_relative_to(artifact_root)):
                raise
            self._reject_symlink_components(candidate)
            if not candidate.is_file():
                raise FileNotFoundError(f"诊断 Artifact 不存在：{relative.as_posix()}")
            return candidate

    @staticmethod
    def _relative(raw_path: object) -> Path:
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError("path 必须是非空相对路径")
        path = Path(raw_path)
        if path.is_absolute() or ".." in path.parts:
            raise PermissionError("禁止绝对路径或父目录穿越")
        return path

    def _reject_symlink_components(self, candidate: Path) -> None:
        current = self._root
        try:
            relative = candidate.relative_to(self._root)
        except ValueError as exc:
            raise PermissionError("路径已经逃逸项目目录") from exc
        for part in relative.parts:
            current = current / part
            if current.exists() and current.is_symlink():
                raise PermissionError("禁止通过符号链接访问修复范围")


class _SessionTool(BaseTool):
    toolset = "code_repair"

    def __init__(self, session: RepairToolSession) -> None:
        self._session = session
        self._paths = _RepairPathResolver(session)


class SearchCodeTool(_SessionTool):
    name = "search_code"
    description = "在 src、scripts、tests 中搜索代码文本；大型结果会保存为可继续读取的 Artifact。"
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "paths": {"type": "array", "items": {"type": "string"}},
            "glob": {"type": "string"},
            "max_results": {"type": "integer", "minimum": 1, "maximum": 1000},
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def execute(self, arguments: dict[str, Any], context: ToolContext | None = None) -> ToolResult:
        query = arguments.get("query")
        if not isinstance(query, str) or not query:
            return ToolResult("query 必须是非空字符串", True)
        raw_paths = arguments.get("paths", ["src", "scripts", "tests"])
        if not isinstance(raw_paths, list) or not raw_paths:
            return ToolResult("paths 必须是非空相对路径数组", True)
        paths: list[Path] = []
        try:
            for raw in raw_paths:
                path = self._paths.source(raw)
                if path.exists():
                    paths.append(path)
        except (ValueError, PermissionError) as exc:
            return ToolResult(str(exc), True)
        if not paths:
            return ToolResult(json.dumps({"summary": "没有可搜索的目录", "truncated": False, "artifact_path": None}, ensure_ascii=False))
        limit = arguments.get("max_results", 200)
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 1000:
            return ToolResult("max_results 必须位于 1..1000", True)
        command = ["rg", "-n", "--no-heading", "--color", "never", "-F", query]
        glob = arguments.get("glob")
        if glob is not None:
            if not isinstance(glob, str) or not glob:
                return ToolResult("glob 必须是非空字符串", True)
            command.extend(["-g", glob])
        command.extend(str(path.relative_to(self._session.project_root)) for path in paths)
        try:
            completed = subprocess.run(command, cwd=self._session.project_root, text=True, capture_output=True, shell=False)
        except FileNotFoundError:
            return ToolResult("当前环境缺少 rg，无法执行代码搜索", True)
        if completed.returncode not in {0, 1}:
            return ToolResult(completed.stderr.strip() or "rg 搜索失败", True)
        output = "\n".join(completed.stdout.splitlines()[:limit])
        return ToolResult(self._session.render_output(kind="search", content=output))


class ReadRepairFileTool(_SessionTool):
    name = "read_repair_file"
    description = "按行读取允许范围内的源码或本次修复产生的诊断 Artifact。"
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "start_line": {"type": "integer", "minimum": 1},
            "end_line": {"type": "integer", "minimum": 1},
        },
        "required": ["path"],
        "additionalProperties": False,
    }

    def execute(self, arguments: dict[str, Any], context: ToolContext | None = None) -> ToolResult:
        try:
            path = self._paths.readable(arguments.get("path"))
            start = int(arguments.get("start_line", 1))
            end = int(arguments.get("end_line", start + 399))
            if start < 1 or end < start or end - start > 2000:
                raise ValueError("读取行范围无效或超过 2000 行")
            rows = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except (OSError, TypeError, ValueError, PermissionError) as exc:
            return ToolResult(str(exc), True)
        rendered = "\n".join(f"{index}: {rows[index - 1]}" for index in range(start, min(end, len(rows)) + 1))
        return ToolResult(rendered)


class EditRepairFileTool(_SessionTool):
    name = "edit_repair_file"
    description = "精确替换已有文件中唯一一次出现的文本；匹配零次或多次时拒绝修改。"
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "old_text": {"type": "string"},
            "new_text": {"type": "string"},
        },
        "required": ["path", "old_text", "new_text"],
        "additionalProperties": False,
    }

    def execute(self, arguments: dict[str, Any], context: ToolContext | None = None) -> ToolResult:
        old_text = arguments.get("old_text")
        new_text = arguments.get("new_text")
        if not isinstance(old_text, str) or not old_text or not isinstance(new_text, str):
            return ToolResult("old_text 必须非空且 new_text 必须是字符串", True)
        try:
            path = self._paths.source(arguments.get("path"), must_exist=True)
            content = path.read_text(encoding="utf-8")
            matches = content.count(old_text)
            if matches != 1:
                return ToolResult(f"old_text 精确匹配次数为 {matches}，必须等于 1；请重新读取文件", True)
            _atomic_write(path, content.replace(old_text, new_text, 1))
        except (OSError, ValueError, PermissionError) as exc:
            return ToolResult(str(exc), True)
        return ToolResult(json.dumps({"path": path.relative_to(self._session.project_root).as_posix(), "replacements": 1}, ensure_ascii=False))


class CreateRepairFileTool(_SessionTool):
    name = "create_repair_file"
    description = "在 src、scripts、tests 中创建新的文本文件；目标已存在时拒绝覆盖。"
    input_schema = {
        "type": "object",
        "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
        "required": ["path", "content"],
        "additionalProperties": False,
    }

    def execute(self, arguments: dict[str, Any], context: ToolContext | None = None) -> ToolResult:
        content = arguments.get("content")
        if not isinstance(content, str):
            return ToolResult("content 必须是字符串", True)
        try:
            path = self._paths.source(arguments.get("path"))
            if path.exists():
                return ToolResult("目标文件已经存在，禁止覆盖", True)
            path.parent.mkdir(parents=True, exist_ok=True)
            path = self._paths.source(arguments.get("path"))
            _atomic_write(path, content, require_absent=True)
        except (OSError, ValueError, PermissionError) as exc:
            return ToolResult(str(exc), True)
        return ToolResult(json.dumps({"path": path.relative_to(self._session.project_root).as_posix(), "created": True}, ensure_ascii=False))


class RunRepairCommandTool(_SessionTool):
    name = "run_repair_command"
    description = "以 argv 和 shell=False 运行 pytest 或 compileall；每个命令具有独立超时。"
    input_schema = {
        "type": "object",
        "properties": {
            "argv": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 900},
        },
        "required": ["argv"],
        "additionalProperties": False,
    }

    def execute(self, arguments: dict[str, Any], context: ToolContext | None = None) -> ToolResult:
        raw = arguments.get("argv")
        if not isinstance(raw, list) or not raw or not all(isinstance(item, str) and item for item in raw):
            return ToolResult("argv 必须是非空字符串数组", True)
        if any(item in _SHELL_CONTROL_TOKENS for item in raw):
            return ToolResult("禁止 shell 控制符、管道或重定向", True)
        try:
            self._validate_command_paths(raw)
            command = self._normalize_command(raw)
            timeout = int(arguments.get("timeout_seconds", self._session.default_timeout_seconds))
        except (TypeError, ValueError, PermissionError) as exc:
            return ToolResult(str(exc), True)
        if not 1 <= timeout <= self._session.maximum_timeout_seconds:
            return ToolResult(f"timeout_seconds 必须位于 1..{self._session.maximum_timeout_seconds}", True)
        env = os.environ.copy()
        source_root = str(self._session.project_root / "src")
        env["PYTHONPATH"] = source_root + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        runner = self._session.command_runner or subprocess.run
        try:
            completed = runner(command, cwd=self._session.project_root, text=True, capture_output=True, shell=False, timeout=timeout, env=env)
            output = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
            exit_code = int(completed.returncode)
        except subprocess.TimeoutExpired as exc:
            output = f"命令在 {timeout} 秒后超时\n{exc.stdout or ''}\n{exc.stderr or ''}".strip()
            exit_code = 124
        rendered = self._session.render_output(kind="command", content=output, extra={"argv": raw, "exit_code": exit_code})
        payload = json.loads(rendered)
        self._session.tests_run.append(
            RepairCommandRecord(tuple(raw), exit_code == 0, exit_code, payload.get("artifact_path"))
        )
        return ToolResult(rendered, is_error=exit_code != 0)

    def _validate_command_paths(self, argv: list[str]) -> None:
        """校验命令中的文件目标，防止借 pytest/compileall 间接越过修复目录。

        pytest 的表达式、marker 和普通开关不是路径，因此这里只识别绝对路径、父目录、
        带目录分隔符、Python 文件及已存在的相对路径；一旦识别为文件目标，就复用与
        读写工具完全相同的 ``resolve``/符号链接边界检查。
        """

        for raw in argv[1:]:
            if raw.startswith("-"):
                option, separator, value = raw.partition("=")
                if not separator or option not in {
                    "--rootdir",
                    "--confcutdir",
                    "--basetemp",
                    "--junitxml",
                }:
                    continue
                raw = value
            candidate = raw.split("::", 1)[0]
            normalized = candidate.replace("\\", "/")
            path = Path(candidate)
            looks_like_path = (
                path.is_absolute()
                or ".." in path.parts
                or "/" in normalized
                or normalized.endswith(".py")
                or (self._session.project_root / path).exists()
            )
            if looks_like_path:
                self._paths.source(candidate)

    @staticmethod
    def _normalize_command(argv: list[str]) -> list[str]:
        executable = argv[0].lower()
        if executable in {"pytest", "pytest.exe"}:
            return [sys.executable, "-m", "pytest", *argv[1:]]
        if executable in {"python", "python.exe"} and len(argv) >= 3 and argv[1] == "-m":
            if argv[2] not in {"pytest", "compileall"}:
                raise PermissionError("只允许 python -m pytest 或 python -m compileall")
            return [sys.executable, *argv[1:]]
        raise PermissionError("只允许 pytest、python -m pytest 和 python -m compileall")


class InspectRepairDiffTool(_SessionTool):
    name = "inspect_repair_diff"
    description = "只读检查 src、scripts、tests 的 Git 状态和 diff，不执行暂存、提交或回退。"
    input_schema = {"type": "object", "properties": {}, "additionalProperties": False}

    def execute(self, arguments: dict[str, Any], context: ToolContext | None = None) -> ToolResult:
        status = subprocess.run(["git", "status", "--porcelain", "--", "src", "scripts", "tests"], cwd=self._session.project_root, text=True, capture_output=True, shell=False)
        diff = subprocess.run(["git", "diff", "--", "src", "scripts", "tests"], cwd=self._session.project_root, text=True, capture_output=True, shell=False)
        if status.returncode != 0 or diff.returncode != 0:
            return ToolResult(status.stderr or diff.stderr or "Git diff 读取失败", True)
        content = f"Git status:\n{status.stdout}\nGit diff:\n{diff.stdout}".strip()
        return ToolResult(self._session.render_output(kind="diff", content=content))


def build_repair_tool_registry(
    *,
    project_root: Path,
    workflow_id: str,
    attempt: int,
    max_inline_chars: int = 12_000,
    session: RepairToolSession | None = None,
) -> ToolRegistry:
    """显式构建仅含六个工具的 Registry，防止普通业务工具泄漏到修复 Agent。"""

    active = session or RepairToolSession(project_root, workflow_id, attempt, max_inline_chars)
    registry = ToolRegistry()
    for tool_type in (SearchCodeTool, ReadRepairFileTool, EditRepairFileTool, CreateRepairFileTool, RunRepairCommandTool, InspectRepairDiffTool):
        registry.register(tool_type(active))
    return registry


def _atomic_write(path: Path, content: str, *, require_absent: bool = False) -> None:
    """在目标目录写临时文件后原子替换，避免中断留下半个源码文件。"""

    if require_absent and path.exists():
        raise FileExistsError("目标文件已经存在，禁止覆盖")
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.repair.tmp")
    try:
        temporary.write_text(content, encoding="utf-8", newline="")
        if require_absent and path.exists():
            raise FileExistsError("目标文件已经存在，禁止覆盖")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
