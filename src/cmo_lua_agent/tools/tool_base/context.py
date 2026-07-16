from __future__ import annotations

from dataclasses import dataclass

from cmo_lua_agent.tools.tool_base.progress import ToolProgressReporter


@dataclass(frozen=True)
class ToolContext:
    tool_use_id: str
    tool_name: str
    progress: ToolProgressReporter
