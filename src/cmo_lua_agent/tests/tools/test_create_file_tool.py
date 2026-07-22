from __future__ import annotations

import json
from pathlib import Path

from cmo_lua_agent.hooks.manager import HookManager
from cmo_lua_agent.hooks.permission_hook import PermissionHook
from cmo_lua_agent.tools.create_file_tool import CreateFileTool
from cmo_lua_agent.tools.tool_base.registry import ToolRegistry


def _payload(result: object) -> dict[str, object]:
    return json.loads(result.content)  # type: ignore[attr-defined]


def test_create_file_copies_source_with_verified_replacements(tmp_path: Path) -> None:
    source = tmp_path / "scenario.json"
    source.write_text('{"weapon": "YJ-18"}\n', encoding="utf-8")
    tool = CreateFileTool(workdir=tmp_path)

    result = tool.execute(
        {
            "path": "scenario_fixed.json",
            "source_path": "scenario.json",
            "replacements": [
                {
                    "old_text": "YJ-18",
                    "new_text": "YJ-18 [3M54E Klub Copy]",
                    "expected_count": 1,
                }
            ],
        }
    )

    target = tmp_path / "scenario_fixed.json"
    assert result.is_error is False
    assert source.read_text(encoding="utf-8") == '{"weapon": "YJ-18"}\n'
    assert target.read_text(encoding="utf-8") == '{"weapon": "YJ-18 [3M54E Klub Copy]"}\n'
    assert _payload(result)["mode"] == "copy_with_replacements"


def test_create_file_can_create_explicit_text_content(tmp_path: Path) -> None:
    result = CreateFileTool(workdir=tmp_path).execute(
        {"path": "notes.md", "content": "# Review\n"}
    )

    assert result.is_error is False
    assert (tmp_path / "notes.md").read_text(encoding="utf-8") == "# Review\n"
    assert _payload(result)["mode"] == "content"


def test_create_file_never_overwrites_or_creates_outside_workspace(tmp_path: Path) -> None:
    target = tmp_path / "exists.json"
    target.write_text("original", encoding="utf-8")
    outside = tmp_path.parent / f"{tmp_path.name}-outside.json"
    tool = CreateFileTool(workdir=tmp_path)

    for arguments in (
        {"path": "exists.json", "content": "replacement"},
        {"path": str(outside), "content": "outside"},
        {"path": "broken.json", "content": "x", "source_path": "exists.json"},
        {"path": "broken.json", "source_path": "exists.json"},
    ):
        result = tool.execute(arguments)
        assert result.is_error is True

    assert target.read_text(encoding="utf-8") == "original"
    assert not outside.exists()


def test_create_file_requires_approval_before_writing(tmp_path: Path) -> None:
    hooks = HookManager()
    hooks.register(PermissionHook(approval_function=lambda _name, _arguments: False))
    registry = ToolRegistry(hook_manager=hooks)
    registry.register(CreateFileTool(workdir=tmp_path))

    result = registry.dispatch(
        "create_file",
        {"path": "new.json", "content": "new"},
    )

    assert result.is_error is True
    assert not (tmp_path / "new.json").exists()
