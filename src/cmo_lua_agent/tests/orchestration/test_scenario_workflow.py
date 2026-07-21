from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from cmo_lua_agent.contract import (
    DatabaseResolutionOutput,
    DatabaseResolver,
    IRBuilder,
    IRValidator,
    ManifestBuildOutput,
    ManifestBuilder,
    ResolvedScenarioManifest,
    ScenarioContract,
    ScenarioIR,
    ScenarioSchemaValidator,
    ScenarioSemanticValidator,
    SemanticValidationOutput,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)
from cmo_lua_agent.generation import (
    LuaGenerationResult,
    LuaPreflightReport,
)
from cmo_lua_agent.ingest import JsonLoader
from cmo_lua_agent.integrations.cmolua import (
    CmoDatabaseRecord,
    CmoLuaGenerationError,
)
from cmo_lua_agent.orchestration import (
    ScenarioWorkflow,
    WorkflowStage,
    WorkflowStatus,
)


FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures/cmolua/golden/source.json"
)


def _issue(code: str) -> ValidationResult:
    return ValidationResult(
        issues=(
            ValidationIssue(
                code=code,
                message=code,
                path="$",
                severity=ValidationSeverity.ERROR,
            ),
        )
    )


class FakeRepository:
    def get_platform(
        self,
        dbid: int,
        *,
        category: str | None = None,
    ) -> CmoDatabaseRecord:
        platform_category = (
            "aircraft" if dbid == 2496 else "ship"
        )
        return CmoDatabaseRecord(
            dbid=dbid,
            name=f"Platform-{dbid}",
            category=platform_category,
            raw={"ID": dbid},
        )

    def get_loadout(self, loadout_id: int) -> CmoDatabaseRecord:
        return CmoDatabaseRecord(
            dbid=loadout_id,
            name=f"Loadout-{loadout_id}",
            category="loadout",
            raw={"ID": loadout_id},
        )

    def loadout_belongs_to_aircraft(
        self,
        *,
        aircraft_dbid: int,
        loadout_id: int,
    ) -> bool:
        return aircraft_dbid == 2496 and loadout_id == 9682

    def get_weapon(self, dbid: int) -> CmoDatabaseRecord | None:
        if dbid == 2137:
            return CmoDatabaseRecord(
                dbid=2137,
                name="YJ-83K",
                category="weapon",
                raw={"ID": 2137},
            )
        return None

    def find_weapon_exact(
        self,
        name: str,
    ) -> tuple[CmoDatabaseRecord, ...]:
        if name == "YJ-18":
            return (
                CmoDatabaseRecord(
                    dbid=500,
                    name="YJ-18",
                    category="weapon",
                    raw={"ID": 500},
                ),
            )
        return ()


class StubGenerationService:
    def __init__(
        self,
        *,
        accepted: bool = True,
        error: Exception | None = None,
    ) -> None:
        self.accepted = accepted
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def generate(self, **kwargs: Any) -> LuaGenerationResult:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error

        report = LuaPreflightReport(
            validation=(
                ValidationResult()
                if self.accepted
                else _issue("preflight.rejected")
            )
        )
        return LuaGenerationResult(
            success=self.accepted,
            lua_text=(
                "print('accepted')"
                if self.accepted
                else "DumpAmmo('rejected')"
            ),
            output_path=(
                Path(kwargs["output_path"])
                if self.accepted
                else None
            ),
            generator_warnings=(),
            preflight=report,
        )


class ExplodingComponent:
    def __getattr__(self, name: str):
        def explode(*args: Any, **kwargs: Any):
            raise AssertionError(
                f"downstream component unexpectedly called: {name}"
            )
        return explode


class RejectingSchemaValidator:
    def validate(self, scenario: Any) -> ValidationResult:
        return _issue("schema.invalid")


class RejectingSemanticValidator:
    def validate_and_normalize(
        self,
        scenario: Any,
    ) -> SemanticValidationOutput:
        return SemanticValidationOutput(
            normalized=scenario.raw,
            validation=_issue("semantic.invalid"),
        )


class RejectingIRValidator:
    def validate(self, ir: ScenarioIR) -> ValidationResult:
        return _issue("ir.invalid")


class RejectingDatabaseResolver:
    def resolve(
        self,
        ir: ScenarioIR,
    ) -> DatabaseResolutionOutput:
        return DatabaseResolutionOutput(
            resolved_ir=ir,
            validation=_issue("database.invalid"),
            report={"summary": {"errors": 1}},
        )


class PlatformResolutionRequiredResolver:
    def resolve(
        self,
        ir: ScenarioIR,
    ) -> DatabaseResolutionOutput:
        return DatabaseResolutionOutput(
            resolved_ir=ir,
            validation=_issue("database.platform_resolution_required"),
            report={"summary": {"errors": 1}},
        )


class RejectingManifestBuilder:
    def build(
        self,
        ir: ScenarioIR,
    ) -> ManifestBuildOutput:
        return ManifestBuildOutput(
            manifest=ResolvedScenarioManifest(
                data={
                    "manifestVersion": "resolved-scenario-manifest-v1",
                    "scenario": {"id": "invalid"},
                    "sides": {},
                    "strikePlan": [],
                }
            ),
            contract=ScenarioContract(
                scenario_id="invalid",
                unit_ids=(),
                unit_names=(),
                shooter_ids=(),
                target_ids=(),
            ),
            validation=_issue("manifest.invalid"),
        )


def _workflow(
    generation_service: Any,
    *,
    schema_validator: Any | None = None,
    semantic_validator: Any | None = None,
    ir_validator: Any | None = None,
    database_resolver: Any | None = None,
    manifest_builder: Any | None = None,
) -> ScenarioWorkflow:
    return ScenarioWorkflow(
        loader=JsonLoader(),
        schema_validator=(
            schema_validator or ScenarioSchemaValidator()
        ),
        semantic_validator=(
            semantic_validator or ScenarioSemanticValidator()
        ),
        ir_builder=IRBuilder(),
        ir_validator=ir_validator or IRValidator(),
        database_resolver=(
            database_resolver
            or DatabaseResolver(FakeRepository())  # type: ignore[arg-type]
        ),
        manifest_builder=manifest_builder or ManifestBuilder(),
        generation_service=generation_service,
    )


def _workflow_result(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_complete_pipeline_persists_all_standard_artifacts(
    tmp_path: Path,
) -> None:
    generation = StubGenerationService(accepted=True)
    workflow = _workflow(generation)

    result = workflow.run(
        FIXTURE,
        runs_root=tmp_path / "runs",
        run_id="success",
    )

    paths = result.state.artifact_paths
    assert result.success is True
    assert result.state.status is WorkflowStatus.COMPLETED
    assert result.state.stage is WorkflowStage.COMPLETED
    assert Path(paths["source_json"]).is_file()
    assert Path(paths["schema_report"]).is_file()
    assert Path(paths["semantic_report"]).is_file()
    assert Path(paths["scenario_ir"]).is_file()
    assert Path(paths["ir_report"]).is_file()
    assert Path(paths["database_report"]).is_file()
    assert Path(paths["manifest_report"]).is_file()
    assert Path(paths["scenario_contract"]).is_file()
    assert Path(paths["resolved_manifest"]).is_file()
    assert Path(paths["lua_preflight_report"]).is_file()
    assert Path(paths["original_lua"]).read_text(
        encoding="utf-8"
    ) == "print('accepted')"
    assert not Path(paths["rejected_lua"]).exists()
    assert generation.calls[0]["manifest_path"] == Path(
        paths["resolved_manifest"]
    )
    persisted = _workflow_result(Path(paths["workflow_result"]))
    assert persisted["success"] is True
    assert persisted["state"]["status"] == "completed"


def test_schema_failure_stops_before_semantic_database_and_generation(
    tmp_path: Path,
) -> None:
    generation = StubGenerationService()
    workflow = ScenarioWorkflow(
        loader=JsonLoader(),
        schema_validator=RejectingSchemaValidator(),
        semantic_validator=ExplodingComponent(),
        ir_builder=ExplodingComponent(),
        ir_validator=ExplodingComponent(),
        database_resolver=ExplodingComponent(),
        manifest_builder=ExplodingComponent(),
        generation_service=generation,
    )

    result = workflow.run(
        FIXTURE,
        runs_root=tmp_path / "runs",
        run_id="schema-failure",
    )

    assert result.success is False
    assert result.failed_stage is WorkflowStage.SCHEMA
    assert result.state.status is WorkflowStatus.FAILED
    assert result.state.stage is WorkflowStage.SCHEMA
    assert result.validation is not None
    assert result.validation.errors[0].code == "schema.invalid"
    assert generation.calls == []
    assert Path(result.state.artifact_paths["schema_report"]).is_file()
    assert not Path(
        result.state.artifact_paths["semantic_report"]
    ).exists()


def test_semantic_failure_is_persisted_and_stops_before_ir(
    tmp_path: Path,
) -> None:
    workflow = ScenarioWorkflow(
        loader=JsonLoader(),
        schema_validator=ScenarioSchemaValidator(),
        semantic_validator=RejectingSemanticValidator(),
        ir_builder=ExplodingComponent(),
        ir_validator=ExplodingComponent(),
        database_resolver=ExplodingComponent(),
        manifest_builder=ExplodingComponent(),
        generation_service=ExplodingComponent(),
    )

    result = workflow.run(
        FIXTURE,
        runs_root=tmp_path / "runs",
        run_id="semantic-failure",
    )

    assert result.failed_stage is WorkflowStage.SEMANTIC
    assert Path(
        result.state.artifact_paths["semantic_report"]
    ).is_file()
    assert not Path(result.state.artifact_paths["scenario_ir"]).exists()


def test_ir_failure_stops_before_database(tmp_path: Path) -> None:
    workflow = _workflow(
        ExplodingComponent(),
        ir_validator=RejectingIRValidator(),
        database_resolver=ExplodingComponent(),
    )

    result = workflow.run(
        FIXTURE,
        runs_root=tmp_path / "runs",
        run_id="ir-failure",
    )

    assert result.failed_stage is WorkflowStage.IR
    assert Path(result.state.artifact_paths["scenario_ir"]).is_file()
    assert Path(result.state.artifact_paths["ir_report"]).is_file()
    assert not Path(
        result.state.artifact_paths["database_report"]
    ).exists()


def test_database_failure_saves_validation_and_resolution_report(
    tmp_path: Path,
) -> None:
    workflow = _workflow(
        ExplodingComponent(),
        database_resolver=RejectingDatabaseResolver(),
        manifest_builder=ExplodingComponent(),
    )

    result = workflow.run(
        FIXTURE,
        runs_root=tmp_path / "runs",
        run_id="database-failure",
    )

    assert result.failed_stage is WorkflowStage.DATABASE
    report_path = Path(
        result.state.artifact_paths["database_report"]
    )
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["validation"]["valid"] is False
    assert payload["resolution"]["summary"]["errors"] == 1
    assert not Path(
        result.state.artifact_paths["resolved_manifest"]
    ).exists()


def test_platform_ambiguity_stops_for_user_confirmation(
    tmp_path: Path,
) -> None:
    generation = StubGenerationService()
    workflow = _workflow(
        generation,
        database_resolver=PlatformResolutionRequiredResolver(),
        manifest_builder=ExplodingComponent(),
    )

    result = workflow.run(
        FIXTURE,
        runs_root=tmp_path / "runs",
        run_id="needs-platform-decision",
    )

    assert result.success is False
    assert result.state.status is WorkflowStatus.NEEDS_USER_INPUT
    assert result.state.error_code == "platform_resolution_required"
    assert result.failed_stage is WorkflowStage.DATABASE
    assert generation.calls == []


def test_manifest_failure_saves_report_without_calling_generator(
    tmp_path: Path,
) -> None:
    generation = StubGenerationService()
    workflow = _workflow(
        generation,
        manifest_builder=RejectingManifestBuilder(),
    )

    result = workflow.run(
        FIXTURE,
        runs_root=tmp_path / "runs",
        run_id="manifest-failure",
    )

    assert result.failed_stage is WorkflowStage.MANIFEST
    assert Path(
        result.state.artifact_paths["manifest_report"]
    ).is_file()
    assert not Path(
        result.state.artifact_paths["resolved_manifest"]
    ).exists()
    assert generation.calls == []


def test_rejected_lua_is_normal_failed_result(tmp_path: Path) -> None:
    generation = StubGenerationService(accepted=False)
    workflow = _workflow(generation)

    result = workflow.run(
        FIXTURE,
        runs_root=tmp_path / "runs",
        run_id="rejected",
    )

    assert result.success is False
    assert result.failed_stage is WorkflowStage.GENERATION
    assert result.generation is not None
    assert result.generation.success is False
    assert result.state.status is WorkflowStatus.FAILED
    assert Path(
        result.state.artifact_paths["rejected_lua"]
    ).is_file()
    assert not Path(
        result.state.artifact_paths["original_lua"]
    ).exists()


def test_generator_exception_records_generation_failure_and_reraises(
    tmp_path: Path,
) -> None:
    workflow = _workflow(
        StubGenerationService(
            error=CmoLuaGenerationError("generator failed")
        )
    )

    with pytest.raises(
        CmoLuaGenerationError,
        match="generator failed",
    ):
        workflow.run(
            FIXTURE,
            runs_root=tmp_path / "runs",
            run_id="generator-error",
        )

    result_path = (
        tmp_path
        / "runs/generator-error/result/workflow_result.json"
    )
    persisted = _workflow_result(result_path)
    assert persisted["status"] == "failed"
    assert persisted["stage"] == "generation"
    assert persisted["error_code"] == "generation_failed"
    assert not (
        tmp_path
        / "runs/generator-error/generation/original.lua"
    ).exists()
