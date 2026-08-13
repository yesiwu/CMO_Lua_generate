"""通用工作区搜索工具的行为测试。"""

from __future__ import annotations

import json
from pathlib import Path

from cmo_lua_agent.tools.search_workspace_tool import SearchWorkspaceTool
from cmo_lua_agent.tools.tool_base.base import ToolResult


def test_search_workspace_finds_visible_text_and_skips_dot_directories(
    tmp_path: Path,
) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text(
        "MAIN_SYSTEM_PROMPT = 'visible'\n", encoding="utf-8"
    )
    (tmp_path / ".pytest-tmp").mkdir()
    (tmp_path / ".pytest-tmp" / "secret.py").write_text(
        "MAIN_SYSTEM_PROMPT = 'hidden'\n", encoding="utf-8"
    )

    result = SearchWorkspaceTool(workdir=tmp_path).execute(
        {"query": "MAIN_SYSTEM_PROMPT", "paths": ["."], "glob": "*.py"}
    )

    assert isinstance(result, str)
    assert "src/main.py:1:" in result.replace("\\", "/")
    assert "secret.py" not in result


def test_search_workspace_rejects_hidden_or_outside_paths(tmp_path: Path) -> None:
    (tmp_path / ".github").mkdir()
    tool = SearchWorkspaceTool(workdir=tmp_path)

    hidden = tool.execute({"query": "x", "paths": [".github"]})
    outside = tool.execute({"query": "x", "paths": [str(tmp_path.parent)]})

    assert isinstance(hidden, ToolResult) and hidden.is_error
    assert isinstance(outside, ToolResult) and outside.is_error


def test_search_workspace_saves_large_results_without_losing_matches(
    tmp_path: Path,
) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "many.py").write_text(
        "\n".join(f"needle = {index}" for index in range(30)), encoding="utf-8"
    )
    tool = SearchWorkspaceTool(workdir=tmp_path, max_inline_chars=60)

    result = tool.execute({"query": "needle", "paths": ["src"]})

    payload = json.loads(result)
    assert payload["truncated"] is True
    artifact = tmp_path / payload["artifact_path"]
    assert artifact.is_file()
    assert "needle = 29" in artifact.read_text(encoding="utf-8")
