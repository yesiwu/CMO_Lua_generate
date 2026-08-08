from __future__ import annotations

from cmo_lua_agent.orchestration.context_manager import ContextManager


def test_context_manager_keeps_recent_messages_and_compacts_older_history() -> None:
    messages = [
        {"role": "user", "content": "old request"},
        {"role": "assistant", "content": "old answer"},
        {"role": "user", "content": "recent request"},
        {"role": "assistant", "content": "recent answer"},
    ]

    context = ContextManager(recent_message_count=2).build(
        messages,
        training_summary={"workflow_id": "training-001", "status": "RUNNING"},
    )

    assert context[0]["role"] == "user"
    assert "Training workflow" in context[0]["content"]
    assert "old request" in context[0]["content"]
    assert context[-2:] == messages[-2:]
