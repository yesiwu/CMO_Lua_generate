from __future__ import annotations

from cmo_lua_agent.orchestration.ui_state import UIState


def test_ui_state_defaults_to_an_unbounded_agent_loop() -> None:
    assert UIState().max_turns is None


def test_tool_progress_tracks_steps_and_limits_output_lines() -> None:
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
    state.update_tool_progress(
        tool_use_id="tool-1",
        event_type="step_progress",
        status="running",
        step_id="simulation",
        message="仿真时间 2026-07-01 00:45:00",
        detail="脉冲 1418",
        progress=0.5,
    )
    for index in range(10):
        state.update_tool_progress(
            tool_use_id="tool-1",
            event_type="output",
            status="running",
            step_id="simulation",
            message=f"line {index}",
        )

    execution = state.active_tools["tool-1"]
    assert execution.arguments == {}
    step = execution.steps["simulation"]
    assert step.message == "仿真时间 2026-07-01 00:45:00"
    assert step.detail == "脉冲 1418"
    assert step.progress == 0.5
    assert execution.output_lines == [f"line {index}" for index in range(2, 10)]


def test_tool_execution_copies_arguments() -> None:
    arguments = {"lua_path": "test.lua"}
    state = UIState()
    state.start_tool(
        tool_use_id="tool-1",
        tool_name="execute_cmo",
        arguments=arguments,
    )
    arguments["lua_path"] = "changed.lua"

    assert state.active_tools["tool-1"].arguments == {"lua_path": "test.lua"}


def test_finishing_tool_removes_only_matching_active_execution() -> None:
    state = UIState()
    for tool_id in ("tool-1", "tool-2"):
        state.start_tool(
            tool_use_id=tool_id,
            tool_name="execute_cmo",
            arguments={},
        )

    state.finish_tool(
        tool_use_id="tool-1",
        success=True,
        content="ok",
        duration_seconds=1.0,
    )

    assert "tool-1" not in state.active_tools
    assert "tool-2" in state.active_tools
