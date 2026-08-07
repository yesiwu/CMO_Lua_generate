"""Strict JSON adapter for the existing non-streaming Claude client."""
from __future__ import annotations

import json
import hashlib
import re
from collections.abc import Mapping
from typing import Protocol


class MessageClient(Protocol):
    def create_message(self, *, system: str, messages: list[dict[str, object]]) -> object: ...


class JsonCompletionError(ValueError):
    """Strict JSON parsing failure without retaining model response text."""

    code = "proposal_json_invalid"

    def __init__(self, diagnostics: Mapping[str, object]) -> None:
        self.diagnostics = dict(diagnostics)
        super().__init__(self.code)


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
            raise JsonCompletionError(_diagnostics(None, response_type=type(content).__name__))
        text = getattr(content[0], "text", None)
        if not isinstance(text, str) or not text.strip():
            raise JsonCompletionError(_diagnostics(text, response_type=type(text).__name__))
        payload, trailing_text = _json_payload(text)
        try:
            value = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise JsonCompletionError(
                _diagnostics(
                    text,
                    decoder_message=exc.msg,
                    decoder_line=exc.lineno,
                    decoder_column=exc.colno,
                    has_trailing_text=trailing_text or exc.msg == "Extra data",
                )
            ) from exc
        if trailing_text:
            raise JsonCompletionError(_diagnostics(text, has_trailing_text=True))
        if not isinstance(value, Mapping):
            raise JsonCompletionError(_diagnostics(text))
        return dict(value)

    def complete_text(self, *, system: str, prompt: str) -> str:
        """Return a single non-empty text completion without JSON parsing."""
        message = self._client.create_message(
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        content = getattr(message, "content", None)
        if not isinstance(content, list) or len(content) != 1:
            raise JsonCompletionError(_diagnostics(None, response_type=type(content).__name__))
        text = getattr(content[0], "text", None)
        if not isinstance(text, str) or not text.strip():
            raise JsonCompletionError(_diagnostics(text, response_type=type(text).__name__))
        return text.strip() + "\n"


_FENCED_JSON = re.compile(r"\A\s*```json[ \t]*\r?\n(?P<body>.*?)\r?\n```\s*\Z", re.DOTALL)


def _json_payload(text: str) -> tuple[str, bool]:
    match = _FENCED_JSON.match(text)
    if match is not None:
        return match.group("body"), False
    stripped = text.strip()
    if stripped.startswith("{"):
        return stripped, False
    return stripped, True


def _diagnostics(
    text: object,
    *,
    response_type: str | None = None,
    decoder_message: str | None = None,
    decoder_line: int | None = None,
    decoder_column: int | None = None,
    has_trailing_text: bool = False,
) -> dict[str, object]:
    rendered = text if isinstance(text, str) else ""
    return {
        "response_type": response_type or type(text).__name__,
        "response_length": len(rendered),
        "decoder_message": decoder_message,
        "decoder_line": decoder_line,
        "decoder_column": decoder_column,
        "has_markdown_fence": "```" in rendered,
        "has_trailing_text": has_trailing_text,
        "response_checksum": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
    }
