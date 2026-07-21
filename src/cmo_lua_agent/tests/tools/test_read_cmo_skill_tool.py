from __future__ import annotations

import json
from pathlib import Path

from cmo_lua_agent.integrations.cmolua.config import CmoLuaIntegrationConfig
from cmo_lua_agent.integrations.cmolua.skill_repository import CmoSkillRepository
from cmo_lua_agent.tools.read_cmo_skill_tool import ReadCmoSkillTool
from cmo_lua_agent.tools.tool_base.context import ToolContext
from cmo_lua_agent.tools.tool_base.progress import ToolProgressReporter


def _repository(tmp_path: Path) -> CmoSkillRepository:
    skill_root = tmp_path / "CMOLua-main"
    (skill_root / "references").mkdir(parents=True)
    (skill_root / "mcp" / "db").mkdir(parents=True)
    (skill_root / "tools").mkdir()
    (skill_root / "SKILL.md").write_text("# Skill\n", encoding="utf-8")
    (skill_root / "references" / "api.md").write_text(
        "one\ntwo\nthree\n",
        encoding="utf-8",
    )
    generator_path = skill_root / "tools" / "json_to_lua.py"
    generator_path.write_text("", encoding="utf-8")
    database_path = skill_root / "mcp" / "db" / "DB3K_504.db3"
    database_path.write_bytes(b"")
    outputs_dir = tmp_path / "outputs" / "lua"
    outputs_dir.mkdir(parents=True)
    return CmoSkillRepository(
        CmoLuaIntegrationConfig(
            skill_root=skill_root,
            generator_path=generator_path,
            database_path=database_path,
            outputs_dir=outputs_dir,
        )
    )


def _context(events: list) -> ToolContext:
    return ToolContext(
        tool_use_id="tool-1",
        tool_name="read_cmo_skill",
        progress=ToolProgressReporter(
            tool_use_id="tool-1",
            tool_name="read_cmo_skill",
            callback=events.append,
        ),
    )


def test_reads_repository_content_and_reports_progress(tmp_path: Path) -> None:
    events = []
    tool = ReadCmoSkillTool(skill_repository=_repository(tmp_path))

    result = tool.execute(
        {"relative_path": "references/api.md", "start_line": 2, "limit": 1},
        context=_context(events),
    )

    assert result.is_error is False
    assert json.loads(result.content) == {
        "success": True,
        "relative_path": "references/api.md",
        "start_line": 2,
        "end_line": 2,
        "text": "two",
        "truncated": True,
        "content_truncated": False,
    }
    assert [(event.event_type, event.step_id) for event in events] == [
        ("tool_started", None),
        ("step_started", "read"),
        ("step_completed", "read"),
        ("tool_completed", None),
    ]


def test_invalid_path_returns_error_tool_result(tmp_path: Path) -> None:
    tool = ReadCmoSkillTool(skill_repository=_repository(tmp_path))

    result = tool.execute({"relative_path": "../outside.md"})

    assert result.is_error is True
    payload = json.loads(result.content)
    assert payload["success"] is False
    assert payload["error"]["code"] == "invalid_skill_read_request"


def test_rejects_values_outside_tool_schema_bounds(tmp_path: Path) -> None:
    tool = ReadCmoSkillTool(skill_repository=_repository(tmp_path))

    result = tool.execute({"relative_path": "SKILL.md", "limit": 201})

    assert result.is_error is True
    assert json.loads(result.content)["error"]["code"] == "invalid_skill_read_request"
