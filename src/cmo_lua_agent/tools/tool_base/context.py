"""工具调用的上下文载体。

ToolRegistry 在每次工具调用时注入本对象，以传递调用 ID、进度上报器和可选授权回执；
这些运行时元数据不进入模型参数 JSON，避免把框架控制信息与用户业务输入混在一起。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cmo_lua_agent.tools.tool_base.progress import ToolProgressReporter


@dataclass(frozen=True)
class ToolContext:
    """单次工具调用的不可变运行时上下文。"""
    tool_use_id: str
    tool_name: str
    progress: ToolProgressReporter
    approval_receipt: Any | None = None

#未来还可在 ToolContext 增加取消信号、调用追踪 ID、运行目录、调用预算等系统能力，而不污染模型暴露的 JSON 参数。
