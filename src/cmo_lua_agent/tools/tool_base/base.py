"""
工具基础数据结构。

BaseTool 同时保存：
1. 提供给 LLM 的工具名称、说明和参数 Schema；
2. Python 侧真正执行工具的统一接口；
3. 后续所需的工具分组、权限等级和可用性检查。

ToolResult 用于统一表达工具执行成功或失败，
避免不同工具返回互不兼容的结果格式。

当前仍允许工具直接返回字符串，由 ToolRegistry 自动转换，
便于兼容现有的 EchoTool、ReadFileTool 等简单工具。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, TypeAlias

from cmo_lua_agent.tools.tool_base.context import ToolContext


@dataclass(frozen=True)
class ToolResult:
    """
    一次工具调用的标准结果。

    content:
        返回给 LLM 的文本内容。

    is_error:
        标记本次工具调用是否失败。
        Agent Loop 会将其转换为 Anthropic tool_result 的 is_error 字段。
    """

    content: str
    is_error: bool = False


# 过渡阶段允许工具返回 ToolResult 或普通字符串。
# ToolRegistry 会将普通字符串转换为 ToolResult。
ToolReturn: TypeAlias = ToolResult | str


class BaseTool(ABC):
    """
    所有 Agent 工具都需要实现的公共接口。

    具体工具通常通过类属性声明名称、描述和输入 Schema，
    并通过 execute() 实现真正的工具逻辑。
    """

    name: str
    description: str
    input_schema: dict[str, Any]

    # 用于未来按照 Agent 角色筛选工具。
    toolset: str = "common"

    # 用于未来的权限 Hook。
    requires_approval: bool = False

    def to_anthropic_schema(self) -> dict[str, Any]:
        """
        返回 Anthropic Messages API 使用的工具定义。

        该方法只负责工具 Schema，不包含执行逻辑。
        """
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


    @abstractmethod
    def execute(
        self,
        arguments: dict[str, Any],
        context: ToolContext | None = None,
    ) -> ToolReturn:
        """
        执行工具。

        arguments 是 LLM tool_use 中返回的结构化参数。
        工具可以暂时返回字符串，也可以返回 ToolResult。
        """
        raise NotImplementedError
