
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from cmo_lua_agent.contract import (
    ResolvedScenarioManifest,
    ScenarioContract,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)
from cmo_lua_agent.generation import (
    LuaGenerationResult,
    LuaPreflightReport,
)
from cmo_lua_agent.integrations.cmolua.generator_adapter import (
    CmoLuaGenerationError,
)
from cmo_lua_agent.orchestration import (
    WorkflowContext,
    WorkflowStage,
    WorkflowStatus,
    WorkflowTransitionError,
)


def _manifest() -> ResolvedScenarioManifest:
    return ResolvedScenarioManifest(
        data={
            "manifestVersion": "resolved-scenario-manifest-v1",
            "scenario": {"id": "demo", "name": "演示场景"},
            "sides": {
                "red": {"name": "红方", "units": []},
                "blue": {"name": "蓝方", "units": []},
            },
            "strikePlan": [],
        }
    )


def _contract() -> ScenarioContract:
    return ScenarioContract(
        scenario_id="demo",
        unit_ids=(),
        unit_names=(),
        shooter_ids=(),
        target_ids=(),
    )


def _valid_report() -> LuaPreflightReport:
    return LuaPreflightReport(validation=ValidationResult())


def _invalid_report() -> LuaPreflightReport:
    return LuaPreflightReport(
        validation=ValidationResult(
            issues=(
                ValidationIssue(
                    code="preflight.forbidden_api",
                    message="禁止 API",
                    path="$.lua",
                    severity=ValidationSeverity.ERROR,
                ),
            )
        )
    )


class StubGenerationService:
    def __init__(
        self,
        *,
        result: LuaGenerationResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def generate(self, **kwargs: Any) -> LuaGenerationResult:
        self.calls.append(kwargs)
        manifest_path = Path(kwargs["manifest_path"])
        assert manifest_path.is_file()
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def _success_result(output_path: Path) -> LuaGenerationResult:
    return LuaGenerationResult(
        success=True,
        lua_text="print('accepted')",
        output_path=output_path,
        generator_warnings=(),
        preflight=_valid_report(),
    )


def _rejected_result() -> LuaGenerationResult:
    return LuaGenerationResult(
        success=False,
        lua_text="DumpAmmo('rejected')",
        output_path=None,
        generator_warnings=("unsafe",),
        preflight=_invalid_report(),
    )


def _read_state(context: WorkflowContext) -> dict[str, Any]:
    return json.loads(
        context.store.paths.workflow_result.read_text(
            encoding="utf-8"
        )
    )


def test_create_persists_initial_state_with_canonical_paths(
    tmp_path: Path,
) -> None:
    context = WorkflowContext.create(
        tmp_path / "runs",
        run_id="run-001",
    )

    persisted = _read_state(context)
    assert context.state.status is WorkflowStatus.CREATED
    assert context.state.stage is WorkflowStage.CREATED
    assert persisted == context.state.to_dict()
    assert persisted["artifact_paths"] == context.store.paths.to_dict()


def test_save_manifest_uses_store_once_and_updates_state(
    tmp_path: Path,
) -> None:
    context = WorkflowContext.create(
        tmp_path / "runs",
        run_id="run-002",
    )

    path = context.save_manifest(_manifest())

    assert path == context.store.paths.resolved_manifest
    assert json.loads(path.read_text(encoding="utf-8")) == (
        _manifest().to_dict()
    )
    assert context.state.status is WorkflowStatus.RUNNING
    assert context.state.stage is WorkflowStage.MANIFEST
    assert _read_state(context) == context.state.to_dict()

    with pytest.raises(WorkflowTransitionError):
        context.save_manifest(_manifest())


def test_generate_accepted_persists_preflight_and_original_lua(
    tmp_path: Path,
) -> None:
    context = WorkflowContext.create(
        tmp_path / "runs",
        run_id="run-003",
    )
    manifest = _manifest()
    context.save_manifest(manifest)
    service = StubGenerationService(
        result=_success_result(context.store.paths.original_lua)
    )

    result = context.generate_lua(
        service,  # type: ignore[arg-type]
        manifest=manifest,
        contract=_contract(),
    )

    assert result.success is True
    assert context.store.paths.original_lua.read_text(
        encoding="utf-8"
    ) == "print('accepted')"
    assert context.store.paths.rejected_lua.exists() is False
    assert json.loads(
        context.store.paths.lua_preflight_report.read_text(
            encoding="utf-8"
        )
    ) == _valid_report().to_dict()
    assert service.calls[0]["manifest_path"] == (
        context.store.paths.resolved_manifest
    )
    assert service.calls[0]["output_path"] == (
        context.store.paths.original_lua
    )
    assert context.state.stage is WorkflowStage.GENERATION
    assert context.state.status is WorkflowStatus.RUNNING
    assert _read_state(context) == context.state.to_dict()


def test_generate_rejected_persists_rejected_lua_only(
    tmp_path: Path,
) -> None:
    context = WorkflowContext.create(
        tmp_path / "runs",
        run_id="run-004",
    )
    manifest = _manifest()
    context.save_manifest(manifest)
    service = StubGenerationService(result=_rejected_result())

    result = context.generate_lua(
        service,  # type: ignore[arg-type]
        manifest=manifest,
        contract=_contract(),
    )

    assert result.success is False
    assert context.store.paths.original_lua.exists() is False
    assert context.store.paths.rejected_lua.read_text(
        encoding="utf-8"
    ) == "DumpAmmo('rejected')"
    assert context.store.paths.lua_preflight_report.is_file()
    assert context.state.stage is WorkflowStage.GENERATION
    assert context.state.status is WorkflowStatus.RUNNING


def test_generator_exception_records_failed_state_and_re_raises(
    tmp_path: Path,
) -> None:
    context = WorkflowContext.create(
        tmp_path / "runs",
        run_id="run-005",
    )
    manifest = _manifest()
    context.save_manifest(manifest)
    service = StubGenerationService(
        error=CmoLuaGenerationError("generator failed")
    )

    with pytest.raises(CmoLuaGenerationError, match="generator failed"):
        context.generate_lua(
            service,  # type: ignore[arg-type]
            manifest=manifest,
            contract=_contract(),
        )

    assert context.state.status is WorkflowStatus.FAILED
    assert context.state.stage is WorkflowStage.GENERATION
    assert context.state.error_code == "generation_failed"
    assert "generator failed" in (context.state.error_message or "")
    assert _read_state(context) == context.state.to_dict()
    assert context.store.paths.original_lua.exists() is False
    assert context.store.paths.rejected_lua.exists() is False


def test_rejected_generation_cannot_be_completed(
    tmp_path: Path,
) -> None:
    context = WorkflowContext.create(
        tmp_path / "runs",
        run_id="run-rejected-complete",
    )
    manifest = _manifest()
    context.save_manifest(manifest)
    context.generate_lua(
        StubGenerationService(result=_rejected_result()),  # type: ignore[arg-type]
        manifest=manifest,
        contract=_contract(),
    )

    with pytest.raises(
        WorkflowTransitionError,
        match="没有生成成功 Lua",
    ):
        context.complete()

    assert context.state.status is WorkflowStatus.RUNNING
    assert context.state.stage is WorkflowStage.GENERATION


def test_complete_and_explicit_fail_persist_terminal_state(
    tmp_path: Path,
) -> None:
    completed_context = WorkflowContext.create(
        tmp_path / "runs",
        run_id="run-complete",
    )
    manifest = _manifest()
    completed_context.save_manifest(manifest)
    completed_context.generate_lua(
        StubGenerationService(
            result=_success_result(
                completed_context.store.paths.original_lua
            )
        ),  # type: ignore[arg-type]
        manifest=manifest,
        contract=_contract(),
    )

    completed = completed_context.complete()

    assert completed.status is WorkflowStatus.COMPLETED
    assert completed.stage is WorkflowStage.COMPLETED
    assert _read_state(completed_context) == completed.to_dict()

    failed_context = WorkflowContext.create(
        tmp_path / "runs",
        run_id="run-fail",
    )
    failed = failed_context.fail("cancelled", "用户取消")

    assert failed.status is WorkflowStatus.FAILED
    assert failed.error_code == "cancelled"
    assert _read_state(failed_context) == failed.to_dict()
