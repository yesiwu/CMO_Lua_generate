"""按模型窗口占用率触发的上下文管理测试。"""

from __future__ import annotations

from cmo_lua_agent.orchestration.context_manager import (
    ContextCompactionNotice,
    ContextManager,
)


class RecordingSummarizer:
    def __init__(self, result: str = '{"goal":"继续任务"}') -> None:
        self.result = result
        self.calls: list[list[dict[str, object]]] = []

    def summarize(self, messages):
        self.calls.append([dict(message) for message in messages])
        return self.result


class FailingSummarizer:
    def summarize(self, messages):
        raise ConnectionError("摘要端点暂时不可用")


def test_context_manager_keeps_every_message_below_eighty_percent() -> None:
    messages = [
        {"role": "user", "content": "很早的问题"},
        {"role": "assistant", "content": "很早的回答"},
        {"role": "user", "content": "最近的问题"},
    ]
    manager = ContextManager(context_window_tokens=1_000)

    context = manager.build(messages, system_prompt="主提示词", tools=[])

    assert context == messages
    assert context is not messages


def test_context_manager_compacts_only_after_threshold_and_targets_sixty_percent() -> None:
    messages = [
        {"role": "user" if index % 2 == 0 else "assistant", "content": "上下文" * 80}
        for index in range(20)
    ]
    manager = ContextManager(
        context_window_tokens=2_000,
        recent_message_count=4,
    )

    context = manager.build(messages, system_prompt="主提示词", tools=[])

    assert len(context) < len(messages)
    assert "较早对话摘要" in context[0]["content"]
    assert context[-4:] == messages[-4:]
    assert manager.estimate_request_tokens(
        context, system_prompt="主提示词", tools=[]
    ) <= 1_200


def test_context_manager_never_separates_tool_use_from_tool_result() -> None:
    tool_use = {
        "role": "assistant",
        "content": [{"type": "tool_use", "id": "call-1", "name": "read_file", "input": {}}],
    }
    tool_result = {
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": "call-1", "content": "ok"}],
    }
    messages = [
        {"role": "user", "content": "旧内容" * 500},
        {"role": "assistant", "content": "旧回答" * 500},
        tool_use,
        tool_result,
    ]
    manager = ContextManager(context_window_tokens=1_000, recent_message_count=1)

    context = manager.build(messages, system_prompt="", tools=[])

    assert context[-2:] == [tool_use, tool_result]


def test_real_usage_calibrates_the_next_estimate() -> None:
    manager = ContextManager(context_window_tokens=10_000)
    messages = [{"role": "user", "content": "abc" * 100}]
    before = manager.estimate_request_tokens(messages, system_prompt="", tools=[])
    manager.build(messages, system_prompt="", tools=[])

    manager.observe_usage(before * 2)

    after = manager.estimate_request_tokens(messages, system_prompt="", tools=[])
    assert after > before


def test_context_manager_reports_no_compaction_below_threshold() -> None:
    notices: list[ContextCompactionNotice] = []
    manager = ContextManager(context_window_tokens=10_000)

    manager.build(
        [{"role": "user", "content": "短消息"}],
        compaction_observer=notices.append,
    )

    assert notices == []


def test_context_manager_reports_started_and_completed_compaction() -> None:
    notices: list[ContextCompactionNotice] = []
    messages = [
        {"role": "user" if index % 2 == 0 else "assistant", "content": "上下文" * 100}
        for index in range(20)
    ]
    manager = ContextManager(context_window_tokens=2_000, recent_message_count=4)

    manager.build(messages, compaction_observer=notices.append)

    assert [notice.phase for notice in notices] == ["started", "completed"]
    started, completed = notices
    assert started.estimated_tokens_before > 1_600
    assert started.context_window_tokens == 2_000
    assert started.target_tokens == 1_200
    assert completed.estimated_tokens_before == started.estimated_tokens_before
    assert completed.estimated_tokens_after <= 1_200
    assert completed.retained_message_count >= 4
    assert completed.duration_seconds is not None
    assert completed.duration_seconds >= 0


def test_context_manager_uses_semantic_summary_for_older_messages() -> None:
    summarizer = RecordingSummarizer()
    messages = [
        {"role": "user" if index % 2 == 0 else "assistant", "content": "重要旧内容" * 120}
        for index in range(10)
    ]
    manager = ContextManager(
        context_window_tokens=3_000,
        recent_message_count=2,
        summarizer=summarizer,
    )

    context = manager.build(messages)

    assert len(summarizer.calls) == 1
    assert summarizer.calls[0] == messages[:-2]
    assert "较早对话语义摘要" in context[0]["content"]
    assert '"goal":"继续任务"' in context[0]["content"]
    assert context[-2:] == messages[-2:]


def test_context_manager_falls_back_when_semantic_summary_fails() -> None:
    notices: list[ContextCompactionNotice] = []
    messages = [
        {"role": "user" if index % 2 == 0 else "assistant", "content": "上下文" * 120}
        for index in range(12)
    ]
    manager = ContextManager(
        context_window_tokens=2_000,
        recent_message_count=2,
        summarizer=FailingSummarizer(),
    )

    context = manager.build(messages, compaction_observer=notices.append)

    assert "确定性降级摘要" in context[0]["content"]
    assert notices[-1].strategy == "deterministic_fallback"
    assert notices[-1].fallback_reason == "ConnectionError"


def test_semantic_summary_is_reused_until_active_context_reaches_threshold_again() -> None:
    summarizer = RecordingSummarizer()
    messages = [
        {"role": "user" if index % 2 == 0 else "assistant", "content": "旧内容" * 150}
        for index in range(10)
    ]
    manager = ContextManager(
        context_window_tokens=3_000,
        recent_message_count=2,
        summarizer=summarizer,
    )

    first = manager.build(messages)
    messages.append({"role": "user", "content": "一条很短的新消息"})
    second_notices: list[ContextCompactionNotice] = []
    second = manager.build(messages, compaction_observer=second_notices.append)

    assert len(summarizer.calls) == 1
    assert second_notices == []
    assert second[0] == first[0]
    assert second[-1]["content"] == "一条很短的新消息"
