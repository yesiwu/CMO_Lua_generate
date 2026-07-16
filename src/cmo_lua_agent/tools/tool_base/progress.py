from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


TOOL_PROGRESS_EVENT_TYPES = frozenset(
    {
        "tool_started",
        "step_started",
        "step_progress",
        "step_completed",
        "output",
        "tool_completed",
        "tool_failed",
    }
)
TOOL_PROGRESS_STATUSES = frozenset(
    {"pending", "running", "success", "failed", "warning"}
)


@dataclass(frozen=True)
class ToolProgressEvent:
    tool_use_id: str
    tool_name: str
    event_type: str
    status: str
    message: str
    detail: str | None = None
    progress: float | None = None
    step_id: str | None = None
    parent_step_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolProgressReporter:
    """Domain-neutral progress reporter; callback failures never affect tools."""

    def __init__(
        self,
        *,
        tool_use_id: str,
        tool_name: str,
        callback: Callable[[ToolProgressEvent], None] | None = None,
    ) -> None:
        self.tool_use_id = tool_use_id
        self.tool_name = tool_name
        self._callback = callback

    def emit(self, *, event_type: str, status: str, message: str,
             detail: str | None = None, progress: float | None = None,
             step_id: str | None = None, parent_step_id: str | None = None,
             metadata: dict[str, Any] | None = None) -> None:
        if event_type not in TOOL_PROGRESS_EVENT_TYPES:
            raise ValueError(f"未知工具进度事件类型：{event_type}")
        if status not in TOOL_PROGRESS_STATUSES:
            raise ValueError(f"未知工具进度状态：{status}")
        if progress is not None:
            if isinstance(progress, bool):
                raise ValueError("progress 必须是 0 到 1 之间的数字")
            progress = float(progress)
            if not 0.0 <= progress <= 1.0:
                raise ValueError("progress 必须在 0 到 1 之间")
        event = ToolProgressEvent(
            tool_use_id=self.tool_use_id,
            tool_name=self.tool_name,
            event_type=event_type,
            status=status,
            message=message,
            detail=detail,
            progress=progress,
            step_id=step_id,
            parent_step_id=parent_step_id,
            metadata=dict(metadata or {}),
        )
        if self._callback is None:
            return
        try:
            self._callback(event)
        except Exception:
            return

    def tool_started(self, message: str, detail: str | None = None) -> None:
        self.emit(event_type="tool_started", status="running", message=message, detail=detail)

    def step_started(self, step_id: str, message: str, detail: str | None = None) -> None:
        self.emit(event_type="step_started", status="running", message=message, detail=detail, step_id=step_id)

    def step_progress(self, step_id: str, message: str, detail: str | None = None, progress: float | None = None) -> None:
        self.emit(event_type="step_progress", status="running", message=message, detail=detail, progress=progress, step_id=step_id)

    def output(self, message: str, detail: str | None = None, metadata: dict[str, Any] | None = None) -> None:
        self.emit(event_type="output", status="running", message=message, detail=detail, metadata=metadata)

    def step_completed(self, step_id: str, message: str, detail: str | None = None) -> None:
        self.emit(event_type="step_completed", status="success", message=message, detail=detail, progress=1.0, step_id=step_id)

    def tool_completed(self, message: str, detail: str | None = None) -> None:
        self.emit(event_type="tool_completed", status="success", message=message, detail=detail, progress=1.0)

    def tool_failed(self, message: str, detail: str | None = None) -> None:
        self.emit(event_type="tool_failed", status="failed", message=message, detail=detail)
