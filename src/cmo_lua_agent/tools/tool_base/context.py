from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cmo_lua_agent.tools.tool_base.progress import ToolProgressReporter


@dataclass(frozen=True)
class ToolContext:
    tool_use_id: str
    tool_name: str
    progress: ToolProgressReporter
    approval_receipt: Any | None = None

#未来还可在 ToolContext 增加取消信号、调用追踪 ID、运行目录、调用预算等系统能力，而不污染模型暴露的 JSON 参数。
