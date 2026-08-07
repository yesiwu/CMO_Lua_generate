"""Read-only Tool for loading one curated Skill Markdown body by ID."""
from __future__ import annotations

import json
from typing import Any

from cmo_lua_agent.learning.skill_evolution.curated_skill_registry import CuratedSkillRegistry, CuratedSkillRegistryError
from cmo_lua_agent.tools.tool_base.base import BaseTool, ToolResult
from cmo_lua_agent.tools.tool_base.context import ToolContext


class ViewCuratedSkillTool(BaseTool):
    name = "view_curated_skill"
    description = "Load the complete SKILL.md body for one skill_id returned by list_curated_skills."
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"skill_id": {"type": "string"}},
        "required": ["skill_id"],
        "additionalProperties": False,
    }
    toolset = "curated_skills"

    def __init__(self, *, registry: CuratedSkillRegistry) -> None:
        self._registry = registry

    def execute(self, arguments: dict[str, Any], context: ToolContext | None = None) -> ToolResult:
        skill_id = arguments.get("skill_id")
        try:
            payload = self._registry.view(skill_id)
        except CuratedSkillRegistryError as exc:
            return ToolResult(json.dumps({"success": False, "error": {"code": str(exc)}}), is_error=True)
        return ToolResult(json.dumps({"success": True, **payload}, ensure_ascii=False))
