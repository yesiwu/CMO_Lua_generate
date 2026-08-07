"""
只读工具：用于输出经过筛选整理的技能摘要，不会返回 Markdown 格式的完整技能正文
"""
from __future__ import annotations

import json
from typing import Any

# 导入技能进化模块里的精选技能注册表、注册表自定义异常
from cmo_lua_agent.learning.skill_evolution.curated_skill_registry import CuratedSkillRegistry, CuratedSkillRegistryError
# 工具基类与工具返回结果实体
from cmo_lua_agent.tools.tool_base.base import BaseTool, ToolResult
# 工具运行上下文
from cmo_lua_agent.tools.tool_base.context import ToolContext


class ListCuratedSkillsTool(BaseTool):
    # 工具名称，智能体通过该名称调用工具
    name = "list_curated_skills"
    # 工具功能描述，供给大模型理解用途
    description = "列出人工整理的战术技能精简摘要。如需查看技能完整内容，请单独调用 view_curated_skill 并传入对应 skill_id。"
    # 入参JSON Schema，约束大模型传入参数的结构、类型
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "mission_type": {"type": "string"}  # 任务类型，用于筛选对应战术技能
        },
        "additionalProperties": False,  # 禁止传入schema以外多余参数
    }
    toolset = "curated_skills"  # 归属工具分组：精选技能组

    def __init__(self, *, registry: CuratedSkillRegistry) -> None:
        """构造方法，注入技能注册表实例（依赖注入）"""
        self._registry = registry

    def execute(self, arguments: dict[str, Any], context: ToolContext | None = None) -> ToolResult:
        """
        工具核心执行逻辑
        :param arguments: 大模型传入的参数字典
        :param context: 工具运行上下文，可携带会话、环境、权限等信息
        :return: ToolResult 工具执行结果对象
        """
        mission_type = arguments.get("mission_type")

        # 参数校验：如果传入了mission_type，但类型不是字符串，判定参数非法
        if mission_type is not None and not isinstance(mission_type, str):
            err_data = json.dumps({"success": False, "error": {"code": "mission_type_invalid"}})
            return ToolResult(err_data, is_error=True)

        try:
            # 调用注册表，根据任务类型筛选并获取技能摘要列表
            summaries = self._registry.list_summaries(mission_type=mission_type)
        except CuratedSkillRegistryError as exc:
            # 捕获注册表自定义异常，封装错误信息返回
            err_data = json.dumps({"success": False, "error": {"code": str(exc)}})
            return ToolResult(err_data, is_error=True)

        # 正常返回：成功标记、技能总数、技能摘要数组
        resp_data = json.dumps(
            {"success": True, "count": len(summaries), "skills": summaries},
            ensure_ascii=False  # 关闭ASCII转义，正常输出中文
        )
        return ToolResult(resp_data)