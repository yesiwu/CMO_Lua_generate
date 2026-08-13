"""Claude 非流式客户端的严格 JSON 输出适配层。

这个文件不负责 Agent 推理，也不负责业务逻辑。

它只做一件事：
要求 Claude 返回“可以直接被程序使用的 JSON 对象”。

如果 Claude 返回多余说明、非法 JSON、空内容等，
就立即报错，避免脏数据继续流入后面的工作流。
"""

from __future__ import annotations

import json
import hashlib
import re
from collections.abc import Mapping
from typing import Protocol


class MessageClient(Protocol):
    """规定底层 LLM 客户端至少需要提供 create_message()。"""

    def create_message(
        self,
        *,
        system: str,
        messages: list[dict[str, object]],
    ) -> object:
        ...


class JsonCompletionError(ValueError):
    """模型返回的 JSON 不符合要求时抛出。

    不保存完整模型响应，只保存长度、错误位置、哈希等诊断信息，
    避免日志中泄露完整模型输出。
    """

    code = "proposal_json_invalid"

    def __init__(self, diagnostics: Mapping[str, object]) -> None:
        self.diagnostics = dict(diagnostics)
        super().__init__(self.code)


class ClaudeJsonClient:
    """在普通 ClaudeClient 外面增加严格 JSON / 文本输出能力。"""

    def __init__(self, client: MessageClient) -> None:
        self._client = client

    def complete_json(
        self,
        *,
        system: str,
        prompt: str,
    ) -> object:
        """调用 Claude，并要求最终结果必须是一个 JSON 对象。"""

        message = self._client.create_message(
            system=system,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        # 当前接口要求只能返回一个内容块，
        # 避免同时出现文本、工具调用等复杂结果。
        content = getattr(message, "content", None)

        if not isinstance(content, list) or len(content) != 1:
            raise JsonCompletionError(
                _diagnostics(
                    None,
                    response_type=type(content).__name__,
                )
            )

        text = getattr(content[0], "text", None)

        # 返回内容必须是非空文本
        if not isinstance(text, str) or not text.strip():
            raise JsonCompletionError(
                _diagnostics(
                    text,
                    response_type=type(text).__name__,
                )
            )

        # 支持两种合法形式：
        # 1. 直接返回 {...}
        # 2. ```json ... ``` 包裹的 JSON
        payload, trailing_text = _json_payload(text)

        try:
            value = json.loads(payload)

        except json.JSONDecodeError as exc:
            # JSON语法错误时记录错误位置，方便定位 Prompt/模型输出问题
            raise JsonCompletionError(
                _diagnostics(
                    text,
                    decoder_message=exc.msg,
                    decoder_line=exc.lineno,
                    decoder_column=exc.colno,
                    has_trailing_text=(
                        trailing_text
                        or exc.msg == "Extra data"
                    ),
                )
            ) from exc

        # 即使JSON本身合法，只要前后夹了额外解释文字也拒绝
        if trailing_text:
            raise JsonCompletionError(
                _diagnostics(
                    text,
                    has_trailing_text=True,
                )
            )

        # 系统要求顶层必须是JSON对象：
        # {} 可以，[] / "abc" / 123 不可以。
        if not isinstance(value, Mapping):
            raise JsonCompletionError(
                _diagnostics(text)
            )

        return dict(value)

    def complete_text(
        self,
        *,
        system: str,
        prompt: str,
    ) -> str:
        """普通文本模式：只要求 Claude 返回单个非空文本块。"""

        message = self._client.create_message(
            system=system,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        content = getattr(message, "content", None)

        if not isinstance(content, list) or len(content) != 1:
            raise JsonCompletionError(
                _diagnostics(
                    None,
                    response_type=type(content).__name__,
                )
            )

        text = getattr(content[0], "text", None)

        if not isinstance(text, str) or not text.strip():
            raise JsonCompletionError(
                _diagnostics(
                    text,
                    response_type=type(text).__name__,
                )
            )

        return text.strip() + "\n"


# 允许这种格式：
#
# ```json
# {"a": 1}
# ```
_FENCED_JSON = re.compile(
    r"\A\s*```json[ \t]*\r?\n(?P<body>.*?)\r?\n```\s*\Z",
    re.DOTALL,
)


def _json_payload(text: str) -> tuple[str, bool]:
    """从模型文本中提取 JSON 内容。

    返回：
        JSON正文
        是否包含JSON之外的多余文本
    """

    # Markdown JSON代码块
    match = _FENCED_JSON.match(text)

    if match is not None:
        return match.group("body"), False

    stripped = text.strip()

    # 直接以 { 开头，认为模型尝试直接返回JSON
    if stripped.startswith("{"):
        return stripped, False

    # 其它情况认为混入了多余说明
    return stripped, True


def _diagnostics(
    text: object,
    *,
    response_type: str | None = None,
    decoder_message: str | None = None,
    decoder_line: int | None = None,
    decoder_column: int | None = None,
    has_trailing_text: bool = False,
) -> dict[str, object]:
    """生成安全的错误诊断信息。

    不保存完整模型输出，只记录：
    - 返回类型
    - 文本长度
    - JSON解析错误位置
    - 是否出现Markdown代码块
    - 是否出现多余文本
    - 响应内容哈希
    """

    rendered = text if isinstance(text, str) else ""

    return {
        "response_type": (
            response_type
            or type(text).__name__
        ),
        "response_length": len(rendered),

        "decoder_message": decoder_message,
        "decoder_line": decoder_line,
        "decoder_column": decoder_column,

        "has_markdown_fence": "```" in rendered,
        "has_trailing_text": has_trailing_text,

        # 用哈希标记这次响应，
        # 可以判断两次错误是否来自同一份输出，
        # 但不会把完整内容写进日志。
        "response_checksum": hashlib.sha256(
            rendered.encode("utf-8")
        ).hexdigest(),
    }