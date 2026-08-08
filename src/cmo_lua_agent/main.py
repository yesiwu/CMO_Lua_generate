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


main.py
├── chat 模式
│   └── InteractiveScenarioService
│       ├── 使用已积累的策略经验
│       ├── 根据用户要求批量生成 Lua
│       ├── 执行、评分和展示结果
│       └── 允许人工审批和调整
│
└── auto 模式
    └── OptimizationWorkflow
        ├── CandidateGenerator
        ├── ScenarioWorkflow
        ├── CombatEvaluator
        ├── CandidateSelector
        ├── ExperienceStore
        └── OptimizationController
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
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
from cmo_lua_agent.orchestration.chat_session_store import (
    ChatSessionStore,
)
from cmo_lua_agent.orchestration.ui_state import (
    UIState,
)
from cmo_lua_agent.tools.tool_base.factory import (
    build_tool_registry,
)
from cmo_lua_agent.evolution.production_service import (
    create_production_evolution_campaign_service,
)
from cmo_lua_agent.training.service import TrainingService

from cmo_lua_agent.bootstrap import (
    create_application,
    create_tool_services,
)
from cmo_lua_agent.cli.run_scenario import (
    run_scenario_workflow,
)


CHAT_SYSTEM_PROMPT = """
你是一个 CMO Lua Agent。

当前处于交互式开发和调试模式。
你可以根据用户需求调用已提供的工具。

当需要获取真实文件内容或执行操作时，应调用工具，
不得假装已经执行工具。

工具执行失败时，应根据工具返回的错误信息判断下一步，
不得声称失败操作已经成功。

读取普通文件使用 read_file；查看目录内容使用 list_directory。
如果工具错误中给出 suggested_tool，应优先调用该建议工具，
不要重复相同的失败调用。

修改文件必须遵守：
- 先用 read_file 读取目标文件，再向用户逐项说明路径、精确替换内容和预期影响；
- 必须等待用户明确同意后，才调用 edit_file；该工具会进行第二次终端人工审批；
- 只能使用 edit_file 的精确 replacements，不得尝试通过其他工具、脚本或命令绕过审批修改文件；
- 替换失败时不得猜测重试，应读取当前文件并重新向用户说明差异。
- 对 JSON 场景文件的首次修复，默认使用 create_json_copy，并用 JSON Pointer 指向每个字段；
  绝不通过文本计数替换 JSON，也不得改动汇总显示 key。用户只回答“同意”表示允许创建副本，
  不表示允许改原文件。只有用户明确输入“修改原文件”时才允许 edit_file 指向原文件；
  后续修复应针对 create_json_copy 返回的副本使用 edit_file。所有写入工具都需要用户同意和终端人工审批。

处理 JSON 转 Lua 请求时必须遵守：
- 用户没有提供明确的 JSON 路径时，直接询问路径；不得列出工作区、示例目录，
  也不得猜测要使用哪个 JSON 文件。
- 用户提供 JSON 路径时，优先调用 generate_cmo_lua；不必先浏览 Skill、模板或 CMOLua-main。
- 只有需要规则、模板或报错解释时，才调用 list_skills 或 load_skill。
- load_skill 返回 linked_files 后，只能以其中列出的相对 file_path 再次调用 load_skill；
  不得用 read_file 猜测 CMOLua-main 中的路径。
- 成功获得 lua_path 后立即总结。只有用户明确要求仿真时，才调用 execute_cmo。
- 若 generate_cmo_lua 返回 platform_resolution_required 或
  database.platform_resolution_required：展示工具返回的候选平台，请用户明确确认每个单位的
  category 与 dbid；在用户确认前不得调用 generate_cmo_lua 的 platform_resolutions，
  更不得自行选择舰船、飞机或其他平台。
- 用户确认后才可用其原样确认的值调用 generate_cmo_lua(platform_resolutions=...)；
  不得修改源 JSON，也不得补充用户未确认的单位。
- 当生成返回 weapon_not_found、weapon_name_mismatch、loadout_not_found、
  loadout_mismatch 或平台歧义时，优先调用 query_cmo_database 核验事实。
   若需要某架飞机可用的挂载方案，调用
   query_cmo_database(operation="loadouts_for_aircraft", aircraft_dbid=...)。
  若需要核验某个挂载包含哪些武器，调用
  query_cmo_database(operation="loadout_weapons", loadout_id=...)。
  查询结果仅用于向用户说明候选项；武器、挂载、平台或 DBID 的选择仍须用户明确确认。
""".strip()


def _campaign_receipt_persister(service: object):
    """Persist generation grants only for the generation execution tool."""

    def persist(receipt: object, context: dict[str, Any]) -> str:
        tool = context.get("tool")
        if getattr(tool, "name", None) == "execute_evolution_generation":
            return service.persist_permission_grant(receipt, context)
        return str(getattr(receipt, "receipt_id"))

    return persist


def build_parser() -> argparse.ArgumentParser:
    """
    创建命令行参数解析器。
    """
    parser = argparse.ArgumentParser(
        description=(
            "CMO Lua generation and repair agent"
        )
    )
    parser.add_argument(
        "--workdir",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="项目工作目录；默认使用项目根目录",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    chat_parser = subparsers.add_parser(
        "chat",
        help="启动交互式 Agent",
    )
    chat_parser.add_argument(
        "--profile",
        choices=("standard", "campaign", "training"),
        default="standard",
        help="Chat tool profile.",
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
    run_parser.add_argument(
        "--runs-root",
        type=Path,
        default=Path("runs"),
        help="运行产物保存目录，默认使用 runs",
    )

    run_parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="指定本次运行 ID；省略时自动生成",
    )
    run_parser.add_argument(
        "--resolution-file",
        type=Path,
        default=None,
        help="用户确认的平台决策 JSON 文件；自动化模式不会自行猜测 DBID",
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
    profile: str = "standard",
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
        max_turns=12,
        
    )

    terminal_display = TerminalDisplay(
        state=ui_state,
    )

    hook_manager = HookManager()

    evolution_service = None
    training_service = None
    if profile == "campaign":
        evolution_service = create_production_evolution_campaign_service(
            project_root=workdir,
            app_config=config,
            llm_client=llm_client,
        )
    elif profile == "training":
        training_service = TrainingService(project_root=workdir)
    elif profile != "standard":
        raise ValueError("unknown_chat_profile")

    hook_manager.register(
        PermissionHook(
            approval_function=TerminalApprover(
                pause=terminal_display.stop,
                resume=terminal_display.start,
            ),
            receipt_persister=(
                _campaign_receipt_persister(evolution_service)
                if evolution_service is not None
                else None
            ),
        )
    )

    application = create_application(workdir) if profile == "standard" else None
    #create_application() 不是“启动程序”，而是一个依赖组装工厂。它的作用是把运行 JSON→Lua 所需的对象一次性创建并连接起来。
    cmo_lua_services = (
        create_tool_services(application)
        if application is not None
        else None
    )

    tool_registry = build_tool_registry(
        workdir=workdir,
        hook_manager=hook_manager,
        cmo_lua_services=cmo_lua_services,
        chat_profile=profile,
        evolution_campaign_service=evolution_service,
        training_service=training_service,
    )

    agent_loop = AgentLoop(
        llm_client=llm_client,
        tool_registry=tool_registry,
        system_prompt=CHAT_SYSTEM_PROMPT,
        max_turns=12,
        event_handler=terminal_display.handle,
    )

    return (
        agent_loop,
        terminal_display,
    )


def run_scenario(
    *,
    input_path: Path,
    workdir: Path,
    runs_root: Path,
    run_id: str | None,
    resolution_file: Path | None = None,
) -> int:
    """
    执行 JSON → Lua 场景工作流。

    main.py 只负责装配和调用，不包含具体的 JSON 校验、
    数据库解析或 Lua 生成实现。
    """
    try:
        application = create_application(
            workdir,
        )
    except Exception as exc:
        print(
            "CMO Lua 应用初始化失败："
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1

    platform_resolutions: Mapping[str, Any] | None = None
    if resolution_file is not None:
        try:
            payload = json.loads(
                Path(resolution_file).read_text(encoding="utf-8")
            )
            if not isinstance(payload, dict):
                raise ValueError("resolution-file 根节点必须是对象")
            platform_resolutions = payload.get("platform_resolutions", payload)
        except Exception as exc:
            print(f"平台决策文件无效：{type(exc).__name__}: {exc}", file=sys.stderr)
            return 2

    return run_scenario_workflow(
        workflow=application.scenario_workflow,
        source_path=input_path,
        runs_root=runs_root,
        run_id=run_id,
        platform_resolutions=platform_resolutions,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )


def main() -> int:
    """
    程序主入口。
    """
    parser = build_parser()
    args = parser.parse_args()

    workdir = Path(args.workdir).resolve()

    if args.command == "chat":
        try:
            config = load_config()
        except Exception as exc:
            print(
                "配置加载失败："
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            return 2

        build_kwargs = {"config": config, "workdir": workdir}
        if args.profile != "standard":
            build_kwargs["profile"] = args.profile
        agent_loop, terminal_display = build_chat_components(**build_kwargs)

        return run_chat(
            agent_loop=agent_loop,
            display=terminal_display,
            session_store=ChatSessionStore(workdir),
        )

    if args.command == "run":
        return run_scenario(
            input_path=args.input,
            workdir=workdir,
            runs_root=args.runs_root,
            run_id=args.run_id,
            resolution_file=args.resolution_file,
        )

    parser.error(
        f"未知命令：{args.command}"
    )

    return 2


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
