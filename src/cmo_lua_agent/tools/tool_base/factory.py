
"""
工具注册表构建模块。

该模块负责创建 ToolRegistry，并显式注册当前程序
允许 LLM 调用的所有工具。

具体工具逻辑位于各自的 *_tool.py 文件中；
AgentLoop 不直接依赖具体工具。
"""

from __future__ import annotations

from pathlib import Path
import os

from cmo_lua_agent.bootstrap.tool_factory import (
    CmoLuaToolServices,
)
from cmo_lua_agent.core.run_artifact_store import (
    RunArtifactStore,
)
from cmo_lua_agent.execution.cmo_job_config import (
    CmoJobConfig,
)
from cmo_lua_agent.execution.cmo_process_runner import (
    CmoProcessRunner,
)
from cmo_lua_agent.execution.cmo_runner import (
    CmoRunner,
)
from cmo_lua_agent.hooks.manager import (
    HookManager,
)

from cmo_lua_agent.tools.execute_cmo_tool import (
    ExecuteCmoTool,
)
from cmo_lua_agent.tools.edit_file_tool import EditFileTool
from cmo_lua_agent.tools.create_file_tool import CreateFileTool
from cmo_lua_agent.tools.create_json_copy_tool import CreateJsonCopyTool
from cmo_lua_agent.tools.read_file_tool import (
    ReadFileTool,
)
from cmo_lua_agent.tools.list_directory_tool import ListDirectoryTool
from cmo_lua_agent.tools.list_skills_tool import (
    ListSkillsTool,
)
from cmo_lua_agent.tools.load_skill_tool import (
    LoadSkillTool,
)
from cmo_lua_agent.tools.tool_base.registry import (
    ToolRegistry,
)
from cmo_lua_agent.tools.generate_cmo_lua_tool import GenerateCmoLuaTool
from cmo_lua_agent.tools.query_cmo_database_tool import QueryCmoDatabaseTool


DEFAULT_CMO_RUNNER_PATH = Path(
    r"C:\CMO\CmoBatchRunner\CmoBatchRunner.exe"
)

PACKAGE_SKILLS_ROOT = Path(__file__).resolve().parents[2] / "skills"


def build_tool_registry(
    *,
    workdir: Path,
    hook_manager: HookManager,
    cmo_runner_path: Path | None = None,
    cmo_config_path: Path | None = None,
    cmo_lua_services: CmoLuaToolServices | None = None,
) -> ToolRegistry:
    """
    创建并注册项目工具。

    Args:
        workdir:
            当前项目工作目录。

        hook_manager:
            ToolRegistry 使用的 Hook 管理器。

        cmo_runner_path:
            CmoBatchRunner.exe 路径。

        cmo_config_path:
            CmoBatchRunner 任务 JSON 路径。

        cmo_lua_services:
            JSON 转 Lua 工具与 CMOLua Skill 工具共享的应用服务。
            未提供时，仅注册与该依赖无关的基础工具。

    Returns:
        完成注册的 ToolRegistry。
    """
    workdir = Path(
        workdir
    ).resolve()

    configured_runner = (
        cmo_runner_path
        or os.environ.get("CMO_BATCH_RUNNER_PATH")
        or DEFAULT_CMO_RUNNER_PATH
    )
    configured_config = (
        cmo_config_path
        or os.environ.get("CMO_JOB_CONFIG_PATH")
        or (workdir / "json_data" / "tot-three.json")
    )
    cmo_runner_path = Path(configured_runner).expanduser().resolve()
    cmo_config_path = Path(configured_config).expanduser().resolve()

    registry = ToolRegistry(
        hook_manager=hook_manager,
    )


    registry.register(
        ReadFileTool(
            workdir=workdir
        )
    )

    registry.register(
        EditFileTool(
            workdir=workdir
        )
    )

    registry.register(
        CreateFileTool(
            workdir=workdir
        )
    )

    registry.register(
        CreateJsonCopyTool(
            workdir=workdir
        )
    )

    registry.register(
        ListDirectoryTool(
            workdir=workdir
        )
    )

    registry.register(
        ListSkillsTool(
            skills_root=PACKAGE_SKILLS_ROOT,
        )
    )

    registry.register(
        LoadSkillTool(
            skills_root=PACKAGE_SKILLS_ROOT,
        )
    )

    if cmo_lua_services is not None:
        registry.register(
            GenerateCmoLuaTool(
                scenario_workflow=(
                    cmo_lua_services.scenario_workflow
                ),
                workdir=workdir,
            )
        )
        registry.register(
            QueryCmoDatabaseTool(
                repository=cmo_lua_services.database_repository,
            )
        )
    artifact_store = RunArtifactStore(
        runs_dir=workdir / "runs",
    )

    job_config = CmoJobConfig(
        config_path=cmo_config_path,
    )

    # 第一轮真实接入暂时不主动按进程名清理
    # Command.exe 和 Launcher.exe，避免误杀用户
    # 手工打开的 CMO。
    #
    # 超时时仍会根据 CmoBatchRunner 的 PID
    # 终止其进程树。
    process_runner = CmoProcessRunner(
        runner_path=cmo_runner_path,
        cleanup_process_names=(),
    )

    cmo_runner = CmoRunner(
        config_path=cmo_config_path,
        job_config=job_config,
        process_runner=process_runner,
        artifact_store=artifact_store,
    )

    registry.register(
        ExecuteCmoTool(
            cmo_runner=cmo_runner,
        )
    )

    return registry
