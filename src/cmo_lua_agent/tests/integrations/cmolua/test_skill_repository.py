from __future__ import annotations

import os
from pathlib import Path

import pytest

from cmo_lua_agent.integrations.cmolua.config import CmoLuaIntegrationConfig
from cmo_lua_agent.integrations.cmolua.skill_repository import (
    CmoSkillAccessError,
    CmoSkillRepository,
)


def _build_config(tmp_path: Path) -> CmoLuaIntegrationConfig:
    skill_root = tmp_path / "CMOLua-main"
    (skill_root / "templates").mkdir(parents=True)
    (skill_root / "references").mkdir()
    (skill_root / "errors").mkdir()
    (skill_root / "examples").mkdir()
    (skill_root / "mcp" / "db").mkdir(parents=True)
    (skill_root / "outputs").mkdir()
    (skill_root / "_archive").mkdir()
    (skill_root / "tools").mkdir()

    (skill_root / "SKILL.md").write_text(
        "# CMO Lua Skill\n禁止编造 DBID。\n先搜索模板，再读取文档。\n",
        encoding="utf-8",
    )
    (skill_root / "templates" / "attack.lua").write_text(
        "-- 对海攻击模板\nlocal target = '目标舰'\n",
        encoding="utf-8",
    )
    (skill_root / "templates" / "patrol.md").write_text(
        "# 巡逻任务\n使用任务区和警戒区。\n",
        encoding="utf-8",
    )
    (skill_root / "references" / "api.md").write_text(
        "# API\nScenEdit_AddUnit 用于添加单位。\nDBID 必须来自数据库。\n",
        encoding="utf-8",
    )
    (skill_root / "errors" / "common.md").write_text(
        "# 常见错误\n找不到目标时检查单位名称。\n",
        encoding="utf-8",
    )
    (skill_root / "examples" / "carrier.json").write_text(
        '{"name": "航母场景", "note": "目标舰"}\n',
        encoding="utf-8",
    )

    # These files must never be visible through the repository.
    (skill_root / "mcp" / "db" / "DB3K_504.db3").write_bytes(
        b"target DBID secret"
    )
    (skill_root / "outputs" / "old.lua").write_text(
        "-- 目标舰 historical output\n", encoding="utf-8"
    )
    (skill_root / "_archive" / "old.md").write_text(
        "目标舰 archived\n", encoding="utf-8"
    )
    (skill_root / "templates" / "binary.bin").write_bytes(
        b"\x00target\xff"
    )

    generator_path = skill_root / "tools" / "json_to_lua.py"
    generator_path.write_text("def generate_cmo_lua(path): return '-- ok'\n")
    database_path = skill_root / "mcp" / "db" / "DB3K_504.db3"
    outputs_dir = tmp_path / "outputs" / "lua"
    outputs_dir.mkdir(parents=True)

    return CmoLuaIntegrationConfig(
        skill_root=skill_root,
        generator_path=generator_path,
        database_path=database_path,
        outputs_dir=outputs_dir,
    )


def test_search_finds_chinese_text_and_returns_relative_paths(tmp_path: Path) -> None:
    repository = CmoSkillRepository(_build_config(tmp_path))

    hits = repository.search("目标舰")

    assert [(hit.relative_path, hit.area, hit.line_number) for hit in hits] == [
        ("templates/attack.lua", "templates", 2),
        ("examples/carrier.json", "examples", 1),
    ]
    assert all("目标舰" in hit.snippet for hit in hits)


def test_search_can_filter_area_and_is_case_insensitive(tmp_path: Path) -> None:
    repository = CmoSkillRepository(_build_config(tmp_path))

    hits = repository.search("dbid", area="references")

    assert len(hits) == 1
    assert hits[0].relative_path == "references/api.md"
    assert hits[0].line_number == 3


def test_search_limit_is_deterministic(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    (config.skill_root / "references" / "a.md").write_text(
        "DBID first\nDBID second\n", encoding="utf-8"
    )
    repository = CmoSkillRepository(config)

    hits = repository.search("DBID", limit=2)

    assert [(hit.relative_path, hit.line_number) for hit in hits] == [
        ("SKILL.md", 2),
        ("references/a.md", 1),
    ]


def test_read_returns_requested_lines_and_truncation_state(tmp_path: Path) -> None:
    repository = CmoSkillRepository(_build_config(tmp_path))

    result = repository.read(
        "references/api.md",
        start_line=2,
        limit=1,
    )

    assert result.relative_path == "references/api.md"
    assert result.start_line == 2
    assert result.end_line == 2
    assert result.text == "ScenEdit_AddUnit 用于添加单位。"
    assert result.truncated is True


def test_read_returns_empty_range_when_start_is_after_end(tmp_path: Path) -> None:
    repository = CmoSkillRepository(_build_config(tmp_path))

    result = repository.read("errors/common.md", start_line=20, limit=5)

    assert result.start_line == 20
    assert result.end_line == 19
    assert result.text == ""
    assert result.truncated is False


@pytest.mark.parametrize(
    "relative_path",
    [
        "../outside.md",
        "mcp/db/DB3K_504.db3",
        "outputs/old.lua",
        "_archive/old.md",
        "templates/binary.bin",
    ],
)
def test_read_rejects_out_of_scope_or_binary_paths(
    tmp_path: Path,
    relative_path: str,
) -> None:
    repository = CmoSkillRepository(_build_config(tmp_path))

    with pytest.raises(CmoSkillAccessError):
        repository.read(relative_path)


def test_read_rejects_absolute_path(tmp_path: Path) -> None:
    repository = CmoSkillRepository(_build_config(tmp_path))

    with pytest.raises(CmoSkillAccessError):
        repository.read(str((tmp_path / "outside.md").resolve()))


def test_symlink_cannot_escape_skill_root(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_text("目标舰 outside\n", encoding="utf-8")
    link = config.skill_root / "templates" / "escape.md"

    try:
        os.symlink(outside, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable")

    repository = CmoSkillRepository(config)

    with pytest.raises(CmoSkillAccessError):
        repository.read("templates/escape.md")

    assert all(
        hit.relative_path != "templates/escape.md"
        for hit in repository.search("目标舰")
    )


@pytest.mark.parametrize(
    ("query", "limit"),
    [
        ("", 10),
        ("   ", 10),
        ("DBID", 0),
        ("DBID", 101),
    ],
)
def test_search_rejects_invalid_arguments(
    tmp_path: Path,
    query: str,
    limit: int,
) -> None:
    repository = CmoSkillRepository(_build_config(tmp_path))

    with pytest.raises(CmoSkillAccessError):
        repository.search(query, limit=limit)


@pytest.mark.parametrize(
    ("start_line", "limit"),
    [
        (0, 10),
        (1, 0),
        (1, 501),
    ],
)
def test_read_rejects_invalid_line_arguments(
    tmp_path: Path,
    start_line: int,
    limit: int,
) -> None:
    repository = CmoSkillRepository(_build_config(tmp_path))

    with pytest.raises(CmoSkillAccessError):
        repository.read(
            "SKILL.md",
            start_line=start_line,
            limit=limit,
        )