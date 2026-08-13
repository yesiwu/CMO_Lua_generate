"""提供给 Chat / Tool 入口使用的精简服务集合。

完整应用 CmoLuaApplication 包含很多组件，
但是工具层不需要知道全部内容。

这里从完整应用中提取工具真正需要的服务，
降低模块之间的耦合。
"""

from __future__ import annotations

from dataclasses import dataclass

from cmo_lua_agent.bootstrap.app_factory import CmoLuaApplication
from cmo_lua_agent.integrations.cmolua import CmoDatabaseRepository
from cmo_lua_agent.orchestration import ScenarioWorkflow


@dataclass(frozen=True, slots=True)
class CmoLuaToolServices:
    """提供给 CMO Lua Chat 工具使用的公共服务。

    工具目前只需要：

    1. ScenarioWorkflow：
       处理 JSON → Lua 的完整流程。

    2. CmoDatabaseRepository：
       查询 CMO 数据库。

    不直接暴露整个 CmoLuaApplication，
    避免工具层依赖过多无关组件。
    """

    scenario_workflow: ScenarioWorkflow
    database_repository: CmoDatabaseRepository

    def __post_init__(self) -> None:
        # 启动时检查依赖类型是否正确，
        # 避免运行到工具调用阶段才发现配置错误。
        if not isinstance(self.scenario_workflow, ScenarioWorkflow):
            raise TypeError(
                "scenario_workflow 必须是 ScenarioWorkflow 类型"
            )

        if not isinstance(self.database_repository, CmoDatabaseRepository):
            raise TypeError(
                "database_repository 必须是 CmoDatabaseRepository 类型"
            )


def create_tool_services(
    application: CmoLuaApplication,
) -> CmoLuaToolServices:
    """从完整应用中提取 Chat 工具需要的服务。

    输入：

        CmoLuaApplication
        （完整应用依赖图）

              ↓

    输出：

        CmoLuaToolServices
        （工具需要的最小服务集合）

    """

    if not isinstance(application, CmoLuaApplication):
        raise TypeError(
            "application 必须是 CmoLuaApplication 类型"
        )

    return CmoLuaToolServices(
        # 提供 JSON → Lua 工作流能力
        scenario_workflow=application.scenario_workflow,

        # 提供数据库查询能力
        database_repository=application.database_repository,
    )


__all__ = [
    "CmoLuaToolServices",
    "create_tool_services",
]