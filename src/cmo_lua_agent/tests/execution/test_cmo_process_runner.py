"""
CMO 子进程运行器测试。

验证：
1. CmoBatchRunner 正常结束时返回退出码和控制台输出；
2. 超时时终止进程树并返回专用退出码 124；
3. 运行器不存在时不启动进程；
4. 配置文件不存在时不启动进程；
5. 能够兼容 UTF-8 和 GBK 控制台输出。
"""
from __future__ import annotations
import sys
from pathlib import Path

# 自动注入项目根目录，修复模块导入报错
root_dir = Path(__file__).parents[5]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import subprocess
from pathlib import Path
from typing import Any

import pytest

from cmo_lua_agent.execution.cmo_process_runner import (
    CmoProcessRunner,
    decode_console_output,
)


class FakeSuccessProcess:
    """
    模拟正常结束的 CmoBatchRunner 进程。
    """

    pid = 10001

    def __init__(self) -> None:
        self.returncode: int | None = None
        self._output_file: Any | None = None

    def set_output_file(self, output_file: Any) -> None:
        self._output_file = output_file

    def wait(
        self,
        timeout: int | float | None = None,
    ) -> int:
        assert self._output_file is not None
        self._output_file.write("CMO 执行成功".encode("utf-8"))
        self._output_file.flush()
        self.returncode = 0
        return self.returncode


class FakeTimeoutProcess:
    """
    第一次 communicate 模拟超时；
    终止进程树后第二次 communicate 返回残余输出。
    """

    pid = 10002
    returncode: int | None = None

    def __init__(self) -> None:
        self.wait_count = 0
        self._output_file: Any | None = None

    def set_output_file(self, output_file: Any) -> None:
        self._output_file = output_file

    def wait(
        self,
        timeout: int | float | None = None,
    ) -> int:
        self.wait_count += 1

        if self.wait_count == 1:
            raise subprocess.TimeoutExpired(
                cmd="CmoBatchRunner.exe",
                timeout=timeout,
            )

        self.returncode = -1
        assert self._output_file is not None
        self._output_file.write("CMO 执行超时".encode("utf-8"))
        self._output_file.flush()
        return self.returncode


class FakeWaitProcess:
    """模拟只应等待直接子进程退出的 BatchRunner。"""

    pid = 10003
    returncode: int | None = None

    def __init__(self) -> None:
        self.wait_calls: list[int | float | None] = []
        self._output_file: Any | None = None

    def set_output_file(self, output_file: Any) -> None:
        self._output_file = output_file

    def wait(self, timeout: int | float | None = None) -> int:
        self.wait_calls.append(timeout)
        assert self._output_file is not None
        self._output_file.write("CMO 直接子进程已退出".encode("utf-8"))
        self._output_file.flush()
        self.returncode = 0
        return self.returncode

    def communicate(
        self,
        timeout: int | float | None = None,
    ) -> tuple[bytes, None]:
        return (b"legacy communicate output", None)


class FakePollingProcess:
    """Creates and extends runner.log across two wait slices."""

    pid = 10004
    returncode: int | None = None

    def __init__(self, results_dir: Path) -> None:
        self.results_dir = results_dir
        self.wait_count = 0
        self._output_file: Any | None = None

    def set_output_file(self, output_file: Any) -> None:
        self._output_file = output_file

    def wait(self, timeout: int | float | None = None) -> int:
        self.wait_count += 1
        batch_dir = self.results_dir / "20260715-210000"
        batch_dir.mkdir(parents=True, exist_ok=True)
        log_path = batch_dir / "runner.log"

        if self.wait_count == 1:
            log_path.write_text(
                "[2026-07-15 21:00:00] CMO 批量推演与战斗采集启动。\n"
                "[2026-07-15 21:00:02] [1/1] 加载想定并执行：all\n",
                encoding="utf-8",
            )
            raise subprocess.TimeoutExpired("CmoBatchRunner.exe", timeout)

        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(
                "[2026-07-15 21:00:04] 仿真时间 2026-07-01 00:45:00，"
                "现实耗时 2.0 秒，脉冲 1418\n"
                "[2026-07-15 21:00:06] 执行结束：成功 1，失败 0。\n"
            )
        assert self._output_file is not None
        self._output_file.write(b"done")
        self._output_file.flush()
        self.returncode = 0
        return 0


def create_required_files(
    tmp_path: Path,
) -> tuple[Path, Path]:
    runner_path = (
        tmp_path / "CmoBatchRunner.exe"
    )
    config_path = (
        tmp_path / "tot-three.json"
    )

    runner_path.write_bytes(b"fake executable")
    config_path.write_text(
        '{"jobs": []}',
        encoding="utf-8",
    )

    return runner_path, config_path


def test_run_returns_process_result_when_process_succeeds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner_path, config_path = (
        create_required_files(tmp_path)
    )

    fake_process = FakeSuccessProcess()

    popen_arguments: dict[str, Any] = {}

    def fake_popen(
        command: list[str],
        **kwargs: Any,
    ) -> FakeSuccessProcess:
        popen_arguments["command"] = command
        popen_arguments["kwargs"] = kwargs
        fake_process.set_output_file(kwargs["stdout"])
        return fake_process

    monkeypatch.setattr(
        subprocess,
        "Popen",
        fake_popen,
    )

    runner = CmoProcessRunner(
        runner_path=runner_path,
        cleanup_process_names=(),
    )

    result = runner.run(
        config_path=config_path,
        timeout_seconds=60,
    )

    assert result.exit_code == 0
    assert result.timed_out is False
    assert result.duration_seconds >= 0
    assert result.console_output == "CMO 执行成功"

    assert popen_arguments["command"] == [
        str(runner_path.resolve()),
        str(config_path.resolve()),
    ]

    assert (
        popen_arguments["kwargs"]["shell"]
        is False
    )

    assert (
        popen_arguments["kwargs"]["cwd"]
        == str(runner_path.parent.resolve())
    )


def test_run_waits_for_direct_child_and_reads_dedicated_log(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner_path, config_path = create_required_files(tmp_path)
    fake_process = FakeWaitProcess()

    def fake_popen(
        command: list[str],
        **kwargs: Any,
    ) -> FakeWaitProcess:
        fake_process.set_output_file(kwargs["stdout"])
        return fake_process

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    runner = CmoProcessRunner(
        runner_path=runner_path,
        cleanup_process_names=(),
    )

    result = runner.run(
        config_path=config_path,
        timeout_seconds=60,
    )

    assert fake_process.wait_calls == [2.0]
    assert result.console_output == "CMO 直接子进程已退出"
    assert list(tmp_path.glob("*.log")) == []


def test_run_reports_new_batch_result_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner_path, config_path = create_required_files(tmp_path)
    results_dir = tmp_path / "Results"
    config_path.write_text(
        '{"outputDirectory": "' + str(results_dir).replace("\\", "\\\\") + '"}',
        encoding="utf-8",
    )
    fake_process = FakeWaitProcess()

    def fake_popen(
        command: list[str],
        **kwargs: Any,
    ) -> FakeWaitProcess:
        fake_process.set_output_file(kwargs["stdout"])
        return fake_process

    original_wait = fake_process.wait

    def wait_and_create_batch(timeout: int | float | None = None) -> int:
        batch_dir = results_dir / "20260715-120000"
        batch_dir.mkdir(parents=True)
        (batch_dir / "runner.log").write_text(
            "执行结束：成功 1，失败 0。\n",
            encoding="utf-8",
        )
        return original_wait(timeout)

    fake_process.wait = wait_and_create_batch  # type: ignore[method-assign]
    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    result = CmoProcessRunner(
        runner_path=runner_path,
        cleanup_process_names=(),
    ).run(config_path=config_path, timeout_seconds=60)

    assert result.batch_result_dir == results_dir / "20260715-120000"


def test_run_polls_only_new_batch_log_and_emits_incremental_progress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner_path, config_path = create_required_files(tmp_path)
    results_dir = tmp_path / "Results"
    old_dir = results_dir / "20260715-190000"
    old_dir.mkdir(parents=True)
    (old_dir / "runner.log").write_text(
        "[1/1] 加载想定并执行：old\n",
        encoding="utf-8",
    )
    config_path.write_text(
        '{"outputDirectory": "' + str(results_dir).replace("\\", "\\\\") + '"}',
        encoding="utf-8",
    )
    fake_process = FakePollingProcess(results_dir)
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: (
            fake_process.set_output_file(kwargs["stdout"]) or fake_process
        ),
    )
    events = []

    result = CmoProcessRunner(
        runner_path=runner_path,
        cleanup_process_names=(),
    ).run(
        config_path=config_path,
        timeout_seconds=60,
        progress_callback=events.append,
    )

    assert fake_process.wait_count == 2
    assert result.batch_result_dir == results_dir / "20260715-210000"
    assert [event.kind for event in events] == [
        "batch_started",
        "scenario_started",
        "simulation_progress",
        "batch_completed",
    ]
    assert all("old" not in event.message for event in events)


def test_progress_callback_failure_does_not_fail_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner_path, config_path = create_required_files(tmp_path)
    results_dir = tmp_path / "Results"
    config_path.write_text(
        '{"outputDirectory": "' + str(results_dir).replace("\\", "\\\\") + '"}',
        encoding="utf-8",
    )
    fake_process = FakePollingProcess(results_dir)
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: (
            fake_process.set_output_file(kwargs["stdout"]) or fake_process
        ),
    )

    result = CmoProcessRunner(
        runner_path=runner_path,
        cleanup_process_names=(),
    ).run(
        config_path=config_path,
        timeout_seconds=60,
        progress_callback=lambda event: (_ for _ in ()).throw(RuntimeError("ui failed")),
    )

    assert result.exit_code == 0


def test_run_terminates_process_tree_when_timeout_occurs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner_path, config_path = (
        create_required_files(tmp_path)
    )

    fake_process = FakeTimeoutProcess()
    terminated_process_ids: list[int] = []

    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: (
            fake_process.set_output_file(kwargs["stdout"])
            or fake_process
        ),
    )

    runner = CmoProcessRunner(
        runner_path=runner_path,
        cleanup_process_names=(),
    )

    monkeypatch.setattr(
        runner,
        "_terminate_process_tree",
        lambda process_id: (
            terminated_process_ids.append(
                process_id
            )
        ),
    )

    result = runner.run(
        config_path=config_path,
        timeout_seconds=1,
    )

    assert result.exit_code == 124
    assert result.timed_out is True
    assert result.console_output == "CMO 执行超时"

    assert terminated_process_ids == [
        fake_process.pid
    ]

    assert fake_process.wait_count == 2


def test_run_rejects_missing_runner(
    tmp_path: Path,
) -> None:
    config_path = (
        tmp_path / "tot-three.json"
    )

    config_path.write_text(
        '{"jobs": []}',
        encoding="utf-8",
    )

    runner = CmoProcessRunner(
        runner_path=(
            tmp_path / "missing.exe"
        ),
        cleanup_process_names=(),
    )

    with pytest.raises(
        FileNotFoundError,
        match="CMO 运行器不存在",
    ):
        runner.run(
            config_path=config_path,
        )


def test_run_rejects_missing_config(
    tmp_path: Path,
) -> None:
    runner_path = (
        tmp_path / "CmoBatchRunner.exe"
    )

    runner_path.write_bytes(
        b"fake executable"
    )

    runner = CmoProcessRunner(
        runner_path=runner_path,
        cleanup_process_names=(),
    )

    with pytest.raises(
        FileNotFoundError,
        match="CMO 任务配置不存在",
    ):
        runner.run(
            config_path=(
                tmp_path / "missing.json"
            ),
        )


def test_run_rejects_invalid_timeout(
    tmp_path: Path,
) -> None:
    runner_path, config_path = (
        create_required_files(tmp_path)
    )

    runner = CmoProcessRunner(
        runner_path=runner_path,
        cleanup_process_names=(),
    )

    with pytest.raises(
        ValueError,
        match="timeout_seconds",
    ):
        runner.run(
            config_path=config_path,
            timeout_seconds=0,
        )


@pytest.mark.parametrize(
    ("raw_output", "expected"),
    [
        (
            "CMO 启动成功".encode("utf-8"),
            "CMO 启动成功",
        ),
        (
            "未将对象引用设置到对象的实例"
            .encode("gbk"),
            "未将对象引用设置到对象的实例",
        ),
        (
            b"",
            "",
        ),
        (
            None,
            "",
        ),
    ],
)
def test_decode_console_output(
    raw_output: bytes | None,
    expected: str,
) -> None:
    assert (
        decode_console_output(raw_output)
        == expected
    )
