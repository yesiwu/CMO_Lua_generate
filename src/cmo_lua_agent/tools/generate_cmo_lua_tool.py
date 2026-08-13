"""把现有“JSON → Lua”确定性工作流包装成一个 Agent 工具。

这个工具本身不负责生成 Lua 的具体业务逻辑，
它只是把 ScenarioWorkflow 暴露给 Agent 使用。

也就是说：

    LLM
      ↓
    GenerateCmoLuaTool
      ↓
    ScenarioWorkflow
      ↓
    JSON → 校验 → 数据库解析 → Manifest → Lua

该工具不会真正启动 CMO 仿真，只负责生成和预检 Lua。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cmo_lua_agent.orchestration import (
    ScenarioWorkflow,
    ScenarioWorkflowResult,
)
from cmo_lua_agent.tools.tool_base.base import (
    BaseTool,
    ToolResult,
)
from cmo_lua_agent.tools.tool_base.context import ToolContext


class GenerateCmoLuaTool(BaseTool):
    """把既有 JSON→Lua 工作流包装成 Agent 可调用工具。"""

    # LLM 调用工具时使用的稳定名称
    name = "generate_cmo_lua"

    # 提供给 LLM 的工具说明
    description = (
        "从工作区内的 JSON 场景生成并预检 CMO Lua。"
        "该工具不会执行 CMO。"
    )

    # 告诉 LLM 这个工具允许传入哪些参数
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "json_path": {
                "type": "string",
                "description": "工作区内的场景 JSON 路径。",
            },
            "runs_root": {
                "type": "string",
                "description": "工作区内可选的运行产物目录。",
                "default": "runs",
            },
            "run_id": {
                "type": "string",
                "description": "可选的明确运行标识。",
            },
            "platform_resolutions": {
                "type": "object",
                "description": (
                    "仅在用户明确确认后提供的平台决策："
                    "{unit_id: {category, dbid}}。"
                ),
            },
        },
        "required": ["json_path"],
        "additionalProperties": False,
    }

    # 工具属于 CMO Lua 工具组
    toolset = "cmolua"

    # 这里只生成 Lua，不真正执行 CMO，因此不要求用户审批
    requires_approval = False

    def __init__(
        self,
        *,
        scenario_workflow: ScenarioWorkflow,
        workdir: Path,
    ) -> None:
        """注入真正负责 JSON→Lua 的工作流，以及允许访问的工作区。"""

        # 防止传进来的对象根本不是可运行的 ScenarioWorkflow
        if not callable(
            getattr(
                scenario_workflow,
                "run",
                None,
            )
        ):
            raise TypeError(
                "scenario_workflow 必须提供 run() 方法"
            )

        self._scenario_workflow = scenario_workflow

        # 固定工作区根目录。
        # 后续所有 json_path / runs_root 都不能逃出这个目录。
        self._workdir = (
            Path(workdir)
            .expanduser()
            .resolve(strict=False)
        )

    def execute(
        self,
        arguments: dict[str, Any],
        context: ToolContext | None = None,
    ) -> ToolResult:
        """执行一次 JSON→Lua 工具调用。

        主要步骤：

        1. 校验输入参数和路径；
        2. 调用 ScenarioWorkflow；
        3. 把工作流结果整理成 Agent 容易理解的 JSON；
        4. 通过 ToolResult 返回给 LLM；
        5. 执行过程中通过 ToolContext 上报进度。
        """

        # 告诉终端/Web UI：这个工具开始执行了
        if context is not None:
            context.progress.tool_started(
                "正在生成 CMO Lua"
            )

        try:
            # -------------------------
            # 第一步：校验输入参数
            # -------------------------
            if context is not None:
                context.progress.step_started(
                    "validate_input",
                    "正在校验场景与运行目录路径",
                )

            # 解析 JSON 文件路径。
            # 必须存在、必须是文件、必须位于工作区内。
            source_path = self._resolve_workspace_path(
                self._read_non_blank_string(
                    arguments,
                    "json_path",
                ),
                field_name="json_path",
                must_exist=True,
                require_file=True,
            )

            # runs_root 是本次工作流产物保存目录。
            # 默认使用工作区内的 runs。
            runs_root = self._resolve_workspace_path(
                self._read_optional_string(
                    arguments,
                    "runs_root",
                )
                or "runs",
                field_name="runs_root",
            )

            # run_id 可选。
            # 如果用户没有提供，由工作流内部决定如何生成。
            run_id = self._read_optional_string(
                arguments,
                "run_id",
            )

            # 用户如果已经确认了平台歧义，
            # 可以把选择好的 category/dbid 再传回工作流。
            platform_resolutions = arguments.get(
                "platform_resolutions"
            )

            if (
                platform_resolutions is not None
                and not isinstance(
                    platform_resolutions,
                    dict,
                )
            ):
                raise ValueError(
                    "platform_resolutions 必须是对象"
                )

            if context is not None:
                context.progress.step_completed(
                    "validate_input",
                    "场景与运行目录路径校验完成",
                    str(source_path),
                )

                context.progress.step_started(
                    "scenario_workflow",
                    "正在执行 JSON 转 Lua 工作流",
                )

            # -------------------------
            # 第二步：调用真正的工作流
            # -------------------------
            workflow_arguments: dict[str, Any] = {
                "runs_root": runs_root,
                "run_id": run_id,
            }

            # 只有用户已经给出平台确认结果时才传入
            if platform_resolutions is not None:
                workflow_arguments[
                    "platform_resolutions"
                ] = platform_resolutions

            # 真正的 JSON→Lua 逻辑都在 ScenarioWorkflow.run() 中。
            # 当前 Tool 只负责适配。
            result = self._scenario_workflow.run(
                source_path,
                **workflow_arguments,
            )

            # 工具和工作流之间约定必须返回统一结果对象。
            if not isinstance(
                result,
                ScenarioWorkflowResult,
            ):
                raise TypeError(
                    "scenario_workflow.run 必须返回 "
                    "ScenarioWorkflowResult"
                )

            # 把复杂的工作流结果转换成简洁 JSON，
            # 方便 LLM 判断成功、失败、错误阶段和产物路径。
            payload = _result_payload(result)

            # -------------------------
            # 第三步：处理成功结果
            # -------------------------
            if result.success:
                if context is not None:
                    context.progress.step_completed(
                        "scenario_workflow",
                        "Lua 生成与预检完成",
                        payload["lua_path"],
                    )

                    context.progress.tool_completed(
                        "CMO Lua 生成完成"
                    )

                return self._result(payload)

            # -------------------------
            # 第四步：工作流正常返回“失败”
            # -------------------------
            # 注意：
            # 这里不是 Python 异常，
            # 而是工作流明确告诉我们“业务处理失败”。
            if context is not None:
                context.progress.tool_failed(
                    "CMO Lua 工作流失败",
                    payload["error"]["message"],
                )

            return self._result(
                payload,
                is_error=True,
            )

        except ValueError as exc:
            # 用户参数、路径等可预期输入错误
            return self._failure(
                code="invalid_generation_request",
                message=str(exc),
                context=context,
            )

        except Exception as exc:
            # 其他未预期异常统一包装，
            # 不让异常直接冲出 ToolRegistry。
            return self._failure(
                code="lua_generation_tool_failed",
                message=(
                    str(exc)
                    or type(exc).__name__
                ),
                context=context,
                error_type=type(exc).__name__,
            )

    def _resolve_workspace_path(
        self,
        raw_path: str,
        *,
        field_name: str,
        must_exist: bool = False,
        require_file: bool = False,
    ) -> Path:
        """把用户提供的路径限制在工作区内部。

        目的：

        LLM 可以指定 json_path，
        但不能借此读取或写入工作区之外的任意路径。

        例如禁止：

            ../../Windows/System32/...

        这是工具层的一道路径安全边界。
        """

        candidate = Path(
            raw_path
        ).expanduser()

        # 绝对路径直接解析；
        # 相对路径则以 workdir 为基准。
        resolved = (
            candidate.resolve(strict=False)
            if candidate.is_absolute()
            else (
                self._workdir / candidate
            ).resolve(strict=False)
        )

        # 路径不能逃出工作区
        if not resolved.is_relative_to(
            self._workdir
        ):
            raise ValueError(
                f"{field_name} 必须位于工作区内"
            )

        # 某些参数必须已经存在，例如 json_path
        if must_exist and not resolved.exists():
            raise ValueError(
                f"{field_name} 不存在：{resolved}"
            )

        # json_path 要求必须是真实文件，不能传目录
        if (
            require_file
            and not resolved.is_file()
        ):
            raise ValueError(
                f"{field_name} 必须是文件：{resolved}"
            )

        return resolved

    @staticmethod
    def _read_non_blank_string(
        arguments: dict[str, Any],
        field_name: str,
    ) -> str:
        """读取必须存在的非空字符串参数。"""

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
    def _read_optional_string(
        arguments: dict[str, Any],
        field_name: str,
    ) -> str | None:
        """读取可选字符串参数。

        没传返回 None；
        一旦传了，就必须是非空字符串。
        """

        value = arguments.get(
            field_name
        )

        if value is None:
            return None

        if (
            not isinstance(value, str)
            or not value.strip()
        ):
            raise ValueError(
                f"{field_name} 提供时必须是非空字符串"
            )

        return value.strip()

    @staticmethod
    def _result(
        payload: dict[str, Any],
        *,
        is_error: bool = False,
    ) -> ToolResult:
        """把 Python 字典统一转换为 ToolResult。

        ToolRegistry / AgentLoop 最终只需要处理 ToolResult，
        不需要理解 ScenarioWorkflowResult 的内部结构。
        """

        return ToolResult(
            content=json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
            is_error=is_error,
        )

    def _failure(
        self,
        *,
        code: str,
        message: str,
        context: ToolContext | None,
        error_type: str | None = None,
    ) -> ToolResult:
        """统一生成工具失败结果。"""

        if context is not None:
            context.progress.tool_failed(
                "CMO Lua 生成失败",
                message,
            )

        error: dict[str, str] = {
            "code": code,
            "message": message,
        }

        if error_type is not None:
            error["type"] = error_type

        return self._result(
            {
                "success": False,
                "error": error,
            },
            is_error=True,
        )


def _result_payload(
    result: ScenarioWorkflowResult,
) -> dict[str, Any]:
    """把完整 WorkflowResult 压缩成适合返回给 Agent 的结果。

    Agent 最关心的是：

    - 成功还是失败；
    - run_id 是什么；
    - Lua 保存在哪里；
    - Manifest 保存在哪里；
    - 哪个阶段失败；
    - 有哪些错误和警告；
    - 是否需要用户确认平台歧义。

    不需要把整个工作流内部对象全部暴露给模型。
    """

    paths = result.state.artifact_paths

    # 收集工作流产生的校验问题
    issues = (
        [
            issue.to_dict()
            for issue in result.validation.issues
        ]
        if result.validation is not None
        else []
    )

    warnings: list[str] = []

    # 收集普通 Validation warning
    if result.validation is not None:
        warnings.extend(
            issue.message
            for issue in result.validation.warnings
        )

    # 收集 Lua generator / preflight 阶段的 warning
    if result.generation is not None:
        warnings.extend(
            result.generation.generator_warnings
        )

        warnings.extend(
            issue.message
            for issue
            in result.generation.preflight.validation.warnings
        )

    # 返回给 LLM 的标准结果
    payload: dict[str, Any] = {
        "success": result.success,

        # 当前工作流运行标识
        "run_id": result.state.run_id,

        # 当前运行产物根目录
        "run_root": paths.get(
            "run_root"
        ),

        # 成功则返回正式 Lua；
        # 失败时如果生成过 Lua，则返回 rejected Lua。
        "lua_path": (
            paths.get("original_lua")
            if result.success
            else paths.get("rejected_lua")
        ),

        # 工作流最终结果文件
        "workflow_result_path": paths.get(
            "workflow_result"
        ),

        # 数据库解析完成后的 Manifest
        "resolved_manifest_path": paths.get(
            "resolved_manifest"
        ),

        # 当前工作流最终状态
        "workflow_status": (
            result.state.status.value
        ),

        # 如果失败，告诉 Agent 是在哪个阶段失败
        "failed_stage": (
            result.failed_stage.value
            if result.failed_stage
            else None
        ),

        "issues": issues,

        # 去重后返回 warning
        "warnings": list(
            dict.fromkeys(warnings)
        ),
    }

    # 失败时提供额外信息，
    # 方便 Agent 决定是重试、换参数还是询问用户。
    if not result.success:
        payload["error"] = {
            "code": (
                result.state.error_code
                or "workflow_failed"
            ),
            "message": (
                result.state.error_message
                or "工作流失败"
            ),
        }

        # 如果失败原因是平台 DBID / category 存在歧义，
        # 把候选项直接暴露给 Chat Agent，
        # 避免它自己去随意读取内部产物文件。
        payload[
            "platform_resolution_candidates"
        ] = _platform_resolution_candidates(
            paths
        )

        # 告诉 Agent：
        # 当前错误是不是必须让用户做决定。
        payload[
            "requires_user_confirmation"
        ] = (
            result.state.status.value
            == "needs_user_input"
        )

    return payload


def _platform_resolution_candidates(
    paths: Any,
) -> list[dict[str, Any]]:
    """从数据库解析报告中提取“需要用户确认的平台候选项”。

    这里不会让 Chat Agent 自己去读取任意内部文件。

    它只挑出数据库解析阶段已经明确标记为：

        resolution_required

    的单位，然后把候选 category/dbid 返回给 Agent。
    """

    try:
        database_report_path = Path(
            paths["database_report"]
        )

        payload = json.loads(
            database_report_path.read_text(
                encoding="utf-8"
            )
        )

        platforms = (
            payload["resolution"]["platforms"]
        )

    except (
        KeyError,
        OSError,
        TypeError,
        json.JSONDecodeError,
    ):
        # 报告文件不存在、格式损坏等情况，
        # 不影响主错误结果，只是不返回候选信息。
        return []

    return [
        {
            "unit_id": item.get(
                "unitId"
            ),
            "dbid": item.get(
                "dbid"
            ),
            "candidates": item.get(
                "candidates",
                [],
            ),
        }
        for item in platforms
        if (
            item.get("status")
            == "resolution_required"
        )
    ]


__all__ = [
    "GenerateCmoLuaTool",
]