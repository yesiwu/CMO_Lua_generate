from __future__ import annotations

from types import SimpleNamespace

import pytest

from cmo_lua_agent.orchestration.agent_loop import AgentLoop


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
