from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from cmo_lua_agent.cli import (
    RunScenarioExitCode,
    build_run_scenario_parser,
    run_scenario_command,
)
from cmo_lua_agent.contract import (
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)
from cmo_lua_agent.generation import (
    LuaGenerationResult,
    LuaPreflightReport,
)
from cmo_lua_agent.orchestration import (
    ScenarioWorkflowResult,
    WorkflowStage,
    WorkflowState,
    WorkflowStatus,
)


def _paths(tmp_path: Path, run_id: str) -> dict[str, str]:
    run_root = tmp_path / "runs" / run_id
    return {
        "run_id": run_id,
        "run_root": str(run_root),
        "original_lua": str(
            run_root / "generation/original.lua"
        ),
        "rejected_lua": str(
            run_root / "generation/rejected.lua"
        ),
        "workflow_result": str(
            run_root / "result/workflow_result.json"
        ),
    }


def _success_result(
    tmp_path: Path,
    *,
    run_id: str = "run-success",
) -> ScenarioWorkflowResult:
    paths = _paths(tmp_path, run_id)
    state = WorkflowState(
        run_id=run_id,
        status=WorkflowStatus.COMPLETED,
        stage=WorkflowStage.COMPLETED,
        artifact_paths=paths,
    )
    preflight = LuaPreflightReport(
        validation=ValidationResult()
    )
    generation = LuaGenerationResult(
        success=True,
        lua_text="print('ok')",
        output_path=Path(paths["original_lua"]),
        generator_warnings=(),
        preflight=preflight,
    )
    return ScenarioWorkflowResult(
        success=True,
        state=state,
        failed_stage=None,
        validation=None,
        generation=generation,
    )


def _failed_result(
    tmp_path: Path,
    *,
    stage: WorkflowStage = WorkflowStage.SCHEMA,
    run_id: str = "run-failed",
) -> ScenarioWorkflowResult:
    paths = _paths(tmp_path, run_id)
    validation = ValidationResult(
        issues=(
            ValidationIssue(
                code="schema.missing_field",
                message="缺少 scenario 字段",
                path="$.scenario",
                severity=ValidationSeverity.ERROR,
            ),
            ValidationIssue(
                code="schema.invalid_type",
                message="sides 必须是对象",
                path="$.sides",
                severity=ValidationSeverity.ERROR,
            ),
        )
    )
    state = WorkflowState(
        run_id=run_id,
        status=WorkflowStatus.FAILED,
        stage=stage,
        artifact_paths=paths,
        error_code="schema_validation_failed",
        error_message="缺少 scenario 字段",
    )
    return ScenarioWorkflowResult(
        success=False,
        state=state,
        failed_stage=stage,
        validation=validation,
        generation=None,
    )


class StubWorkflow:
    def __init__(
        self,
        result: ScenarioWorkflowResult | None = None,
        *,
        error: Exception | None = None,
        raw_result: Any | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.raw_result = raw_result
        self.calls: list[dict[str, Any]] = []

    def run(
        self,
        source_path: Path,
        *,
        runs_root: Path,
        run_id: str | None = None,
    ) -> Any:
        self.calls.append(
            {
                "source_path": source_path,
                "runs_root": runs_root,
                "run_id": run_id,
            }
        )
        if self.error is not None:
            raise self.error
        if self.raw_result is not None:
            return self.raw_result
        return self.result


def test_parser_supports_source_runs_root_and_run_id() -> None:
    parser = build_run_scenario_parser()

    args = parser.parse_args(
        [
            "inputs/demo.json",
            "--runs-root",
            "custom-runs",
            "--run-id",
            "run-001",
        ]
    )

    assert args.source_path == Path("inputs/demo.json")
    assert args.runs_root == Path("custom-runs")
    assert args.run_id == "run-001"


def test_parser_uses_runs_directory_and_auto_run_id_by_default() -> None:
    parser = build_run_scenario_parser()

    args = parser.parse_args(["inputs/demo.json"])

    assert args.runs_root == Path("runs")
    assert args.run_id is None


@pytest.mark.parametrize("value", ["", "   "])
def test_parser_rejects_blank_run_id(value: str) -> None:
    parser = build_run_scenario_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(
            [
                "inputs/demo.json",
                "--run-id",
                value,
            ]
        )

    assert exc_info.value.code == 2


def test_success_calls_workflow_and_prints_artifact_summary(
    tmp_path: Path,
) -> None:
    workflow = StubWorkflow(_success_result(tmp_path))
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_scenario_command(
        workflow,
        [
            "inputs/demo.json",
            "--runs-root",
            str(tmp_path / "runs"),
            "--run-id",
            "run-success",
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == RunScenarioExitCode.SUCCESS
    assert workflow.calls == [
        {
            "source_path": Path("inputs/demo.json"),
            "runs_root": tmp_path / "runs",
            "run_id": "run-success",
        }
    ]
    output = stdout.getvalue()
    assert "状态: 成功" in output
    assert "Run ID: run-success" in output
    assert f"Run 目录: {tmp_path / 'runs/run-success'}" in output
    assert (
        f"Lua 文件: "
        f"{tmp_path / 'runs/run-success/generation/original.lua'}"
        in output
    )
    assert "workflow_result.json" in output
    assert stderr.getvalue() == ""


def test_validation_failure_prints_stage_and_all_errors(
    tmp_path: Path,
) -> None:
    workflow = StubWorkflow(_failed_result(tmp_path))
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_scenario_command(
        workflow,
        ["inputs/invalid.json"],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == RunScenarioExitCode.WORKFLOW_FAILED
    assert stdout.getvalue() == ""
    output = stderr.getvalue()
    assert "状态: 失败" in output
    assert "失败阶段: schema" in output
    assert "错误数量: 2" in output
    assert (
        "[schema.missing_field] $.scenario: 缺少 scenario 字段"
        in output
    )
    assert (
        "[schema.invalid_type] $.sides: sides 必须是对象"
        in output
    )
    assert "Run 目录:" in output


def test_failure_without_validation_uses_state_error_metadata(
    tmp_path: Path,
) -> None:
    run_id = "run-no-validation"
    paths = _paths(tmp_path, run_id)
    state = WorkflowState(
        run_id=run_id,
        status=WorkflowStatus.FAILED,
        stage=WorkflowStage.GENERATION,
        artifact_paths=paths,
        error_code="generation_failed",
        error_message="生成器不可用",
    )
    result = ScenarioWorkflowResult(
        success=False,
        state=state,
        failed_stage=WorkflowStage.GENERATION,
        validation=None,
        generation=None,
    )
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_scenario_command(
        StubWorkflow(result),
        ["inputs/demo.json"],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == RunScenarioExitCode.WORKFLOW_FAILED
    assert "generation_failed: 生成器不可用" in stderr.getvalue()


def test_runtime_exception_is_reported_without_traceback(
    tmp_path: Path,
) -> None:
    workflow = StubWorkflow(
        error=FileNotFoundError("source missing")
    )
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_scenario_command(
        workflow,
        [
            "inputs/missing.json",
            "--runs-root",
            str(tmp_path / "runs"),
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == RunScenarioExitCode.RUNTIME_ERROR
    assert stdout.getvalue() == ""
    output = stderr.getvalue()
    assert "状态: 异常" in output
    assert "异常类型: FileNotFoundError" in output
    assert "错误: source missing" in output
    assert "Traceback" not in output


def test_wrong_workflow_result_type_is_runtime_error() -> None:
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_scenario_command(
        StubWorkflow(raw_result={}),
        ["inputs/demo.json"],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == RunScenarioExitCode.RUNTIME_ERROR
    assert "ScenarioWorkflowResult" in stderr.getvalue()


def test_keyboard_interrupt_is_not_swallowed() -> None:
    workflow = StubWorkflow(error=KeyboardInterrupt())

    with pytest.raises(KeyboardInterrupt):
        run_scenario_command(
            workflow,
            ["inputs/demo.json"],
            stdout=StringIO(),
            stderr=StringIO(),
        )