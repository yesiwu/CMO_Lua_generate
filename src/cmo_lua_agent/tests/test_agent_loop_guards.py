from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from cmo_lua_agent.orchestration.agent_loop import AgentLoop
from cmo_lua_agent.orchestration.events import AgentEventType
from cmo_lua_agent.tools.tool_base.base import ToolResult


def _tool_use(call_id: str, name: str, arguments: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        type="tool_use",
        id=call_id,
        name=name,
        input=arguments,
    )


def _response(*content: Any, stop_reason: str = "tool_use") -> SimpleNamespace:
    return SimpleNamespace(content=list(content), stop_reason=stop_reason, usage=None)


class ScriptedClient:
    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self._responses = iter(responses)
        self.requests: list[list[dict[str, Any]]] = []

    def stream_message(self, **kwargs: Any) -> SimpleNamespace:
        self.requests.append(list(kwargs["messages"]))
        return next(self._responses)


class SafeTool:
    requires_approval = False


class FakeRegistry:
    def __init__(self, results: dict[str, list[ToolResult]]) -> None:
        self._results = {name: list(values) for name, values in results.items()}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get_definitions(self) -> list[dict[str, Any]]:
        return []

    def get(self, name: str) -> SafeTool | None:
        return SafeTool() if name in {"read_file", "list_directory"} else None

    def dispatch(self, *, name: str, arguments: dict[str, Any], **_: Any) -> ToolResult:
        self.calls.append((name, arguments))
        return self._results[name].pop(0)


def test_text_response_without_json_path_requires_no_tool_call() -> None:
    client = ScriptedClient(
        [_response(SimpleNamespace(type="text", text="请提供场景 JSON 路径。"), stop_reason="end_turn")]
    )
    registry = FakeRegistry({})
    loop = AgentLoop(client, registry, "test")
    messages = [{"role": "user", "content": "使用 Lua Skill 生成 Lua"}]

    result = loop.run(messages)

    assert result == "请提供场景 JSON 路径。"
    assert registry.calls == []
    assert len(client.requests) == 1


def test_directory_read_recovers_once_with_list_directory() -> None:
    original_error = json.dumps(
        {
            "success": False,
            "error": {"message": "目标路径是目录", "suggested_tool": "list_directory"},
        }
    )
    client = ScriptedClient(
        [
            _response(_tool_use("call-1", "read_file", {"path": "runs"})),
            _response(SimpleNamespace(type="text", text="目录已列出。"), stop_reason="end_turn"),
        ]
    )
    registry = FakeRegistry(
        {
            "read_file": [ToolResult(original_error, is_error=True)],
            "list_directory": [ToolResult('{"success": true, "entries": []}')],
        }
    )
    events = []
    loop = AgentLoop(client, registry, "test", event_handler=events.append)
    messages = [{"role": "user", "content": "读取 runs"}]

    assert loop.run(messages) == "目录已列出。"
    assert registry.calls == [
        ("read_file", {"path": "runs"}),
        ("list_directory", {"path": "runs"}),
    ]
    tool_result = client.requests[1][-1]["content"][0]
    payload = json.loads(tool_result["content"])
    assert payload["recovered_from"]["tool"] == "read_file"
    assert payload["recovery"]["tool"] == "list_directory"
    assert [event.type for event in events].count(AgentEventType.TOOL_STARTED) == 2


def test_repeated_identical_failure_ends_with_actionable_summary() -> None:
    failure = ToolResult('{"success": false, "error": {"message": "文件不存在"}}', is_error=True)
    client = ScriptedClient(
        [
            _response(_tool_use("call-1", "read_file", {"path": "missing.txt"})),
            _response(_tool_use("call-2", "read_file", {"path": "missing.txt"})),
        ]
    )
    registry = FakeRegistry({"read_file": [failure, failure]})
    events = []
    loop = AgentLoop(client, registry, "test", event_handler=events.append)
    messages = [{"role": "user", "content": "读取文件"}]

    result = loop.run(messages)

    assert "连续失败两次" in result
    assert len(registry.calls) == 2
    assert events[-1].type is AgentEventType.AGENT_NEEDS_INPUT
    assert messages[-1] == {"role": "assistant", "content": result}


def test_default_loop_has_no_fixed_turn_ceiling() -> None:
    tool_calls = [
        _response(_tool_use(f"call-{index}", "generate_cmo_lua", {"json_path": "a.json"}))
        for index in range(1, 12)
    ]
    client = ScriptedClient([
        *tool_calls,
        _response(SimpleNamespace(type="text", text="done"), stop_reason="end_turn"),
    ])
    registry = FakeRegistry({"generate_cmo_lua": [ToolResult('{"success": true}')] * 11})

    result = AgentLoop(client, registry, "test").run([
        {"role": "user", "content": "complete a long task"},
    ])

    assert result == "done"
    assert len(client.requests) == 12
def test_three_discovery_turns_end_without_max_turn_exception() -> None:
    client = ScriptedClient(
        [
            _response(_tool_use("call-1", "list_directory", {"path": "one"})),
            _response(_tool_use("call-2", "list_directory", {"path": "two"})),
            _response(_tool_use("call-3", "list_directory", {"path": "three"})),
        ]
    )
    registry = FakeRegistry(
        {"list_directory": [ToolResult("{}"), ToolResult("{}"), ToolResult("{}")]}
    )
    loop = AgentLoop(client, registry, "test")
    messages = [{"role": "user", "content": "探索"}]

    result = loop.run(messages)

    assert "连续进行了目录、Skill 或文件探索" in result
    assert len(client.requests) == 3
    assert messages[-1] == {"role": "assistant", "content": result}


def test_explicit_json_path_does_not_trigger_discovery_budget() -> None:
    client = ScriptedClient(
        [
            _response(_tool_use("call-1", "read_file", {"path": "scene.json"})),
            _response(_tool_use("call-2", "list_skills", {})),
            _response(_tool_use("call-3", "load_skill", {"skill_id": "cmo-lua"})),
            _response(
                _tool_use(
                    "call-4",
                    "generate_cmo_lua",
                    {"json_path": "scene.json"},
                )
            ),
            _response(
                SimpleNamespace(type="text", text="Lua 已生成。"),
                stop_reason="end_turn",
            ),
        ]
    )
    registry = FakeRegistry(
        {
            "read_file": [ToolResult("{}")],
            "list_skills": [ToolResult("{}")],
            "load_skill": [ToolResult("{}")],
            "generate_cmo_lua": [ToolResult('{"success": true}')],
        }
    )
    loop = AgentLoop(client, registry, "test")
    messages = [{"role": "user", "content": "将 D:\\work\\scene.json 转为 Lua"}]

    assert loop.run(messages) == "Lua 已生成。"
    assert [name for name, _ in registry.calls] == [
        "read_file",
        "list_skills",
        "load_skill",
        "generate_cmo_lua",
    ]


def test_turn_budget_ends_with_summary_instead_of_raising() -> None:
    client = ScriptedClient(
        [
            _response(_tool_use("call-1", "generate_cmo_lua", {"json_path": "a.json"})),
            _response(SimpleNamespace(type="text", text="completed"), stop_reason="end_turn"),
        ]
    )
    registry = FakeRegistry({"generate_cmo_lua": [ToolResult('{"success": true}')]})
    loop = AgentLoop(client, registry, "test", max_turns=1)
    messages = [{"role": "user", "content": "生成"}]

    result = loop.run(messages)

    assert result == "completed"
    assert messages[-1]["content"][0].text == result
