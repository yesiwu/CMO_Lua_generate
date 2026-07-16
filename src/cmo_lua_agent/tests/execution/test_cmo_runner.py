"""
CMO 单次执行协调器测试。

验证：
1. 成功执行时生成完整运行产物；
2. 控制台包含 Lua 错误时，即使退出码为 0 也判定失败；
3. 超时时生成 process_timeout 错误；
4. 非零退出码且没有可解析错误时生成 process_exit_error；
5. 新 Run 执行 generation/original.lua 快照；
6. 后续修复轮次可以复用同一个 Run。
"""
from __future__ import annotations
import sys
from pathlib import Path

# 路径注入修复：自动定位项目根目录，解决 ModuleNotFoundError
root_dir = Path(__file__).parents[5]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from cmo_lua_agent.core.run_artifact_store import RunArtifactStore
from cmo_lua_agent.execution.cmo_runner import CmoExecutionRecord, CmoRunner
from cmo_lua_agent.execution.models import CmoProcessResult
from cmo_lua_agent.execution.cmo_progress_parser import CmoProgressMessage


class FakeJobConfig:
    """
    模拟 CmoJobConfig。

    只记录 use_script() 收到的参数，不修改真实 JSON。
    """

    def __init__(self) -> None:
        self.calls: list[tuple[Path, int]] = []
        self.entered = False
        self.exited = False

    @contextmanager
    def use_script(
        self,
        *,
        lua_path: Path,
        job_index: int = 0,
    ) -> Iterator[None]:
        self.calls.append(
            (
                Path(lua_path),
                job_index,
            )
        )

        self.entered = True

        try:
            yield
        finally:
            self.exited = True


class FakeProcessRunner:
    """
    返回预先配置的 CmoProcessResult。
    """

    def __init__(
        self,
        result: CmoProcessResult,
    ) -> None:
        self._result = result
        self.calls: list[
            tuple[Path, int | None]
        ] = []
        self.progress_callbacks = []

    def run(
        self,
        *,
        config_path: Path,
        timeout_seconds: int | None = 3600,
        progress_callback=None,
    ) -> CmoProcessResult:
        self.calls.append(
            (
                Path(config_path),
                timeout_seconds,
            )
        )
        self.progress_callbacks.append(progress_callback)

        return self._result


def create_source_lua(
    tmp_path: Path,
    *,
    name: str = "generated.lua",
) -> Path:
    lua_path = tmp_path / name

    lua_path.write_text(
        "-- test lua\n"
        "print('hello')\n",
        encoding="utf-8",
    )

    return lua_path


def create_config_file(
    tmp_path: Path,
) -> Path:
    config_path = (
        tmp_path / "tot-three.json"
    )

    config_path.write_text(
        json.dumps(
            {
                "jobs": [
                    {
                        "name": "single-job",
                        "script": "old.lua",
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return config_path


def test_run_success_creates_artifacts(
    tmp_path: Path,
) -> None:
    source_lua = create_source_lua(
        tmp_path
    )

    config_path = create_config_file(
        tmp_path
    )

    process_result = CmoProcessResult(
        exit_code=0,
        timed_out=False,
        duration_seconds=3.25,
        console_output=(
            "[1/1] 执行成功\n"
            "Simulation completed."
        ),
    )

    job_config = FakeJobConfig()
    process_runner = FakeProcessRunner(
        process_result
    )

    artifact_store = RunArtifactStore(
        runs_dir=tmp_path / "runs",
    )

    runner = CmoRunner(
        config_path=config_path,
        job_config=job_config,
        process_runner=process_runner,
        artifact_store=artifact_store,
    )

    record = runner.run(
        lua_path=source_lua,
        job_index=0,
        timeout_seconds=60,
        run_id="run_success",
    )

    assert isinstance(
        record,
        CmoExecutionRecord,
    )

    assert record.result.success is True
    assert record.result.error is None
    assert record.result.restore_succeeded is True

    assert record.run_paths.run_id == (
        "run_success"
    )

    assert (
        record.round_paths.round_number
        == 0
    )

    assert (
        record.round_paths.cmo_output_path
        .is_file()
    )

    assert (
        record.round_paths.result_path
        .is_file()
    )

    # 新建 Run 时，实际执行的是复制到 generation
    # 目录中的不可变 original.lua，而不是源文件本身。
    assert job_config.calls == [
        (
            record.run_paths.original_lua_path,
            0,
        )
    ]

    assert job_config.entered is True
    assert job_config.exited is True

    assert process_runner.calls == [
        (
            config_path.resolve(),
            60,
        )
    ]

    payload = json.loads(
        record.round_paths.result_path.read_text(
            encoding="utf-8",
        )
    )

    assert payload["success"] is True
    assert payload["exit_code"] == 0
    assert payload["error"] is None


def test_run_forwards_progress_callback_to_process_runner(tmp_path: Path) -> None:
    source_lua = create_source_lua(tmp_path)
    config_path = create_config_file(tmp_path)
    process_runner = FakeProcessRunner(
        CmoProcessResult(
            exit_code=0,
            timed_out=False,
            duration_seconds=1.0,
            console_output="ok",
        )
    )
    callback = lambda event: None
    runner = CmoRunner(
        config_path=config_path,
        job_config=FakeJobConfig(),
        process_runner=process_runner,
        artifact_store=RunArtifactStore(runs_dir=tmp_path / "runs"),
    )

    runner.run(
        lua_path=source_lua,
        run_id="run_progress",
        progress_callback=callback,
    )

    assert process_runner.progress_callbacks == [callback]


def test_exit_code_zero_with_lua_error_is_failure(
    tmp_path: Path,
) -> None:
    source_lua = create_source_lua(
        tmp_path
    )

    config_path = create_config_file(
        tmp_path
    )

    console_output = """
[2026-07-15 10:33:53] [1/1] 失败，状态=NotStarted，原因=LuaFailed，
错误=NLua.Exceptions.LuaScriptException: [string "Console"]:132: 'in' expected near '('
"""

    process_result = CmoProcessResult(
        exit_code=0,
        timed_out=False,
        duration_seconds=0.107,
        console_output=console_output,
    )

    runner = CmoRunner(
        config_path=config_path,
        job_config=FakeJobConfig(),
        process_runner=FakeProcessRunner(
            process_result
        ),
        artifact_store=RunArtifactStore(
            runs_dir=tmp_path / "runs",
        ),
    )

    record = runner.run(
        lua_path=source_lua,
        run_id="run_lua_error",
    )

    result = record.result

    assert result.success is False
    assert result.process_result.exit_code == 0
    assert result.error is not None

    assert (
        result.error.category
        == "lua_syntax_error"
    )

    assert result.error.source == "Console"
    assert result.error.line == 132

    assert (
        result.error.message
        == "'in' expected near '('"
    )


def test_timeout_creates_process_timeout_error(
    tmp_path: Path,
) -> None:
    source_lua = create_source_lua(
        tmp_path
    )

    config_path = create_config_file(
        tmp_path
    )

    process_result = CmoProcessResult(
        exit_code=124,
        timed_out=True,
        duration_seconds=60.01,
        console_output="CMO 执行超时",
    )

    runner = CmoRunner(
        config_path=config_path,
        job_config=FakeJobConfig(),
        process_runner=FakeProcessRunner(
            process_result
        ),
        artifact_store=RunArtifactStore(
            runs_dir=tmp_path / "runs",
        ),
    )

    record = runner.run(
        lua_path=source_lua,
        timeout_seconds=60,
        run_id="run_timeout",
    )

    result = record.result

    assert result.success is False
    assert result.error is not None

    assert (
        result.error.category
        == "process_timeout"
    )

    assert (
        "60" in result.error.message
    )


def test_nonzero_exit_without_parsed_error_creates_process_exit_error(
    tmp_path: Path,
) -> None:
    source_lua = create_source_lua(
        tmp_path
    )

    config_path = create_config_file(
        tmp_path
    )

    process_result = CmoProcessResult(
        exit_code=7,
        timed_out=False,
        duration_seconds=1.2,
        console_output=(
            "CmoBatchRunner stopped."
        ),
    )

    runner = CmoRunner(
        config_path=config_path,
        job_config=FakeJobConfig(),
        process_runner=FakeProcessRunner(
            process_result
        ),
        artifact_store=RunArtifactStore(
            runs_dir=tmp_path / "runs",
        ),
    )

    record = runner.run(
        lua_path=source_lua,
        run_id="run_exit_error",
    )

    result = record.result

    assert result.success is False
    assert result.error is not None

    assert (
        result.error.category
        == "process_exit_error"
    )

    assert "7" in result.error.message


def test_zero_exit_with_failed_batch_job_is_failure(
    tmp_path: Path,
) -> None:
    source_lua = create_source_lua(tmp_path)
    config_path = create_config_file(tmp_path)
    batch_dir = tmp_path / "Results" / "20260715-120000"
    batch_dir.mkdir(parents=True)
    (batch_dir / "runner.log").write_text(
        "执行结束：成功 1，失败 2。\n",
        encoding="utf-8",
    )

    process_result = CmoProcessResult(
        exit_code=0,
        timed_out=False,
        duration_seconds=2.0,
        console_output="BatchRunner exited.",
        batch_result_dir=batch_dir,
    )

    runner = CmoRunner(
        config_path=config_path,
        job_config=FakeJobConfig(),
        process_runner=FakeProcessRunner(process_result),
        artifact_store=RunArtifactStore(runs_dir=tmp_path / "runs"),
    )

    record = runner.run(lua_path=source_lua, run_id="run_batch_failure")

    assert record.result.success is False
    assert record.result.error is not None
    assert record.result.error.category == "batch_job_failure"
    assert record.result.batch_success_count == 1
    assert record.result.batch_failure_count == 2
    assert "成功 1" in record.result.error.message
    assert "失败 2" in record.result.error.message


def test_successful_batch_summary_is_included_in_result(tmp_path: Path) -> None:
    source_lua = create_source_lua(tmp_path)
    config_path = create_config_file(tmp_path)
    batch_dir = tmp_path / "Results" / "20260715-120100"
    batch_dir.mkdir(parents=True)
    (batch_dir / "runner.log").write_text(
        "执行结束：成功 2，失败 0。\n",
        encoding="utf-8",
    )
    runner = CmoRunner(
        config_path=config_path,
        job_config=FakeJobConfig(),
        process_runner=FakeProcessRunner(
            CmoProcessResult(
                exit_code=0,
                timed_out=False,
                duration_seconds=2.0,
                console_output="ok",
                batch_result_dir=batch_dir,
            )
        ),
        artifact_store=RunArtifactStore(runs_dir=tmp_path / "runs"),
    )

    record = runner.run(lua_path=source_lua, run_id="run_batch_success")
    payload = json.loads(record.round_paths.result_path.read_text(encoding="utf-8"))

    assert record.result.success is True
    assert record.result.batch_success_count == 2
    assert record.result.batch_failure_count == 0
    assert payload["batch_success_count"] == 2
    assert payload["batch_failure_count"] == 0


def test_existing_run_can_create_next_repair_round(
    tmp_path: Path,
) -> None:
    original_lua = create_source_lua(
        tmp_path,
        name="original_source.lua",
    )

    repaired_lua = create_source_lua(
        tmp_path,
        name="repaired.lua",
    )

    config_path = create_config_file(
        tmp_path
    )

    artifact_store = RunArtifactStore(
        runs_dir=tmp_path / "runs",
    )

    run_paths = artifact_store.create_run(
        original_lua=original_lua,
        run_id="run_repair",
    )

    process_result = CmoProcessResult(
        exit_code=0,
        timed_out=False,
        duration_seconds=2.0,
        console_output="执行成功",
    )

    job_config = FakeJobConfig()

    runner = CmoRunner(
        config_path=config_path,
        job_config=job_config,
        process_runner=FakeProcessRunner(
            process_result
        ),
        artifact_store=artifact_store,
    )

    record = runner.run(
        lua_path=repaired_lua,
        run_paths=run_paths,
        round_number=1,
    )

    assert (
        record.run_paths
        == run_paths
    )

    assert (
        record.round_paths.round_number
        == 1
    )

    assert (
        record.round_paths.round_dir.name
        == "round_01"
    )

    # 后续轮次执行的是明确传入的 repaired.lua，
    # 不再替换成 generation/original.lua。
    assert job_config.calls == [
        (
            repaired_lua.resolve(),
            0,
        )
    ]
