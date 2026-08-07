from __future__ import annotations

from types import SimpleNamespace


class _ToolThenJsonClient:
    def __init__(self) -> None:
        self.calls = 0

    def stream_message(self, **_kwargs):
        self.calls += 1
        if self.calls == 1:
            return SimpleNamespace(
                stop_reason="tool_use",
                usage=None,
                content=[SimpleNamespace(
                    type="tool_use", id="tool-1", name="list_curated_skills", input={},
                )],
            )
        return SimpleNamespace(
            stop_reason="end_turn",
            usage=None,
            content=[SimpleNamespace(type="text", text='{"intents": []}')],
        )


def test_agent_loop_json_client_allows_curated_skill_tool_before_json() -> None:
    from cmo_lua_agent.llm.agent_loop_json_client import AgentLoopJsonClient
    from cmo_lua_agent.tools.tool_base.registry import ToolRegistry
    from cmo_lua_agent.tools.tool_base.base import BaseTool, ToolResult

    class _ListTool(BaseTool):
        name = "list_curated_skills"
        description = "list"
        input_schema = {"type": "object", "properties": {}, "additionalProperties": False}

        def execute(self, arguments, context=None):
            return ToolResult('{"skills": []}')

    client = _ToolThenJsonClient()
    registry = ToolRegistry()
    registry.register(_ListTool())
    adapter = AgentLoopJsonClient(client=client, tool_registry=registry, max_turns=3)

    assert adapter.complete_json(system="Return JSON.", prompt="Plan.") == {"intents": []}
    assert adapter.last_calls == 2


def test_agent_loop_json_client_accepts_a_single_fenced_json_response() -> None:
    from cmo_lua_agent.llm.agent_loop_json_client import AgentLoopJsonClient
    from cmo_lua_agent.tools.tool_base.registry import ToolRegistry

    class _FencedClient:
        def stream_message(self, **_kwargs):
            return SimpleNamespace(
                stop_reason="end_turn",
                usage=None,
                content=[SimpleNamespace(type="text", text="```json\n{\"intents\": []}\n```")],
            )

    adapter = AgentLoopJsonClient(
        client=_FencedClient(), tool_registry=ToolRegistry(), max_turns=1
    )

    assert adapter.complete_json(system="Return JSON.", prompt="Plan.") == {"intents": []}
