"""
交互式聊天命令。

该模块负责：

1. 从终端读取用户输入；
2. 维护 Anthropic 格式的聊天历史；
3. 将用户输入同步到 TerminalDisplay；
4. 在 Agent 执行期间启动 Rich 动态显示；
5. 调用 AgentLoop 完成模型和工具交互；
6. 正确处理退出、中断和运行异常。

本模块只负责终端交互，不创建 LLM、工具、Hook
或其他底层组件。
"""

from __future__ import annotations

import os
from typing import Any

from cmo_lua_agent.cli.terminal_display import (
    TerminalDisplay,
)
from cmo_lua_agent.orchestration.agent_loop import (
    AgentLoop,
)


_EXIT_COMMANDS = {
    "q",
    "quit",
    "exit",
}


def run_chat(
    *,
    agent_loop: AgentLoop,
    display: TerminalDisplay,
) -> int:
    """
    启动交互式聊天循环。

    Args:
        agent_loop:
            已完成依赖组装的 AgentLoop。

        display:
            用于展示模型流式输出和工具执行过程的
            TerminalDisplay。

    Returns:
        程序退出码。正常退出返回 0。
    """
    history: list[dict[str, Any]] = []

    # 首次进入聊天模式时显示静态标题。
    # start 后立即 stop，可以留下完整标题和状态栏，
    # 又不会让 Rich Live 干扰普通 input()。
    display.start()
    display.stop()

    print()
    print("输入问题，输入 q 退出。")
    print()

    while True:
        query = _read_user_query()

        if query is None:
            return 0

        if query.lower() in _EXIT_COMMANDS:
            return 0

        if not query:
            continue

        history.append(
            {
                "role": "user",
                "content": query,
            }
        )

        # 用户消息没有经过 AgentLoop，因此由聊天入口
        # 主动加入终端显示状态。
        display.add_user_message(query)

        # 清理当前屏幕，然后根据完整 UIState 重绘。
        # 这样不会在每轮请求后重复堆叠旧的 Rich Live 区域。
        _clear_terminal()

        interrupted = False
        fallback_error: Exception | None = None

        try:
            display.start()

            # 模型文本已经通过 TEXT_DELTA 事件实时展示。
            # 不再打印 run() 返回的 final_text，
            # 否则最终回答会重复出现两次。
            agent_loop.run(history)

        except KeyboardInterrupt:
            interrupted = True
            display.mark_interrupted()

        except Exception as exc:
            # AgentLoop 正常情况下已经发出 AGENT_FAILED，
            # TerminalDisplay 会展示错误。
            #
            # 保存异常只是为了在显示层失效时提供降级输出。
            fallback_error = exc

        finally:
            # 无论模型调用、工具执行还是终端中断，
            # 都必须停止 Rich Live，恢复光标和终端状态。
            display.stop()

        if interrupted:
            print()
            print("当前任务已中断，可以继续输入。")
            print()
            continue

        if (
            fallback_error is not None
            and display.state.last_error is None
        ):
            print()
            print(
                "Agent 执行失败："
                f"{type(fallback_error).__name__}: "
                f"{fallback_error}"
            )
            print()

        if display.last_display_error:
            print()
            print(
                "终端显示发生异常："
                f"{display.last_display_error}"
            )
            print()


def _read_user_query() -> str | None:
    """
    从终端读取一条用户输入。

    Returns:
        去除首尾空格后的用户输入；
        收到 EOF 或在输入阶段按 Ctrl+C 时返回 None。
    """
    try:
        query = input(
            "\033[36m"
            "  cmo 用户输入（q 退出） >> "
            "\033[0m"
        )
    except (EOFError, KeyboardInterrupt):
        print()
        return None

    return query.strip()


def _clear_terminal() -> None:
    """
    清理当前终端屏幕。

    Rich Live 每次停止后会保留最终渲染结果。
    下一轮启动前清屏，再依据 UIState 重绘全部历史，
    可以避免相同内容重复堆叠。
    """
    command = (
        "cls"
        if os.name == "nt"
        else "clear"
    )

    exit_code = os.system(command)

    if exit_code != 0:
        # 某些 IDE 内置终端不支持 cls/clear。
        # 此时使用 ANSI 转义序列作为降级方案。
        print(
            "\033[2J\033[H",
            end="",
            flush=True,
        )