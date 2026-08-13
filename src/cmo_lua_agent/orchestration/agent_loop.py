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
7. 按可选墙钟期限控制特殊任务，普通聊天不设置任意工具轮数上限；
8. 在失败时发出 AGENT_FAILED 事件。

边界约束：
- 不包含具体工具实现；
- 不执行权限判断；
- 不负责终端绘制；
- 不解析 CMO 或 Lua 错误；
- 不保存数据库或日志文件。
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from cmo_lua_agent.llm.client import ClaudeClient
from cmo_lua_agent.orchestration.context_manager import (
    ContextCompactionNotice,
    ContextManager,
)
from cmo_lua_agent.orchestration.events import AgentEvent, AgentEventType
from cmo_lua_agent.tools.tool_base.registry import ToolRegistry
from cmo_lua_agent.tools.tool_base.context import ToolContext
from cmo_lua_agent.tools.tool_base.progress import ToolProgressEvent, ToolProgressReporter


logger = logging.getLogger(__name__)

EventHandler = Callable[[AgentEvent], None]

_RECOVERY_TOOLS = frozenset({"read_file", "list_directory"})
_MAX_AUTOMATIC_RECOVERIES = 1


class AgentLoopDeadlineExceeded(TimeoutError):
    """单次 Agent 请求超过调用方给出的墙钟期限。"""


@dataclass(frozen=True, slots=True)
class AgentLoopPolicy:
    """控制通用循环的终止策略；默认值保持普通聊天的既有保护行为。"""

    use_chat_guards: bool = True
    deadline_seconds: float | None = None

    @classmethod
    def code_repair(cls, *, deadline_seconds: float = 1800) -> "AgentLoopPolicy":
        if deadline_seconds <= 0:
            raise ValueError("deadline_seconds 必须大于 0")
        return cls(use_chat_guards=False, deadline_seconds=deadline_seconds)


@dataclass
class _RunGuard:
    """记录一次用户请求内的工具失败，供模型收到结构化恢复提示。"""

    failures_by_call: dict[str, int] = field(default_factory=dict)
    attempted_tools: list[str] = field(default_factory=list)
    latest_error: str | None = None
    automatic_recoveries: int = 0


@dataclass
class _ToolExecutionOutcome:
    tool_results: list[dict[str, Any]]
    tool_names: list[str]
    stop_message: str | None = None


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
        max_turns: int | None = None,
        event_handler: EventHandler | None = None,
        run_policy: AgentLoopPolicy | None = None,
        context_manager: ContextManager | None = None,
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
        if max_turns is not None and max_turns < 1:
            raise ValueError("max_turns 必须大于等于 1")

        self._llm_client = llm_client
        self._tool_registry = tool_registry
        self._system_prompt = system_prompt
        self._max_turns = max_turns
        self._event_handler = event_handler
        self._run_policy = run_policy or AgentLoopPolicy()
        self._context_manager = context_manager

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
        safe_message_count = len(messages)
        guard = _RunGuard()

        self._emit(
            AgentEvent(
                type=AgentEventType.AGENT_STARTED,
                message="正在处理请求",
                data={"turn": 0, "max_turns": self._max_turns},
            )
        )

        try:
            turn = 0
            # Completion is driven by the model's final response or a
            # concrete guard outcome, never by an arbitrary request-turn cap.
            while True:
                if (
                    self._run_policy.deadline_seconds is not None
                    and perf_counter() - agent_started_at >= self._run_policy.deadline_seconds
                ):
                    raise AgentLoopDeadlineExceeded("Agent 修复已达到单次运行期限")
                turn += 1
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

                if self._run_policy.use_chat_guards:
                    outcome = self._execute_tool_calls(
                        content=response.content,
                        guard=guard,
                    )
                else:
                    outcome = _ToolExecutionOutcome(
                        tool_results=self._execute_tool_calls_legacy(
                            content=response.content
                        ),
                        tool_names=[],
                    )
                tool_results = outcome.tool_results

                if not tool_results:
                    raise RuntimeError(
                        "模型 stop_reason=tool_use，"
                        "但 response.content 中没有 tool_use 内容块"
                    )

                messages.append({"role": "user", "content": tool_results})
                safe_message_count = len(messages)

        except KeyboardInterrupt:
            # An interrupted tool call has no tool_result. Remove the
            # incomplete assistant tool_use so the next API request remains
            # protocol-valid.
            del messages[safe_message_count:]
            raise

        except Exception as exc:
            del messages[safe_message_count:]
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
        llm_started_at = perf_counter()

        tool_definitions = self._tool_registry.get_definitions()
        outbound_messages = (
            self._context_manager.build(
                messages,
                system_prompt=self._system_prompt,
                tools=tool_definitions,
                compaction_observer=lambda notice: self._emit_context_compaction(
                    notice=notice,
                    turn=turn,
                ),
            )
            if self._context_manager is not None
            else messages
        )
        self._emit(
            AgentEvent(
                type=AgentEventType.LLM_STARTED,
                message="正在请求模型",
                data={"turn": turn, "max_turns": self._max_turns},
            )
        )
        response = self._llm_client.stream_message(
            system=self._system_prompt,
            messages=outbound_messages,
            tools=tool_definitions,
            on_text_delta=lambda text: self._emit_text_delta(text=text, turn=turn),
        )

        duration_seconds = perf_counter() - llm_started_at
        usage = getattr(response, "usage", None)
        input_tokens = self._get_usage_value(usage, "input_tokens")
        if self._context_manager is not None:
            self._context_manager.observe_usage(input_tokens)

        self._emit(
            AgentEvent(
                type=AgentEventType.LLM_COMPLETED,
                message="模型调用完成",
                data={
                    "turn": turn,
                    "max_turns": self._max_turns,
                    "stop_reason": getattr(response, "stop_reason", None),
                    "input_tokens": input_tokens,
                    "output_tokens": self._get_usage_value(usage, "output_tokens"),
                    "duration_seconds": duration_seconds,
                },
            )
        )
        return response

    def _emit_context_compaction(
        self,
        *,
        notice: ContextCompactionNotice,
        turn: int,
    ) -> None:
        """把 ContextManager 的无界面通知转换为统一 AgentEvent。"""

        event_type = (
            AgentEventType.CONTEXT_COMPACTION_STARTED
            if notice.phase == "started"
            else AgentEventType.CONTEXT_COMPACTION_COMPLETED
        )
        self._emit(
            AgentEvent(
                type=event_type,
                message=event_type.display_name,
                data={
                    "turn": turn,
                    "estimated_tokens_before": notice.estimated_tokens_before,
                    "estimated_tokens_after": notice.estimated_tokens_after,
                    "context_window_tokens": notice.context_window_tokens,
                    "target_tokens": notice.target_tokens,
                    "retained_message_count": notice.retained_message_count,
                    "duration_seconds": notice.duration_seconds,
                    "strategy": notice.strategy,
                    "fallback_reason": notice.fallback_reason,
                },
            )
        )

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

    #执行模型本轮需要执行的全部工具。
    def _execute_tool_calls_legacy(self, *, content: list[Any]) -> list[dict[str, Any]]:
        """
        执行模型本轮需要执行的全部工具。

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
            reporter = ToolProgressReporter(
                tool_use_id=tool_use_id,
                tool_name=tool_name,
                callback=self._emit_tool_progress,
            )
            #分发并执行
            result = self._tool_registry.dispatch(
                name=tool_name,
                arguments=arguments,
                context=ToolContext(
                    tool_use_id=tool_use_id,
                    tool_name=tool_name,
                    progress=reporter,
                ),
            )
            duration_seconds = perf_counter() - tool_started_at
            event_type = AgentEventType.TOOL_FAILED if result.is_error else AgentEventType.TOOL_COMPLETED

            #通过emit
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

    def _execute_tool_calls(
        self,
        *,
        content: list[Any],
        guard: _RunGuard,
    ) -> _ToolExecutionOutcome:
        """执行一批工具调用，并对可安全更正的读/目录误用做一次恢复。"""
        tool_results: list[dict[str, Any]] = []
        tool_names: list[str] = []
        stop_message: str | None = None
        for block in content:
            if getattr(block, "type", None) != "tool_use":
                continue

            tool_use_id = str(getattr(block, "id", ""))
            tool_name = str(getattr(block, "name", ""))
            arguments = self._normalize_arguments(getattr(block, "input", {}))
            tool_names.append(tool_name)
            guard.attempted_tools.append(tool_name)
            result, _ = self._dispatch_tool(
                tool_use_id=tool_use_id,
                name=tool_name,
                arguments=arguments,
            )

            content_for_model = result.content
            is_error_for_model = result.is_error
            call_key = self._tool_call_key(tool_name, arguments)
            if result.is_error:
                guard.failures_by_call[call_key] = (
                    guard.failures_by_call.get(call_key, 0) + 1
                )
                guard.latest_error = self._error_message(result.content)
                recovered = self._try_automatic_recovery(
                    original_tool_use_id=tool_use_id,
                    original_tool_name=tool_name,
                    original_arguments=arguments,
                    original_content=result.content,
                    guard=guard,
                )
                if recovered is not None:
                    recovery_name, recovery_result = recovered
                    tool_names.append(recovery_name)
                    guard.attempted_tools.append(recovery_name)
                    content_for_model = self._recovery_payload(
                        original_tool_name=tool_name,
                        original_content=result.content,
                        recovery_tool_name=recovery_name,
                        recovery_content=recovery_result.content,
                        recovery_success=not recovery_result.is_error,
                    )
                    is_error_for_model = recovery_result.is_error
                    if recovery_result.is_error:
                        guard.latest_error = self._error_message(
                            recovery_result.content
                        )
                if guard.failures_by_call[call_key] >= 2:
                    content_for_model = json.dumps(
                        {
                            "error": "repeated_identical_failure",
                            "tool": tool_name,
                            "arguments": arguments,
                            "latest_error": guard.latest_error,
                            "instruction": (
                                "相同工具和参数已经重复失败。不要再次原样调用；"
                                "请重新分析，改用其他工具，或向用户明确说明缺少什么信息。"
                            ),
                        },
                        ensure_ascii=False,
                    )
                    is_error_for_model = True
            else:
                # 失败计数描述的是“连续相同失败”，中间成功必须打断该序列。
                guard.failures_by_call.pop(call_key, None)
                guard.latest_error = None

            tool_results.append(
                self._tool_result(
                    tool_use_id=tool_use_id,
                    content=content_for_model,
                    is_error=is_error_for_model,
                )
            )

        return _ToolExecutionOutcome(
            tool_results=tool_results,
            tool_names=tool_names,
            stop_message=stop_message,
        )

    def _dispatch_tool(
        self,
        *,
        tool_use_id: str,
        name: str,
        arguments: dict[str, Any],
        parent_tool_use_id: str | None = None,
    ) -> tuple[Any, float]:
        """Dispatch one tool and emit its terminal lifecycle."""
        started_data: dict[str, Any] = {
            "tool_use_id": tool_use_id,
            "tool_name": name,
            "arguments": arguments,
        }
        if parent_tool_use_id is not None:
            started_data["parent_tool_use_id"] = parent_tool_use_id
            started_data["recovery"] = True
        self._emit(
            AgentEvent(
                type=AgentEventType.TOOL_STARTED,
                message=f"正在执行工具 {name}",
                data=started_data,
            )
        )
        tool_started_at = perf_counter()
        reporter = ToolProgressReporter(
            tool_use_id=tool_use_id,
            tool_name=name,
            callback=self._emit_tool_progress,
        )
        result = self._tool_registry.dispatch(
            name=name,
            arguments=arguments,
            context=ToolContext(
                tool_use_id=tool_use_id,
                tool_name=name,
                progress=reporter,
            ),
        )
        duration_seconds = perf_counter() - tool_started_at
        self._emit(
            AgentEvent(
                type=(
                    AgentEventType.TOOL_FAILED
                    if result.is_error
                    else AgentEventType.TOOL_COMPLETED
                ),
                message=result.content,
                data={
                    **started_data,
                    "content": result.content,
                    "duration_seconds": duration_seconds,
                },
            )
        )
        return result, duration_seconds

    def _try_automatic_recovery(
        self,
        *,
        original_tool_use_id: str,
        original_tool_name: str,
        original_arguments: dict[str, Any],
        original_content: str,
        guard: _RunGuard,
    ) -> tuple[str, Any] | None:
        if guard.automatic_recoveries >= _MAX_AUTOMATIC_RECOVERIES:
            return None
        suggested_tool = self._suggested_tool(original_content)
        if (
            suggested_tool not in _RECOVERY_TOOLS
            or suggested_tool == original_tool_name
            or not isinstance(original_arguments.get("path"), str)
        ):
            return None
        get_tool = getattr(self._tool_registry, "get", None)
        original = get_tool(original_tool_name) if callable(get_tool) else None
        suggested = get_tool(suggested_tool) if callable(get_tool) else None
        if (
            original is None
            or suggested is None
            or getattr(original, "requires_approval", True)
            or getattr(suggested, "requires_approval", True)
        ):
            return None

        recovery_arguments: dict[str, Any] = {"path": original_arguments["path"]}
        limit = original_arguments.get("limit")
        if isinstance(limit, int) and not isinstance(limit, bool):
            if suggested_tool == "list_directory" and 1 <= limit <= 200:
                recovery_arguments["limit"] = limit
            elif suggested_tool == "read_file" and limit >= 1:
                recovery_arguments["limit"] = limit
        guard.automatic_recoveries += 1
        recovery_result, _ = self._dispatch_tool(
            tool_use_id=f"{original_tool_use_id}:recovery",
            name=suggested_tool,
            arguments=recovery_arguments,
            parent_tool_use_id=original_tool_use_id,
        )
        return suggested_tool, recovery_result

    @staticmethod
    def _tool_result(
        *,
        tool_use_id: str,
        content: str,
        is_error: bool,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": content,
        }
        if is_error:
            result["is_error"] = True
        return result

    @staticmethod
    def _tool_call_key(name: str, arguments: dict[str, Any]) -> str:
        arguments_text = json.dumps(
            arguments,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        return f"{name}:{arguments_text}"

    @staticmethod
    def _error_message(content: str) -> str:
        try:
            payload = json.loads(content)
        except (TypeError, ValueError):
            return content
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return error["message"]
        return content

    @staticmethod
    def _suggested_tool(content: str) -> str | None:
        try:
            payload = json.loads(content)
        except (TypeError, ValueError):
            return None
        error = payload.get("error") if isinstance(payload, dict) else None
        value = error.get("suggested_tool") if isinstance(error, dict) else None
        return value if isinstance(value, str) else None

    @staticmethod
    def _recovery_payload(
        *,
        original_tool_name: str,
        original_content: str,
        recovery_tool_name: str,
        recovery_content: str,
        recovery_success: bool,
    ) -> str:
        def decode(content: str) -> Any:
            try:
                return json.loads(content)
            except (TypeError, ValueError):
                return content

        return json.dumps(
            {
                "success": recovery_success,
                "recovered_from": {
                    "tool": original_tool_name,
                    "result": decode(original_content),
                },
                "recovery": {
                    "tool": recovery_tool_name,
                    "result": decode(recovery_content),
                },
            },
            ensure_ascii=False,
        )

    def _emit_tool_progress(self, progress: ToolProgressEvent) -> None:
        self._emit(
            AgentEvent(
                type=AgentEventType.TOOL_PROGRESS,
                message=progress.message,
                data={
                    "tool_use_id": progress.tool_use_id,
                    "tool_name": progress.tool_name,
                    "event_type": progress.event_type,
                    "status": progress.status,
                    "detail": progress.detail,
                    "progress": progress.progress,
                    "step_id": progress.step_id,
                    "parent_step_id": progress.parent_step_id,
                    "metadata": progress.metadata,
                },
            )
        )

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
