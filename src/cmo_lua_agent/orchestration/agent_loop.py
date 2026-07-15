"""
Agent 核心循环实现。

该模块负责维护完整工具调用闭环：

    用户消息
        → 流式调用 LLM
        → 发出模型运行事件
        → 解析 tool_use
        → ToolRegistry 分发工具
        → 发出工具执行事件
        → 封装 tool_result
        → 进入下一轮 LLM
        → 返回最终文本

主要职责：
1. 维护并原地更新对话消息历史；
2. 流式调用 LLM；
3. 将运行过程转换为 AgentEvent；
4. 识别 text 和 tool_use 内容块；
5. 分发并执行工具；
6. 封装 Anthropic tool_result；
7. 限制最大循环轮数；
8. 在失败时发出 AGENT_FAILED 事件。

边界约束：
- 不包含具体工具实现；
- 不执行权限判断；
- 不负责终端绘制；
- 不解析 CMO 或 Lua 错误；
- 不保存数据库或日志文件。
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from time import perf_counter
from typing import Any

from cmo_lua_agent.llm.client import ClaudeClient
from cmo_lua_agent.orchestration.events import AgentEvent, AgentEventType
from cmo_lua_agent.tools.tool_base.registry import ToolRegistry


logger = logging.getLogger(__name__)

EventHandler = Callable[[AgentEvent], None]


class AgentLoop:
    """
    Claude 工具调用循环。

    负责串联 ClaudeClient 和 ToolRegistry，并通过
    AgentEvent 向终端显示层或日志监听器报告运行过程。
    """

    def __init__(
        self,
        llm_client: ClaudeClient,
        tool_registry: ToolRegistry,
        system_prompt: str,
        max_turns: int = 10,
        event_handler: EventHandler | None = None,
    ) -> None:
        """
        初始化 AgentLoop。

        Args:
            llm_client:
                Claude LLM 客户端。

            tool_registry:
                工具注册中心。

            system_prompt:
                每轮模型请求携带的系统提示词。

            max_turns:
                最大模型调用轮数，必须大于等于 1。

            event_handler:
                可选的事件处理函数，例如
                TerminalDisplay.handle。

        Raises:
            ValueError:
                max_turns 小于 1。
        """
        if max_turns < 1:
            raise ValueError("max_turns 必须大于等于 1")

        self._llm_client = llm_client
        self._tool_registry = tool_registry
        self._system_prompt = system_prompt
        self._max_turns = max_turns
        self._event_handler = event_handler

############核心#######
    def run(self, messages: list[dict[str, Any]]) -> str | None:
        """
        执行完整 Agent 工具调用循环。

        该方法会原地修改 messages，追加 assistant 消息
        和 tool_result 消息。

        Args:
            messages:
                Anthropic 消息历史。

        Returns:
            模型最终文本；没有文本时返回 None。

        Raises:
            RuntimeError:
                模型协议异常，或者达到最大循环次数。

            Exception:
                LLM 调用等未被底层组件处理的异常。
        """
        agent_started_at = perf_counter()
        completed_turns = 0

        self._emit(
            AgentEvent(
                type=AgentEventType.AGENT_STARTED,
                message="正在处理请求",
                data={"turn": 0, "max_turns": self._max_turns},
            )
        )

        try:
            for turn in range(1, self._max_turns + 1):
                completed_turns = turn

                response = self._request_model(messages=messages, turn=turn)

                # 必须先保存完整 assistant 响应。
                # 其中可能同时包含 text 和 tool_use。
                messages.append({"role": "assistant", "content": response.content})

                if response.stop_reason != "tool_use":
                    final_text = self._extract_text(response.content)

                    self._emit(
                        AgentEvent(
                            type=AgentEventType.AGENT_COMPLETED,
                            message="Agent 处理完成",
                            data={
                                "turns": turn,
                                "final_text": final_text,
                                "duration_seconds": perf_counter() - agent_started_at,
                            },
                        )
                    )
                    return final_text

                tool_results = self._execute_tool_calls(content=response.content)

                if not tool_results:
                    raise RuntimeError(
                        "模型 stop_reason=tool_use，"
                        "但 response.content 中没有 tool_use 内容块"
                    )

                messages.append({"role": "user", "content": tool_results})

            raise RuntimeError(f"Agent 超过最大循环次数：{self._max_turns}")

        except Exception as exc:
            self._emit(
                AgentEvent(
                    type=AgentEventType.AGENT_FAILED,
                    message=str(exc),
                    data={
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                        "turns": completed_turns,
                        "duration_seconds": perf_counter() - agent_started_at,
                    },
                )
            )
            raise

    def _request_model(self, *, messages: list[dict[str, Any]], turn: int) -> Any:
        """
        发起一轮流式模型请求，并发送对应事件。
        """
        self._emit(
            AgentEvent(
                type=AgentEventType.LLM_STARTED,
                message="正在请求模型",
                data={"turn": turn, "max_turns": self._max_turns},
            )
        )

        llm_started_at = perf_counter()

        response = self._llm_client.stream_message(
            system=self._system_prompt,
            messages=messages,
            tools=self._tool_registry.get_definitions(),
            on_text_delta=lambda text: self._emit_text_delta(text=text, turn=turn),
        )

        duration_seconds = perf_counter() - llm_started_at
        usage = getattr(response, "usage", None)

        self._emit(
            AgentEvent(
                type=AgentEventType.LLM_COMPLETED,
                message="模型调用完成",
                data={
                    "turn": turn,
                    "max_turns": self._max_turns,
                    "stop_reason": getattr(response, "stop_reason", None),
                    "input_tokens": self._get_usage_value(usage, "input_tokens"),
                    "output_tokens": self._get_usage_value(usage, "output_tokens"),
                    "duration_seconds": duration_seconds,
                },
            )
        )
        return response

    def _emit_text_delta(self, *, text: str, turn: int) -> None:
        """
        将模型流式文本转换为 TEXT_DELTA 事件。
        """
        if not text:
            return
        self._emit(
            AgentEvent(
                type=AgentEventType.TEXT_DELTA,
                message=text,
                data={"turn": turn},
            )
        )

    def _execute_tool_calls(self, *, content: list[Any]) -> list[dict[str, Any]]:
        """
        执行模型本轮返回的全部 tool_use 内容块。

        单个工具返回错误结果时，不会中断后续工具调用；
        错误会通过 is_error=True 返回给模型。
        """
        tool_results: list[dict[str, Any]] = []
        for block in content:
            if getattr(block, "type", None) != "tool_use":
                continue

            tool_use_id = str(getattr(block, "id", ""))
            tool_name = str(getattr(block, "name", ""))
            arguments = self._normalize_arguments(getattr(block, "input", {}))

            self._emit(
                AgentEvent(
                    type=AgentEventType.TOOL_STARTED,
                    message=f"正在执行工具 {tool_name}",
                    data={
                        "tool_use_id": tool_use_id,
                        "tool_name": tool_name,
                        "arguments": arguments,
                    },
                )
            )

            tool_started_at = perf_counter()
            result = self._tool_registry.dispatch(name=tool_name, arguments=arguments)
            duration_seconds = perf_counter() - tool_started_at
            event_type = AgentEventType.TOOL_FAILED if result.is_error else AgentEventType.TOOL_COMPLETED

            self._emit(
                AgentEvent(
                    type=event_type,
                    message=result.content,
                    data={
                        "tool_use_id": tool_use_id,
                        "tool_name": tool_name,
                        "arguments": arguments,
                        "content": result.content,
                        "duration_seconds": duration_seconds,
                    },
                )
            )

            tool_result = {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": result.content,
            }
            if result.is_error:
                tool_result["is_error"] = True
            tool_results.append(tool_result)
        return tool_results

    def _emit(self, event: AgentEvent) -> None:
        """
        向外部监听器发送事件。

        显示层属于观察者。显示层出现异常时，不应导致
        Agent、工具或 LLM 请求失败，因此这里捕获事件
        处理器异常并记录日志。
        """
        if self._event_handler is None:
            return
        try:
            self._event_handler(event)
        except Exception:
            logger.exception("处理 AgentEvent 时发生异常：%s", event.type.value)

    @staticmethod
    def _normalize_arguments(arguments: Any) -> dict[str, Any]:
        """
        将工具参数规范化为字典。

        Anthropic tool_use.input 通常是 dict。
        这里兼容其他 Mapping 类型，并避免非字典输入
        直接导致 ToolRegistry 调用失败。
        """
        if isinstance(arguments, dict):
            return arguments
        if isinstance(arguments, Mapping):
            return dict(arguments)
        return {"value": arguments}

    @staticmethod
    def _get_usage_value(usage: Any, field_name: str) -> int | None:
        """
        安全读取 response.usage 中的 Token 数量。
        """
        value = getattr(usage, field_name, None)
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        return None

    @staticmethod
    def _extract_text(content: list[Any]) -> str | None:
        """
        从模型混合内容块中提取全部文本块。
        """
        texts = [
            block.text
            for block in content
            if getattr(block, "type", None) == "text" and isinstance(getattr(block, "text", None), str)
        ]
        if not texts:
            return None
        return "\n".join(texts)