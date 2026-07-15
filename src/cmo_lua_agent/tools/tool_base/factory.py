"""
工具注册表构建模块。

该模块负责创建 ToolRegistry，并根据当前配置注册程序需要的工具。
具体工具的实现位于各自模块中，Agent Loop 不直接依赖具体工具。

当前使用显式注册，便于阅读、测试和依赖注入。
后续工具数量增多时，可以根据配置、Agent 角色或 toolset
选择性注册工具，但不建议过早加入自动扫描和模块自注册。
"""

from __future__ import annotations

from pathlib import Path

from cmo_lua_agent.hooks.manager import HookManager

from cmo_lua_agent.tools.ReadFileTool import ReadFileTool
from cmo_lua_agent.tools.tool_base.registry import ToolRegistry


def build_tool_registry(
    *,
    workdir: Path,
    hook_manager: HookManager | None = None,
) -> ToolRegistry:
    """
    创建并返回当前程序使用的工具注册表。

    workdir:
        工具允许操作的工作目录。

    hook_manager:
        可选 HookManager。
        没有 Hook 时可以传 None。
    """
    registry = ToolRegistry(
        hook_manager=hook_manager,
    )

    registry.register(
        ReadFileTool(
            workdir=workdir,
        )
    )

    ####通过 toolset 决定给不同 Agent 看哪些工具。

    # 后续可以依次添加：
    #
    # registry.register(
    #     ReadJsonTool(workdir=workdir)
    # )
    #
    # registry.register(
    #     LoadSkillTool(skill_dir=skill_dir)
    # )
    #
    # registry.register(
    #     WriteLuaTool(runs_dir=runs_dir)
    # )
    #
    # registry.register(
    #     ExecuteCmoTool(executor=cmo_executor)
    # )
    #
    # registry.register(
    #     QueryCmoStateTool(
    #         state_reader=cmo_state_reader
    #     )
    # )

    return registry