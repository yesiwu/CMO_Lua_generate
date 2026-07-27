"""Strict JSON adapter for the existing non-streaming Claude client."""
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Protocol


class MessageClient(Protocol):
    def create_message(self, *, system: str, messages: list[dict[str, object]]) -> object: ...


class ClaudeJsonClient:
    """Expose one JSON-only completion without widening the LLM boundary."""

    def __init__(self, client: MessageClient) -> None:
        self._client = client

    def complete_json(self, *, system: str, prompt: str) -> object:
        message = self._client.create_message(
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        content = getattr(message, "content", None)
        if not isinstance(content, list) or len(content) != 1:
            raise ValueError("JSON completion must contain exactly one text block")
        text = getattr(content[0], "text", None)
        if not isinstance(text, str) or not text.strip():
            raise ValueError("JSON completion is empty or not text")
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("JSON completion is invalid") from exc
        if not isinstance(value, Mapping):
            raise ValueError("JSON completion must be an object")
        return dict(value)
