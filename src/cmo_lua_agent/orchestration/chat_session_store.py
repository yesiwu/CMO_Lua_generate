"""Durable storage for terminal chat sessions."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class ChatSession:
    """A persisted chat transcript and its session metadata."""

    session_id: str
    messages: list[dict[str, Any]]
    created_at: str
    updated_at: str


class ChatSessionStore:
    """Store independent chat transcripts beneath a project work directory."""

    def __init__(self, workdir: Path) -> None:
        self._root = Path(workdir) / ".cmo_lua_agent" / "chat_sessions"
        self._sessions_dir = self._root / "sessions"
        self._active_path = self._root / "active_session.json"

    def load_active(self) -> ChatSession:
        """Return the active session, creating one when no session exists yet."""
        active_session_id = self._load_active_session_id()
        if active_session_id is not None:
            session = self._load_session(active_session_id)
            if session is not None:
                return session

        return self.create()

    def create(self) -> ChatSession:
        """Create an empty session and make it active."""
        timestamp = _utc_timestamp()
        session = ChatSession(
            session_id=f"session-{uuid4().hex}",
            messages=[],
            created_at=timestamp,
            updated_at=timestamp,
        )
        self._write_session(session)
        self._write_active_session_id(session.session_id)
        return session

    def list_sessions(self) -> list[ChatSession]:
        """Return saved sessions from most recently updated to oldest."""
        if not self._sessions_dir.exists():
            return []

        sessions = [
            session
            for path in self._sessions_dir.glob("*.json")
            if (session := self._load_session(path.stem)) is not None
        ]
        return sorted(sessions, key=lambda session: session.updated_at, reverse=True)

    def activate(self, session_id: str) -> ChatSession:
        """Make an existing session active and return it."""
        session = self._load_session(session_id)
        if session is None:
            raise KeyError(f"unknown chat session: {session_id}")
        self._write_active_session_id(session.session_id)
        return session

    def save_messages(self, session_id: str, messages: Sequence[Mapping[str, Any]]) -> ChatSession:
        """Replace a session transcript with JSON-safe message data."""
        existing = self._load_session(session_id)
        if existing is None:
            raise KeyError(f"unknown chat session: {session_id}")

        session = ChatSession(
            session_id=existing.session_id,
            messages=_json_safe(list(messages)),
            created_at=existing.created_at,
            updated_at=_utc_timestamp(),
        )
        self._write_session(session)
        self._write_active_session_id(session.session_id)
        return session

    def _load_active_session_id(self) -> str | None:
        try:
            data = json.loads(self._active_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return None
        session_id = data.get("session_id") if isinstance(data, dict) else None
        return session_id if isinstance(session_id, str) else None

    def _load_session(self, session_id: str) -> ChatSession | None:
        path = self._sessions_dir / f"{session_id}.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        messages = data.get("messages")
        if not isinstance(messages, list):
            return None
        try:
            return ChatSession(
                session_id=str(data["session_id"]),
                messages=messages,
                created_at=str(data["created_at"]),
                updated_at=str(data["updated_at"]),
            )
        except KeyError:
            return None

    def _write_session(self, session: ChatSession) -> None:
        self._sessions_dir.mkdir(parents=True, exist_ok=True)
        path = self._sessions_dir / f"{session.session_id}.json"
        path.write_text(
            json.dumps(asdict(session), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _write_active_session_id(self, session_id: str) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        self._active_path.write_text(
            json.dumps({"session_id": session_id}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _utc_timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _json_safe(value: Any) -> Any:
    """Convert Anthropic SDK response blocks and nested values to JSON data."""
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_json_safe(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return _json_safe(asdict(value))
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump())
    if hasattr(value, "__dict__"):
        return _json_safe(
            {key: item for key, item in vars(value).items() if not key.startswith("_")}
        )
    raise TypeError(f"cannot serialize chat message value: {type(value).__name__}")
