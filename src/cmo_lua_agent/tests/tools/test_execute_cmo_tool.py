"""
ExecuteCmoTool 测试。

验证：
1. 工具元数据和输入 Schema；
2. 成功执行时返回 is_error=False；
3. CMO 业务失败时返回 is_error=True；
4. 返回内容包含 run_id 和轮次目录；
5. 参数会正确传给 CmoRunner；
6. 非法参数会在启动 CMO 前被拒绝。
"""
from __future__ import annotations
import sys
from pathlib import Path

# 自动注入项目根目录，解决 ModuleNotFoundError
root_dir = Path(__file__).parents[5]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import json
from pathlib import Path

import pytest

from cmo_lua_agent.core.run_artifact_store import RoundPaths, RunPaths
from cmo_lua_agent.execution.cmo_runner import CmoExecutionRecord
from cmo_lua_agent.execution.models import CmoError, CmoProcessResult, CmoRunResult
from cmo_lua_agent.execution.cmo_progress_parser import CmoProgressMessage
from cmo_lua_agent.tools.execute_cmo_tool import ExecuteCmoTool
from cmo_lua_agent.tools.tool_base.context import ToolContext
from cmo_lua_agent.tools.tool_base.progress import ToolProgressReporter


class FakeCmoRunner:
    """
    返回预先准备好的执行记录，并保存调用参数。
    """

    def __init__(self, record: CmoExecutionRecord) -> None:
        self._record = record
        self.calls: list[dict] = []

    def run(
        self,
        *,
        lua_path: Path,
        job_index: int = 0,
        timeout_seconds: int | None = 3600,
        progress_callback=None,
    ) -> CmoExecutionRecord:
        self.calls.append({
            "lua_path": lua_path,
            "job_index": job_index,
            "timeout_seconds": timeout_seconds,
        })
        if progress_callback is not None:
            progress_callback(
                CmoProgressMessage(
                    kind="batch_started",
                    status="running",
                    message="CMO 批次已启动",
                )
            )
            progress_callback(
                CmoProgressMessage(
                    kind="scenario_started",
                    status="running",
                    message="[1/1] 加载场景 all",
                    progress=0.0,
                )
            )
            progress_callback(
                CmoProgressMessage(
                    kind="simulation_progress",
                    status="running",
                    message="仿真时间 2026-07-01 00:45:00",
                    detail="现实耗时 2 秒 · 脉冲 1418",
                    real_elapsed_seconds=2.0,
                    pulse=1418,
                )
            )
            progress_callback(
                CmoProgressMessage(
                    kind="batch_completed",
                    status="success" if self._record.result.success else "failed",
                    message=(
                        "批次完成：成功 1，失败 0"
                        if self._record.result.success
                        else "批次完成：成功 0，失败 1"
                    ),
                    success_count=1 if self._record.result.success else 0,
                    failure_count=0 if self._record.result.success else 1,
                )
            )
            progress_callback(
                CmoProgressMessage(
                    kind="result_dir",
                    status="success",
                    message="CMO 结果目录已生成",
                    detail=r"C:\synthetic-cmo-results\test",
                    result_dir=r"C:\synthetic-cmo-results\test",
                )
            )
        return self._record


def build_record(tmp_path: Path, *, success: bool) -> CmoExecutionRecord:
    run_dir = tmp_path / "runs" / "run_test_001"
    generation_dir = run_dir / "generation"
    repair_rounds_dir = run_dir / "repair_rounds"
    round_dir = repair_rounds_dir / "round_00"

    generation_dir.mkdir(parents=True)
    round_dir.mkdir(parents=True)

    lua_path = generation_dir / "original.lua"
    log_path = round_dir / "cmo_output.txt"

    lua_path.write_text("-- test lua", encoding="utf-8")
    log_path.write_text("CMO output", encoding="utf-8")

    process_result = CmoProcessResult(
        exit_code=0,
        timed_out=False,
        duration_seconds=4.25,
        console_output="CMO output",
    )

    error = None
    if not success:
        error = CmoError(
            category="lua_syntax_error",
            message="'in' expected near '('",
            source="Console",
            line=132,
        )

    result = CmoRunResult(
        success=success,
        lua_path=lua_path,
        log_path=log_path,
        process_result=process_result,
        restore_succeeded=True,
        error=error,
    )

    run_paths = RunPaths(
        run_id="run_test_001",
        run_dir=run_dir,
        generation_dir=generation_dir,
        original_lua_path=lua_path,
        repair_rounds_dir=repair_rounds_dir,
    )

    round_paths = RoundPaths(
        round_number=0,
        round_dir=round_dir,
        cmo_output_path=log_path,
        result_path=round_dir / "result.json",
    )

    return CmoExecutionRecord(result=result, run_paths=run_paths, round_paths=round_paths)


def test_tool_metadata() -> None:
    assert ExecuteCmoTool.name == "execute_cmo"
    assert ExecuteCmoTool.toolset == "cmo"
    assert ExecuteCmoTool.requires_approval is True

    schema = ExecuteCmoTool.input_schema
    assert schema["type"] == "object"
    assert schema["required"] == ["lua_path"]
    assert schema["properties"]["lua_path"]["type"] == "string"
    assert schema["properties"]["job_index"]["minimum"] == 0
    assert schema["properties"]["timeout_seconds"]["minimum"] == 1


def test_execute_success_returns_non_error_result(tmp_path: Path) -> None:
    record = build_record(tmp_path, success=True)
    fake_runner = FakeCmoRunner(record)
    tool = ExecuteCmoTool(cmo_runner=fake_runner)

    input_lua = tmp_path / "input.lua"
    result = tool.execute({
        "lua_path": str(input_lua),
        "job_index": 0,
        "timeout_seconds": 120,
    })

    assert result.is_error is False
    payload = json.loads(result.content)
    assert payload["success"] is True
    assert payload["run_id"] == "run_test_001"
    assert payload["round_number"] == 0
    assert payload["error"] is None
    assert fake_runner.calls == [{
        "lua_path": input_lua,
        "job_index": 0,
        "timeout_seconds": 120,
    }]


def test_execute_failure_returns_error_result(tmp_path: Path) -> None:
    record = build_record(tmp_path, success=False)
    fake_runner = FakeCmoRunner(record)
    tool = ExecuteCmoTool(cmo_runner=fake_runner)

    result = tool.execute({"lua_path": str(tmp_path / "broken.lua")})
    assert result.is_error is True
    payload = json.loads(result.content)
    assert payload["success"] is False
    assert payload["error"] == {
        "category": "lua_syntax_error",
        "message": "'in' expected near '('",
        "source": "Console",
        "line": 132,
    }
    assert payload["round_dir"].endswith("round_00")


def test_execute_reports_five_structured_steps(tmp_path: Path) -> None:
    events = []
    tool = ExecuteCmoTool(cmo_runner=FakeCmoRunner(build_record(tmp_path, success=True)))
    context = ToolContext(
        tool_use_id="tool-1",
        tool_name="execute_cmo",
        progress=ToolProgressReporter(
            tool_use_id="tool-1",
            tool_name="execute_cmo",
            callback=events.append,
        ),
    )

    result = tool.execute(
        {"lua_path": str(tmp_path / "input.lua")},
        context=context,
    )

    assert result.is_error is False
    started_steps = [
        event.step_id for event in events if event.event_type == "step_started"
    ]
    assert started_steps == [
        "validate",
        "prepare",
        "launch",
        "simulation",
        "collect",
    ]
    assert any(
        event.event_type == "step_progress"
        and event.step_id == "simulation"
        and "仿真时间" in event.message
        for event in events
    )
    assert events[-1].event_type == "tool_completed"
    simulation_completed_at = next(
        index
        for index, event in enumerate(events)
        if event.event_type == "step_completed" and event.step_id == "simulation"
    )
    assert not any(
        event.event_type == "step_progress" and event.step_id == "simulation"
        for event in events[simulation_completed_at + 1 :]
    )


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"lua_path": ""},
        {"lua_path": "test.lua", "job_index": -1},
        {"lua_path": "test.lua", "job_index": True},
        {"lua_path": "test.lua", "timeout_seconds": 0},
        {"lua_path": "test.lua", "timeout_seconds": 8000},
    ],
)
def test_execute_rejects_invalid_arguments(tmp_path: Path, arguments: dict) -> None:
    record = build_record(tmp_path, success=True)
    fake_runner = FakeCmoRunner(record)
    tool = ExecuteCmoTool(cmo_runner=fake_runner)

    with pytest.raises(ValueError):
        tool.execute(arguments)
    assert fake_runner.calls == []
