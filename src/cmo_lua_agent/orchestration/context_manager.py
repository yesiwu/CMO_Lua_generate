"""Build a bounded request context without discarding persisted chat history."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any


class ContextManager:
    """Keep recent message objects intact and summarize only older re-readable history."""

    def __init__(self, *, recent_message_count: int = 12) -> None:
        if recent_message_count < 1:
            raise ValueError("recent_message_count_must_be_positive")
        self._recent = recent_message_count

    def build(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        training_summary: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        copied = [dict(message) for message in messages]
        older = copied[:-self._recent]
        recent = copied[-self._recent:]
        if not older and training_summary is None:
            return recent
        summary_lines: list[str] = []
        if training_summary is not None:
            summary_lines.append("Training workflow:\n" + json.dumps(dict(training_summary), ensure_ascii=False, sort_keys=True))
        if older:
            summary_lines.append("Earlier conversation:\n" + self._summarize(older))
        return [{"role": "user", "content": "\n\n".join(summary_lines)}, *recent]

    @staticmethod
    def _summarize(messages: Sequence[Mapping[str, Any]]) -> str:
        rows: list[str] = []
        for message in messages:
            content = message.get("content", "")
            if isinstance(content, str):
                text = content
            else:
                text = json.dumps(content, ensure_ascii=False, default=str)
            rows.append(f"{message.get('role', 'unknown')}: {text[:1200]}")
        return "\n".join(rows)
