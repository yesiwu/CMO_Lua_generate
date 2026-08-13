"""LLM 上下文窗口配置测试。"""

from __future__ import annotations

from cmo_lua_agent.llm_config import load_config


def test_deepseek_context_window_defaults_to_one_million_tokens(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fixture-key")
    monkeypatch.setenv("MODEL_ID", "deepseek-chat")
    monkeypatch.delenv("LLM_CONTEXT_WINDOW_TOKENS", raising=False)

    config = load_config()

    assert config.llm.context_window_tokens == 1_000_000


def test_context_window_can_be_overridden_for_compatible_endpoints(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fixture-key")
    monkeypatch.setenv("MODEL_ID", "compatible-model")
    monkeypatch.setenv("LLM_CONTEXT_WINDOW_TOKENS", "128000")

    config = load_config()

    assert config.llm.context_window_tokens == 128_000
