#!/usr/bin/env python3
"""
程序命令行入口。

该模块负责：
1. 解析用户输入的命令行参数；
2. 加载项目配置；
3. 根据运行模式组装 LLM、Hook、工具注册表、
   TerminalDisplay 和 AgentLoop；
4. 启动交互式聊天或自动化场景处理流程；
5. 将最终退出状态返回给操作系统。

本文件属于项目的依赖组装入口，可以创建并连接各个组件，
但不应包含具体的 LLM 调用、工具执行、JSON 解析、
CMO 脚本执行或终端审批实现。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from cmo_lua_agent.cli.chat import run_chat
from cmo_lua_agent.cli.terminal_approval import (
    TerminalApprover,
)
from cmo_lua_agent.cli.terminal_display import (
    TerminalDisplay,
)
from cmo_lua_agent.hooks.manager import HookManager
from cmo_lua_agent.hooks.permission_hook import (
    PermissionHook,
)
from cmo_lua_agent.llm.client import ClaudeClient
from cmo_lua_agent.llm_config import load_config
from cmo_lua_agent.orchestration.agent_loop import (
    AgentLoop,
)
from cmo_lua_agent.orchestration.ui_state import (
    UIState,
)
from cmo_lua_agent.tools.tool_base.factory import (
    build_tool_registry,
)


CHAT_SYSTEM_PROMPT = """
你是一个 CMO Lua Agent。

当前处于交互式开发和调试模式。
你可以根据用户需求调用已提供的工具。

当需要获取真实文件内容或执行操作时，应调用工具，
不得假装已经执行工具。

工具执行失败时，应根据工具返回的错误信息判断下一步，
不得声称失败操作已经成功。
""".strip()


def build_parser() -> argparse.ArgumentParser:
    """
    创建命令行参数解析器。
    """
    parser = argparse.ArgumentParser(
        description=(
            "CMO Lua generation and repair agent"
        )
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    subparsers.add_parser(
        "chat",
        help="启动交互式 Agent",
    )

    run_parser = subparsers.add_parser(
        "run",
        help="从 JSON 生成并执行 CMO Lua",
    )

    run_parser.add_argument(
        "input",
        type=Path,
        help="输入场景 JSON 文件",
    )

    return parser


def resolve_model_name(
    llm_config: Any,
) -> str:
    """
    从 LLM 配置中提取模型名称。

    兼容 model_id、model 和 model_name 三种常见字段名，
    避免终端显示层依赖某一种具体配置结构。
    """
    candidate_fields = (
        "model_id",
        "model",
        "model_name",
    )

    for field_name in candidate_fields:
        value = getattr(
            llm_config,
            field_name,
            None,
        )

        if value:
            return str(value)

    return "Claude"


def build_chat_components(
    *,
    config: Any,
    workdir: Path,
) -> tuple[AgentLoop, TerminalDisplay]:
    """
    创建交互式聊天模式需要的全部组件。

    组装顺序：

        LLM 配置
            → ClaudeClient
            → HookManager
            → PermissionHook
            → ToolRegistry
            → UIState
            → TerminalDisplay
            → AgentLoop

    chat 模式允许通过终端进行人工审批。

    Returns:
        包含 AgentLoop 和 TerminalDisplay 的元组。
    """
    llm_client = ClaudeClient(
        config.llm
    )

    hook_manager = HookManager()

    hook_manager.register(
        PermissionHook(
            approval_function=TerminalApprover(),
        )
    )

    tool_registry = build_tool_registry(
        workdir=workdir,
        hook_manager=hook_manager,
    )

    ui_state = UIState(
        agent_name="军事CMO Lua 自动化Agent ",
        version="0.1.0",
        model_name=resolve_model_name(
            config.llm
        ),
        workdir=str(
            workdir.resolve()
        ),
        mode="chat",
        max_turns=10,
        
    )

    terminal_display = TerminalDisplay(
        state=ui_state,
    )

    agent_loop = AgentLoop(
        llm_client=llm_client,
        tool_registry=tool_registry,
        system_prompt=CHAT_SYSTEM_PROMPT,
        max_turns=10,
        event_handler=terminal_display.handle,
    )

    return (
        agent_loop,
        terminal_display,
    )


def run_scenario(
    *,
    input_path: Path,
    config: Any,
    workdir: Path,
) -> int:
    """
    执行 JSON 场景自动化处理流程。

    当前只是占位实现。
    后续应交给 ScenarioWorkflow，而不是在 main.py 中
    直接编写 JSON、Lua 和 CMO 处理逻辑。
    """
    resolved_path = input_path.resolve()

    if not resolved_path.exists():
        print(
            f"输入文件不存在：{resolved_path}"
        )
        return 2

    if not resolved_path.is_file():
        print(
            f"输入路径不是文件：{resolved_path}"
        )
        return 2

    print(
        f"待处理场景：{resolved_path}"
    )
    print(
        "ScenarioWorkflow 尚未实现。"
    )

    return 0


def main() -> int:
    """
    程序主入口。
    """
    parser = build_parser()
    args = parser.parse_args()

    try:
        config = load_config()
    except Exception as exc:
        print(
            "配置加载失败："
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    workdir = Path.cwd()

    if args.command == "chat":
        (
            agent_loop,
            terminal_display,
        ) = build_chat_components(
            config=config,
            workdir=workdir,
        )

        return run_chat(
            agent_loop=agent_loop,
            display=terminal_display,
        )

    if args.command == "run":
        return run_scenario(
            input_path=args.input,
            config=config,
            workdir=workdir,
        )

    parser.error(
        f"未知命令：{args.command}"
    )

    return 2


if __name__ == "__main__":
    raise SystemExit(
        main()
    )