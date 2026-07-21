"""Command-line boundary for running one JSON-to-Lua scenario workflow."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from enum import IntEnum
from pathlib import Path
from typing import Protocol, TextIO

from cmo_lua_agent.orchestration import (
    ScenarioWorkflowResult,
    WorkflowStatus,
)


class RunScenarioExitCode(IntEnum):
    """Stable process exit codes for the ``run`` command."""

    SUCCESS = 0
    RUNTIME_ERROR = 1
    WORKFLOW_FAILED = 2
    NEEDS_USER_INPUT = 3


class ScenarioWorkflowRunner(Protocol):
    """Minimal workflow interface required by the CLI."""

    def run(
        self,
        source_path: Path,
        *,
        runs_root: Path,
        run_id: str | None = None,
        platform_resolutions: Mapping[str, object] | None = None,
    ) -> ScenarioWorkflowResult:
        ...


def add_run_scenario_arguments(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    """Attach the shared ``run`` arguments to an existing parser."""

    parser.add_argument(
        "source_path",
        type=Path,
        metavar="SCENARIO_JSON",
        help="输入场景 JSON 文件路径",
    )
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=Path("runs"),
        metavar="DIR",
        help="Run 产物根目录，默认：runs",
    )
    parser.add_argument(
        "--run-id",
        type=_non_blank_run_id,
        default=None,
        metavar="ID",
        help="指定 Run ID；省略时自动生成",
    )
    return parser


def build_run_scenario_parser() -> argparse.ArgumentParser:
    """Create the standalone parser for the JSON-to-Lua run command."""

    parser = argparse.ArgumentParser(
        prog="cmo-lua-agent run",
        description=(
            "读取一个场景 JSON，执行完整校验和数据库解析，"
            "生成经过预检的 CMO Lua。"
        ),
    )
    return add_run_scenario_arguments(parser)


def run_scenario_command(
    workflow: ScenarioWorkflowRunner,
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Parse arguments, execute one workflow, and print a concise summary.

    Argument parsing errors intentionally keep argparse's standard
    ``SystemExit(2)`` behavior. Workflow validation failures are normal command
    outcomes and return ``WORKFLOW_FAILED``. Infrastructure and programming
    exceptions are rendered without a traceback and return ``RUNTIME_ERROR``.
    """

    args = build_run_scenario_parser().parse_args(argv)

    return run_scenario_workflow(
        workflow=workflow,
        source_path=args.source_path,
        runs_root=args.runs_root,
        run_id=args.run_id,
        stdout=stdout,
        stderr=stderr,
    )


def run_scenario_workflow(
    *,
    workflow: ScenarioWorkflowRunner,
    source_path: Path,
    runs_root: Path,
    run_id: str | None,
    platform_resolutions: Mapping[str, object] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run an already configured workflow and render its CLI summary."""

    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr

    try:
        arguments: dict[str, object] = {
            "runs_root": runs_root,
            "run_id": run_id,
        }
        if platform_resolutions is not None:
            arguments["platform_resolutions"] = platform_resolutions
        result = workflow.run(source_path, **arguments)
        if not isinstance(result, ScenarioWorkflowResult):
            raise TypeError(
                "scenario workflow must return ScenarioWorkflowResult"
            )
    except Exception as exc:
        _print_runtime_error(exc, stream=err)
        return int(RunScenarioExitCode.RUNTIME_ERROR)

    if result.success:
        _print_success(result, stream=out)
        return int(RunScenarioExitCode.SUCCESS)

    if result.state.status is WorkflowStatus.NEEDS_USER_INPUT:
        _print_needs_user_input(result, stream=err)
        return int(RunScenarioExitCode.NEEDS_USER_INPUT)

    _print_workflow_failure(result, stream=err)
    return int(RunScenarioExitCode.WORKFLOW_FAILED)


def _print_success(
    result: ScenarioWorkflowResult,
    *,
    stream: TextIO,
) -> None:
    paths = result.state.artifact_paths
    print("状态: 成功", file=stream)
    print(f"Run ID: {result.state.run_id}", file=stream)
    print(
        f"Run 目录: {_artifact_path(paths, 'run_root')}",
        file=stream,
    )
    print(
        f"Lua 文件: {_artifact_path(paths, 'original_lua')}",
        file=stream,
    )
    print(
        f"结果文件: {_artifact_path(paths, 'workflow_result')}",
        file=stream,
    )


def _print_workflow_failure(
    result: ScenarioWorkflowResult,
    *,
    stream: TextIO,
) -> None:
    paths = result.state.artifact_paths
    failed_stage = (
        result.failed_stage.value
        if result.failed_stage is not None
        else result.state.stage.value
    )

    print("状态: 失败", file=stream)
    print(f"Run ID: {result.state.run_id}", file=stream)
    print(
        f"Run 目录: {_artifact_path(paths, 'run_root')}",
        file=stream,
    )
    print(f"失败阶段: {failed_stage}", file=stream)

    errors = (
        result.validation.errors
        if result.validation is not None
        else ()
    )
    if errors:
        print(f"错误数量: {len(errors)}", file=stream)
        for issue in errors:
            print(
                f"- [{issue.code}] {issue.path}: {issue.message}",
                file=stream,
            )
    else:
        code = result.state.error_code or "workflow_failed"
        message = (
            result.state.error_message
            or "工作流失败，但没有返回详细校验信息"
        )
        print("错误数量: 1", file=stream)
        print(f"- {code}: {message}", file=stream)

    print(
        f"结果文件: {_artifact_path(paths, 'workflow_result')}",
        file=stream,
    )


def _print_needs_user_input(
    result: ScenarioWorkflowResult,
    *,
    stream: TextIO,
) -> None:
    """Render a normal, actionable stop instead of an infrastructure failure."""
    paths = result.state.artifact_paths
    print("状态: 需要用户决策", file=stream)
    print(f"Run ID: {result.state.run_id}", file=stream)
    print(f"Run 目录: {_artifact_path(paths, 'run_root')}", file=stream)
    print(f"阶段: {result.state.stage.value}", file=stream)
    print("请在 --resolution-file 中为每个歧义单位提供 category 和 dbid。", file=stream)
    for issue in result.validation.errors if result.validation else ():
        print(f"- [{issue.code}] {issue.path}: {issue.message}", file=stream)
    print(
        f"结果文件: {_artifact_path(paths, 'workflow_result')}",
        file=stream,
    )


def _print_runtime_error(
    exc: Exception,
    *,
    stream: TextIO,
) -> None:
    message = str(exc).strip() or type(exc).__name__
    print("状态: 异常", file=stream)
    print(f"异常类型: {type(exc).__name__}", file=stream)
    print(f"错误: {message}", file=stream)


def _artifact_path(
    paths: object,
    key: str,
) -> str:
    try:
        value = paths[key]  # type: ignore[index]
    except (KeyError, TypeError):
        return "<未提供>"
    return str(value)


def _non_blank_run_id(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise argparse.ArgumentTypeError(
            "run-id 不能为空或只包含空白字符"
        )
    return normalized


__all__ = [
    "RunScenarioExitCode",
    "add_run_scenario_arguments",
    "ScenarioWorkflowRunner",
    "build_run_scenario_parser",
    "run_scenario_command",
]
