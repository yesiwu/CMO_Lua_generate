"""
CMO 单次 Lua 执行协调器。

该模块负责组合：

1. CmoJobConfig：
   临时切换任务 JSON 中的 Lua 路径，并在结束后恢复；

2. CmoProcessRunner：
   启动 CmoBatchRunner.exe，处理超时并捕获输出；

3. parse_cmo_error：
   将控制台文本解析为结构化错误；

4. RunArtifactStore：
   保存 original.lua、cmo_output.txt 和 result.json。

当前 MVP 约束：

- 一次只执行一个 Lua；
- tot-three.json 应只配置一个待执行 job；
- 串行执行；
- 不处理多个 Lua 的并发修复；
- 不在本模块中调用 LLM。
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import re
from typing import Callable

from cmo_lua_agent.core.run_artifact_store import (
    RoundPaths,
    RunArtifactStore,
    RunPaths,
)
from cmo_lua_agent.execution.cmo_error_parser import (
    parse_cmo_error,
)
from cmo_lua_agent.execution.cmo_job_config import (
    CmoJobConfig,
)
from cmo_lua_agent.execution.cmo_process_runner import (
    DEFAULT_TIMEOUT_SECONDS,
    CmoProcessRunner,
)
from cmo_lua_agent.execution.cmo_progress_parser import CmoProgressMessage
from cmo_lua_agent.execution.models import (
    CmoError,
    CmoProcessResult,
    CmoRunResult,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CmoExecutionRecord:
    """
    一次 CMO 执行的完整返回记录。

    result:
        本轮结构化执行结果。

    run_paths:
        整个任务 Run 的目录信息。

    round_paths:
        当前执行轮次的目录信息。
    """

    result: CmoRunResult
    run_paths: RunPaths
    round_paths: RoundPaths


class CmoRunner:
    """
    单 Lua、串行 CMO 执行协调器。
    """

    def __init__(
        self,
        *,
        config_path: Path,
        job_config: CmoJobConfig,
        process_runner: CmoProcessRunner,
        artifact_store: RunArtifactStore,
        completion_hook: Callable[[CmoExecutionRecord], None] | None = None,
    ) -> None:
        """
        初始化 CmoRunner。

        Args:
            config_path:
                CmoBatchRunner 使用的任务 JSON。

            job_config:
                负责临时切换 jobs[index].script。

            process_runner:
                负责启动 CmoBatchRunner.exe。

            artifact_store:
                负责保存运行产物。

            completion_hook:
                可选的执行完成回调。仅在 CMO 结果和本轮运行产物
                都已保存后调用；回调异常不会改变 CMO 的业务结果。
        """
        self._config_path = Path(
            config_path
        ).resolve()

        self._job_config = job_config
        self._process_runner = (
            process_runner
        )

        self._artifact_store = (
            artifact_store
        )
        self._completion_hook = completion_hook

    def run(
        self,
        *,
        lua_path: Path,
        job_index: int = 0,
        timeout_seconds: int | None = (
            DEFAULT_TIMEOUT_SECONDS
        ),
        run_paths: RunPaths | None = None,
        round_number: int = 0,
        run_id: str | None = None,
        progress_callback: Callable[[CmoProgressMessage], None] | None = None,
    ) -> CmoExecutionRecord:
        """
        执行一轮单 Lua CMO 仿真。

        新任务调用示例：

            record = runner.run(
                lua_path=generated_lua,
                round_number=0,
            )

        修复后的下一轮调用：

            record = runner.run(
                lua_path=repaired_lua,
                run_paths=previous.run_paths,
                round_number=1,
            )

        Args:
            lua_path:
                待执行 Lua 文件。

            job_index:
                任务 JSON 中的 jobs 下标。

            timeout_seconds:
                CMO 最大执行时长。

            run_paths:
                已存在的 Run。

                为 None 时创建新的 Run，并将 lua_path
                复制为 generation/original.lua。

            round_number:
                当前执行轮次。

                round_00 是原始 Lua；
                round_01 是第一次修复后的 Lua。

            run_id:
                创建新 Run 时使用的可选 ID。
                测试时可传入固定值。

        Returns:
            CmoExecutionRecord。
        """
        source_lua_path = Path(
            lua_path
        ).resolve()

        if not source_lua_path.is_file():
            raise FileNotFoundError(
                "待执行 Lua 文件不存在："
                f"{source_lua_path}"
            )

        actual_run_paths: RunPaths
        execution_lua_path: Path

        if run_paths is None:
            if round_number != 0:
                raise ValueError(
                    "创建新 Run 时 "
                    "round_number 必须为 0"
                )

            actual_run_paths = (
                self._artifact_store
                .create_run(
                    original_lua=(
                        source_lua_path
                    ),
                    run_id=run_id,
                )
            )

            # 新任务执行复制后的不可变快照，
            # 防止原始输入文件在执行期间被修改。
            execution_lua_path = (
                actual_run_paths
                .original_lua_path
            )

        else:
            if run_id is not None:
                raise ValueError(
                    "传入 run_paths 时不能"
                    "同时传入 run_id"
                )

            actual_run_paths = run_paths

            # 修复轮次执行明确传入的 repaired.lua。
            execution_lua_path = (
                source_lua_path
            )

        round_paths = (
            self._artifact_store
            .prepare_round(
                run_paths=(
                    actual_run_paths
                ),
                round_number=round_number,
            )
        )

        self._emit_progress(
            progress_callback,
            CmoProgressMessage(
                kind="artifacts_prepared",
                status="success",
                message="CMO 运行文件已准备",
                detail=str(round_paths.round_dir),
            ),
        )

        self._emit_progress(
            progress_callback,
            CmoProgressMessage(
                kind="runner_starting",
                status="running",
                message="正在启动 CmoBatchRunner",
            ),
        )

        process_result = (
            self._execute_process(
                lua_path=(
                    execution_lua_path
                ),
                job_index=job_index,
                timeout_seconds=(
                    timeout_seconds
                ),
                progress_callback=progress_callback,
            )
        )

        log_path = (
            self._artifact_store
            .save_console_output(
                round_paths=round_paths,
                console_output=(
                    process_result
                    .console_output
                ),
            )
        )

        batch_summary = self._read_batch_summary(
            batch_result_dir=process_result.batch_result_dir,
        )

        error = self._resolve_error(
            process_result=process_result,
            timeout_seconds=(
                timeout_seconds
            ),
            batch_summary=batch_summary,
        )

        # 能正常离开 use_script() 上下文，
        # 说明配置恢复没有抛出异常。
        restore_succeeded = True

        success = (
            process_result.exit_code == 0
            and not process_result.timed_out
            and error is None
            and restore_succeeded
        )

        result = CmoRunResult(
            success=success,
            lua_path=execution_lua_path,
            log_path=log_path,
            process_result=process_result,
            restore_succeeded=(
                restore_succeeded
            ),
            error=error,
            batch_result_dir=(
                process_result.batch_result_dir
            ),
            batch_success_count=(
                batch_summary[0] if batch_summary is not None else None
            ),
            batch_failure_count=(
                batch_summary[1] if batch_summary is not None else None
            ),
        )

        self._artifact_store.save_result(
            round_paths=round_paths,
            result=result,
        )

        record = CmoExecutionRecord(
            result=result,
            run_paths=actual_run_paths,
            round_paths=round_paths,
        )

        if self._completion_hook is not None:
            try:
                self._completion_hook(record)
            except Exception:
                logger.exception("CMO execution completion hook failed")

        return record

    def _execute_process(
        self,
        *,
        lua_path: Path,
        job_index: int,
        timeout_seconds: int | None,
        progress_callback: Callable[[CmoProgressMessage], None] | None,
    ) -> CmoProcessResult:
        """
        临时切换 JSON 脚本路径并执行 CMO。

        CmoJobConfig 的 finally 会在正常结束、CMO 异常
        或用户中断时尝试恢复原始 script。
        """
        with self._job_config.use_script(
            lua_path=lua_path,
            job_index=job_index,
        ):
            return self._process_runner.run(
                config_path=(
                    self._config_path
                ),
                timeout_seconds=(
                    timeout_seconds
                ),
                progress_callback=progress_callback,
            )

    @staticmethod
    def _emit_progress(
        callback: Callable[[CmoProgressMessage], None] | None,
        event: CmoProgressMessage,
    ) -> None:
        if callback is None:
            return
        try:
            callback(event)
        except Exception:
            logger.debug("CMO 进度回调执行失败", exc_info=True)

    @staticmethod
    def _resolve_error(
        *,
        process_result: CmoProcessResult,
        timeout_seconds: int | None,
        batch_summary: tuple[int, int] | None,
    ) -> CmoError | None:
        """
        根据进程结果和控制台输出确定最终错误。

        优先级：

        1. 超时；
        2. 控制台中可解析的 Lua/CMO 错误；
        3. 非零进程退出码；
        4. 没有错误。
        """
        if process_result.timed_out:
            timeout_description = (
                f"{timeout_seconds} 秒"
                if timeout_seconds
                is not None
                else "配置的最大时长"
            )

            return CmoError(
                category="process_timeout",
                message=(
                    "CMO 执行超过"
                    f"{timeout_description}，"
                    "进程已被终止"
                ),
            )

        batch_error = CmoRunner._resolve_batch_error(
            batch_result_dir=(
                process_result.batch_result_dir
            ),
            batch_summary=batch_summary,
        )

        if batch_error is not None:
            return batch_error

        parsed_error = parse_cmo_error(
            process_result.console_output
        )

        if parsed_error is not None:
            return parsed_error

        if process_result.exit_code != 0:
            return CmoError(
                category=(
                    "process_exit_error"
                ),
                message=(
                    "CmoBatchRunner "
                    "异常退出，退出码="
                    f"{process_result.exit_code}"
                ),
            )

        return None

    @staticmethod
    def _resolve_batch_error(
        *,
        batch_result_dir: Path | None,
        batch_summary: tuple[int, int] | None = None,
    ) -> CmoError | None:
        if batch_summary is None:
            batch_summary = CmoRunner._read_batch_summary(
                batch_result_dir=batch_result_dir,
            )
        if batch_summary is None:
            return None

        success_count, failure_count = batch_summary
        if failure_count == 0:
            return None

        return CmoError(
            category="batch_job_failure",
            message=(
                "CMO 批处理存在失败场景："
                f"成功 {success_count}，失败 {failure_count}；"
                f"结果目录：{batch_result_dir}"
            ),
        )

    @staticmethod
    def _read_batch_summary(
        *,
        batch_result_dir: Path | None,
    ) -> tuple[int, int] | None:
        if batch_result_dir is None:
            return None

        runner_log = Path(batch_result_dir) / "runner.log"

        if not runner_log.is_file():
            return None

        content = runner_log.read_text(
            encoding="utf-8-sig",
            errors="replace",
        )
        summary = re.search(
            r"执行结束：成功\s*(?P<success>\d+)\s*，失败\s*(?P<failure>\d+)",
            content,
        )

        if summary is None:
            return None

        success_count = int(summary.group("success"))
        failure_count = int(summary.group("failure"))
        return success_count, failure_count
