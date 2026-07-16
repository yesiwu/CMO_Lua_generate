
"""
CMO BatchRunner 子进程运行器。

该模块只负责 Windows 进程层面的工作：

1. 校验 CmoBatchRunner.exe 和任务 JSON 是否存在；
2. 运行前清理指定的 CMO 残留进程；
3. 启动 CmoBatchRunner.exe；
4. 捕获 stdout 和 stderr；
5. 处理全局运行超时；
6. 超时时终止完整进程树；
7. 运行结束后再次清理残留进程；
8. 返回标准 CmoProcessResult。

本模块不修改任务 JSON、不解析 Lua 错误、
不保存运行产物，也不调用 LLM。
"""

from __future__ import annotations

import codecs
import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Callable, Final

from cmo_lua_agent.execution.cmo_progress_parser import (
    CmoProgressMessage,
    CmoProgressParser,
)
from cmo_lua_agent.execution.models import (
    CmoProcessResult,
)


logger = logging.getLogger(__name__)


DEFAULT_TIMEOUT_SECONDS: Final[int] = 3600

TIMEOUT_EXIT_CODE: Final[int] = 124
PROGRESS_POLL_INTERVAL_SECONDS: Final[float] = 2.0


class _RunnerLogTail:
    """Incrementally decode complete UTF-8 lines from a growing log file."""

    def __init__(self) -> None:
        self._offset = 0
        self._buffer = ""
        self._decoder = self._new_decoder()

    @staticmethod
    def _new_decoder():
        return codecs.getincrementaldecoder("utf-8-sig")(errors="replace")

    def read(self, path: Path, *, final: bool = False) -> list[str]:
        try:
            size = path.stat().st_size
            if size < self._offset:
                self._offset = 0
                self._buffer = ""
                self._decoder = self._new_decoder()
            with path.open("rb") as log_file:
                log_file.seek(self._offset)
                chunk = log_file.read()
                self._offset = log_file.tell()
        except OSError:
            return []

        self._buffer += self._decoder.decode(chunk, final=final)
        lines: list[str] = []
        remaining = self._buffer
        while True:
            newline_index = remaining.find("\n")
            if newline_index < 0:
                break
            lines.append(remaining[: newline_index + 1])
            remaining = remaining[newline_index + 1 :]
        if final and remaining:
            lines.append(remaining)
            remaining = ""
        self._buffer = remaining
        return lines


def decode_console_output(
    raw_output: bytes | None,
) -> str:
    """
    将 Windows 子进程字节输出转换为字符串。

    CMO、批处理文件和 Windows 控制台可能使用不同编码，
    因此依次尝试常见编码。

    Args:
        raw_output:
            subprocess 捕获的原始字节。

    Returns:
        解码后的控制台文本。
    """
    if not raw_output:
        return ""

    encodings = (
        "utf-8-sig",
        "utf-8",
        "gb18030",
        "gbk",
    )

    for encoding in encodings:
        try:
            return raw_output.decode(
                encoding
            )
        except UnicodeDecodeError:
            continue

    return raw_output.decode(
        "utf-8",
        errors="replace",
    )


class CmoProcessRunner:
    """
    单实例、串行的 CMO BatchRunner 进程执行器。

    当前 MVP 一次只启动一个 CmoBatchRunner，
    不支持异步执行和多个 Python 进程并发调用。
    """

    def __init__(
        self,
        *,
        runner_path: Path,
        cleanup_process_names: tuple[
            str,
            ...,
        ] = (
            "Command.exe",
            "Launcher.exe",
        ),
    ) -> None:
        """
        初始化运行器。

        Args:
            runner_path:
                CmoBatchRunner.exe 的路径。

            cleanup_process_names:
                运行前后需要检查并清理的进程名称。

                测试时可以传入空元组，避免真正调用
                Windows taskkill。
        """
        self._runner_path = Path(
            runner_path
        )

        self._cleanup_process_names = tuple(
            cleanup_process_names
        )

    @property
    def runner_path(self) -> Path:
        """
        返回 CmoBatchRunner.exe 路径。
        """
        return self._runner_path

    def run(
        self,
        *,
        config_path: Path,
        timeout_seconds: int | None = (
            DEFAULT_TIMEOUT_SECONDS
        ),
        progress_callback: Callable[[CmoProgressMessage], None] | None = None,
    ) -> CmoProcessResult:
        """
        启动一次 CmoBatchRunner 执行。

        Args:
            config_path:
                CmoBatchRunner 使用的任务 JSON 路径。

            timeout_seconds:
                最大执行时长，单位秒。

                传入 None 表示不设置超时；
                传入整数时必须大于 0。

        Returns:
            CmoProcessResult。

        Raises:
            FileNotFoundError:
                运行器或配置文件不存在。

            ValueError:
                timeout_seconds 非法。

            OSError:
                Windows 无法启动 CmoBatchRunner。
        """
        runner_path = (
            self._runner_path.resolve()
        )

        config_path = Path(
            config_path
        ).resolve()

        self._validate_inputs(
            runner_path=runner_path,
            config_path=config_path,
            timeout_seconds=timeout_seconds,
        )

        self._cleanup_processes(
            stage="运行前"
        )

        results_dir = self._read_results_dir(
            config_path=config_path
        )
        known_batch_dirs = self._list_batch_dirs(
            results_dir=results_dir
        )

        started_at = perf_counter()

        process: subprocess.Popen[
            bytes
        ] | None = None

        console_log_path: Path | None = None
        exit_code = 1
        timed_out = False
        batch_result_dir: Path | None = None
        progress_parser = CmoProgressParser()
        runner_log_tail = _RunnerLogTail()

        try:
            file_descriptor, raw_console_log_path = (
                tempfile.mkstemp(
                    prefix="cmo-batch-",
                    suffix=".log",
                )
            )
            os.close(file_descriptor)
            console_log_path = Path(raw_console_log_path)

            with console_log_path.open("w+b") as console_log:
                process = subprocess.Popen(
                    [
                        str(runner_path),
                        str(config_path),
                    ],
                    cwd=str(
                        runner_path.parent
                    ),
                    stdin=subprocess.DEVNULL,
                    stdout=console_log,
                    stderr=subprocess.STDOUT,
                    shell=False,
                )

                while True:
                    remaining = (
                        None
                        if timeout_seconds is None
                        else timeout_seconds - (perf_counter() - started_at)
                    )
                    if remaining is not None and remaining <= 0:
                        timed_out = True
                    else:
                        wait_timeout = (
                            PROGRESS_POLL_INTERVAL_SECONDS
                            if remaining is None
                            else min(PROGRESS_POLL_INTERVAL_SECONDS, remaining)
                        )
                        try:
                            # 不使用 communicate()：CMO 子进程可能继承 stdout
                            # 管道，导致 BatchRunner 已退出但管道仍未 EOF。
                            process.wait(timeout=wait_timeout)
                        except subprocess.TimeoutExpired:
                            batch_result_dir = self._poll_runner_log(
                                results_dir=results_dir,
                                known_batch_dirs=known_batch_dirs,
                                batch_result_dir=batch_result_dir,
                                log_tail=runner_log_tail,
                                parser=progress_parser,
                                callback=progress_callback,
                            )
                            if (
                                remaining is not None
                                and remaining <= PROGRESS_POLL_INTERVAL_SECONDS
                            ):
                                timed_out = True
                            else:
                                continue
                        else:
                            exit_code = (
                                process.returncode
                                if process.returncode is not None
                                else 1
                            )
                            batch_result_dir = self._poll_runner_log(
                                results_dir=results_dir,
                                known_batch_dirs=known_batch_dirs,
                                batch_result_dir=batch_result_dir,
                                log_tail=runner_log_tail,
                                parser=progress_parser,
                                callback=progress_callback,
                                final=True,
                            )
                            break

                    if timed_out:
                        exit_code = TIMEOUT_EXIT_CODE
                        logger.warning(
                            "CMO 执行超过 %s 秒，准备终止进程树，PID=%s",
                            timeout_seconds,
                            process.pid,
                        )
                        self._terminate_process_tree(process.pid)
                        process.wait()
                        batch_result_dir = self._poll_runner_log(
                            results_dir=results_dir,
                            known_batch_dirs=known_batch_dirs,
                            batch_result_dir=batch_result_dir,
                            log_tail=runner_log_tail,
                            parser=progress_parser,
                            callback=progress_callback,
                            final=True,
                        )
                        break

            raw_output = console_log_path.read_bytes()

        finally:
            self._cleanup_processes(
                stage="运行后"
            )

            if console_log_path is not None:
                try:
                    console_log_path.unlink(
                        missing_ok=True
                    )
                except OSError as exc:
                    logger.warning(
                        "无法删除 CMO 临时控制台日志 %s：%s",
                        console_log_path,
                        exc,
                    )

        duration_seconds = (
            perf_counter() - started_at
        )

        return CmoProcessResult(
            exit_code=exit_code,
            timed_out=timed_out,
            duration_seconds=duration_seconds,
            console_output=(
                decode_console_output(
                    raw_output
                )
            ),
            batch_result_dir=(
                batch_result_dir
                or self._find_new_batch_dir(
                    results_dir=results_dir,
                    known_batch_dirs=known_batch_dirs,
                )
            ),
        )

    @classmethod
    def _poll_runner_log(
        cls,
        *,
        results_dir: Path | None,
        known_batch_dirs: set[Path],
        batch_result_dir: Path | None,
        log_tail: _RunnerLogTail,
        parser: CmoProgressParser,
        callback: Callable[[CmoProgressMessage], None] | None,
        final: bool = False,
    ) -> Path | None:
        if batch_result_dir is None:
            batch_result_dir = cls._find_new_batch_dir(
                results_dir=results_dir,
                known_batch_dirs=known_batch_dirs,
            )
        if batch_result_dir is None:
            return None

        lines = log_tail.read(batch_result_dir / "runner.log", final=final)
        for event in parser.feed(lines):
            if callback is None:
                continue
            try:
                callback(event)
            except Exception:
                logger.debug("CMO 进度回调执行失败", exc_info=True)
        return batch_result_dir

    @staticmethod
    def _read_results_dir(
        *,
        config_path: Path,
    ) -> Path | None:
        try:
            config = json.loads(
                config_path.read_text(
                    encoding="utf-8-sig",
                )
            )
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None

        output_directory = config.get("outputDirectory")

        if not isinstance(output_directory, str):
            return None

        if not output_directory.strip():
            return None

        return Path(output_directory).resolve()

    @staticmethod
    def _list_batch_dirs(
        *,
        results_dir: Path | None,
    ) -> set[Path]:
        if results_dir is None or not results_dir.is_dir():
            return set()

        return {
            path.resolve()
            for path in results_dir.iterdir()
            if path.is_dir()
        }

    @classmethod
    def _find_new_batch_dir(
        cls,
        *,
        results_dir: Path | None,
        known_batch_dirs: set[Path],
    ) -> Path | None:
        candidates = cls._list_batch_dirs(
            results_dir=results_dir
        ) - known_batch_dirs

        if not candidates:
            return None

        return max(
            candidates,
            key=lambda path: path.stat().st_mtime,
        )

    @staticmethod
    def _validate_inputs(
        *,
        runner_path: Path,
        config_path: Path,
        timeout_seconds: int | None,
    ) -> None:
        """
        在启动进程前校验必要参数。
        """
        if not runner_path.is_file():
            raise FileNotFoundError(
                "CMO 运行器不存在："
                f"{runner_path}"
            )

        if not config_path.is_file():
            raise FileNotFoundError(
                "CMO 任务配置不存在："
                f"{config_path}"
            )

        if (
            timeout_seconds is not None
            and (
                isinstance(
                    timeout_seconds,
                    bool,
                )
                or not isinstance(
                    timeout_seconds,
                    int,
                )
                or timeout_seconds <= 0
            )
        ):
            raise ValueError(
                "timeout_seconds 必须是"
                "大于 0 的整数或 None"
            )

    def _cleanup_processes(
        self,
        *,
        stage: str,
    ) -> None:
        """
        清理指定的 CMO 残留进程。

        清理失败只记录警告，不直接让本次执行失败。
        是否必须把清理失败视为阻断条件，可以在后续
        CmoRunner 中根据实际情况调整。
        """
        for process_name in (
            self._cleanup_process_names
        ):
            try:
                result = subprocess.run(
                    [
                        "taskkill",
                        "/F",
                        "/T",
                        "/IM",
                        process_name,
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    shell=False,
                    check=False,
                )

            except OSError as exc:
                logger.warning(
                    "%s清理进程 %s 时无法调用 "
                    "taskkill：%s",
                    stage,
                    process_name,
                    exc,
                )
                continue

            output = decode_console_output(
                result.stdout
            ).strip()

            if result.returncode == 0:
                logger.info(
                    "%s已清理进程：%s",
                    stage,
                    process_name,
                )
                continue

            if self._means_process_not_found(
                output
            ):
                logger.debug(
                    "%s进程未运行：%s",
                    stage,
                    process_name,
                )
                continue

            logger.warning(
                "%s清理进程 %s 未确认成功，"
                "退出码=%s，输出=%s",
                stage,
                process_name,
                result.returncode,
                output,
            )

    @staticmethod
    def _terminate_process_tree(
        process_id: int,
    ) -> None:
        """
        根据 PID 强制终止进程及全部子进程。

        Windows 命令：

            taskkill /F /T /PID <pid>
        """
        result = subprocess.run(
            [
                "taskkill",
                "/F",
                "/T",
                "/PID",
                str(process_id),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=False,
            check=False,
        )

        output = decode_console_output(
            result.stdout
        ).strip()

        if result.returncode == 0:
            logger.info(
                "已终止 CMO 进程树，PID=%s",
                process_id,
            )
            return

        raise RuntimeError(
            "无法确认 CMO 进程树已终止："
            f"PID={process_id}，"
            f"taskkill 退出码={result.returncode}，"
            f"输出={output}"
        )

    @staticmethod
    def _means_process_not_found(
        output: str,
    ) -> bool:
        """
        判断 taskkill 输出是否表示目标进程未运行。
        """
        lowered = output.lower()

        markers = (
            "没有找到",
            "找不到",
            "not found",
            "no running instance",
        )

        return any(
            marker in lowered
            for marker in markers
        )
