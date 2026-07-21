import json
from pathlib import Path

from cmo_lua_agent.hooks.manager import HookManager
from cmo_lua_agent.hooks.permission_hook import PermissionHook
from cmo_lua_agent.tools.list_directory_tool import ListDirectoryTool
from cmo_lua_agent.tools.read_file_tool import ReadFileTool
from cmo_lua_agent.tools.tool_base.base import ToolResult
from cmo_lua_agent.tools.tool_base.registry import ToolRegistry


def test_read_file_allows_paths_outside_workdir(tmp_path: Path) -> None:
    workdir = tmp_path / "project"
    workdir.mkdir()
    result_file = tmp_path / "Results" / "runner.log"
    result_file.parent.mkdir()
    result_file.write_text("batch output", encoding="utf-8")

    result = ReadFileTool(workdir=workdir).execute(
        {"path": str(result_file)}
    )

    assert result == "batch output"


def test_read_file_returns_actionable_error_for_directory(tmp_path: Path) -> None:
    directory = tmp_path / "runs"
    directory.mkdir()

    result = ReadFileTool(workdir=tmp_path).execute({"path": str(directory)})

    assert isinstance(result, ToolResult)
    assert result.is_error is True
    assert json.loads(result.content)["error"] == {
        "code": "path_is_directory",
        "message": f"目标路径是目录，不能使用 read_file：{directory}",
        "suggested_tool": "list_directory",
    }


def test_list_directory_allows_paths_outside_workdir(tmp_path: Path) -> None:
    workdir = tmp_path / "project"
    workdir.mkdir()
    results_directory = tmp_path / "Results"
    results_directory.mkdir()
    (results_directory / "runner.log").write_text("batch output", encoding="utf-8")
    (results_directory / "nested").mkdir()

    result = ListDirectoryTool(workdir=workdir).execute(
        {"path": str(results_directory)}
    )

    assert result.is_error is False
    payload = json.loads(result.content)
    assert payload["path"] == str(results_directory)
    assert [(entry["name"], entry["type"]) for entry in payload["entries"]] == [
        ("nested", "directory"),
        ("runner.log", "file"),
    ]


def test_read_file_does_not_request_approval(tmp_path: Path) -> None:
    target = tmp_path / "result.txt"
    target.write_text("safe read", encoding="utf-8")
    approval_calls: list[tuple[str, dict[str, object]]] = []
    hook_manager = HookManager()
    hook_manager.register(
        PermissionHook(
            approval_function=lambda name, arguments: (
                approval_calls.append((name, arguments)) or True
            )
        )
    )
    registry = ToolRegistry(hook_manager=hook_manager)
    registry.register(ReadFileTool(workdir=tmp_path))

    result = registry.dispatch("read_file", {"path": str(target)})

    assert result.content == "safe read"
    assert result.is_error is False
    assert approval_calls == []
