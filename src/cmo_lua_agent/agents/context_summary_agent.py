"""使用当前 LLM 端点生成可继续执行任务的语义上下文摘要。

上游 ``ContextManager`` 只在请求达到压缩阈值后调用本 Agent。它通过已有
``ClaudeJsonClient`` 发起一次无工具请求，校验稳定字段后返回规范 JSON 文本。
本模块不判断压缩阈值、不修改会话历史，也不运行完整 ``AgentLoop``，因此不会形成
“压缩过程再次触发压缩”的递归。
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Protocol


class JsonSummaryClient(Protocol):
    """摘要 Agent 所需的最小 LLM JSON 接口。"""

    def complete_json(self, *, system: str, prompt: str) -> object:
        ...


_SYSTEM_PROMPT = """你是 Agent 上下文压缩器。请把较早对话压缩为后续 Agent 可以直接继续执行任务的结构化摘要。

必须保留：
1. 用户当前目标和原始任务；
2. 已确认的需求、约束和偏好；
3. 已完成工作及验证结果；
4. 当前执行状态；
5. 关键文件、路径、ID、参数、错误和工具产生的重要事实；
6. 尚未解决的问题与明确的下一步；
7. 已失败方案及失败原因。

必须遵守：
1. 不得调用任何工具，只能根据输入内容生成摘要；
2. 不得添加原对话中不存在的信息；
3. 不得猜测用户意图，不能把不确定信息写成确定事实；
4. 不得省略会影响后续执行的技术细节；
5. 大型工具输出只保留结论、路径、关键错误和重新读取方式，不复制无关原文；
6. 只输出一个 JSON 对象，不要 Markdown 代码块或额外说明。

JSON 字段必须完整：
{
  "goal": "字符串",
  "constraints": ["字符串"],
  "completed": ["字符串"],
  "current_state": "字符串",
  "important_facts": ["字符串"],
  "open_issues": ["字符串"],
  "next_steps": ["字符串"],
  "failed_attempts": ["字符串"]
}
"""

_STRING_FIELDS = ("goal", "current_state")
_LIST_FIELDS = (
    "constraints",
    "completed",
    "important_facts",
    "open_issues",
    "next_steps",
    "failed_attempts",
)


class ContextSummaryAgent:
    """将较早协议消息转换为严格、可复用的中文 JSON 摘要。"""

    def __init__(self, client: JsonSummaryClient) -> None:
        self._client = client

    def summarize(self, messages: Sequence[Mapping[str, Any]]) -> str:
        """摘要旧消息并返回规范 JSON；非法模型输出直接交给上游降级。"""

        payload = self._client.complete_json(
            system=_SYSTEM_PROMPT,
            prompt=(
                "以下是需要压缩的较早对话消息。请严格按照系统要求生成摘要：\n"
                + json.dumps(
                    list(messages),
                    ensure_ascii=False,
                    default=str,
                    separators=(",", ":"),
                )
            ),
        )
        if not isinstance(payload, Mapping):
            raise ValueError("上下文摘要必须是 JSON 对象")

        normalized = dict(payload)
        for field in _STRING_FIELDS:
            if not isinstance(normalized.get(field), str):
                raise ValueError(f"上下文摘要字段 {field} 必须是字符串")
        for field in _LIST_FIELDS:
            value = normalized.get(field)
            if not isinstance(value, list) or any(
                not isinstance(item, str) for item in value
            ):
                raise ValueError(f"上下文摘要字段 {field} 必须是字符串数组")

        return json.dumps(
            {field: normalized[field] for field in (*_STRING_FIELDS, *_LIST_FIELDS)},
            ensure_ascii=False,
            separators=(",", ":"),
        )


__all__ = ["ContextSummaryAgent", "JsonSummaryClient"]
