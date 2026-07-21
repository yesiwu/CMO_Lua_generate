"""列出项目内可用文档型 Skill 的 Agent 工具。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cmo_lua_agent.skills.skill_loader import (
    SkillLoaderError,
    list_skills,
)
from cmo_lua_agent.tools.tool_base.base import BaseTool, ToolResult
from cmo_lua_agent.tools.tool_base.context import ToolContext


class ListSkillsTool(BaseTool):
    """向模型暴露项目 Skill 的轻量目录。"""

    name = "list_skills"
    description = (
        "列出项目正式 Skill 根目录中的轻量元数据：名称、描述、分类和标签。"
        "不搜索 Skill 正文，也不访问 CMOLua-main。"
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "可选的 Skill 分类，例如 cmo、rag 或 presentation。",
            }
        },
        "additionalProperties": False,
    }
    toolset = "skills"

    def __init__(self, *, skills_root: Path) -> None:
        self._skills_root = Path(skills_root).resolve(strict=False)

    def execute(
        self,
        arguments: dict[str, Any],
        context: ToolContext | None = None,
    ) -> ToolResult:
        if context is not None:
            context.progress.tool_started("正在列出可用 Skill")
            context.progress.step_started("discover", "正在扫描 Skill 目录")
        try:
            category = arguments.get("category")
            skills = list_skills(self._skills_root, category=category)
        except SkillLoaderError as exc:
            return self._failure(str(exc), context)

        if context is not None:
            context.progress.step_completed(
                "discover",
                f"找到 {len(skills)} 个 Skill",
            )
            context.progress.tool_completed("Skill 目录加载完成")
        return ToolResult(
            content=json.dumps(
                {"success": True, "count": len(skills), "skills": skills},
                ensure_ascii=False,
                indent=2,
            )
        )

    @staticmethod
    def _failure(message: str, context: ToolContext | None) -> ToolResult:
        if context is not None:
            context.progress.tool_failed("列出 Skill 失败", message)
        return ToolResult(
            content=json.dumps(
                {
                    "success": False,
                    "error": {
                        "code": "skill_catalog_error",
                        "message": message,
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            is_error=True,
        )
