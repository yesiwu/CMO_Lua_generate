from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from cmo_lua_agent.orchestration.chat_session_store import ChatSessionStore


def test_load_active_restores_saved_messages_after_restart(tmp_path: Path) -> None:
    store = ChatSessionStore(tmp_path)
    session = store.load_active()
    messages = [
        {"role": "user", "content": "continue optimisation for seven runs"},
        {"role": "assistant", "content": [{"type": "text", "text": "started"}]},
    ]

    store.save_messages(session.session_id, messages)

    restored = ChatSessionStore(tmp_path).load_active()

    assert restored.session_id == session.session_id
    assert restored.messages == messages


def test_save_messages_serializes_sdk_content_blocks(tmp_path: Path) -> None:
    store = ChatSessionStore(tmp_path)
    session = store.load_active()
    block = SimpleNamespace(
        type="tool_use",
        id="tool_001",
        name="inspect_evolution_campaign",
        input={"campaign_id": "campaign-001"},
    )

    store.save_messages(
        session.session_id,
        [{"role": "assistant", "content": [block]}],
    )

    restored = store.load_active()

    assert restored.messages == [
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "tool_001",
                    "name": "inspect_evolution_campaign",
                    "input": {"campaign_id": "campaign-001"},
                }
            ],
        }
    ]


def test_create_and_list_sessions_keep_the_new_session_active(tmp_path: Path) -> None:
    store = ChatSessionStore(tmp_path)
    first = store.load_active()
    second = store.create()

    sessions = store.list_sessions()

    assert store.load_active().session_id == second.session_id
    assert [item.session_id for item in sessions] == [second.session_id, first.session_id]
