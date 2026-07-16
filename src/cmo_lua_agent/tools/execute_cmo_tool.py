"""
CMO Lua 单次执行工具。

该工具将 CmoRunner 暴露给 LLM，允许模型执行指定的
Lua 文件，并获得结构化的 CMO 执行结果。

工具本身只负责：

1. 校验工具参数；
2. 调用 CmoRunner；
3. 将 CmoExecutionRecord 转换为 JSON；
4. 根据业务执行结果设置 ToolResult.is_error。

工具不直接启动子进程、不修改 CMO 配置、
不解析错误，也不执行自动修复循环。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cmo_lua_agent.execution.cmo_runner import (
    CmoRunner,
)
from cmo_lua_agent.execution.cmo_progress_parser import CmoProgressMessage
from cmo_lua_agent.tools.tool_base.base import (
    BaseTool,
    ToolResult,
)
from cmo_lua_agent.tools.tool_base.context import ToolContext


class ExecuteCmoTool(BaseTool):
    """
    执行单个 CMO Lua 文件的 Agent Tool。
    """

    name = "execute_cmo"

    description = (
        "执行指定的 CMO Lua 脚本。"
        "工具会临时更新 CmoBatchRunner 任务配置，"
        "启动 CMO 批量运行器，捕获控制台输出，"
        "解析 Lua 或 CMO 错误，并保存本轮运行产物。"
        "一次只能执行一个 Lua 文件。"
    )

    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "lua_path": {
                "type": "string",
                "description": (
                    "待执行 Lua 文件路径。"
                    "可以是绝对路径或当前工作目录下的"
                    "相对路径。"
                ),
            },
            "job_index": {
                "type": "integer",
                "minimum": 0,
                "default": 0,
                "description": (
                    "CmoBatchRunner JSON 中 jobs 的下标。"
                    "MVP 阶段通常固定为 0。"
                ),
            },
            "timeout_seconds": {
                "type": "integer",
                "minimum": 1,
                "maximum": 7200,
                "default": 3600,
                "description": (
                    "CMO 单次执行超时时间，单位秒。"
                ),
            },
        },
        "required": [
            "lua_path",
        ],
        "additionalProperties": False,
    }

    toolset = "cmo"

    # CMO 执行会启动外部进程并临时修改任务配置，
    # 因此交互模式下必须经过人工审批。
    requires_approval = True

    def __init__(
        self,
        *,
        cmo_runner: CmoRunner,
    ) -> None:
        self._cmo_runner = cmo_runner

    def execute(
        self,
        arguments: dict[str, Any],
        context: ToolContext | None = None,
    ) -> ToolResult:
        """
        执行一次单 Lua CMO 仿真。

        Args:
            arguments:
                Anthropic tool_use.input。

        Returns:
            JSON 格式 ToolResult。

            CMO 执行成功：
                is_error=False

            Lua、CMO、超时或进程执行失败：
                is_error=True

        Raises:
            ValueError:
                工具参数非法。

            Exception:
                CmoRunner 未捕获的基础设施异常。
                ToolRegistry 会将其转换为错误 ToolResult。
        """
        lua_path_text = self._require_string(
            arguments=arguments,
            field_name="lua_path",
        )

        job_index = self._read_integer(
            arguments=arguments,
            field_name="job_index",
            default=0,
            minimum=0,
        )

        timeout_seconds = self._read_integer(
            arguments=arguments,
            field_name="timeout_seconds",
            default=3600,
            minimum=1,
            maximum=7200,
        )

        reporter = context.progress if context is not None else None
        started_steps: set[str] = set()
        completed_steps: set[str] = set()

        def start_step(step_id: str, message: str, detail: str | None = None) -> None:
            if reporter is None or step_id in started_steps:
                return
            reporter.step_started(step_id, message, detail)
            started_steps.add(step_id)

        def finish_step(
            step_id: str,
            message: str,
            *,
            success: bool = True,
            detail: str | None = None,
        ) -> None:
            if reporter is None or step_id in completed_steps:
                return
            if success:
                reporter.step_completed(step_id, message, detail)
            else:
                reporter.emit(
                    event_type="step_completed",
                    status="failed",
                    message=message,
                    detail=detail,
                    progress=1.0,
                    step_id=step_id,
                )
            completed_steps.add(step_id)

        if reporter is not None:
            reporter.tool_started("开始执行 CMO")
            start_step("validate", "校验执行参数")
            finish_step("validate", "执行参数有效")
            start_step("prepare", "准备 CMO 运行文件")

        def handle_cmo_progress(event: CmoProgressMessage) -> None:
            if reporter is None:
                return
            if event.kind == "artifacts_prepared":
                finish_step("prepare", "CMO 运行文件已准备", detail=event.detail)
                start_step("launch", "启动 CmoBatchRunner")
                return
            if event.kind == "runner_starting":
                finish_step("prepare", "CMO 运行文件已准备")
                start_step("launch", "启动 CmoBatchRunner")
                reporter.step_progress("launch", event.message, event.detail)
                return
            if event.kind == "batch_started":
                start_step("launch", "启动 CmoBatchRunner")
                finish_step("launch", "CmoBatchRunner 已启动")
                start_step("simulation", "执行 CMO 场景")
                return

            start_step("simulation", "执行 CMO 场景")
            if event.kind == "batch_completed":
                finish_step(
                    "simulation",
                    event.message,
                    success=event.failure_count == 0,
                    detail=event.detail,
                )
                return
            if event.kind == "scenario_failed":
                reporter.emit(
                    event_type="output",
                    status="failed",
                    message=event.message,
                    detail=event.detail,
                    step_id="simulation",
                    metadata=dict(event.metadata),
                )
                return
            if event.kind == "result_dir":
                reporter.output(
                    event.message,
                    event.detail,
                    metadata={"result_dir": event.result_dir},
                )
                return
            reporter.step_progress(
                "simulation",
                event.message,
                event.detail,
                event.progress,
            )

        record = self._cmo_runner.run(
            lua_path=Path(lua_path_text),
            job_index=job_index,
            timeout_seconds=timeout_seconds,
            progress_callback=handle_cmo_progress,
        )

        payload = record.result.to_dict()

        # CmoRunResult 描述执行结果；
        # 下面三个字段描述结果保存在哪里。
        payload.update(
            {
                "run_id": (
                    record.run_paths.run_id
                ),
                "round_number": (
                    record.round_paths
                    .round_number
                ),
                "round_dir": str(
                    record.round_paths
                    .round_dir
                ),
            }
        )

        result = ToolResult(
            content=json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
            is_error=(
                not record.result.success
            ),
        )
        if reporter is not None:
            finish_step("prepare", "CMO 运行文件已准备")
            start_step("launch", "启动 CmoBatchRunner")
            finish_step("launch", "CmoBatchRunner 已结束")
            start_step("simulation", "执行 CMO 场景")
            finish_step(
                "simulation",
                "CMO 场景执行完成" if not result.is_error else "CMO 场景执行失败",
                success=not result.is_error,
                detail=(
                    record.result.error.message
                    if record.result.error is not None
                    else None
                ),
            )
            start_step("collect", "收集 CMO 运行结果")
            finish_step(
                "collect",
                "CMO 运行结果已保存",
                detail=str(record.round_paths.round_dir),
            )
            if result.is_error:
                reporter.tool_failed(
                    "CMO 执行失败",
                    record.result.error.message if record.result.error else None,
                )
            else:
                reporter.tool_completed("CMO 执行完成")
        return result

    @staticmethod
    def _require_string(
        *,
        arguments: dict[str, Any],
        field_name: str,
    ) -> str:
        """
        读取必填非空字符串参数。
        """
        value = arguments.get(
            field_name
        )

        if (
            not isinstance(value, str)
            or not value.strip()
        ):
            raise ValueError(
                f"{field_name} 必须是非空字符串"
            )

        return value.strip()

    @staticmethod
    def _read_integer(
        *,
        arguments: dict[str, Any],
        field_name: str,
        default: int,
        minimum: int | None = None,
        maximum: int | None = None,
    ) -> int:
        """
        读取并校验整数参数。

        bool 在 Python 中属于 int 的子类，
        因此必须显式排除 True 和 False。
        """
        value = arguments.get(
            field_name,
            default,
        )

        if (
            isinstance(value, bool)
            or not isinstance(value, int)
        ):
            raise ValueError(
                f"{field_name} 必须是整数"
            )

        if (
            minimum is not None
            and value < minimum
        ):
            raise ValueError(
                f"{field_name} 不能小于 "
                f"{minimum}"
            )

        if (
            maximum is not None
            and value > maximum
        ):
            raise ValueError(
                f"{field_name} 不能大于 "
                f"{maximum}"
            )

        return value
