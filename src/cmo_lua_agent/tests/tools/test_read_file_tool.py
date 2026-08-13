import json
from pathlib import Path

from cmo_lua_agent.hooks.manager import HookManager
from cmo_lua_agent.hooks.permission_hook import PermissionHook
from cmo_lua_agent.tools.list_directory_tool import ListDirectoryTool
from cmo_lua_agent.tools.read_file_tool import ReadFileTool
from cmo_lua_agent.tools.tool_base.base import ToolResult
from cmo_lua_agent.tools.tool_base.registry import ToolRegistry


def test_read_file_rejects_paths_outside_workdir(tmp_path: Path) -> None:
    workdir = tmp_path / "project"
    workdir.mkdir()
    result_file = tmp_path / "Results" / "runner.log"
    result_file.parent.mkdir()
    result_file.write_text("batch output", encoding="utf-8")

    result = ReadFileTool(workdir=workdir).execute(
        {"path": str(result_file)}
    )

    assert isinstance(result, ToolResult)
    assert result.is_error is True


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


def test_list_directory_hides_dot_paths_and_rejects_outside_workdir(tmp_path: Path) -> None:
    workdir = tmp_path / "project"
    workdir.mkdir()
    results_directory = tmp_path / "Results"
    results_directory.mkdir()
    (results_directory / "runner.log").write_text("batch output", encoding="utf-8")
    (results_directory / "nested").mkdir()

    outside_result = ListDirectoryTool(workdir=workdir).execute(
        {"path": str(results_directory)}
    )

    (workdir / "visible").mkdir()
    (workdir / ".pytest-tmp").mkdir()
    result = ListDirectoryTool(workdir=workdir).execute({"path": "."})

    assert outside_result.is_error is True
    assert result.is_error is False
    payload = json.loads(result.content)
    assert [(entry["name"], entry["type"]) for entry in payload["entries"]] == [("visible", "directory")]


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


def test_read_file_reads_an_exact_line_range(tmp_path: Path) -> None:
    target = tmp_path / "notes.md"
    target.write_text("第一行\n第二行\n第三行\n第四行\n", encoding="utf-8")

    result = ReadFileTool(workdir=tmp_path).execute(
        {"path": "notes.md", "start_line": 2, "end_line": 3}
    )

    assert result == "第二行\n第三行"


def test_read_file_rejects_binary_content(tmp_path: Path) -> None:
    target = tmp_path / "payload.bin"
    target.write_bytes(b"text-before-nul\x00text-after-nul")

    result = ReadFileTool(workdir=tmp_path).execute({"path": "payload.bin"})

    assert isinstance(result, ToolResult)
    assert result.is_error is True
    assert json.loads(result.content)["error"]["code"] == "binary_file_not_supported"


def test_read_file_rejects_known_binary_extension_even_without_nul(tmp_path: Path) -> None:
    target = tmp_path / "image.png"
    target.write_bytes(b"ascii-looking-binary-fixture")

    result = ReadFileTool(workdir=tmp_path).execute({"path": "image.png"})

    assert isinstance(result, ToolResult)
    assert json.loads(result.content)["error"]["code"] == "binary_file_not_supported"


def test_read_file_preserves_large_output_as_readable_artifact(tmp_path: Path) -> None:
    target = tmp_path / "large.log"
    target.write_text("\n".join(f"line-{index}" for index in range(30)), encoding="utf-8")
    tool = ReadFileTool(workdir=tmp_path, max_inline_chars=40)

    result = tool.execute({"path": "large.log"})

    payload = json.loads(result)
    assert payload["truncated"] is True
    artifact_path = payload["artifact_path"]
    page = tool.execute({"path": artifact_path, "start_line": 25, "end_line": 27})
    assert page == "line-24\nline-25\nline-26"
