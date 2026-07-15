"""
Agent 运行事件模型测试。

这些测试用于固定 AgentEvent 和 AgentEventType 的基本协议，
确保终端显示层、日志系统以及未来的 Web UI
都可以依赖统一且稳定的事件结构。

当前测试先于实现编写。
运行时应先因为 events.py 尚未实现而失败。
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from cmo_lua_agent.orchestration.events import (
    AgentEvent,
    AgentEventType,
)


def test_event_type_values_are_stable() -> None:
    """
    事件枚举值将被终端显示层和日志系统使用，
    因此名称和值都应保持稳定。
    """
    assert AgentEventType.AGENT_STARTED.value == "agent_started"
    assert AgentEventType.LLM_STARTED.value == "llm_started"
    assert AgentEventType.TEXT_DELTA.value == "text_delta"
    assert AgentEventType.LLM_COMPLETED.value == "llm_completed"

    assert AgentEventType.TOOL_STARTED.value == "tool_started"
    assert AgentEventType.TOOL_COMPLETED.value == "tool_completed"
    assert AgentEventType.TOOL_FAILED.value == "tool_failed"

    assert AgentEventType.AGENT_COMPLETED.value == "agent_completed"
    assert AgentEventType.AGENT_FAILED.value == "agent_failed"


def test_event_uses_empty_message_and_data_by_default() -> None:
    """
    创建事件时可以只提供事件类型。
    """
    event = AgentEvent(
        type=AgentEventType.AGENT_STARTED,
    )

    assert event.type is AgentEventType.AGENT_STARTED
    assert event.message == ""
    assert event.data == {}


def test_event_data_is_not_shared_between_instances() -> None:
    """
    不同事件实例不能共享同一个默认字典。
    """
    first = AgentEvent(
        type=AgentEventType.LLM_STARTED,
    )

    second = AgentEvent(
        type=AgentEventType.LLM_STARTED,
    )

    assert first.data is not second.data


def test_event_can_carry_structured_tool_information() -> None:
    """
    工具事件可以携带工具名称、参数、耗时等结构化信息。
    """
    event = AgentEvent(
        type=AgentEventType.TOOL_COMPLETED,
        message="read_file 执行完成",
        data={
            "tool_use_id": "tool_001",
            "tool_name": "read_file",
            "arguments": {
                "path": "README.md",
                "limit": 20,
            },
            "duration_seconds": 0.12,
        },
    )

    assert event.message == "read_file 执行完成"
    assert event.data["tool_name"] == "read_file"
    assert event.data["arguments"]["path"] == "README.md"
    assert event.data["duration_seconds"] == 0.12


def test_event_is_immutable() -> None:
    """
    事件发出后不应被显示层或其他监听器修改。
    """
    event = AgentEvent(
        type=AgentEventType.TEXT_DELTA,
        message="正在生成",
    )

    with pytest.raises(FrozenInstanceError):
        event.message = "被修改的内容"  # type: ignore[misc]