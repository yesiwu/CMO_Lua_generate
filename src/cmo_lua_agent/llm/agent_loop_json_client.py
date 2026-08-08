"""Strict JSON completion backed by the existing tool-capable AgentLoop."""
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from cmo_lua_agent.llm.json_client import (
    ClaudeJsonClient,
    JsonCompletionError,
    _diagnostics,
    _json_payload,
)
from cmo_lua_agent.orchestration.agent_loop import AgentLoop
from cmo_lua_agent.orchestration.events import AgentEvent, AgentEventType
from cmo_lua_agent.tools.tool_base.registry import ToolRegistry


class AgentLoopJsonClient:
    """Allow one read-only tool loop before returning strict JSON."""

    def __init__(
        self,
        *,
        client: Any,
        tool_registry: ToolRegistry,
        max_turns: int | None = None,
    ) -> None:
        self._client = client
        self._tool_registry = tool_registry
        self._max_turns = max_turns
        self.last_calls = 0

    def complete_json(self, *, system: str, prompt: str) -> object:
        calls = 0
        selected_skills: list[dict[str, Any]] = []

        def observe(event: AgentEvent) -> None:
            nonlocal calls
            if event.type is AgentEventType.LLM_STARTED:
                calls += 1
            if (
                event.type is AgentEventType.TOOL_COMPLETED
                and event.data.get("tool_name") == "view_curated_skill"
                and len(selected_skills) < 3
            ):
                try:
                    payload = json.loads(str(event.data.get("content", "")))
                except json.JSONDecodeError:
                    return
                if isinstance(payload, Mapping) and payload.get("success") is True:
                    selected_skills.append(dict(payload))

        loop = AgentLoop(
            self._client,
            self._tool_registry,
            system_prompt=(
                system
                + "\nBefore returning JSON, call list_curated_skills. If it returns any Skills, "
                "view one to three relevant Skills with view_curated_skill before planning. "
                "You may use only the supplied read-only Skill tools. "
                "Return only the required JSON object after any tool calls."
            ),
            max_turns=self._max_turns,
            event_handler=observe,
        )
        text = loop.run([{"role": "user", "content": prompt}])
        self.last_calls = calls
        if not isinstance(text, str) or not text.strip():
            raise JsonCompletionError({"response_type": type(text).__name__, "response_length": 0})
        try:
            return self._parse_json(text)
        except JsonCompletionError:
            # Some Anthropic-compatible providers perform the read-only tool
            # calls correctly but return prose in the final turn.  Keep the
            # AgentLoop's selected Skill context and make one strict JSON-only
            # finalization request; never scrape JSON from prose.
            if not selected_skills:
                raise
            calls += 1
            self.last_calls = calls
            return ClaudeJsonClient(self._client).complete_json(
                system=(
                    system
                    + "\nThe following Skills were selected through a read-only AgentLoop. "
                    "Use them as context and return only the required JSON object."
                ),
                prompt=(
                    prompt
                    + "\n\nSelected curated Skills:\n"
                    + json.dumps(selected_skills, ensure_ascii=False, sort_keys=True)
                ),
            )

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
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
        if trailing_text or not isinstance(value, Mapping):
            raise JsonCompletionError(_diagnostics(text, has_trailing_text=trailing_text))
        return dict(value)
