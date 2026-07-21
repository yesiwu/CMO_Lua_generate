from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from cmo_lua_agent.skills.skill_loader import (
    SkillLoaderError,
    list_skills,
    load_skill,
)
from cmo_lua_agent.tools.list_skills_tool import ListSkillsTool
from cmo_lua_agent.tools.load_skill_tool import LoadSkillTool
from cmo_lua_agent.tools.tool_base.context import ToolContext
from cmo_lua_agent.tools.tool_base.progress import ToolProgressReporter


def _create_skill(
    root: Path,
    *,
    category: str = "cmo",
    directory_name: str = "cmo-lua",
    name: str = "cmo-lua",
    description: str = "生成 CMO Lua 脚本。",
) -> Path:
    skill_dir = root / category / directory_name
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        "version: 1.0.0\n"
        "metadata:\n"
        "  cmo_lua_agent:\n"
        "    tags: [cmo, lua]\n"
        "---\n"
        "\n"
        "# Skill\n",
        encoding="utf-8",
    )
    (skill_dir / "references" / "api.md").write_text(
        "API reference\n",
        encoding="utf-8",
    )
    return skill_dir


def _context(events: list) -> ToolContext:
    return ToolContext(
        tool_use_id="tool-1",
        tool_name="skill-tool",
        progress=ToolProgressReporter(
            tool_use_id="tool-1",
            tool_name="skill-tool",
            callback=events.append,
        ),
    )


def test_list_skills_returns_lightweight_frontmatter_metadata(tmp_path: Path) -> None:
    _create_skill(tmp_path)

    skills = list_skills(tmp_path)

    assert skills == [
        {
            "id": "cmo-lua",
            "name": "cmo-lua",
            "description": "生成 CMO Lua 脚本。",
            "category": "cmo",
            "tags": ["cmo", "lua"],
            "path": "cmo/cmo-lua",
        }
    ]


def test_load_skill_returns_manifest_and_linked_files(tmp_path: Path) -> None:
    _create_skill(tmp_path)

    result = load_skill(tmp_path, "cmo-lua")

    assert result["file_path"] == "SKILL.md"
    assert result["truncated"] is False
    assert result["linked_files"] == {"references": ["references/api.md"]}
    assert "# Skill" in result["content"]


def test_load_skill_reads_allowed_linked_file(tmp_path: Path) -> None:
    _create_skill(tmp_path)

    result = load_skill(tmp_path, "cmo-lua", file_path="references/api.md")

    assert result["file_path"] == "references/api.md"
    assert result["content"] == "API reference\n"


@pytest.mark.parametrize(
    "file_path",
    ["../outside.md", "SKILL.md", "references/binary.bin"],
)
def test_load_skill_rejects_untrusted_file_paths(
    tmp_path: Path,
    file_path: str,
) -> None:
    skill_dir = _create_skill(tmp_path)
    (skill_dir / "references" / "binary.bin").write_bytes(b"binary")

    with pytest.raises(SkillLoaderError):
        load_skill(tmp_path, "cmo-lua", file_path=file_path)


def test_list_skills_rejects_duplicate_skill_names(tmp_path: Path) -> None:
    _create_skill(tmp_path, category="cmo", directory_name="first")
    _create_skill(tmp_path, category="rag", directory_name="second")

    with pytest.raises(SkillLoaderError, match="名称重复"):
        list_skills(tmp_path)


def test_list_skills_rejects_missing_frontmatter(tmp_path: Path) -> None:
    skill_dir = tmp_path / "cmo" / "bad"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Missing metadata\n", encoding="utf-8")

    with pytest.raises(SkillLoaderError, match="Frontmatter"):
        list_skills(tmp_path)


def test_load_skill_truncates_large_content(tmp_path: Path) -> None:
    skill_dir = _create_skill(tmp_path)
    (skill_dir / "references" / "large.md").write_text(
        "x" * 25_000,
        encoding="utf-8",
    )

    result = load_skill(tmp_path, "cmo-lua", file_path="references/large.md")

    assert result["truncated"] is True
    assert len(result["content"]) == 24_000


def test_symlink_cannot_escape_skill_directory(tmp_path: Path) -> None:
    skill_dir = _create_skill(tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_text("outside", encoding="utf-8")
    link = skill_dir / "references" / "escape.md"
    try:
        os.symlink(outside, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable")

    with pytest.raises(SkillLoaderError, match="越出根目录"):
        load_skill(tmp_path, "cmo-lua", file_path="references/escape.md")


def test_generic_skill_tools_return_results_and_progress(tmp_path: Path) -> None:
    _create_skill(tmp_path)
    events = []

    listed = ListSkillsTool(skills_root=tmp_path).execute({}, context=_context(events))
    loaded = LoadSkillTool(skills_root=tmp_path).execute(
        {"skill_id": "cmo-lua"},
        context=_context(events),
    )

    assert listed.is_error is False
    assert json.loads(listed.content)["count"] == 1
    assert loaded.is_error is False
    assert json.loads(loaded.content)["file_path"] == "SKILL.md"
    assert [event.event_type for event in events] == [
        "tool_started",
        "step_started",
        "step_completed",
        "tool_completed",
        "tool_started",
        "step_started",
        "step_completed",
        "tool_completed",
    ]


def test_generic_skill_tools_return_error_results(tmp_path: Path) -> None:
    _create_skill(tmp_path)

    result = LoadSkillTool(skills_root=tmp_path).execute(
        {"skill_id": "missing"}
    )

    assert result.is_error is True
    assert json.loads(result.content)["error"]["code"] == "skill_load_error"
