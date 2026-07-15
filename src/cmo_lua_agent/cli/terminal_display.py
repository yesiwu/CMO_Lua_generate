"""
Rich 交互式终端显示。  动态刷新。

该模块负责将 AgentEvent 转换为 UIState，并使用 Rich
动态渲染 Agent 的运行过程，包括：

1. Agent 标题、模型名称和工作目录；
2. 用户输入和模型流式回答；
3. 工具调用参数、执行状态和耗时；
4. 模型等待动画和当前活动；
5. Agent 错误信息；
6. 当前轮次、Token 使用量和状态栏。

本模块只负责展示，不执行工具、不进行权限判断，
也不决定 Agent 是否继续运行。

显示层发生异常时，不应影响 Agent 主流程。
"""

from __future__ import annotations

import json
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.rule import Rule
from rich.spinner import Spinner
from rich.text import Text
from rich.table import Table


from cmo_lua_agent.orchestration.events import (
    AgentEvent,
    AgentEventType,
)
from cmo_lua_agent.orchestration.ui_state import (
    ToolStatus,
    TranscriptItem,
    TranscriptItemType,
    UIState,
)


# 工具参数中出现这些字段时，终端中不直接展示真实内容。
_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "password",
    "secret",
    "token",
    "access_token",
    "refresh_token",
}


class TerminalDisplay:
    """
    基于 Rich Live 的 Agent 终端显示器。

    TerminalDisplay 接收 AgentEvent，更新 UIState，
    然后重新渲染整个终端内容。

    该类可以被直接作为 AgentLoop 的 event_handler：

        display = TerminalDisplay(state)
        agent_loop = AgentLoop(
            ...,
            event_handler=display.handle,
        )

    在进入交互循环前调用 start()，退出时调用 stop()。
    """

    def __init__(
        self,
        state: UIState,
        console: Console | None = None,
        *,
        refresh_per_second: int = 10,
        max_argument_length: int = 120,
        max_result_length: int = 300,
    ) -> None:
        """
        初始化终端显示器。

        Args:
            state:
                终端界面状态。

            console:
                Rich Console。测试时可以传入输出到 StringIO
                的 Console。

            refresh_per_second:
                Rich Live 每秒刷新次数。

            max_argument_length:
                单个工具参数在终端中的最大显示长度。

            max_result_length:
                工具结果在终端中的最大显示长度。
        """
        if refresh_per_second <= 0:
            raise ValueError(
                "refresh_per_second 必须大于 0"
            )

        if max_argument_length <= 0:
            raise ValueError(
                "max_argument_length 必须大于 0"
            )

        if max_result_length <= 0:
            raise ValueError(
                "max_result_length 必须大于 0"
            )

        self._state = state
        self._console = console or Console()

        self._refresh_per_second = refresh_per_second
        self._max_argument_length = max_argument_length
        self._max_result_length = max_result_length

        self._live: Live | None = None
        self._started = False

        # 后续 AgentLoop 可能在异步线程中发事件，
        # 使用锁保护 UIState 和 Rich Live 更新。
        self._lock = threading.RLock()

        # 记录显示层自身的错误。
        # 显示错误不能向上传播并中断 AgentLoop。
        self._last_display_error: str | None = None

    @property
    def state(self) -> UIState:
        """
        返回当前 UIState。
        """
        return self._state

    @property
    def last_display_error(self) -> str | None:
        """
        返回最近一次显示层异常。
        """
        return self._last_display_error

    def start(self) -> None:
        """
        启动 Rich Live 动态终端。

        重复调用不会创建多个 Live 实例。
        """
        with self._lock:
            if self._started:
                return

            self._live = Live(
                self.render(),
                console=self._console,
                refresh_per_second=(
                    self._refresh_per_second
                ),
                auto_refresh=True,
                transient=False,
                screen=False,
                redirect_stdout=True,
                redirect_stderr=True,
            )

            self._live.start()
            self._started = True

    def stop(self) -> None:
        """
        停止 Rich Live，并恢复终端状态。

        即使停止过程中发生异常，也不向上传播。
        """
        with self._lock:
            if not self._started:
                return

            live = self._live

            self._live = None
            self._started = False

            if live is None:
                return

            try:
                live.update(
                    self.render(),
                    refresh=True,
                )
                live.stop()
            except Exception as exc:
                self._last_display_error = str(exc)

    def __enter__(self) -> "TerminalDisplay":
        """
        支持 with 语法启动终端显示。
        """
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> None:
        """
        离开 with 块时停止终端显示。
        """
        self.stop()

    def add_user_message(
        self,
        text: str,
    ) -> None:
        """
        将用户输入添加到终端对话记录。

        用户输入目前没有对应的 AgentEvent，
        因此由 InteractiveShell 或 chat.py 主动调用。
        """
        if not text:
            return

        with self._lock:
            self._state.add_user_message(text)
            self.refresh()

    def mark_interrupted(self) -> None:
        """
        标记当前 Agent 请求被用户中断。
        """
        with self._lock:
            self._state.interrupted = True
            self._state.is_running = False
            self._state.current_activity = None

            self._state.add_system_message(
                "当前任务已被用户中断"
            )

            self.refresh()

    def handle(
        self,
        event: AgentEvent,
    ) -> None:
        """
        处理一条 AgentEvent。

        该方法可以直接注入 AgentLoop。

        显示层异常会被记录，但不会继续向上传播，
        以避免 UI 问题导致 Agent 主流程停止。
        """
        try:
            with self._lock:
                self._apply_event(event)
                self.refresh()
        except Exception as exc:
            self._last_display_error = (
                f"{type(exc).__name__}: {exc}"
            )

    def refresh(self) -> None:
        """
        根据当前 UIState 刷新终端。

        如果 Live 尚未启动，只更新状态，不主动打印整页内容。
        """
        if not self._started:
            return

        if self._live is None:
            return

        try:
            self._live.update(
                self.render(),
                refresh=True,
            )
        except Exception as exc:
            self._last_display_error = (
                f"{type(exc).__name__}: {exc}"
            )

    def render(self) -> RenderableType:
        """
        将当前 UIState 渲染为一个 Rich Renderable。
        """
        renderables: list[RenderableType] = [
            self._render_header(),
        ]

        if self._state.transcript:
            renderables.append(
                self._render_transcript()
            )

        activity = self._render_activity()

        if activity is not None:
            renderables.append(activity)

        renderables.append(
            self._render_footer()
        )

        return Group(*renderables)

    def _apply_event(
        self,
        event: AgentEvent,
    ) -> None:
        """
        根据事件更新 UIState。
        """
        event_type = event.type
        data = event.data

        if event_type is AgentEventType.AGENT_STARTED:
            self._handle_agent_started(
                event
            )
            return

        if event_type is AgentEventType.LLM_STARTED:
            self._handle_llm_started(
                event
            )
            return

        if event_type is AgentEventType.TEXT_DELTA:
            self._handle_text_delta(
                event
            )
            return

        if event_type is AgentEventType.LLM_COMPLETED:
            self._handle_llm_completed(
                event
            )
            return

        if event_type is AgentEventType.TOOL_STARTED:
            self._handle_tool_started(
                event
            )
            return

        if event_type is AgentEventType.TOOL_COMPLETED:
            self._handle_tool_finished(
                event=event,
                success=True,
            )
            return

        if event_type is AgentEventType.TOOL_FAILED:
            self._handle_tool_finished(
                event=event,
                success=False,
            )
            return

        if event_type is AgentEventType.AGENT_COMPLETED:
            self._handle_agent_completed(
                event
            )
            return

        if event_type is AgentEventType.AGENT_FAILED:
            self._handle_agent_failed(
                event
            )
            return

        self._state.add_system_message(
            f"收到未知事件：{event_type}"
        )

    def _handle_agent_started(
        self,
        event: AgentEvent,
    ) -> None:
        """
        处理 Agent 开始事件。
        """
        data = event.data

        self._state.is_running = True
        self._state.interrupted = False
        self._state.last_error = None
        self._state.current_activity = (
            event.message or "正在处理请求"
        )

        self._state.current_turn = self._to_int(
            data.get("turn"),
            default=0,
        )

        self._state.max_turns = self._to_int(
            data.get("max_turns"),
            default=self._state.max_turns,
        )

        user_message = data.get(
            "user_message"
        )

        if (
            isinstance(user_message, str)
            and user_message
        ):
            self._state.add_user_message(
                user_message
            )

    def _handle_llm_started(
        self,
        event: AgentEvent,
    ) -> None:
        """
        处理开始调用模型事件。
        """
        data = event.data

        self._state.is_running = True
        self._state.current_turn = self._to_int(
            data.get("turn"),
            default=self._state.current_turn,
        )

        self._state.max_turns = self._to_int(
            data.get("max_turns"),
            default=self._state.max_turns,
        )

        self._state.current_activity = (
            event.message or "正在请求模型"
        )

    def _handle_text_delta(
        self,
        event: AgentEvent,
    ) -> None:
        """
        处理模型流式文本。
        """
        text = event.message

        if not text:
            raw_text = event.data.get("text")

            if isinstance(raw_text, str):
                text = raw_text

        if not text:
            return

        # 一旦收到正文，等待模型的 spinner 就停止显示。
        self._state.current_activity = None

        self._state.append_assistant_text(
            text
        )

    def _handle_llm_completed(
        self,
        event: AgentEvent,
    ) -> None:
        """
        处理本轮模型调用结束事件。
        """
        data = event.data

        self._state.finish_assistant_message()
        self._state.current_activity = None

        input_tokens = data.get(
            "input_tokens"
        )
        output_tokens = data.get(
            "output_tokens"
        )
        elapsed_seconds = data.get(
            "duration_seconds",
            data.get("elapsed_seconds"),
        )

        if isinstance(input_tokens, int):
            self._state.input_tokens = (
                input_tokens
            )

        if isinstance(output_tokens, int):
            self._state.output_tokens = (
                output_tokens
            )

        if isinstance(
            elapsed_seconds,
            (int, float),
        ):
            self._state.elapsed_seconds = float(
                elapsed_seconds
            )

    def _handle_tool_started(
        self,
        event: AgentEvent,
    ) -> None:
        """
        处理工具开始执行事件。
        """
        data = event.data

        tool_use_id = self._to_str(
            data.get("tool_use_id")
        )

        tool_name = self._to_str(
            data.get("tool_name")
        )

        arguments = data.get(
            "arguments",
            {},
        )

        if not isinstance(arguments, dict):
            arguments = {
                "value": arguments,
            }

        if not tool_use_id:
            tool_use_id = (
                f"unknown-{len(self._state.transcript)}"
            )

        if not tool_name:
            tool_name = "unknown_tool"

        self._state.finish_assistant_message()

        self._state.start_tool(
            tool_use_id=tool_use_id,
            tool_name=tool_name,
            arguments=arguments,
        )

        self._state.current_activity = (
            event.message
            or f"正在执行工具 {tool_name}"
        )

    def _handle_tool_finished(
        self,
        *,
        event: AgentEvent,
        success: bool,
    ) -> None:
        """
        处理工具执行成功或失败事件。
        """
        data = event.data

        tool_use_id = self._to_str(
            data.get("tool_use_id")
        )

        content = event.message

        if not content:
            raw_content = data.get(
                "content",
                ""
            )

            if isinstance(raw_content, str):
                content = raw_content
            else:
                content = str(raw_content)

        duration_seconds = data.get(
            "duration_seconds",
            0.0,
        )

        if not isinstance(
            duration_seconds,
            (int, float),
        ):
            duration_seconds = 0.0

        self._state.current_activity = None

        self._state.finish_tool(
            tool_use_id=tool_use_id,
            success=success,
            content=content,
            duration_seconds=float(
                duration_seconds
            ),
        )

    def _handle_agent_completed(
        self,
        event: AgentEvent,
    ) -> None:
        """
        处理 Agent 正常完成事件。
        """
        data = event.data

        self._state.finish_assistant_message()
        self._state.is_running = False
        self._state.current_activity = None

        elapsed_seconds = data.get(
            "duration_seconds",
            data.get("elapsed_seconds"),
        )

        if isinstance(
            elapsed_seconds,
            (int, float),
        ):
            self._state.elapsed_seconds = float(
                elapsed_seconds
            )

        # 不在这里添加 final_text。
        # 模型正文已经通过 TEXT_DELTA 写入 transcript，
        # 再添加一次会导致最终回答重复显示。

    def _handle_agent_failed(
        self,
        event: AgentEvent,
    ) -> None:
        """
        处理 Agent 执行失败事件。
        """
        self._state.finish_assistant_message()
        self._state.is_running = False
        self._state.current_activity = None

        error_message = (
            event.message
            or self._to_str(
                event.data.get(
                    "error_message"
                )
            )
            or "Agent 执行失败"
        )

        self._state.add_error(
            error_message
        )

    def _render_header(self) -> RenderableType:
        """
        渲染顶部品牌区。
        """
        title = Text()

        title.append(
            self._state.agent_name,
            style="bold magenta",
        )

        if self._state.version:
            title.append(
                f"  v{self._state.version}",
                style="dim",
            )

        details = Text()

        if self._state.model_name:
            details.append(
                self._state.model_name,
                style="bold",
            )

        if self._state.mode:
            if details.plain:
                details.append(
                    " · ",
                    style="dim",
                )

            details.append(
                self._state.mode,
                style="cyan",
            )

        workdir_text = Text(
            self._state.workdir,
            style="dim",
            overflow="ellipsis",
            no_wrap=True,
        )

        text_header = Group(
            Text(),
            title,
            details,
            workdir_text,
        )

        header_table = Table.grid(
            padding=(0, 3),
            expand=False,
        )

        header_table.add_column(
            vertical="middle",
            no_wrap=True,
        )

        header_table.add_column(
            vertical="middle",
        )

        header_table.add_row(
            self._render_brand_logo(),
            text_header,
        )

        return Group(
            header_table,
            Rule(style="dim"),
        )



    def _render_transcript(
        self,
    ) -> RenderableType:
        """
        渲染全部对话和工具记录。
        """
        renderables: list[RenderableType] = []

        for item in self._state.transcript:
            rendered = self._render_item(
                item
            )

            if rendered is not None:
                renderables.append(
                    rendered
                )

        return Group(*renderables)

    def _render_item(
        self,
        item: TranscriptItem,
    ) -> RenderableType | None:
        """
        渲染一条对话记录。
        """
        if (
            item.item_type
            is TranscriptItemType.USER
        ):
            return self._render_user_item(
                item
            )

        if (
            item.item_type
            is TranscriptItemType.ASSISTANT
        ):
            return self._render_assistant_item(
                item
            )

        if (
            item.item_type
            is TranscriptItemType.TOOL
        ):
            return self._render_tool_item(
                item
            )

        if (
            item.item_type
            is TranscriptItemType.SYSTEM
        ):
            return self._render_system_item(
                item
            )

        if (
            item.item_type
            is TranscriptItemType.ERROR
        ):
            return self._render_error_item(
                item
            )

        return None

    @staticmethod
    def _render_user_item(
        item: TranscriptItem,
    ) -> RenderableType:
        """
        渲染用户消息。
        """
        prefix = Text(
            "> ",
            style="bold cyan",
        )

        content = Text(
            item.text,
            style="bold",
        )

        return Group(
            Text(),
            Text.assemble(
                prefix,
                content,
            ),
        )

    @staticmethod
    def _render_assistant_item(
        item: TranscriptItem,
    ) -> RenderableType:
        """
        渲染模型回答。

        使用普通 Text 而不是 Markdown，
        避免流式输出过程中未闭合的 Markdown
        或代码块导致界面跳动。
        """
        if not item.text:
            return Text()

        prefix = Text(
            "● [模型回答：]",
            style="bold magenta",
        )

        content = Text(
            item.text,
            overflow="fold",
        )

        return Group(
            Text(),
            Text.assemble(
                prefix,
                content,
            ),
        )

    def _render_tool_item(
        self,
        item: TranscriptItem,
    ) -> RenderableType:
        """
        渲染工具调用记录。
        """
        tool_name = (
            item.tool_name
            or "unknown_tool"
        )

        header = Text()

        if (
            item.tool_status
            is ToolStatus.RUNNING
        ):
            header.append(
                "→ ",
                style="bold yellow",
            )
            header.append(
                tool_name,
                style="bold yellow",
            )

        elif (
            item.tool_status
            is ToolStatus.SUCCESS
        ):
            header.append(
                "✓ ",
                style="bold green",
            )
            header.append(
                tool_name,
                style="bold green",
            )
            header.append(
                " 完成",
                style="green",
            )

        elif (
            item.tool_status
            is ToolStatus.FAILED
        ):
            header.append(
                "✗ ",
                style="bold red",
            )
            header.append(
                tool_name,
                style="bold red",
            )
            header.append(
                " 失败",
                style="red",
            )

        else:
            header.append(
                "→ ",
                style="yellow",
            )
            header.append(
                tool_name,
                style="yellow",
            )

        if item.duration_seconds is not None:
            header.append(
                (
                    " · "
                    f"{item.duration_seconds:.2f}s"
                ),
                style="dim",
            )

        renderables: list[RenderableType] = [
            Text(),
            header,
        ]

        if item.arguments:
            renderables.append(
                self._render_arguments(
                    item.arguments
                )
            )

        if (
            item.text
            and item.tool_status
            in {
                ToolStatus.SUCCESS,
                ToolStatus.FAILED,
            }
        ):
            result_style = (
                "red"
                if item.tool_status
                is ToolStatus.FAILED
                else "dim"
            )

            result_text = self._truncate_text(
                item.text,
                self._max_result_length,
            )

            renderables.append(
                Text(
                    f"  {result_text}",
                    style=result_style,
                    overflow="fold",
                )
            )

        return Group(*renderables)

    @staticmethod
    def _render_system_item(
        item: TranscriptItem,
    ) -> RenderableType:
        """
        渲染系统消息。
        """
        return Group(
            Text(),
            Text(
                f"  {item.text}",
                style="dim italic",
            ),
        )

    @staticmethod
    def _render_error_item(
        item: TranscriptItem,
    ) -> RenderableType:
        """
        渲染错误消息。
        """
        return Group(
            Text(),
            Panel(
                Text(
                    item.text,
                    style="red",
                    overflow="fold",
                ),
                title="Agent 执行失败",
                border_style="red",
                expand=False,
            ),
        )

    def _render_arguments(
        self,
        arguments: Mapping[str, Any],
    ) -> RenderableType:
        """
        渲染工具参数摘要。
        """
        lines: list[RenderableType] = []

        for key, value in arguments.items():
            display_value = self._format_argument(
                key=key,
                value=value,
            )

            line = Text()
            line.append(
                f"  {key}: ",
                style="dim",
            )
            line.append(
                display_value,
                style="dim",
            )

            lines.append(line)

        return Group(*lines)

    def _render_activity(
        self,
    ) -> RenderableType | None:
        """
        渲染当前活动和 spinner。
        """
        activity = (
            self._state.current_activity
        )

        if not activity:
            return None

        return Group(
            Text(),
            Spinner(
                "dots",
                text=Text(
                    activity,
                    style="magenta",
                ),
                style="magenta",
            ),
        )

    def _render_footer(self) -> RenderableType:
        """
        渲染底部状态栏。
        """
        status = Text()

        mode = (
            self._state.mode or "chat 底部状态栏"
        )

        status.append(
            mode,
            style="cyan",
        )

        if self._state.max_turns > 0:
            status.append(
                (
                    " · turn "
                    f"{self._state.current_turn}"
                    f"/{self._state.max_turns}"
                ),
                style="dim",
            )

        if self._state.input_tokens is not None:
            status.append(
                (
                    " · input "
                    f"{self._state.input_tokens}"
                ),
                style="dim",
            )

        if self._state.output_tokens is not None:
            status.append(
                (
                    " · output "
                    f"{self._state.output_tokens}"
                ),
                style="dim",
            )

        if self._state.elapsed_seconds > 0:
            status.append(
                (
                    " · "
                    f"{self._state.elapsed_seconds:.1f}s"
                ),
                style="dim",
            )

        if self._state.interrupted:
            status.append(
                " · 已中断",
                style="bold yellow",
            )
        elif self._state.is_running:
            status.append(
                " · 运行中",
                style="bold magenta",
            )
        else:
            status.append(
                " · 就绪",
                style="green",
            )

        keyboard_help = Text(
            "Esc 中断 · Ctrl+C 退出",
            style="dim",
        )

        width = max(
            self._console.size.width,
            40,
        )

        left_text = status.plain
        right_text = keyboard_help.plain

        spacing = max(
            width
            - len(left_text)
            - len(right_text)
            - 1,
            1,
        )

        line = Text()
        line.append_text(status)
        line.append(" " * spacing)
        line.append_text(keyboard_help)

        return Group(
            Text(),
            Rule(style="dim"),
            line,
        )

    def _format_argument(
        self,
        *,
        key: str,
        value: Any,
    ) -> str:
        """
        将工具参数转换为适合终端显示的字符串。

        敏感字段会被隐藏，复杂值会使用 JSON 表示，
        超长内容会被截断。
        """
        normalized_key = (
            key.strip()
            .lower()
            .replace("-", "_")
        )

        if normalized_key in _SENSITIVE_KEYS:
            return "***"

        if value is None:
            text = "null"

        elif isinstance(value, bool):
            text = (
                "true"
                if value
                else "false"
            )

        elif isinstance(
            value,
            (dict, list, tuple),
        ):
            try:
                text = json.dumps(
                    value,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    default=str,
                )
            except (
                TypeError,
                ValueError,
            ):
                text = str(value)

        else:
            text = str(value)

        return self._truncate_text(
            text,
            self._max_argument_length,
        )

    @staticmethod
    def _truncate_text(
        text: str,
        max_length: int,
    ) -> str:
        """
        截断过长文本。

        换行会被转换为空格，避免一个参数占据过多行。
        """
        normalized = " ".join(
            text.splitlines()
        )

        if len(normalized) <= max_length:
            return normalized

        if max_length <= 3:
            return normalized[:max_length]

        return (
            normalized[: max_length - 3]
            + "..."
        )

    @staticmethod
    def _to_str(
        value: Any,
    ) -> str:
        """
        安全地将值转换为字符串。
        """
        if value is None:
            return ""

        return str(value)

    @staticmethod
    def _to_int(
        value: Any,
        *,
        default: int,
    ) -> int:
        """
        安全地将值转换为整数。
        """
        if isinstance(value, bool):
            return default

        if isinstance(value, int):
            return value

        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return default

        return default
    @staticmethod
    def _render_brand_logo() -> Text:
        """
        渲染专门为终端设计的 MANO 字符 Logo。

        这里不直接缩放 ICO 图片，而是使用固定字符图案，
        避免高分辨率图片缩小后变成无法识别的色块。
        """
        background = "#42689f"

        logo_lines = [
            "                                ",
            "          ███████               ",
            "        ██       ████████████   ",
            "        ██ CMO   ██             ",
            "      ██████████████████        ",
            "     ██  M   A   N   O  ██      ",
            "     ██████████████████████     ",
            "      ██  ██  ██  ██  ██        ",
            "                                ",
        ]
        logo = Text()

        for index, line in enumerate(logo_lines):
            logo.append(
                line,
                style=f"bold white on {background}",
            )

            if index < len(logo_lines) - 1:
                logo.append("\n")

        return logo