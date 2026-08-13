"""语义上下文摘要 Agent 的输出契约测试。"""

from __future__ import annotations

import json

import pytest

from cmo_lua_agent.agents.context_summary_agent import ContextSummaryAgent


class RecordingJsonClient:
    """记录摘要请求，并返回测试指定的真实 JSON 数据结构。"""

    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[dict[str, str]] = []

    def complete_json(self, *, system: str, prompt: str) -> object:
        self.calls.append({"system": system, "prompt": prompt})
        return self.result


def _valid_summary() -> dict[str, object]:
    return {
        "goal": "完成上下文语义压缩",
        "constraints": ["注释和提示词使用中文"],
        "completed": ["已确认设计"],
        "current_state": "正在实现摘要 Agent",
        "important_facts": ["完整会话历史不能修改"],
        "open_issues": [],
        "next_steps": ["接入 ContextManager"],
        "failed_attempts": [],
    }


def test_summary_agent_returns_canonical_json_without_tools() -> None:
    client = RecordingJsonClient(_valid_summary())
    agent = ContextSummaryAgent(client)

    summary = agent.summarize(
        [
            {"role": "user", "content": "请保留路径 D:/project/main.py"},
            {"role": "assistant", "content": "已读取该文件"},
        ]
    )

    assert json.loads(summary) == _valid_summary()
    assert len(client.calls) == 1
    assert "上下文压缩器" in client.calls[0]["system"]
    assert "不得调用任何工具" in client.calls[0]["system"]
    assert "D:/project/main.py" in client.calls[0]["prompt"]


def test_summary_agent_rejects_missing_or_wrong_field_types() -> None:
    invalid = _valid_summary()
    invalid["constraints"] = "不是数组"
    agent = ContextSummaryAgent(RecordingJsonClient(invalid))

    with pytest.raises(ValueError, match="constraints"):
        agent.summarize([{"role": "user", "content": "旧消息"}])
