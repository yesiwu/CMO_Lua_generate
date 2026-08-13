from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from cmo_lua_agent.tools.repair_tools import build_repair_tool_registry


def _registry(root: Path, *, max_inline_chars: int = 12_000):
    return build_repair_tool_registry(
        project_root=root,
        workflow_id="training-tools",
        attempt=1,
        max_inline_chars=max_inline_chars,
    )


def test_repair_registry_exposes_only_six_repair_tools(tmp_path: Path) -> None:
    names = {
        definition["name"]
        for definition in _registry(tmp_path).get_definitions()
    }

    assert names == {
        "search_code",
        "read_repair_file",
        "edit_repair_file",
        "create_repair_file",
        "run_repair_command",
        "inspect_repair_diff",
    }


def test_edit_requires_old_text_to_match_exactly_once(tmp_path: Path) -> None:
    source = tmp_path / "src" / "package" / "worker.py"
    source.parent.mkdir(parents=True)
    source.write_text("VALUE = 1\nVALUE = 1\n", encoding="utf-8")
    registry = _registry(tmp_path)

    repeated = registry.dispatch(
        "edit_repair_file",
        {"path": "src/package/worker.py", "old_text": "VALUE = 1", "new_text": "VALUE = 2"},
    )
    missing = registry.dispatch(
        "edit_repair_file",
        {"path": "src/package/worker.py", "old_text": "VALUE = 9", "new_text": "VALUE = 2"},
    )

    assert repeated.is_error is True
    assert "2" in repeated.content
    assert missing.is_error is True
    assert "0" in missing.content
    assert source.read_text(encoding="utf-8") == "VALUE = 1\nVALUE = 1\n"


def test_repair_write_tools_reject_absolute_parent_and_outside_paths(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    absolute = str((tmp_path / "src" / "bad.py").resolve())

    results = [
        registry.dispatch(
            "create_repair_file",
            {"path": absolute, "content": "VALUE = 1\n"},
        ),
        registry.dispatch(
            "create_repair_file",
            {"path": "../bad.py", "content": "VALUE = 1\n"},
        ),
        registry.dispatch(
            "create_repair_file",
            {"path": "data/bad.py", "content": "VALUE = 1\n"},
        ),
    ]

    assert all(result.is_error for result in results)
    assert not (tmp_path.parent / "bad.py").exists()
    assert not (tmp_path / "data" / "bad.py").exists()


def test_repair_write_tools_allow_root_tests_directory(tmp_path: Path) -> None:
    result = _registry(tmp_path).dispatch(
        "create_repair_file",
        {"path": "tests/test_regression.py", "content": "def test_ok():\n    assert True\n"},
    )

    assert result.is_error is False
    assert (tmp_path / "tests" / "test_regression.py").is_file()


def test_large_search_output_is_preserved_as_readable_artifact(tmp_path: Path) -> None:
    source = tmp_path / "src" / "package" / "many.py"
    source.parent.mkdir(parents=True)
    source.write_text("\n".join(f"MATCH_{index} = 'needle'" for index in range(40)), encoding="utf-8")
    registry = _registry(tmp_path, max_inline_chars=80)

    result = registry.dispatch(
        "search_code",
        {"query": "needle", "paths": ["src"], "max_results": 100},
    )
    payload = json.loads(result.content)

    assert result.is_error is False
    assert payload["truncated"] is True
    artifact_path = Path(payload["artifact_path"])
    assert not artifact_path.is_absolute()
    full_output = (tmp_path / artifact_path).read_text(encoding="utf-8")
    assert "MATCH_0" in full_output
    assert "MATCH_39" in full_output

    page = registry.dispatch(
        "read_repair_file",
        {"path": artifact_path.as_posix(), "start_line": 1, "end_line": 5},
    )
    assert page.is_error is False
    assert "MATCH_0" in page.content


def test_command_tool_rejects_shell_control_and_git(tmp_path: Path) -> None:
    registry = _registry(tmp_path)

    chained = registry.dispatch(
        "run_repair_command",
        {"argv": ["pytest", "tests/test_x.py", "&&", "git", "status"]},
    )
    git = registry.dispatch("run_repair_command", {"argv": ["git", "status"]})

    assert chained.is_error is True
    assert git.is_error is True


def test_command_tool_rejects_paths_outside_repair_scope(tmp_path: Path) -> None:
    registry = _registry(tmp_path)

    outside_test = registry.dispatch(
        "run_repair_command",
        {"argv": ["pytest", "data/test_generated.py"]},
    )
    parent_compile = registry.dispatch(
        "run_repair_command",
        {"argv": ["python", "-m", "compileall", "../outside"]},
    )

    assert outside_test.is_error is True
    assert parent_compile.is_error is True


def test_repair_tools_reject_symbolic_link_escape(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    source_root = tmp_path / "src"
    source_root.mkdir()
    link = source_root / "escaped"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"当前环境无法创建目录符号链接：{exc}")

    registry = _registry(tmp_path)
    created = registry.dispatch(
        "create_repair_file",
        {"path": "src/escaped/bad.py", "content": "VALUE = 1\n"},
    )

    assert created.is_error is True
    assert not (outside / "bad.py").exists()
