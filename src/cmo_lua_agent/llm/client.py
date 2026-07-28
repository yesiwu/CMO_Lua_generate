"""
大语言模型客户端封装模块。

该模块负责：
1. 根据项目配置创建 Anthropic 客户端；
2. 统一发送 Messages API 请求；
3. 设置模型、超时时间、重试次数和最大 Token 数；
4. 隐藏底层 SDK 调用细节；
5. 为不同 Agent 提供统一的 LLM 调用接口；
6. 便于测试时替换为 Fake 或 Mock 客户端。

其他模块不应直接创建 Anthropic 客户端，
而应通过本模块提供的客户端访问大语言模型。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cmo_lua_agent.llm_config import LlmConfig
from collections.abc import Callable
if TYPE_CHECKING:
    from anthropic.types import Message
else:
    Message = Any

class ClaudeClient:
    def __init__(self, config: LlmConfig):
        from anthropic import Anthropic

        self._config = config

        client_kwargs: dict[str, Any] = {
            "api_key": config.api_key,
            "timeout": config.timeout_seconds,
            "max_retries": config.max_retries,
        }

        if config.base_url:
            client_kwargs["base_url"] = config.base_url

        self._client = Anthropic(**client_kwargs)

    @property
    def model_id(self) -> str:
        return self._config.model_id

    def create_message(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int | None = None,
    ):
        #非流逝请求
        request: dict[str, Any] = {
            "model": self._config.model_id,
            "system": system,
            "messages": messages,
            "max_tokens": (
                max_tokens or self._config.max_tokens
            ),
        }

        if tools:
            request["tools"] = tools

        return self._client.messages.create(**request)
    
    def stream_message(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int | None = None,
        on_text_delta: Callable[[str], None] | None = None,
    ) -> Message:
        """
        以流式方式调用 Claude Messages API。

        模型返回文本时，会逐段调用 on_text_delta。
        流结束后返回完整 Message，AgentLoop 可以继续读取：
        1. response.content；
        2. response.stop_reason；
        3. response.usage；
        4. tool_use 内容块。

        Args:
            system:
                系统提示词。

            messages:
                Anthropic Messages API 对话历史。

            tools:
                提供给模型的工具定义。
                没有工具时可以传入 None 或空列表。

            max_tokens:
                本次请求允许生成的最大 Token 数。
                未提供时使用客户端默认配置。

            on_text_delta:
                每收到一段模型文本时调用的回调函数。

        Returns:
            完整的 Anthropic Message 对象。
        """
        request: dict[str, Any] = {
            "model": self._config.model_id,
            "system": system,
            "messages": messages,
            "max_tokens": (
                max_tokens
                if max_tokens is not None
                else self._config.max_tokens
            ),
        }

        # 没有工具时不传空 tools，
        # 避免向兼容接口发送无意义字段。
        if tools:
            request["tools"] = tools

        with self._client.messages.stream(
            **request
        ) as stream:
            for text in stream.text_stream:
                if on_text_delta is not None:
                    on_text_delta(text)

            return stream.get_final_message()
