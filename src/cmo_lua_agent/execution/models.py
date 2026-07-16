"""
CMO 执行数据模型。

该模块定义 CMO 执行链路各层之间传递的标准数据结构：

1. CmoError：
   表示从 CMO 控制台输出中解析出的结构化错误。

2. CmoProcessResult：
   表示 CmoBatchRunner 子进程的一次原始运行结果。

3. CmoRunResult：
   表示配置修改、进程运行、错误解析和配置恢复完成后，
   对上层返回的最终业务执行结果。

本模块只定义数据结构，不启动进程、不修改配置文件，
也不负责保存日志和 result.json。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CmoError:
    """
    CMO 执行过程中解析出的结构化错误。

    Attributes:
        category:
            稳定的机器错误分类，例如：

            - lua_syntax_error
            - lua_runtime_error
            - cmo_internal_error
            - process_timeout
            - process_start_error
            - unknown_error

        message:
            适合展示或交给修复模型的错误摘要。

        source:
            错误来源，例如 Console 或具体 Lua 文件名。

        line:
            报错行号。无法确定时为 None。
    """

    category: str
    message: str
    source: str | None = None
    line: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """
        转换为可直接写入 JSON 的字典。
        """
        return {
            "category": self.category,
            "message": self.message,
            "source": self.source,
            "line": self.line,
        }


@dataclass(frozen=True)
class CmoProcessResult:
    """
    CmoBatchRunner 子进程的一次原始执行结果。

    该模型只描述 Windows 子进程层面的事实，
    不负责判断 Lua 或 CMO 业务执行是否成功。

    即使 exit_code 为 0，console_output 中仍可能包含
    Internal ERROR，因此不能仅依赖退出码判断最终成功。

    Attributes:
        exit_code:
            CmoBatchRunner.exe 的进程退出码。

        timed_out:
            是否因为超过最大运行时间而被终止。

        duration_seconds:
            子进程从启动到结束的耗时。

        console_output:
            stdout 和 stderr 合并后的完整控制台文本。
    """

    exit_code: int
    timed_out: bool
    duration_seconds: float
    console_output: str
    batch_result_dir: Path | None = None


@dataclass(frozen=True)
class CmoRunResult:
    """
    一次 Lua 脚本 CMO 执行的最终业务结果。

    该模型组合以下信息：

    - 子进程运行结果；
    - 本轮实际执行的 Lua 路径；
    - 原始控制台日志路径；
    - JSON 配置是否成功恢复；
    - 从控制台文本解析出的结构化错误。

    Attributes:
        success:
            CMO 业务执行最终是否成功。

            推荐由 CmoRunner 按以下条件计算：

                exit_code == 0
                and not timed_out
                and error is None
                and restore_succeeded

        lua_path:
            本轮实际执行的 Lua 文件。

        log_path:
            本轮 cmo_output.txt 文件路径。

        process_result:
            CmoBatchRunner 子进程原始运行结果。

        restore_succeeded:
            执行结束后，任务 JSON 是否恢复到运行前状态。

        error:
            结构化错误。执行成功时为 None。
    """

    success: bool
    lua_path: Path
    log_path: Path
    process_result: CmoProcessResult
    restore_succeeded: bool
    error: CmoError | None = None
    batch_result_dir: Path | None = None
    batch_success_count: int | None = None
    batch_failure_count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """
        转换为适合写入 result.json 的字典。

        console_output 不写入 result.json，因为完整原始输出
        会单独保存在 cmo_output.txt 中，避免同一份长日志
        被重复保存。
        """
        return {
            "success": self.success,
            "exit_code": (
                self.process_result.exit_code
            ),
            "timed_out": (
                self.process_result.timed_out
            ),
            "duration_seconds": (
                self.process_result.duration_seconds
            ),
            "lua_path": str(self.lua_path),
            "log_path": str(self.log_path),
            "restore_succeeded": (
                self.restore_succeeded
            ),
            "error": (
                self.error.to_dict()
                if self.error is not None
                else None
            ),
            "batch_result_dir": (
                str(self.batch_result_dir)
                if self.batch_result_dir is not None
                else None
            ),
            "batch_success_count": self.batch_success_count,
            "batch_failure_count": self.batch_failure_count,
        }
