"""
交互式终端界面状态。

该模块保存终端界面当前需要展示的信息，包括：
1. Agent 名称、版本、模型和工作目录；
2. 用户消息、模型回答和工具调用记录；
3. 当前正在执行的活动；
4. Agent 当前轮次、耗时和 Token 使用情况；
5. 工具执行中、成功或失败等状态。

UIState 只保存数据，不负责终端渲染，也不执行任何业务逻辑。
terminal_display.py 会根据 AgentEvent 更新这些状态，
然后使用 Rich 将状态绘制到终端。

终端展示的需要四种， user， system，assist  ，tool
然后工具有另外的运行，成功，失败三种状态
写好这两个类之后就是需要 通用item 可以接收这样的东西

然后就需要uistate 
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TranscriptItemType(str, Enum):
    """
    终端对话记录中的内容类型。

    枚举值使用稳定的英文机器标识，
    具体中文显示方式由 terminal_display.py 决定。
    """

    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"
    ERROR = "error"


class ToolStatus(str, Enum):
    """
    工具调用的当前执行状态。
    """

    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


MAX_TOOL_OUTPUT_LINES = 8


@dataclass
class ToolStepState:
    step_id: str
    message: str
    status: str = "pending"
    detail: str | None = None
    progress: float | None = None


@dataclass
class ToolExecutionState:
    tool_use_id: str
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    status: str = "running"
    summary: str = ""
    current_step_id: str | None = None
    steps: dict[str, ToolStepState] = field(default_factory=dict)
    output_lines: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TranscriptItem:
    """
    终端对话区域中的一条记录。

    item_type:
        当前记录的类型，例如用户消息、模型回答或工具调用。

    text:
        需要展示的主要文本。
        模型流式输出时，该字段会不断追加文本。

    tool_use_id:
        Anthropic tool_use 内容块的唯一 ID。
        非工具记录时为 None。

    tool_name:
        工具名称。
        非工具记录时为 None。

    tool_status:
        工具当前状态。
        非工具记录时为 None。

    arguments:
        工具调用参数。
        只保存结构化数据，显示层会自行决定如何截断展示。

    duration_seconds:
        工具执行耗时。

    metadata:
        预留的额外信息，例如错误码、日志路径和执行轮次。
    """

    item_type: TranscriptItemType
    text: str = ""

    tool_use_id: str | None = None
    tool_name: str | None = None
    tool_status: ToolStatus | None = None

    arguments: dict[str, Any] = field(
        default_factory=dict
    )

    duration_seconds: float | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class UIState:
    """
    交互式终端界面的完整状态。只会内存临时存放，

    TerminalDisplay 会读取该对象，并将其渲染成标题区、
    对话记录区、当前活动区和底部状态栏。
    """

    # ── 顶部标题信息 ──────────────────────────────

    agent_name: str = "军事 CMO Lua 自动化系统"
    version: str = "0.1.0"
    model_name: str = ""
    workdir: str = ""
    mode: str = "chat"


    # ── 对话和工具记录 ────────────────────────────
    #（从上到下按产生时间排序）
    transcript: list[TranscriptItem] = field(
        default_factory=list
    )

    # 当前正在流式生成的 assistant 记录索引。
    # 没有正在生成的模型消息时为 None。
    active_assistant_index: int | None = None

    # 通过 tool_use_id 定位工具记录在 transcript 中的位置。  
    
    tool_item_indexes: dict[str, int] = field(
        default_factory=dict
    )
    active_tools: dict[str, ToolExecutionState] = field(default_factory=dict)

    # ── 当前运行状态 ──────────────────────────────

    current_activity: str | None = None

    current_turn: int = 0
    max_turns: int = 10

    elapsed_seconds: float = 0.0

    input_tokens: int | None = None
    output_tokens: int | None = None

    is_running: bool = False
    interrupted: bool = False
    last_error: str | None = None

    def add_user_message(
        self,
        text: str,
    ) -> None:
        """
        向对话记录中添加用户消息。
        """
        self.transcript.append(
            TranscriptItem(
                item_type=TranscriptItemType.USER,
                text=text,
            )
        )

    def start_assistant_message(self) -> None:
        """
        创建一条新的模型消息，并标记为当前流式输出目标。

        如果当前已经存在正在生成的模型消息，则不重复创建。
        """
        if self.active_assistant_index is not None:
            return

        self.transcript.append(
            TranscriptItem(
                item_type=TranscriptItemType.ASSISTANT,
            )
        )

        self.active_assistant_index = (
            len(self.transcript) - 1
        )

    def append_assistant_text(
        self,
        text: str,
    ) -> None:
        """
        将一段流式文本追加到当前模型消息。

        如果尚未创建模型消息，会先自动创建。
        active_assistant_index作用是：llm是一段一段的输出，通过这个可以直接把llm输出结果进行拼接  来展示
        """
        if self.active_assistant_index is None:
            self.start_assistant_message()

        if self.active_assistant_index is None:
            raise RuntimeError(
                "无法创建模型输出记录"
            )

        item = self.transcript[
            self.active_assistant_index
        ]

        item.text += text

    def finish_assistant_message(self) -> None:
        """
        结束当前模型流式输出。
        把结果进行清空。
        """
        self.active_assistant_index = None

    def start_tool(
        self,
        *,
        tool_use_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> None:
        """
        添加一条正在执行的工具记录。
        """
        item = TranscriptItem(
            item_type=TranscriptItemType.TOOL,
            tool_use_id=tool_use_id,
            tool_name=tool_name,
            tool_status=ToolStatus.RUNNING,
            arguments=dict(arguments),
        )

        self.transcript.append(item)

        self.tool_item_indexes[tool_use_id] = (
            len(self.transcript) - 1
        )
        self.active_tools[tool_use_id] = ToolExecutionState(
            tool_use_id=tool_use_id,
            tool_name=tool_name,
            arguments=dict(arguments),
        )

    def finish_tool(
        self,
        *,
        tool_use_id: str,
        success: bool,
        content: str,
        duration_seconds: float,
    ) -> None:
        """
        更新工具调用的最终执行状态。

        tool_use_id 不存在时会创建一条错误记录，
        避免终端显示层因事件顺序异常而直接崩溃。
        """
        item_index = self.tool_item_indexes.get(
            tool_use_id
        )

        if item_index is None:
            self.transcript.append(
                TranscriptItem(
                    item_type=TranscriptItemType.ERROR,
                    text=(
                        "收到无法匹配的工具结束事件："
                        f"{tool_use_id}"
                    ),
                )
            )
            return

        item = self.transcript[item_index]

        item.tool_status = (
            ToolStatus.SUCCESS
            if success
            else ToolStatus.FAILED
        )

        item.text = content
        item.duration_seconds = duration_seconds
        self.active_tools.pop(tool_use_id, None)

    def update_tool_progress(
        self,
        *,
        tool_use_id: str,
        event_type: str,
        status: str,
        message: str,
        detail: str | None = None,
        progress: float | None = None,
        step_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        item_index = self.tool_item_indexes.get(tool_use_id)
        if item_index is None:
            return
        item = self.transcript[item_index]
        execution = self.active_tools.get(tool_use_id)
        if execution is None:
            return

        execution.summary = message
        execution.metadata.update(dict(metadata or {}))

        if event_type == "output":
            output = message + (f" — {detail}" if detail else "")
            execution.output_lines.append(output)
            del execution.output_lines[:-MAX_TOOL_OUTPUT_LINES]
        elif step_id is not None and event_type.startswith("step_"):
            step = execution.steps.get(step_id)
            if step is None:
                step = ToolStepState(step_id=step_id, message=message)
                execution.steps[step_id] = step
            step.message = message
            step.status = status
            step.detail = detail
            step.progress = progress
            if status == "running":
                execution.current_step_id = step_id
            elif execution.current_step_id == step_id:
                execution.current_step_id = None
        elif event_type in {"tool_completed", "tool_failed"}:
            execution.status = status

        suffix = f" — {detail}" if detail else ""
        if progress is None:
            item.text = message + suffix
        else:
            item.text = f"{message} ({progress * 100:.0f}%)" + suffix

    def add_system_message(
        self,
        text: str,
    ) -> None:
        """
        添加系统状态消息。
        """
        self.transcript.append(
            TranscriptItem(
                item_type=TranscriptItemType.SYSTEM,
                text=text,
            )
        )

    def add_error(
        self,
        text: str,
    ) -> None:
        """
        添加错误记录，并保存最后一次错误。
        """
        self.last_error = text

        self.transcript.append(
            TranscriptItem(
                item_type=TranscriptItemType.ERROR,
                text=text,
            )
        )
