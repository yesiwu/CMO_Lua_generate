
"""
工具注册表构建模块。

该模块负责创建 ToolRegistry，并显式注册当前程序
允许 LLM 调用的所有工具。

具体工具逻辑位于各自的 *_tool.py 文件中；
AgentLoop 不直接依赖具体工具。
"""

from __future__ import annotations

from pathlib import Path

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
from cmo_lua_agent.tools.read_file_tool import (
    ReadFileTool,
)
from cmo_lua_agent.tools.tool_base.registry import (
    ToolRegistry,
)


DEFAULT_CMO_RUNNER_PATH = Path(
    r"D:\CMO\CmoBatchRunner\CmoBatchRunner.exe"
)

DEFAULT_CMO_CONFIG_PATH = Path(
    r"D:\pythonproject\CMO_Lua_generate\json_data\tot-three.json"
    
)


def build_tool_registry(
    *,
    workdir: Path,
    hook_manager: HookManager,
    cmo_runner_path: Path = (
        DEFAULT_CMO_RUNNER_PATH
    ),
    cmo_config_path: Path = (
        DEFAULT_CMO_CONFIG_PATH
    ),
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

    Returns:
        完成注册的 ToolRegistry。
    """
    workdir = Path(
        workdir
    ).resolve()

    cmo_runner_path = Path(
        cmo_runner_path
    ).resolve()

    cmo_config_path = Path(
        cmo_config_path
    ).resolve()

    registry = ToolRegistry(
        hook_manager=hook_manager,
    )


    registry.register(
        ReadFileTool(
            workdir=workdir
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