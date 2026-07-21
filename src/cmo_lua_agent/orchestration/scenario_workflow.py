"""
因为它负责协调多个组件完成完整业务流程：

读取 JSON
→ 构建 IR
→ 校验 IR
→ 构建 Manifest
→ 加载 Skill
→ 调用 LLM 生成 Lua
→ 执行 CMO
→ 解析错误
→ 修复重试
→ 验证结果
→ 保存运行产物

这与 AgentLoop 一样，都属于“编排层”，而不是具体工具或业务组件。


批量执行lua
CI
后台任务
无人值守修复

不能在后台突然等待：

是否允许？[y/N]

否则任务会永久卡住。
"""

from __future__ import annotations

"""
CMO 场景处理工作流。

该模块负责协调各个独立组件，完成从场景 JSON 输入到
Lua 脚本生成、CMO 执行、错误修复和结果验证的完整流程。

主要流程包括：
1. 读取并分析输入 JSON；
2. 将异构 JSON 转换为统一 Scenario IR；
3. 校验 IR 并构建 Execution Manifest；
4. 加载与当前场景相关的 Skill 和模板；
5. 调用 LLM 生成初始 Lua 脚本；
6. 对 Lua 进行静态检查并调用 CMO 执行；
7. 根据执行错误进入有界修复循环；
8. 验证最终结果是否符合初始场景契约；
9. 保存每个阶段的运行产物和执行轨迹。

本模块只负责流程编排，不应包含具体的 JSON 解析、
LLM API 调用、subprocess 执行、错误正则解析或数据库 SQL。
这些逻辑应由对应的组件实现。
"""

#未来 ScenarioWorkflow 可以在某个步骤内部调用 AgentLoop：

"""Dependency-injected orchestration for the complete JSON-to-Lua pipeline."""

from dataclasses import dataclass
from pathlib import Path
from collections.abc import Mapping
from typing import Any

from cmo_lua_agent.artifacts import ArtifactPersistenceError
from cmo_lua_agent.contract import (
    DatabaseResolutionOutput,
    DatabaseResolver,
    IRBuilder,
    IRValidator,
    ManifestBuildOutput,
    ManifestBuilder,
    ScenarioSchemaValidator,
    ScenarioSemanticValidator,
    ValidationResult,
)
from cmo_lua_agent.generation import (
    LuaGenerationResult,
    LuaGenerationService,
)
from cmo_lua_agent.ingest import JsonLoader
from cmo_lua_agent.integrations.cmolua import (
    CmoDatabaseInfrastructureError,
    CmoLuaGenerationError,
    CmoLuaGeneratorImportError,
)
from cmo_lua_agent.orchestration.workflow_context import WorkflowContext
from cmo_lua_agent.orchestration.workflow_result import (
    ScenarioWorkflowResult,
)
from cmo_lua_agent.orchestration.workflow_state import (
    WorkflowStage,
    WorkflowStatus,
)


@dataclass(slots=True)
class ScenarioWorkflow:
    """Run each deterministic pipeline stage in strict order."""

    loader: JsonLoader
    schema_validator: ScenarioSchemaValidator
    semantic_validator: ScenarioSemanticValidator
    ir_builder: IRBuilder
    ir_validator: IRValidator
    database_resolver: DatabaseResolver
    manifest_builder: ManifestBuilder
    generation_service: LuaGenerationService

    def run(
        self,
        source_path: Path,
        *,
        runs_root: Path,
        run_id: str | None = None,
        platform_resolutions: Mapping[str, Any] | None = None,
    ) -> ScenarioWorkflowResult:
        context = WorkflowContext.create(
            runs_root,
            run_id=run_id,
        )

        try:
            context.advance(WorkflowStage.INPUT)
            scenario_input = self.loader.load(source_path)
            context.store.save_source(scenario_input)

            context.advance(WorkflowStage.SCHEMA)
            schema_result = self.schema_validator.validate(
                scenario_input
            )
            context.store.save_validation(
                "schema",
                schema_result,
            )
            if not schema_result.valid:
                return self._finish_validation_failure(
                    context,
                    stage=WorkflowStage.SCHEMA,
                    code="schema_validation_failed",
                    validation=schema_result,
                )

            context.advance(WorkflowStage.SEMANTIC)
            semantic_output = (
                self.semantic_validator.validate_and_normalize(
                    scenario_input
                )
            )
            context.store.save_validation(
                "semantic",
                semantic_output.validation,
            )
            if not semantic_output.validation.valid:
                return self._finish_validation_failure(
                    context,
                    stage=WorkflowStage.SEMANTIC,
                    code="semantic_validation_failed",
                    validation=semantic_output.validation,
                )

            context.advance(WorkflowStage.IR)
            scenario_ir = self.ir_builder.build(
                semantic_output.normalized
            )
            context.store.save_ir(scenario_ir)
            ir_result = self.ir_validator.validate(scenario_ir)
            context.store.save_validation("ir", ir_result)
            if not ir_result.valid:
                return self._finish_validation_failure(
                    context,
                    stage=WorkflowStage.IR,
                    code="ir_validation_failed",
                    validation=ir_result,
                )

            context.advance(WorkflowStage.DATABASE)
            if platform_resolutions is None:
                database_output = self.database_resolver.resolve(scenario_ir)
            else:
                database_output = self.database_resolver.resolve(
                    scenario_ir,
                    platform_resolutions=platform_resolutions,
                )
            _require_database_output(database_output)
            context.store.save_validation(
                "database",
                {
                    "validation": database_output.validation,
                    "resolution": database_output.report,
                },
            )
            if not database_output.validation.valid:
                if _requires_platform_resolution(database_output.validation):
                    return self._finish_needs_user_input(
                        context,
                        stage=WorkflowStage.DATABASE,
                        validation=database_output.validation,
                    )
                return self._finish_validation_failure(
                    context,
                    stage=WorkflowStage.DATABASE,
                    code="database_validation_failed",
                    validation=database_output.validation,
                )

            context.advance(WorkflowStage.MANIFEST)
            manifest_output = self.manifest_builder.build(
                database_output.resolved_ir
            )
            _require_manifest_output(manifest_output)
            context.store.save_validation(
                "manifest",
                manifest_output.validation,
            )
            if not manifest_output.validation.valid:
                return self._finish_validation_failure(
                    context,
                    stage=WorkflowStage.MANIFEST,
                    code="manifest_validation_failed",
                    validation=manifest_output.validation,
                )

            context.store.save_contract(manifest_output.contract)
            context.store.save_manifest(manifest_output.manifest)

            generation = context.generate_lua(
                self.generation_service,
                manifest=manifest_output.manifest,
                contract=manifest_output.contract,
            )
            if not generation.success:
                return self._finish_validation_failure(
                    context,
                    stage=WorkflowStage.GENERATION,
                    code="lua_preflight_failed",
                    validation=generation.preflight.validation,
                    generation=generation,
                )

            context.complete()
            result = ScenarioWorkflowResult(
                success=True,
                state=context.state,
                failed_stage=None,
                validation=None,
                generation=generation,
            )
            context.store.save_final_result(result)
            return result
        except Exception as exc:
            self._record_exception(context, exc)
            raise

    @staticmethod
    def _finish_validation_failure(
        context: WorkflowContext,
        *,
        stage: WorkflowStage,
        code: str,
        validation: ValidationResult,
        generation: LuaGenerationResult | None = None,
    ) -> ScenarioWorkflowResult:
        message = _first_error_message(validation, fallback=code)
        context.fail(code, message)
        result = ScenarioWorkflowResult(
            success=False,
            state=context.state,
            failed_stage=stage,
            validation=validation,
            generation=generation,
        )
        context.store.save_final_result(result)
        return result

    @staticmethod
    def _finish_needs_user_input(
        context: WorkflowContext,
        *,
        stage: WorkflowStage,
        validation: ValidationResult,
    ) -> ScenarioWorkflowResult:
        message = _first_error_message(
            validation,
            fallback="需要确认平台类别和 DBID",
        )
        context.needs_user_input(
            "platform_resolution_required",
            message,
        )
        result = ScenarioWorkflowResult(
            success=False,
            state=context.state,
            failed_stage=stage,
            validation=validation,
            generation=None,
        )
        context.store.save_final_result(result)
        return result

    @staticmethod
    def _record_exception(
        context: WorkflowContext,
        exc: Exception,
    ) -> None:
        if context.state.status is WorkflowStatus.FAILED:
            return

        code = _exception_code(exc)
        message = str(exc).strip() or type(exc).__name__
        try:
            context.fail(code, message)
        except Exception:
            # Preserve the original infrastructure/programming exception.
            pass


def _require_database_output(
    value: Any,
) -> DatabaseResolutionOutput:
    if not isinstance(value, DatabaseResolutionOutput):
        raise TypeError(
            "database_resolver.resolve must return "
            "DatabaseResolutionOutput"
        )
    return value


def _require_manifest_output(value: Any) -> ManifestBuildOutput:
    if not isinstance(value, ManifestBuildOutput):
        raise TypeError(
            "manifest_builder.build must return ManifestBuildOutput"
        )
    return value


def _first_error_message(
    validation: ValidationResult,
    *,
    fallback: str,
) -> str:
    if validation.errors:
        return validation.errors[0].message
    return fallback


def _requires_platform_resolution(validation: ValidationResult) -> bool:
    """Stop at a user-owned ambiguity before asking the model to handle later errors."""
    return any(
        issue.code == "database.platform_resolution_required"
        for issue in validation.errors
    )


def _exception_code(exc: Exception) -> str:
    if isinstance(exc, ArtifactPersistenceError):
        return "artifact_persistence_failed"
    if isinstance(exc, CmoDatabaseInfrastructureError):
        return "database_infrastructure_failed"
    if isinstance(
        exc,
        (CmoLuaGenerationError, CmoLuaGeneratorImportError),
    ):
        return "generation_failed"
    return "workflow_exception"
