"""Application composition root for the JSON-to-Lua pipeline.

This module is the only place that constructs the complete real dependency
graph.  Creating the graph validates configured paths, but keeps the external
generator and database query module lazy: no Lua is generated and no database
query is executed during bootstrap.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from cmo_lua_agent.contract import (
    DatabaseResolver,
    IRBuilder,
    IRValidator,
    ManifestBuilder,
    ScenarioSchemaValidator,
    ScenarioSemanticValidator,
)
from cmo_lua_agent.generation import (
    LuaGenerationService,
    LuaPreflightValidator,
)
from cmo_lua_agent.ingest import JsonLoader
from cmo_lua_agent.integrations.cmolua import (
    CmoDatabaseRepository,
    CmoLuaGeneratorAdapter,
    CmoLuaIntegrationConfig,
    CmoSkillRepository,
)
from cmo_lua_agent.orchestration import ScenarioWorkflow


@dataclass(frozen=True, slots=True)
class CmoLuaApplication:
    """Fully wired, reusable application services.

    The container is immutable, while the wrapped adapters may maintain their
    existing lazy import caches.  One application instance therefore owns one
    coherent repository/adapter/workflow graph.
    """

    project_root: Path
    config: CmoLuaIntegrationConfig
    database_repository: CmoDatabaseRepository
    generator_adapter: CmoLuaGeneratorAdapter
    skill_repository: CmoSkillRepository
    generation_service: LuaGenerationService
    scenario_workflow: ScenarioWorkflow

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "project_root",
            Path(self.project_root).expanduser().resolve(strict=False),
        )
        _require_instance(
            self.config,
            CmoLuaIntegrationConfig,
            field_name="config",
        )
        _require_instance(
            self.database_repository,
            CmoDatabaseRepository,
            field_name="database_repository",
        )
        _require_instance(
            self.generator_adapter,
            CmoLuaGeneratorAdapter,
            field_name="generator_adapter",
        )
        _require_instance(
            self.skill_repository,
            CmoSkillRepository,
            field_name="skill_repository",
        )
        _require_instance(
            self.generation_service,
            LuaGenerationService,
            field_name="generation_service",
        )
        _require_instance(
            self.scenario_workflow,
            ScenarioWorkflow,
            field_name="scenario_workflow",
        )


def create_application(
    project_root: Path,
    *,
    environ: Mapping[str, str] | None = None,
) -> CmoLuaApplication:
    """Validate integration paths and construct the real application graph.

    Relative environment-variable paths are resolved against ``project_root``
    by :meth:`CmoLuaIntegrationConfig.from_project_root`.  The function does
    not create run directories, import the external generator, import the
    external query module, or access SQLite rows.
    """

    root = _normalize_project_root(project_root)
    config = CmoLuaIntegrationConfig.from_project_root(
        root,
        environ=environ,
    )

    database_repository = CmoDatabaseRepository(config)
    generator_adapter = CmoLuaGeneratorAdapter(config)
    skill_repository = CmoSkillRepository(config)

    generation_service = LuaGenerationService(
        adapter=generator_adapter,
        preflight_validator=LuaPreflightValidator(),
        workspace_root=root,
    )

    scenario_workflow = ScenarioWorkflow(
        loader=JsonLoader(),
        schema_validator=ScenarioSchemaValidator(),
        semantic_validator=ScenarioSemanticValidator(),
        ir_builder=IRBuilder(),
        ir_validator=IRValidator(),
        database_resolver=DatabaseResolver(
            database_repository
        ),
        manifest_builder=ManifestBuilder(),
        generation_service=generation_service,
    )

    return CmoLuaApplication(
        project_root=root,
        config=config,
        database_repository=database_repository,
        generator_adapter=generator_adapter,
        skill_repository=skill_repository,
        generation_service=generation_service,
        scenario_workflow=scenario_workflow,
    )


def _normalize_project_root(value: Path) -> Path:
    try:
        return Path(value).expanduser().resolve(strict=False)
    except TypeError as exc:
        raise TypeError("project_root must be path-like") from exc


def _require_instance(
    value: object,
    expected_type: type[object],
    *,
    field_name: str,
) -> None:
    if not isinstance(value, expected_type):
        raise TypeError(
            f"{field_name} must be {expected_type.__name__}"
        )


__all__ = [
    "CmoLuaApplication",
    "create_application",
]