"""
Agent 运行过程事件。

该模块定义 AgentLoop 在模型调用、文本流式返回、
工具执行和流程结束时发出的标准事件。

事件用于终端显示、日志记录以及未来的 Web UI，
只负责描述“发生了什么”，不负责权限判断，
也不能修改 Agent 的执行流程。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AgentEventType(str, Enum):
    """
    Agent 运行过程中可能产生的事件类型。

    枚举值使用稳定的英文机器标识；
    display_name 属性提供中文显示名称。
    """

    AGENT_STARTED = "agent_started"

    LLM_STARTED = "llm_started"
    TEXT_DELTA = "text_delta"
    LLM_COMPLETED = "llm_completed"

    TOOL_STARTED = "tool_started"
    TOOL_PROGRESS = "tool_progress"
    TOOL_COMPLETED = "tool_completed"
    TOOL_FAILED = "tool_failed"

    AGENT_COMPLETED = "agent_completed"
    AGENT_FAILED = "agent_failed"

    @property
    def display_name(self) -> str:
        """
        返回适合终端或界面展示的中文名称。
        """
        names = {
            AgentEventType.AGENT_STARTED: "Agent 开始处理",

            AgentEventType.LLM_STARTED: "正在请求模型",
            AgentEventType.TEXT_DELTA: "模型文本输出",
            AgentEventType.LLM_COMPLETED: "模型调用完成",

            AgentEventType.TOOL_STARTED: "工具开始执行",
            AgentEventType.TOOL_PROGRESS: "工具执行进度",
            AgentEventType.TOOL_COMPLETED: "工具执行完成",
            AgentEventType.TOOL_FAILED: "工具执行失败",

            AgentEventType.AGENT_COMPLETED: "Agent 处理完成",
            AgentEventType.AGENT_FAILED: "Agent 处理失败",
        }

        return names[self]


@dataclass(frozen=True)
class AgentEvent:
    """
    一条 Agent 运行事件。

    type:
        事件类型。

    message:
        可直接用于终端显示的简短文本。
        对于 TEXT_DELTA，它通常就是本次收到的文本片段。

    data:
        与事件相关的结构化数据，例如工具名称、参数、
        当前轮次、执行耗时和错误信息。
    """

    type: AgentEventType
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
