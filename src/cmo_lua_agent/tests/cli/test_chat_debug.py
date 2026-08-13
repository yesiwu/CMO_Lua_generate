from __future__ import annotations

from io import StringIO

from rich.console import Console
from rich.spinner import Spinner

from cmo_lua_agent.cli.chat import (
    _debug_enabled,
    _format_exception_trace,
)
from cmo_lua_agent.cli.terminal_approval import TerminalApprover
from cmo_lua_agent.cli.terminal_display import TerminalDisplay
from cmo_lua_agent.orchestration.events import (
    AgentEvent,
    AgentEventType,
)
from cmo_lua_agent.orchestration.ui_state import UIState


def test_terminal_approver_pauses_live_display(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr("builtins.input", lambda _: "y")

    approved = TerminalApprover(
        pause=lambda: calls.append("pause"),
        resume=lambda: calls.append("resume"),
    )("execute_cmo", {"lua_path": "test.lua"})

    assert approved is True
    assert calls == ["pause", "resume"]


def test_live_render_does_not_redraw_transcript_history() -> None:
    output = StringIO()
    state = UIState()
    state.add_user_message("old user message")
    state.append_assistant_text("old assistant answer")
    display = TerminalDisplay(
        state,
        console=Console(file=output, force_terminal=False, width=100),
    )

    display._console.print(display.render())

    rendered = output.getvalue()
    assert "old user message" not in rendered
    assert "old assistant answer" not in rendered


def test_llm_stream_pauses_live_and_restores_it_after_completion() -> None:
    output = StringIO()
    display = TerminalDisplay(
        UIState(),
        console=Console(file=output, force_terminal=False, width=100),
    )
    display.start()

    display.handle(
        AgentEvent(
            type=AgentEventType.LLM_STARTED,
            message="requesting model",
        )
    )

    assert display._started is False

    for text in ("answer ", "**bold", " text**", "\n"):
        display.handle(
            AgentEvent(
                type=AgentEventType.TEXT_DELTA,
                message=text,
            )
        )

    display.handle(
        AgentEvent(
            type=AgentEventType.LLM_COMPLETED,
            message="model completed",
        )
    )

    assert display._started is True
    assert output.getvalue().count("●[模型回答]") == 1
    assert "answer **bold text**" in output.getvalue()

    display.stop()


def test_agent_failure_closes_stream_and_allows_next_turn_to_start() -> None:
    output = StringIO()
    display = TerminalDisplay(
        UIState(),
        console=Console(file=output, force_terminal=False, width=100),
    )
    display.start()
    display.handle(
        AgentEvent(type=AgentEventType.LLM_STARTED, message="requesting model")
    )
    display.handle(
        AgentEvent(type=AgentEventType.TEXT_DELTA, message="partial answer")
    )

    display.handle(
        AgentEvent(type=AgentEventType.AGENT_FAILED, message="request failed")
    )

    assert display._assistant_stream_open is False
    display.start()
    assert display._started is True
    display.stop()


def test_context_compaction_has_independent_activity_and_completion_summary() -> None:
    output = StringIO()
    state = UIState()
    display = TerminalDisplay(
        state,
        console=Console(file=output, force_terminal=False, width=120),
    )

    display.handle(
        AgentEvent(
            type=AgentEventType.CONTEXT_COMPACTION_STARTED,
            message="正在压缩上下文",
            data={
                "estimated_tokens_before": 812_400,
                "context_window_tokens": 1_000_000,
                "target_tokens": 600_000,
            },
        )
    )

    assert state.current_activity == "正在智能压缩上下文 · 预计 812,400 / 1,000,000 tokens"

    display.handle(
        AgentEvent(
            type=AgentEventType.CONTEXT_COMPACTION_COMPLETED,
            message="上下文压缩完成",
            data={
                "estimated_tokens_before": 812_400,
                "estimated_tokens_after": 598_200,
                "retained_message_count": 12,
                "duration_seconds": 0.15,
            },
        )
    )

    assert state.current_activity == "正在请求模型"
    rendered = output.getvalue()
    assert "上下文压缩完成" in rendered
    assert "812,400 → 598,200 tokens" in rendered
    assert "保留最近 12 条消息" in rendered


def test_context_compaction_reports_semantic_fallback() -> None:
    output = StringIO()
    state = UIState()
    display = TerminalDisplay(
        state,
        console=Console(file=output, force_terminal=False, width=120),
    )

    display.handle(
        AgentEvent(
            type=AgentEventType.CONTEXT_COMPACTION_COMPLETED,
            message="上下文压缩完成",
            data={
                "estimated_tokens_before": 900_000,
                "estimated_tokens_after": 590_000,
                "retained_message_count": 12,
                "strategy": "deterministic_fallback",
                "fallback_reason": "ConnectionError",
            },
        )
    )

    assert "智能压缩失败，已使用确定性降级压缩" in output.getvalue()
    assert "ConnectionError" in output.getvalue()


def test_agent_needs_input_is_not_rendered_as_agent_failure() -> None:
    output = StringIO()
    state = UIState()
    display = TerminalDisplay(
        state,
        console=Console(file=output, force_terminal=False, width=100),
    )

    display.handle(
        AgentEvent(
            type=AgentEventType.AGENT_NEEDS_INPUT,
            message="请提供场景 JSON 路径。",
        )
    )

    assert state.last_error is None
    assert state.transcript[-1].text == "请提供场景 JSON 路径。"
    assert "需要补充信息" in output.getvalue()
    assert "Agent 执行失败" not in output.getvalue()


def test_live_renders_structured_tool_step_and_removes_it_on_completion() -> None:
    output = StringIO()
    state = UIState()
    display = TerminalDisplay(
        state,
        console=Console(file=output, force_terminal=False, width=100),
    )
    display.handle(
        AgentEvent(
            type=AgentEventType.TOOL_STARTED,
            message="running tool",
            data={
                "tool_use_id": "tool-1",
                "tool_name": "execute_cmo",
                "arguments": {},
            },
        )
    )
    display.handle(
        AgentEvent(
            type=AgentEventType.TOOL_PROGRESS,
            message="仿真时间 2026-07-01 00:45:00",
            data={
                "tool_use_id": "tool-1",
                "tool_name": "execute_cmo",
                "event_type": "step_progress",
                "status": "running",
                "step_id": "simulation",
                "detail": "现实耗时 2 秒 · 脉冲 1418",
                "progress": 0.5,
            },
        )
    )

    display._console.print(display.render())
    rendered = output.getvalue()
    assert "execute_cmo" in rendered
    assert "仿真时间 2026-07-01 00:45:00" in rendered
    assert "脉冲 1418" in rendered

    display.handle(
        AgentEvent(
            type=AgentEventType.TOOL_COMPLETED,
            message='{"success": true}',
            data={
                "tool_use_id": "tool-1",
                "tool_name": "execute_cmo",
                "duration_seconds": 2.0,
            },
        )
    )
    assert state.active_tools == {}


def test_running_tool_step_uses_rich_spinner() -> None:
    state = UIState()
    state.start_tool(
        tool_use_id="tool-1",
        tool_name="execute_cmo",
        arguments={},
    )
    state.update_tool_progress(
        tool_use_id="tool-1",
        event_type="step_started",
        status="running",
        step_id="simulation",
        message="执行 CMO 场景",
    )

    rendered = TerminalDisplay._render_tool_execution(
        state.active_tools["tool-1"]
    )

    assert any(isinstance(item, Spinner) for item in rendered.renderables)


def test_failed_tool_summary_includes_lua_source_and_line() -> None:
    display = TerminalDisplay(UIState())
    summary = display._summarize_tool_result(
        '{"success": false, "error": {'
        '"category": "lua_syntax_error", '
        '"message": "in expected", '
        '"source": "Console", "line": 132}}'
    )

    assert "Console:132" in summary
    assert "in expected" in summary


def test_completed_tool_summary_includes_batch_counts() -> None:
    display = TerminalDisplay(UIState())
    summary = display._summarize_tool_result(
        '{"success": true, "batch_success_count": 2, '
        '"batch_failure_count": 0, "duration_seconds": 3.5}'
    )

    assert "成功 2，失败 0" in summary


def test_debug_enabled_when_environment_is_one(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "CMO_AGENT_DEBUG",
        "1",
    )

    assert _debug_enabled() is True


def test_debug_disabled_when_environment_is_missing(
    monkeypatch,
) -> None:
    monkeypatch.delenv(
        "CMO_AGENT_DEBUG",
        raising=False,
    )

    assert _debug_enabled() is False


def test_format_exception_trace_contains_exception_details() -> None:
    try:
        raise ConnectionError(
            "测试连接失败"
        )
    except ConnectionError as exc:
        trace_text = (
            _format_exception_trace(exc)
        )

    assert "ConnectionError" in trace_text
    assert "测试连接失败" in trace_text
    assert (
        "test_format_exception_trace"
        in trace_text
    )


def test_format_exception_trace_contains_cause_chain() -> None:
    try:
        try:
            raise TimeoutError(
                "底层请求超时"
            )
        except TimeoutError as cause:
            raise ConnectionError(
                "LLM 连接失败"
            ) from cause
    except ConnectionError as exc:
        trace_text = (
            _format_exception_trace(exc)
        )

    assert "TimeoutError" in trace_text
    assert "底层请求超时" in trace_text
    assert "ConnectionError" in trace_text
    assert "LLM 连接失败" in trace_text
