"""在接近模型上下文上限时才压缩请求副本。

设计目标：

1. ``ChatSessionStore`` 始终保存完整历史，不因为压缩而丢失原始对话。
2. ``AgentLoop`` 每轮只把“本次请求副本”交给 ContextManager 处理。
3. 估算 system、tools、messages 的总上下文大小。
4. 低于 80% 上下文窗口时，消息原样发送。
5. 达到阈值后，把较早消息压缩成摘要，同时保留最近消息。
6. 使用模型实际返回的 ``input_tokens`` 校准下一轮估算，
   避免把字符数估算误认为精确 tokenizer 结果。

所以这个类本质上是：

    完整会话历史
        ↓
    ContextManager
        ↓
    本轮可发送的请求副本

它只影响“发给模型什么”，不会反向修改持久化会话。
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Protocol


class ContextSummarizer(Protocol):
    """ContextManager 所需的语义摘要接口，具体 LLM 装配留给入口层。"""

    def summarize(self, messages: Sequence[Mapping[str, Any]]) -> str:
        ...


@dataclass(frozen=True, slots=True)
class ContextCompactionNotice:
    """上下文压缩观察通知；只携带统计事实，不暴露对话正文。"""

    phase: str
    estimated_tokens_before: int
    context_window_tokens: int
    target_tokens: int
    estimated_tokens_after: int | None = None
    retained_message_count: int | None = None
    duration_seconds: float | None = None
    strategy: str | None = None
    fallback_reason: str | None = None


class ContextManager:
    """根据上下文占用情况构建本轮模型请求，不修改原始会话历史。"""

    def __init__(
        self,
        *,
        context_window_tokens: int = 1_000_000,
        compression_threshold_ratio: float = 0.8,
        compression_target_ratio: float = 0.6,
        recent_message_count: int = 12,
        summarizer: ContextSummarizer | None = None,
    ) -> None:
        """初始化上下文管理策略。

        参数说明：

        context_window_tokens:
            模型最大上下文窗口。

        compression_threshold_ratio:
            达到多少比例后开始压缩。
            默认 0.8，即预计达到 80% 时触发压缩。

        compression_target_ratio:
            压缩后的目标占用比例。
            默认 0.6，希望压缩后回到约 60%。

        recent_message_count:
            压缩时至少保留最近多少条消息原文。
        """

        if context_window_tokens < 1:
            raise ValueError("上下文窗口 Token 数必须大于 0")

        if not 0 < compression_target_ratio < compression_threshold_ratio < 1:
            raise ValueError(
                "上下文压缩比例配置无效：必须满足 "
                "0 < compression_target_ratio < compression_threshold_ratio < 1"
            )

        if recent_message_count < 1:
            raise ValueError("最近保留消息数量必须大于 0")

        self._window = context_window_tokens
        self._threshold = compression_threshold_ratio
        self._target = compression_target_ratio
        self._recent = recent_message_count
        self._summarizer = summarizer

        # 字符估算和真实 Token 数不会完全一致。
        # 初始先乘 1.15 留一点安全余量，
        # 后续再根据模型真实 input_tokens 自动校准。
        self._calibration = 1.15

        # 保存最近一次“未经校准的原始估算”，
        # 供 observe_usage() 和真实 Token 数进行比较。
        self._last_raw_estimate: float | None = None

        # 完整历史由调用方持有；这里只缓存“摘要 + 压缩后新增消息”的活动请求副本。
        # 同一 messages 列表继续追加时可以复用摘要，避免每个工具轮次重复调用摘要模型。
        self._active_source: Sequence[Mapping[str, Any]] | None = None
        self._active_source_count = 0
        self._active_messages: list[dict[str, Any]] | None = None

    def build(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        system_prompt: str = "",
        tools: Sequence[Mapping[str, Any]] | None = None,
        training_summary: Mapping[str, Any] | None = None,
        compaction_observer: Callable[[ContextCompactionNotice], None] | None = None,
    ) -> list[dict[str, Any]]:
        """构建本轮真正发送给模型的 messages。

        正常情况下直接返回消息副本。

        只有预计上下文达到阈值时，
        才把较早消息压缩成摘要。

        原始 messages 不会被修改。
        """

        # 复制一份消息。
        # ContextManager 后续只操作副本，不能污染 ChatSessionStore 中的完整历史。
        copied = [dict(message) for message in messages]

        can_reuse_active = (
            training_summary is None
            and self._active_source is messages
            and self._active_messages is not None
            and len(messages) >= self._active_source_count
        )
        if can_reuse_active:
            # 压缩后完整历史仍会继续追加。只把新增部分接到活动摘要后面，
            # 直到这份活动上下文再次达到阈值才进行下一次语义压缩。
            copied = [
                *(dict(message) for message in self._active_messages or []),
                *(dict(message) for message in messages[self._active_source_count :]),
            ]
        elif (
            self._active_source is not messages
            or len(messages) < self._active_source_count
        ):
            self._clear_active_context()

        # training_summary 是额外的工作流上下文。
        # 如果存在，把它包装成一条用户消息放到请求最前面。
        if training_summary is not None:
            copied = [
                {
                    "role": "user",
                    "content": (
                        "Training workflow:\n"
                        + json.dumps(
                            dict(training_summary),
                            ensure_ascii=False,
                            sort_keys=True,
                        )
                    ),
                },
                *copied,
            ]

        # 估算完整请求大小。
        # 注意这里不仅计算 messages，
        # system prompt 和 tools schema 同样会占模型上下文。
        raw = self._raw_request_estimate(
            copied,
            system_prompt,
            tools or [],
        )

        self._last_raw_estimate = raw

        # 使用校准系数后仍未达到 80%，说明空间足够。
        # 直接发送完整消息，不进行任何压缩。
        if (
            math.ceil(raw * self._calibration)
            < self._window * self._threshold
        ):
            if can_reuse_active:
                self._active_messages = [dict(message) for message in copied]
                self._active_source_count = len(messages)
            return copied

        # 是否触发压缩由 ContextManager 单独判断。观察者只接收统计事实，
        # AgentLoop/终端无需复制阈值算法，也不会接触被摘要的消息正文。
        estimated_before = max(1, math.ceil(raw * self._calibration))
        target_tokens = int(self._window * self._target)
        if compaction_observer is not None:
            compaction_observer(
                ContextCompactionNotice(
                    phase="started",
                    estimated_tokens_before=estimated_before,
                    context_window_tokens=self._window,
                    target_tokens=target_tokens,
                )
            )

        compaction_started_at = perf_counter()
        compacted, retained_message_count, strategy, fallback_reason = self._compact(
            copied,
            system_prompt,
            tools or [],
        )

        if training_summary is None:
            self._active_source = messages
            self._active_source_count = len(messages)
            self._active_messages = [dict(message) for message in compacted]

        # 压缩完成后重新记录本次原始估算，
        # 下一次 observe_usage() 可以用真实 Token 对它进行校准。
        self._last_raw_estimate = self._raw_request_estimate(
            compacted,
            system_prompt,
            tools or [],
        )

        if compaction_observer is not None:
            compaction_observer(
                ContextCompactionNotice(
                    phase="completed",
                    estimated_tokens_before=estimated_before,
                    context_window_tokens=self._window,
                    target_tokens=target_tokens,
                    estimated_tokens_after=max(
                        1,
                        math.ceil(self._last_raw_estimate * self._calibration),
                    ),
                    retained_message_count=retained_message_count,
                    duration_seconds=perf_counter() - compaction_started_at,
                    strategy=strategy,
                    fallback_reason=fallback_reason,
                )
            )

        return compacted

    def _clear_active_context(self) -> None:
        """切换会话或历史回退时丢弃请求缓存，不触碰调用方的完整消息。"""

        self._active_source = None
        self._active_source_count = 0
        self._active_messages = None

    def estimate_request_tokens(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        system_prompt: str = "",
        tools: Sequence[Mapping[str, Any]] | None = None,
    ) -> int:
        """估算一次完整模型请求大约需要多少 Token。

        估算范围包括：

        - system prompt
        - tool schemas
        - messages

        这里不是精确 tokenizer，
        而是“字符估算 × 动态校准系数”。
        """

        raw = self._raw_request_estimate(
            messages,
            system_prompt,
            tools or [],
        )

        return max(
            1,
            math.ceil(raw * self._calibration),
        )

    def observe_usage(
        self,
        actual_input_tokens: int | None,
    ) -> None:
        """使用模型实际返回的输入 Token 数校准后续估算。

        例如：

        字符模型估算：
            10000

        模型实际返回：
            12000 input_tokens

        那么新的校准系数大约就是：

            12000 / 10000 = 1.2

        后续估算就会更贴近真实模型。
        """

        # 没有真实 Token 数据，或者之前没有估算结果时，
        # 没有办法进行校准。
        if (
            actual_input_tokens is None
            or actual_input_tokens < 1
            or not self._last_raw_estimate
        ):
            return

        observed = (
            actual_input_tokens
            / self._last_raw_estimate
        )

        # 限制校准系数范围，
        # 避免某一次异常统计导致整个估算系统失控。
        self._calibration = min(
            3.0,
            max(0.5, observed),
        )

    def _compact(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: Sequence[Mapping[str, Any]],
    ) -> tuple[list[dict[str, Any]], int, str, str | None]:
        """压缩较早历史，只保留最近消息原文。

        最终结构大致变成：

            较早对话摘要
            +
            最近若干条完整消息

        完整会话历史仍然保存在 ChatSessionStore 中。
        """

        # 默认把最近 recent_message_count 条消息原样保留。
        boundary = max(
            0,
            len(messages) - self._recent,
        )

        # Claude 的工具协议中：
        #
        # assistant tool_use
        # ↓
        # user tool_result
        #
        # 是一组关联消息。
        #
        # 如果刚好在 tool_result 前切开，
        # 会导致模型收到一个“没有对应 tool_use 的 tool_result”。
        #
        # 因此如果边界落在 tool_result，
        # 就额外向前保留一条。
        if (
            boundary
            and self._contains_tool_result(
                messages[boundary]
            )
        ):
            boundary -= 1

        older = messages[:boundary]
        recent = messages[boundary:]

        # 没有旧消息需要压缩。
        if not older:
            return recent, len(recent), "none", None

        # 压缩后的目标大小。
        # 默认希望降到整个上下文窗口的 60% 左右。
        target = int(
            self._window * self._target
        )

        fallback_reason: str | None = None
        if self._summarizer is not None:
            try:
                semantic_summary = self._summarizer.summarize(older)
                if not isinstance(semantic_summary, str) or not semantic_summary.strip():
                    raise ValueError("语义摘要为空")
                prefix = "较早对话语义摘要（完整历史仍保存在会话文件中）：\n"
                summary = prefix + semantic_summary.strip()
                strategy = "semantic"
            except Exception as exc:
                # 摘要端点只是辅助能力。失败时保留主 Agent 的可用性，
                # 并仅暴露异常类型给终端，避免错误信息携带对话正文或密钥。
                fallback_reason = type(exc).__name__
                prefix, summary = self._deterministic_summary(older)
                strategy = "deterministic_fallback"
        else:
            prefix, summary = self._deterministic_summary(older)
            strategy = "deterministic"

        compacted = [
            {
                "role": "user",
                "content": summary,
            },
            *recent,
        ]

        # 如果简单摘要后仍然太大，
        # 就继续按字符长度裁剪摘要。
        #
        # 注意：
        # 这里删的是“请求副本中的摘要”，
        # 不是持久化的原始会话历史。
        while (
            self.estimate_request_tokens(
                compacted,
                system_prompt=system_prompt,
                tools=tools,
            )
            > target
            and len(summary) > len(prefix) + 32
        ):
            current_estimate = (
                self.estimate_request_tokens(
                    compacted,
                    system_prompt=system_prompt,
                    tools=tools,
                )
            )

            # 根据当前超出的比例，
            # 估算摘要应该缩短到多少长度。
            excess_ratio = (
                target
                / max(1, current_estimate)
            )

            # 再乘 0.95 留一点余量，
            # 防止刚好卡在目标边界。
            new_length = max(
                len(prefix) + 32,
                int(
                    len(summary)
                    * excess_ratio
                    * 0.95
                ),
            )

            summary = (
                summary[:new_length]
                + "\n……摘要已缩短"
            )

            compacted[0] = {
                "role": "user",
                "content": summary,
            }

        return compacted, len(recent), strategy, fallback_reason

    def _deterministic_summary(
        self,
        messages: Sequence[Mapping[str, Any]],
    ) -> tuple[str, str]:
        """模型摘要不可用时生成可复现的兜底摘要，保证主流程仍能继续。"""

        prefix = "较早对话摘要（确定性降级摘要；完整历史仍保存在会话文件中）：\n"
        rows = [self._summary_row(message) for message in messages]
        return prefix, prefix + "\n".join(rows)

    @staticmethod
    def _contains_tool_result(
        message: Mapping[str, Any],
    ) -> bool:
        """判断消息中是否包含 Claude 的 tool_result 协议块。"""

        content = message.get("content")

        return (
            isinstance(content, list)
            and any(
                isinstance(block, Mapping)
                and block.get("type") == "tool_result"
                for block in content
            )
        )

    @staticmethod
    def _summary_row(
        message: Mapping[str, Any],
    ) -> str:
        """把一条旧消息压缩成摘要中的一行。

        每条消息最多保留前 400 个字符，
        防止某一次巨大工具结果撑爆摘要。
        """

        content = message.get(
            "content",
            "",
        )

        # 普通文本直接使用。
        #
        # tool_use / tool_result 等结构化内容，
        # 转换成 JSON 文本后再进入摘要。
        text = (
            content
            if isinstance(content, str)
            else json.dumps(
                content,
                ensure_ascii=False,
                default=str,
            )
        )

        role = message.get(
            "role",
            "unknown",
        )

        return (
            f"{role}: {text[:400]}"
        )

    @classmethod
    def _raw_request_estimate(
        cls,
        messages: Sequence[Mapping[str, Any]],
        system_prompt: str,
        tools: Sequence[Mapping[str, Any]],
    ) -> float:
        """根据字符粗略估算整个请求的 Token 数。

        不依赖 Claude 专用 tokenizer，
        因此这里故意只做近似估算。

        ASCII 字符：
            每个约计 0.3 Token

        非 ASCII 字符（例如中文）：
            每个约计 0.6 Token

        最终还会乘以动态 calibration 系数。
        """

        # 把真正会发给模型的主要内容放到同一个结构里，
        # 避免只计算 messages 而漏掉 system 和 tools。
        payload = json.dumps(
            {
                "system": system_prompt,
                "tools": list(tools),
                "messages": list(messages),
            },
            ensure_ascii=False,
            default=str,
            separators=(",", ":"),
        )

        return sum(
            0.3
            if ord(character) < 128
            else 0.6
            for character in payload
        )


__all__ = [
    "ContextCompactionNotice",
    "ContextManager",
    "ContextSummarizer",
]
