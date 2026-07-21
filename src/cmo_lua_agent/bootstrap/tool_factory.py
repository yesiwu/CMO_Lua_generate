"""Narrow application projection used by future chat/tool entry points."""

from __future__ import annotations

from dataclasses import dataclass

from cmo_lua_agent.bootstrap.app_factory import CmoLuaApplication
from cmo_lua_agent.integrations.cmolua import CmoDatabaseRepository
from cmo_lua_agent.orchestration import ScenarioWorkflow


@dataclass(frozen=True, slots=True)
class CmoLuaToolServices:
    """Shared services required by CMO Lua Chat tools."""

    scenario_workflow: ScenarioWorkflow
    database_repository: CmoDatabaseRepository

    def __post_init__(self) -> None:
        if not isinstance(self.scenario_workflow, ScenarioWorkflow):
            raise TypeError(
                "scenario_workflow must be ScenarioWorkflow"
            )
        if not isinstance(self.database_repository, CmoDatabaseRepository):
            raise TypeError(
                "database_repository must be CmoDatabaseRepository"
            )


def create_tool_services(
    application: CmoLuaApplication,
) -> CmoLuaToolServices:
    """Reuse an existing application graph for future tool construction."""

    if not isinstance(application, CmoLuaApplication):
        raise TypeError(
            "application must be CmoLuaApplication"
        )

    return CmoLuaToolServices(
        scenario_workflow=application.scenario_workflow,
        database_repository=application.database_repository,
    )


__all__ = [
    "CmoLuaToolServices",
    "create_tool_services",
]
