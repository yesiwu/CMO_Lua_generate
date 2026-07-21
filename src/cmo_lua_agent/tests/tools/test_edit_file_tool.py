from __future__ import annotations

import json
from pathlib import Path

from cmo_lua_agent.hooks.manager import HookManager
from cmo_lua_agent.hooks.permission_hook import PermissionHook
from cmo_lua_agent.tools.edit_file_tool import EditFileTool
from cmo_lua_agent.tools.tool_base.registry import ToolRegistry


def _payload(result: object) -> dict[str, object]:
    return json.loads(result.content)  # type: ignore[attr-defined]


def test_edit_file_replaces_exact_text_and_reports_summary(tmp_path: Path) -> None:
    target = tmp_path / "scenario.json"
    target.write_text('{"weapon": "YJ-18", "loadoutId": 9682}\n', encoding="utf-8")

    result = EditFileTool(workdir=tmp_path).execute(
        {
            "path": "scenario.json",
            "replacements": [
                {
                    "old_text": '"weapon": "YJ-18"',
                    "new_text": '"weapon": "YJ-18 [3M54E Klub Copy]"',
                    "expected_count": 1,
                },
                {
                    "old_text": ', "loadoutId": 9682',
                    "new_text": "",
                    "expected_count": 1,
                },
            ],
        }
    )

    assert result.is_error is False
    assert target.read_text(encoding="utf-8") == '{"weapon": "YJ-18 [3M54E Klub Copy]"}\n'
    assert _payload(result)["replacements"] == 2


def test_edit_file_keeps_original_when_expected_text_is_not_matched(tmp_path: Path) -> None:
    target = tmp_path / "scenario.json"
    original = '{"weapon": "YJ-18"}\n'
    target.write_text(original, encoding="utf-8")

    result = EditFileTool(workdir=tmp_path).execute(
        {
            "path": "scenario.json",
            "replacements": [
                {"old_text": "missing", "new_text": "new", "expected_count": 1}
            ],
        }
    )

    assert result.is_error is True
    assert _payload(result)["error"]["code"] == "replacement_count_mismatch"
    assert target.read_text(encoding="utf-8") == original


def test_edit_file_rejects_outside_workspace_unknown_arguments_and_binary_extensions(
    tmp_path: Path,
) -> None:
    outside = tmp_path.parent / "outside.json"
    outside.write_text("old", encoding="utf-8")
    binary = tmp_path / "payload.db3"
    binary.write_bytes(b"old")
    tool = EditFileTool(workdir=tmp_path)

    for arguments in (
        {
            "path": str(outside),
            "replacements": [{"old_text": "old", "new_text": "new"}],
        },
        {
            "path": "payload.db3",
            "replacements": [{"old_text": "old", "new_text": "new"}],
        },
        {
            "path": "payload.json",
            "replacements": [{"old_text": "old", "new_text": "new"}],
            "mode": "overwrite",
        },
    ):
        result = tool.execute(arguments)
        assert result.is_error is True


def test_edit_file_requires_permission_hook_approval(tmp_path: Path) -> None:
    target = tmp_path / "scenario.json"
    target.write_text("old", encoding="utf-8")
    approvals: list[tuple[str, dict[str, object]]] = []
    hooks = HookManager()
    hooks.register(
        PermissionHook(
            approval_function=lambda name, arguments: (
                approvals.append((name, arguments)) or False
            )
        )
    )
    registry = ToolRegistry(hook_manager=hooks)
    registry.register(EditFileTool(workdir=tmp_path))

    result = registry.dispatch(
        "edit_file",
        {"path": "scenario.json", "replacements": [{"old_text": "old", "new_text": "new"}]},
    )

    assert result.is_error is True
    assert target.read_text(encoding="utf-8") == "old"
    assert approvals[0][0] == "edit_file"


def test_edit_file_executes_only_after_approval(tmp_path: Path) -> None:
    target = tmp_path / "scenario.json"
    target.write_text("old", encoding="utf-8")
    hooks = HookManager()
    hooks.register(PermissionHook(approval_function=lambda _name, _arguments: True))
    registry = ToolRegistry(hook_manager=hooks)
    registry.register(EditFileTool(workdir=tmp_path))

    result = registry.dispatch(
        "edit_file",
        {"path": "scenario.json", "replacements": [{"old_text": "old", "new_text": "new"}]},
    )

    assert result.is_error is False
    assert target.read_text(encoding="utf-8") == "new"
