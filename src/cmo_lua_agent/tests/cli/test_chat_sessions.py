from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from cmo_lua_agent.cli.chat import run_chat
from cmo_lua_agent.orchestration.chat_session_store import ChatSessionStore


class _Display:
    def __init__(self) -> None:
        self.state = SimpleNamespace(last_error=None)
        self.last_display_error = None

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def add_user_message(self, _: str) -> None:
        pass

    def mark_interrupted(self) -> None:
        pass


class _AgentLoop:
    def run(self, history: list[dict[str, Any]]) -> None:
        history.append({"role": "assistant", "content": "saved response"})


def test_run_chat_saves_completed_turn_to_active_session(
    tmp_path: Path,
    monkeypatch,
) -> None:
    answers = iter(["save this turn", "q"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    store = ChatSessionStore(tmp_path)
    session = store.load_active()

    exit_code = run_chat(
        agent_loop=_AgentLoop(),
        display=_Display(),
        session_store=store,
    )

    assert exit_code == 0
    assert store.load_active().session_id == session.session_id
    assert store.load_active().messages == [
        {"role": "user", "content": "save this turn"},
        {"role": "assistant", "content": "saved response"},
    ]


def test_run_chat_new_command_starts_a_separate_active_session(
    tmp_path: Path,
    monkeypatch,
) -> None:
    answers = iter([":new", "message in new session", "q"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    store = ChatSessionStore(tmp_path)
    original = store.load_active()

    run_chat(
        agent_loop=_AgentLoop(),
        display=_Display(),
        session_store=store,
    )

    active = store.load_active()
    assert active.session_id != original.session_id
    assert active.messages[0] == {
        "role": "user",
        "content": "message in new session",
    }
    assert original.messages == []


def test_run_chat_compacts_request_context_without_losing_full_history(
    tmp_path: Path,
    monkeypatch,
) -> None:
    answers = iter(["new question", "q"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    store = ChatSessionStore(tmp_path)
    session = store.load_active()
    old_messages = [
        {"role": "user", "content": f"old {index}"}
        for index in range(14)
    ]
    store.save_messages(session.session_id, old_messages)

    run_chat(agent_loop=_AgentLoop(), display=_Display(), session_store=store)

    assert store.load_active().messages[:14] == old_messages
    assert store.load_active().messages[-2:] == [
        {"role": "user", "content": "new question"},
        {"role": "assistant", "content": "saved response"},
    ]
