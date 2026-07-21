"""确定性 JSON 转 Lua 工作流的 Agent 工具适配器。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cmo_lua_agent.orchestration import ScenarioWorkflow, ScenarioWorkflowResult
from cmo_lua_agent.tools.tool_base.base import BaseTool, ToolResult
from cmo_lua_agent.tools.tool_base.context import ToolContext


class GenerateCmoLuaTool(BaseTool):
    """执行既有 JSON 转 Lua 工作流，但不启动 CMO 仿真。"""

    name = "generate_cmo_lua"
    description = (
        "从工作区内的 JSON 场景生成并预检 CMO Lua。"
        "该工具不会执行 CMO。"
    )
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
                "description": "仅在用户明确确认后提供的平台决策：{unit_id: {category, dbid}}。",
            },
        },
        "required": ["json_path"],
        "additionalProperties": False,
    }
    toolset = "cmolua"
    requires_approval = False

    def __init__(
        self,
        *,
        scenario_workflow: ScenarioWorkflow,
        workdir: Path,
    ) -> None:
        if not callable(getattr(scenario_workflow, "run", None)):
            raise TypeError("scenario_workflow 必须提供 run() 方法")
        self._scenario_workflow = scenario_workflow
        self._workdir = Path(workdir).expanduser().resolve(strict=False)

    def execute(
        self,
        arguments: dict[str, Any],
        context: ToolContext | None = None,
    ) -> ToolResult:
        if context is not None:
            context.progress.tool_started("正在生成 CMO Lua")

        try:
            if context is not None:
                context.progress.step_started(
                    "validate_input",
                    "正在校验场景与运行目录路径",
                )
            source_path = self._resolve_workspace_path(
                self._read_non_blank_string(arguments, "json_path"),
                field_name="json_path",
                must_exist=True,
                require_file=True,
            )
            runs_root = self._resolve_workspace_path(
                self._read_optional_string(arguments, "runs_root") or "runs",
                field_name="runs_root",
            )
            run_id = self._read_optional_string(arguments, "run_id")
            platform_resolutions = arguments.get("platform_resolutions")
            if platform_resolutions is not None and not isinstance(
                platform_resolutions,
                dict,
            ):
                raise ValueError("platform_resolutions 必须是对象")
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

            workflow_arguments: dict[str, Any] = {
                "runs_root": runs_root,
                "run_id": run_id,
            }
            if platform_resolutions is not None:
                workflow_arguments["platform_resolutions"] = platform_resolutions
            result = self._scenario_workflow.run(source_path, **workflow_arguments)
            if not isinstance(result, ScenarioWorkflowResult):
                raise TypeError(
                    "scenario_workflow.run 必须返回 ScenarioWorkflowResult"
                )

            payload = _result_payload(result)
            if result.success:
                if context is not None:
                    context.progress.step_completed(
                        "scenario_workflow",
                        "Lua 生成与预检完成",
                        payload["lua_path"],
                    )
                    context.progress.tool_completed("CMO Lua 生成完成")
                return self._result(payload)

            if context is not None:
                context.progress.tool_failed(
                    "CMO Lua 工作流失败",
                    payload["error"]["message"],
                )
            return self._result(payload, is_error=True)

        except ValueError as exc:
            return self._failure(
                code="invalid_generation_request",
                message=str(exc),
                context=context,
            )
        except Exception as exc:
            return self._failure(
                code="lua_generation_tool_failed",
                message=str(exc) or type(exc).__name__,
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
        candidate = Path(raw_path).expanduser()
        resolved = (
            candidate.resolve(strict=False)
            if candidate.is_absolute()
            else (self._workdir / candidate).resolve(strict=False)
        )
        if not resolved.is_relative_to(self._workdir):
            raise ValueError(f"{field_name} 必须位于工作区内")
        if must_exist and not resolved.exists():
            raise ValueError(f"{field_name} 不存在：{resolved}")
        if require_file and not resolved.is_file():
            raise ValueError(f"{field_name} 必须是文件：{resolved}")
        return resolved

    @staticmethod
    def _read_non_blank_string(arguments: dict[str, Any], field_name: str) -> str:
        value = arguments.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} 必须是非空字符串")
        return value.strip()

    @staticmethod
    def _read_optional_string(
        arguments: dict[str, Any],
        field_name: str,
    ) -> str | None:
        value = arguments.get(field_name)
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} 提供时必须是非空字符串")
        return value.strip()

    @staticmethod
    def _result(payload: dict[str, Any], *, is_error: bool = False) -> ToolResult:
        return ToolResult(
            content=json.dumps(payload, ensure_ascii=False, indent=2),
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
        if context is not None:
            context.progress.tool_failed("CMO Lua 生成失败", message)
        error: dict[str, str] = {"code": code, "message": message}
        if error_type is not None:
            error["type"] = error_type
        return self._result({"success": False, "error": error}, is_error=True)


def _result_payload(result: ScenarioWorkflowResult) -> dict[str, Any]:
    paths = result.state.artifact_paths
    issues = (
        [issue.to_dict() for issue in result.validation.issues]
        if result.validation is not None
        else []
    )
    warnings: list[str] = []
    if result.validation is not None:
        warnings.extend(issue.message for issue in result.validation.warnings)
    if result.generation is not None:
        warnings.extend(result.generation.generator_warnings)
        warnings.extend(
            issue.message
            for issue in result.generation.preflight.validation.warnings
        )

    payload: dict[str, Any] = {
        "success": result.success,
        "run_id": result.state.run_id,
        "run_root": paths.get("run_root"),
        "lua_path": (
            paths.get("original_lua")
            if result.success
            else paths.get("rejected_lua")
        ),
        "workflow_result_path": paths.get("workflow_result"),
        "resolved_manifest_path": paths.get("resolved_manifest"),
        "workflow_status": result.state.status.value,
        "failed_stage": result.failed_stage.value if result.failed_stage else None,
        "issues": issues,
        "warnings": list(dict.fromkeys(warnings)),
    }
    if not result.success:
        payload["error"] = {
            "code": result.state.error_code or "workflow_failed",
            "message": result.state.error_message or "工作流失败",
         }
        payload["platform_resolution_candidates"] = (
            _platform_resolution_candidates(paths)
        )
        payload["requires_user_confirmation"] = (
            result.state.status.value == "needs_user_input"
        )
    return payload


def _platform_resolution_candidates(
    paths: Any,
) -> list[dict[str, Any]]:
    """Expose database candidates to Chat without letting it inspect arbitrary files."""
    try:
        database_report_path = Path(paths["database_report"])
        payload = json.loads(database_report_path.read_text(encoding="utf-8"))
        platforms = payload["resolution"]["platforms"]
    except (
        KeyError,
        OSError,
        TypeError,
        json.JSONDecodeError,
    ):
        return []

    return [
        {
            "unit_id": item.get("unitId"),
            "dbid": item.get("dbid"),
            "candidates": item.get("candidates", []),
        }
        for item in platforms
        if item.get("status") == "resolution_required"
    ]


__all__ = ["GenerateCmoLuaTool"]
