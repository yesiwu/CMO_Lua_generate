from __future__ import annotations

from types import SimpleNamespace

import pytest

from cmo_lua_agent.orchestration.agent_loop import AgentLoop
from cmo_lua_agent.orchestration.context_manager import ContextManager
from cmo_lua_agent.orchestration.events import AgentEventType


class InterruptingRegistry:
    def get_definitions(self):
        return []

    def dispatch(self, **kwargs):
        raise KeyboardInterrupt


class ToolUseClient:
    def stream_message(self, **kwargs):
        block = SimpleNamespace(
            type="tool_use",
            id="call_001",
            name="execute_cmo",
            input={"lua_path": "test.lua"},
        )
        return SimpleNamespace(
            content=[block],
            stop_reason="tool_use",
            usage=None,
        )


def test_interrupted_tool_call_does_not_leave_dangling_tool_use() -> None:
    messages = [{"role": "user", "content": "run it"}]
    loop = AgentLoop(
        llm_client=ToolUseClient(),
        tool_registry=InterruptingRegistry(),
        system_prompt="test",
    )

    with pytest.raises(KeyboardInterrupt):
        loop.run(messages)

    assert messages == [{"role": "user", "content": "run it"}]


class FinalClient:
    def stream_message(self, **_kwargs):
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="完成")],
            stop_reason="end_turn",
            usage=None,
        )


class EmptyRegistry:
    def get_definitions(self):
        return []


def test_agent_loop_emits_context_compaction_events_before_model_response() -> None:
    events = []
    messages = [
        {"role": "user" if index % 2 == 0 else "assistant", "content": "上下文" * 100}
        for index in range(20)
    ]
    loop = AgentLoop(
        llm_client=FinalClient(),
        tool_registry=EmptyRegistry(),
        system_prompt="test",
        context_manager=ContextManager(
            context_window_tokens=2_000,
            recent_message_count=4,
        ),
        event_handler=events.append,
    )

    assert loop.run(messages) == "完成"

    event_types = [event.type for event in events]
    assert event_types.index(AgentEventType.CONTEXT_COMPACTION_STARTED) < event_types.index(
        AgentEventType.CONTEXT_COMPACTION_COMPLETED
    )
    assert event_types.index(AgentEventType.CONTEXT_COMPACTION_COMPLETED) < event_types.index(
        AgentEventType.LLM_COMPLETED
    )
    completed = next(
        event
        for event in events
        if event.type is AgentEventType.CONTEXT_COMPACTION_COMPLETED
    )
    assert completed.data["estimated_tokens_after"] <= 1_200
    assert completed.data["strategy"] == "deterministic"
