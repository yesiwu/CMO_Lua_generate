from __future__ import annotations

from cmo_lua_agent.execution.cmo_progress_parser import CmoProgressParser


def test_parser_extracts_scenario_simulation_and_summary() -> None:
    parser = CmoProgressParser()

    events = parser.feed(
        [
            "\ufeff[2026-07-15 20:04:11] CMO 批量推演与战斗采集启动。\n",
            "[2026-07-15 20:04:14] [1/1] 加载想定并执行：all\n",
            "[2026-07-15 20:04:20]   Scenario.GameResolution=1; Global_PulseResolution=1; RunningHeadless=True; TimeCompression=0\n",
            "[2026-07-15 20:04:20]   Lua后对象：事件=16，触发器=16，动作=16；时间压缩=0，脉冲=1秒\n",
            "[2026-07-15 20:04:22]   仿真时间 2026-07-01 00:45:00，现实耗时 2.6 秒，脉冲 1418\n",
            "[2026-07-15 20:04:53] [1/1] 成功，状态=Success，原因=ScenarioEnded，现实耗时=38.919秒\n",
            "[2026-07-15 20:04:53] 执行结束：成功 1，失败 0。\n",
            "[2026-07-15 20:04:53] 批次目录：C:\\synthetic-cmo-results\\20260715-200411\n",
        ]
    )

    assert [event.kind for event in events] == [
        "batch_started",
        "scenario_started",
        "scenario_config",
        "lua_objects",
        "simulation_progress",
        "scenario_completed",
        "batch_completed",
        "result_dir",
    ]
    assert events[1].scenario_index == 1
    assert events[1].scenario_total == 1
    assert events[1].scenario_name == "all"
    assert events[4].simulation_time == "2026-07-01 00:45:00"
    assert events[4].real_elapsed_seconds == 2.6
    assert events[4].pulse == 1418
    assert events[6].success_count == 1
    assert events[6].failure_count == 0
    assert events[7].result_dir == r"C:\synthetic-cmo-results\20260715-200411"


def test_parser_extracts_lua_failure_and_deduplicates_lines() -> None:
    parser = CmoProgressParser()
    failure_line = (
        "[2026-07-15 17:22:26] [1/1] 失败，状态=NotStarted，原因=LuaFailed，"
        "现实耗时=4.269秒，错误=NLua.Exceptions.LuaScriptException: "
        "[string \"Console\"]:132: 'in' expected near '('\n"
    )

    first = parser.feed([failure_line, failure_line, "debug noise\n"])
    second = parser.feed([failure_line])

    assert len(first) == 1
    assert second == []
    event = first[0]
    assert event.kind == "scenario_failed"
    assert event.status == "failed"
    assert event.scenario_index == 1
    assert event.real_elapsed_seconds == 4.269
    assert event.error_message is not None
    assert "Console\"]:132" in event.error_message
