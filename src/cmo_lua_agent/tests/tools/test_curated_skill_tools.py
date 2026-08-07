from __future__ import annotations

import json


def _write_skill(root, skill_id: str, description: str) -> None:
    base = root / "curated" / skill_id
    version = base / "versions" / "1.0.0"
    version.mkdir(parents=True)
    (version / "SKILL.md").write_text(
        "---\n"
        f"name: {skill_id}\n"
        f"description: {description}\n"
        "---\n\n"
        "# Test Skill\n\n## Quick Reference\n- Guidance.\n",
        encoding="utf-8",
    )
    (version / "metadata.json").write_text(json.dumps({
        "skill_id": skill_id,
        "version": "1.0.0",
        "status": "curated",
        "mission_type": "naval_air_anti_surface",
    }), encoding="utf-8")
    (base / "current.json").write_text(json.dumps({
        "skill_id": skill_id,
        "version": "1.0.0",
        "relative_path": "versions/1.0.0",
        "status": "curated",
        "description": description,
    }), encoding="utf-8")


def test_curated_skill_tools_use_summary_then_explicit_full_read(tmp_path) -> None:
    from cmo_lua_agent.learning.skill_evolution.curated_skill_registry import CuratedSkillRegistry
    from cmo_lua_agent.tools.list_curated_skills_tool import ListCuratedSkillsTool
    from cmo_lua_agent.tools.view_curated_skill_tool import ViewCuratedSkillTool

    _write_skill(tmp_path / "data" / "skills", "naval-air-survival", "Use when aircraft survival matters.")
    registry = CuratedSkillRegistry(tmp_path / "data" / "skills")

    summaries = registry.list_summaries()
    assert summaries == ({
        "skill_id": "naval-air-survival",
        "version": "1.0.0",
        "mission_type": "naval_air_anti_surface",
        "description": "Use when aircraft survival matters.",
    },)
    assert "content" not in summaries[0]

    listed = json.loads(ListCuratedSkillsTool(registry=registry).execute({}).content)
    viewed = json.loads(ViewCuratedSkillTool(registry=registry).execute({"skill_id": "naval-air-survival"}).content)
    assert listed["skills"] == list(summaries)
    assert viewed["skill_id"] == "naval-air-survival"
    assert "# Test Skill" in viewed["content"]
