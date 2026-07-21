"""按需加载项目内文档型 Skill 的 Agent 工具。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cmo_lua_agent.skills.skill_loader import (
    SkillLoaderError,
    load_skill,
)
from cmo_lua_agent.tools.tool_base.base import BaseTool, ToolResult
from cmo_lua_agent.tools.tool_base.context import ToolContext


class LoadSkillTool(BaseTool):
    """读取 Skill 入口或已列出的关联文件。"""

    name = "load_skill"
    description = (
        "按名称加载一个 Skill 的 SKILL.md，或读取其 linked_files 中明确列出的"
        "关联文件。关联文件必须通过 file_path 传入，例如 references/api.md；"
        "不得猜测或读取 CMOLua-main 路径。"
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "skill_id": {
                "type": "string",
                "description": "由 list_skills 返回的 Skill 标识。",
            },
            "file_path": {
                "type": "string",
                "description": "可选关联文件路径，例如 references/api.md。",
            },
        },
        "required": ["skill_id"],
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
            context.progress.tool_started("正在加载 Skill")
        try:
            skill_id = arguments.get("skill_id")
            if not isinstance(skill_id, str) or not skill_id.strip():
                raise SkillLoaderError("skill_id 必须是非空字符串")
            file_path = arguments.get("file_path")
            if file_path is not None and (
                not isinstance(file_path, str) or not file_path.strip()
            ):
                raise SkillLoaderError(
                    "file_path 提供时必须是非空字符串"
                )
            if context is not None:
                message = (
                    "正在读取 Skill 关联文件"
                    if file_path
                    else "正在读取 Skill 入口文档"
                )
                context.progress.step_started("load", message)
            payload = load_skill(
                self._skills_root,
                skill_id.strip(),
                file_path=(
                    file_path.strip()
                    if isinstance(file_path, str)
                    else None
                ),
            )
        except SkillLoaderError as exc:
            return self._failure(str(exc), context)

        if context is not None:
            context.progress.step_completed(
                "load",
                "Skill 内容加载完成",
                payload["file_path"],
            )
            context.progress.tool_completed("Skill 加载完成")
        return ToolResult(
            content=json.dumps(
                {"success": True, **payload},
                ensure_ascii=False,
                indent=2,
            )
        )

    @staticmethod
    def _failure(message: str, context: ToolContext | None) -> ToolResult:
        if context is not None:
            context.progress.tool_failed("加载 Skill 失败", message)
        return ToolResult(
            content=json.dumps(
                {
                    "success": False,
                    "error": {
                        "code": "skill_load_error",
                        "message": message,
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            is_error=True,
        )
