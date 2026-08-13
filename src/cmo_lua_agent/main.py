#!/usr/bin/env python3
"""
程序命令行入口，也是整个应用的“依赖组装入口（Composition Root）”。

从系统架构角度看，这个文件最重要的职责不是实现业务，而是“把系统接起来”：

    命令行参数
        ↓
    配置加载
        ↓
    根据运行模式创建所需组件
        ↓
    连接 LLM / Hook / 权限 / ToolRegistry / UI / AgentLoop
        ↓
    启动 chat 或 run 两条顶层流程

因此这里应该出现“创建对象、选择实现、连接依赖”的代码，
而不应该出现具体的 LLM 请求、工具执行、JSON 解析、Lua 生成、CMO 执行等业务细节。

系统目前有两条正式入口：
1. ``chat``：启动交互式 Agent，由 AgentLoop 驱动 LLM → 工具 → 结果回填的循环；
2. ``run``：直接执行一次确定性的 JSON → Lua 场景工作流，不经过聊天 Agent。

``--profile`` 只用于缩小 chat 模式下可用的工具和服务范围，便于隔离调试。
它不是不同“人格”，所有 profile 都从同一个核心 System Prompt 派生。
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
from cmo_lua_agent.llm.json_client import ClaudeJsonClient
from cmo_lua_agent.agents.context_summary_agent import ContextSummaryAgent
from cmo_lua_agent.llm_config import load_config
from cmo_lua_agent.orchestration.agent_loop import (
    AgentLoop,
)
from cmo_lua_agent.orchestration.chat_session_store import (
    ChatSessionStore,
)
from cmo_lua_agent.orchestration.context_manager import ContextManager
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


# System Prompt 在这里承担的是“顶层行为策略”角色。
# 具体工具怎么执行由 Tool 层负责；这里约束的是 Agent 应该何时调用工具、
# 哪些事实必须通过工具核验，以及训练 / Campaign 等高风险流程应遵循什么边界。
MAIN_SYSTEM_PROMPT = """你是 CMO Lua Generate 系统的主 Agent。你要理解用户目标，选择最小必要工具持续执行，直到给出真实、可核验的结果。

通用规则：
1. 需要仓库事实时先调用 search_workspace 定位定义和调用，再用 read_file 分页精读；列目录才使用 list_directory。不得访问任何组成部分以点号开头的隐藏路径。
2. 工具结果是事实来源；不得假装调用成功。失败后根据结构化错误换参数、换工具或说明缺少的信息，不要原样重复失败调用。
3. 普通聊天中的文件写入由写工具统一发起一次确认；调用前说明目标文件和影响，不要在对话中再增加一次重复确认。精确替换失败后重新读取，不得猜测。
4. 不为展示能力而调用工具；能直接回答的常识问题直接回答。

场景与 CMO：
1. 用户明确提供 ScenarioIR JSON 并要求生成时调用 generate_cmo_lua；只有需要规则或模板时才加载 Skill。平台、武器、挂载或 DBID 存在歧义时可用 query_cmo_database 核验，但业务选择仍由用户确认。
2. 只有用户明确要求仿真、或已经启动 Training/Campaign 自动流程时才执行 CMO。不要重复启动已经存在的 Worker，不要覆盖已有 Artifact。

持久化训练：
1. 用户给出训练输入、目标和代数并要求启动时，直接调用 start_training；启动请求视为持续授权本次完整训练、CMO、每代 Phase 7、结束后统一 Phase 8 以及后台恢复，不逐代或逐工具确认。
2. 进度问题调用 inspect_training，暂停、恢复、停止才调用 control_training。以 state、journal 和 Artifact 等持久化状态为准，不凭聊天记忆猜测阶段。
3. 训练故障由 RecoveryRouter 区分重试、现有业务修复和 Python Code Repair。CodeRepairAgent 只能在外层 Harness 的快照、VerificationGate、失败 action reconcile、Git commit/push 约束下修改 src/scripts/tests；主 Agent 不直接冒充修复成功。

完成时用中文简明说明实际结果、关键路径和仍存在的缺口。"""

STANDARD_DEBUG_APPENDIX = """

当前是 standard 隔离调试：只使用普通工作区、场景生成、数据库查询和单次 CMO 工具，不启动 Training 或手动 Campaign。"""

TRAINING_DEBUG_APPENDIX = """

当前是 training 隔离调试：只使用持久化 Training 高层工具；不得绕过 TrainingRunner 直接操作 Campaign 或 CMO。"""

CAMPAIGN_DEBUG_APPENDIX = """

当前是 campaign 隔离调试：只使用 Campaign 高层工具，遵守既有 preview、execute、inspect、control 和 reconcile 状态机。"""


def system_prompt_for_profile(profile: str) -> str:
    """
    为指定调试 profile 生成最终 System Prompt。

    设计要点：
    profile 不复制一份完整 Prompt，而是在统一主 Prompt 后追加“能力边界”。
    这样可以避免 standard / training / campaign 三套 Prompt 长期演化后彼此漂移。
    """

    appendices = {
        "all": "",
        "standard": STANDARD_DEBUG_APPENDIX,
        "training": TRAINING_DEBUG_APPENDIX,
        "campaign": CAMPAIGN_DEBUG_APPENDIX,
    }
    try:
        return MAIN_SYSTEM_PROMPT + appendices[profile]
    except KeyError as exc:
        raise ValueError(f"未知的聊天配置范围：{profile}") from exc


def _campaign_receipt_persister(service: object):
    """
    为 Campaign 的“代执行授权”创建专用持久化函数。

    这里不是把所有权限回执都落盘，而是只持久化
    ``execute_evolution_generation`` 这一类执行授权。
    这样可以把“普通一次性审批”和“可跨步骤复用的持续授权”区分开。
    """

    def persist(receipt: object, context: dict[str, Any]) -> str:
        tool = context.get("tool")
        # 只有真正执行一代 Campaign 的工具需要把授权持久化，
        # 其它工具仍保持普通的一次性审批语义。
        if getattr(tool, "name", None) == "execute_evolution_generation":
            return service.persist_permission_grant(receipt, context)
        return str(getattr(receipt, "receipt_id"))

    return persist


def build_parser() -> argparse.ArgumentParser:
    """
    定义程序对外暴露的命令行接口。

    这里体现了最顶层的产品边界：
    - ``chat``：进入 Agent 交互模式；
    - ``run``：进入确定性场景工作流。

    参数解析本身只负责把用户输入转换成结构化参数，
    不在这里执行任何业务。
    """
    parser = argparse.ArgumentParser(
        description=(
            "CMO Lua 生成与修复 Agent"
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
        choices=("all", "standard", "campaign", "training"),
        default="all",
        help="聊天工具范围；默认 all 为完整主 Agent，其他值仅用于隔离调试",
    )
    session_group = chat_parser.add_mutually_exclusive_group()
    session_group.add_argument(
        "--resume",
        action="store_true",
        help="恢复最近活动会话；默认会新建空白会话",
    )
    session_group.add_argument(
        "--session",
        metavar="SESSION_ID",
        help="恢复指定历史会话；可先在聊天中用 :sessions 查看 ID",
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
    从 LLM 配置中提取模型名称，供终端 UI 展示。

    这是一个小型“适配层”：上游配置对象可能使用 ``model_id``、``model``
    或 ``model_name``，这里统一收敛成一个字符串，避免 UI 层了解配置结构差异。
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
    profile: str = "all",
) -> tuple[AgentLoop, TerminalDisplay]:
    """
    组装 chat 模式需要的完整运行时。

    这是本文件最核心的“依赖注入 / 依赖组装”函数。
    它不实现任何一个组件的内部逻辑，只决定：

        创建哪些组件
            ↓
        哪个组件依赖哪个组件
            ↓
        当前 profile 应暴露哪些能力

    大致依赖关系：

        ClaudeClient ─────────────────────┐
                                          │
        UIState → TerminalDisplay         │
                    ↑                     │
                    │ pause/resume        │
        PermissionHook ← TerminalApprover │
              ↓                           │
        HookManager                       │
              ↓                           │
        ToolRegistry ← 各类业务 Service   │
              ↓                           │
        AgentLoop ← ContextManager ←──────┘
              ↓
        event_handler → TerminalDisplay.handle

    返回：
        ``AgentLoop``：负责真正运行 Agent 控制循环；
        ``TerminalDisplay``：负责终端显示与审批交互。
    """
    # 1. 决策能力：把配置对象转换成真正可调用的 LLM Client。
    llm_client = ClaudeClient(
        config.llm
    )

    # 2. 展示状态与终端 UI 独立于 AgentLoop。
    # AgentLoop 只发事件，不直接 print，从而避免“核心控制流”和“界面”耦合。
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
    )

    terminal_display = TerminalDisplay(
        state=ui_state,
    )

    # 3. HookManager 是工具执行生命周期的扩展点。
    # 权限、审计等横切逻辑通过 Hook 接入，而不是写死在 AgentLoop / Tool 内部。
    hook_manager = HookManager()

    # 4. 根据 profile 按需创建高层业务服务。
    # 这里做“能力裁剪”：没有创建的服务后面就不会进入 ToolRegistry，
    # 从结构上避免 standard 调试模式意外触发 Training / Campaign。
    evolution_service = None
    training_service = None
    if profile in {"all", "campaign"}:
        evolution_service = create_production_evolution_campaign_service(
            project_root=workdir,
            app_config=config,
            llm_client=llm_client,
        )
    if profile in {"all", "training"}:
        training_service = TrainingService(project_root=workdir)
    if profile not in {"all", "standard", "campaign", "training"}:
        raise ValueError(f"未知的聊天配置范围：{profile}")

    # 5. 把人工审批包装成 PermissionHook 注册到统一 Hook 生命周期。
    # TerminalApprover 在等待用户输入时会暂停动态终端显示，审批结束后再恢复，
    # 这说明“审批策略”和“终端表现”虽然协作，但仍通过接口解耦。
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

    # 6. 普通场景工具需要一套确定性 JSON → Lua 应用服务。
    # create_application() 不是“启动程序”，而是下一层的依赖组装工厂：
    # 它会把场景解析、数据库解析、Lua 生成等服务创建并连接起来。
    application = create_application(workdir) if profile in {"all", "standard"} else None
    cmo_lua_services = (
        create_tool_services(application)
        if application is not None
        else None
    )

    # 7. ToolRegistry 是 LLM 与真实系统能力之间的“能力目录”。
    # AgentLoop 不需要知道每个 Tool 如何构造，只依赖统一的 Registry 查找和执行工具。
    tool_registry = build_tool_registry(
        workdir=workdir,
        hook_manager=hook_manager,
        cmo_lua_services=cmo_lua_services,
        chat_profile=profile,
        evolution_campaign_service=evolution_service,
        training_service=training_service,
    )

    # 8. 最后创建控制中枢 AgentLoop。
    # 它依赖的 LLM、工具、Prompt、上下文管理和事件输出都从外部注入，
    # 因而 AgentLoop 本身可以专注于“LLM → tool_use → tool_result → 下一轮”的循环。
    agent_loop = AgentLoop(
        llm_client=llm_client,
        tool_registry=tool_registry,
        system_prompt=system_prompt_for_profile(profile),
        event_handler=terminal_display.handle,
        context_manager=ContextManager(
            context_window_tokens=getattr(
                config.llm, "context_window_tokens", 1_000_000
            ),
            summarizer=ContextSummaryAgent(ClaudeJsonClient(llm_client)),
        ),
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
    执行一次确定性的 JSON → Lua 场景工作流。

    与 ``chat`` 的区别是：这里没有 AgentLoop，也不让 LLM 自主决定下一步。
    ``main.py`` 只完成三件事：
    1. 创建确定性场景应用；
    2. 读取用户已经确认的平台解析结果；
    3. 把参数交给 ``run_scenario_workflow``。

    JSON 校验、数据库解析、Lua 生成和 CMO 执行仍属于下层工作流。
    """
    # run 模式复用同一套应用工厂，但只拿其中的 scenario_workflow。
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

    # 平台 / DBID 等存在歧义时，自动化流程不能自行猜测。
    # resolution_file 表示“用户已经确认过的业务决策”，由入口层加载后注入工作流。
    platform_resolutions: Mapping[str, Any] | None = None
    if resolution_file is not None:
        try:
            payload = json.loads(
                Path(resolution_file).read_text(encoding="utf-8")
            )
            if not isinstance(payload, dict):
                raise ValueError("平台决策文件的根节点必须是 JSON 对象")
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
    程序主入口，也是最顶层的命令分发器。

    它只根据 ``args.command`` 选择 chat 或 run，
    不参与两条流程内部的具体业务。
    """
    parser = build_parser()
    args = parser.parse_args()

    workdir = Path(args.workdir).resolve()

    # chat：构造完整 Agent Runtime，再交给 run_chat 管理交互式会话。
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

        # all 是默认生产能力集合；非 all profile 只在隔离调试时显式传入。
        build_kwargs = {"config": config, "workdir": workdir}
        if args.profile != "all":
            build_kwargs["profile"] = args.profile
        agent_loop, terminal_display = build_chat_components(**build_kwargs)

        return run_chat(
            agent_loop=agent_loop,
            display=terminal_display,
            session_store=ChatSessionStore(workdir),
            resume=args.resume,
            session_id=args.session,
        )

    # run：绕过聊天 Agent，直接执行确定性场景工作流。
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


# Python 进程真正的边界：把 main() 返回的状态码交给操作系统。
# 这样 CLI 调用者、脚本或 CI 都可以通过退出码判断执行结果。
if __name__ == "__main__":
    raise SystemExit(
        main()
    )
