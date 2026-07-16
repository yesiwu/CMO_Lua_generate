"""
CMO 控制台错误解析器。

该模块负责从 CMO Batch Runner 的原始控制台输出中，
提取结构化错误信息。

当前支持识别：

1. Lua 语法错误；
2. Lua 运行时错误；
3. CMO Internal ERROR；
4. 普通 ERROR / FATAL / EXCEPTION 错误行；
5. [string "Console"]:行号 格式；
6. Windows Lua 文件路径:行号 格式。

本模块只解析文本，不启动 CMO、不检查进程退出码，
也不决定是否进入修复循环。
"""

from __future__ import annotations

import re

from cmo_lua_agent.execution.models import (
    CmoError,
)


# 典型 CMO 错误位置：
#
# [string "Console"]:229: unfinished string near '"'
#
# 或：
#
# [string "Console"]:229:
# unfinished string near '"'
_STRING_LOCATION_PATTERN = re.compile(
    r"""
    \[
        string
        \s+
        ["']
        (?P<source>[^"']+)
        ["']
    \]
    \s*:\s*
    (?P<line>\d+)
    \s*:\s*
    (?P<message>[^\r\n]*)
    """,
    re.IGNORECASE | re.VERBOSE,
)


# 普通 Lua 文件位置，例如：
#
# D:\CMO\Lua\generated.lua:42: unexpected symbol near ')'
#
# C:\path 中的盘符冒号不会被误认为行号分隔符。
_LUA_FILE_LOCATION_PATTERN = re.compile(
    r"""
    (?P<source>
        (?:[A-Za-z]:)?
        [^:\r\n]+?
        \.lua
    )
    \s*:\s*
    (?P<line>\d+)
    \s*:\s*
    (?P<message>[^\r\n]*)
    """,
    re.IGNORECASE | re.VERBOSE,
)


_INTERNAL_ERROR_PATTERN = re.compile(
    r"""
    Internal
    \s+
    ERROR
    \s*:?\s*
    (?P<message>[^\r\n]*)
    """,
    re.IGNORECASE | re.VERBOSE,
)


_GENERIC_ERROR_PATTERN = re.compile(
    r"""
    ^\s*
    (?:
        \[
            [^\]]*
            (?:ERROR|FATAL|EXCEPTION)
            [^\]]*
        \]
        |
        ERROR
        |
        FATAL
        |
        EXCEPTION
    )
    \s*:?\s*
    (?P<message>.+?)
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)


_SYNTAX_ERROR_MARKERS = (
    "unfinished string",
    "unexpected symbol",
    "syntax error",
    "expected near",
    "unexpected eof",
    "<eof> expected",
    "malformed number",
    "invalid escape",
    "function arguments expected",
    "name expected",
    "then expected",
    "end expected",
    "near '<eof>'",
)


_RUNTIME_ERROR_MARKERS = (
    "attempt to index",
    "attempt to call",
    "attempt to perform",
    "attempt to concatenate",
    "attempt to compare",
    "attempt to get length",
    "nil value",
    "bad argument",
    "stack overflow",
    "divide by zero",
    "division by zero",
)


_NON_ERROR_PATTERNS = (
    re.compile(
        r"\berror\s+count\s*:\s*0\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b0\s+errors?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bno\s+errors?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bwithout\s+error\b",
        re.IGNORECASE,
    ),
)


def parse_cmo_error(
    console_output: str,
) -> CmoError | None:
    """
    从 CMO 控制台输出中解析结构化错误。

    Args:
        console_output:
            stdout 和 stderr 合并后的完整文本。

    Returns:
        检测到错误时返回 CmoError；
        没有可靠错误证据时返回 None。
    """
    normalized_output = _normalize_output(
        console_output
    )

    if not normalized_output:
        return None

    location = _find_error_location(
        normalized_output
    )

    if location is not None:
        source, line, message = location

        category = _classify_error(
            message=message,
            full_output=normalized_output,
        )

        return CmoError(
            category=category,
            message=message,
            source=source,
            line=line,
        )

    candidate_message = _find_error_message(
        normalized_output
    )

    if candidate_message is None:
        return None

    category = _classify_error(
        message=candidate_message,
        full_output=normalized_output,
    )

    return CmoError(
        category=category,
        message=candidate_message,
        source=None,
        line=None,
    )


def _normalize_output(
    console_output: str,
) -> str:
    """
    统一换行和空字符，避免正则受控制字符影响。
    """
    if not isinstance(console_output, str):
        raise TypeError(
            "console_output 必须是字符串"
        )

    return (
        console_output
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\x00", "")
        .strip()
    )


def _find_error_location(
    console_output: str,
) -> tuple[str, int, str] | None:
    """
    查找带来源和行号的 Lua 错误。

    Returns:
        (source, line, message)，或 None。
    """
    for pattern in (
        _STRING_LOCATION_PATTERN,
        _LUA_FILE_LOCATION_PATTERN,
    ):
        match = pattern.search(
            console_output
        )

        if match is None:
            continue

        source = match.group(
            "source"
        ).strip()

        line = int(
            match.group("line")
        )

        message = _clean_message(
            match.group("message")
        )

        # 某些 CMO 输出会把真正错误消息放在下一行：
        #
        # [string "Console"]:229:
        # unfinished string near '"'
        if not message:
            message = _first_meaningful_line(
                console_output[
                    match.end():
                ]
            )

        if not message:
            message = (
                "CMO reported an error "
                f"at {source}:{line}"
            )

        return (
            source,
            line,
            message,
        )

    return None


def _find_error_message(
    console_output: str,
) -> str | None:
    """
    在没有来源和行号时寻找最有代表性的错误消息。
    """
    lines = [
        line.strip()
        for line in console_output.splitlines()
        if line.strip()
    ]

    # 优先寻找明确的 Lua 语法或运行时错误。
    for line in lines:
        if _is_non_error_line(line):
            continue

        lowered = line.lower()

        if (
            _contains_any(
                lowered,
                _SYNTAX_ERROR_MARKERS,
            )
            or _contains_any(
                lowered,
                _RUNTIME_ERROR_MARKERS,
            )
        ):
            return _clean_message(line)

    # 其次处理 Internal ERROR。
    internal_match = _INTERNAL_ERROR_PATTERN.search(
        console_output
    )

    if internal_match is not None:
        message = _clean_message(
            internal_match.group("message")
        )

        if not message:
            message = _first_meaningful_line(
                console_output[
                    internal_match.end():
                ]
            )

        return (
            message
            or "CMO Internal ERROR"
        )

    # 最后处理显式 ERROR / FATAL / EXCEPTION 行。
    for line in lines:
        if _is_non_error_line(line):
            continue

        generic_match = (
            _GENERIC_ERROR_PATTERN.match(line)
        )

        if generic_match is None:
            continue

        message = _clean_message(
            generic_match.group("message")
        )

        if message:
            return message

    return None


def _classify_error(
    *,
    message: str,
    full_output: str,
) -> str:
    """
    根据错误消息和完整输出确定稳定分类。
    """
    searchable_text = (
        f"{message}\n{full_output}"
    ).lower()

    if _contains_any(
        searchable_text,
        _SYNTAX_ERROR_MARKERS,
    ):
        return "lua_syntax_error"

    if _contains_any(
        searchable_text,
        _RUNTIME_ERROR_MARKERS,
    ):
        return "lua_runtime_error"

    if "internal error" in searchable_text:
        return "cmo_internal_error"

    return "unknown_error"


def _first_meaningful_line(
    text: str,
) -> str:
    """
    返回文本中的第一条有效错误消息行。
    """
    for raw_line in text.splitlines():
        line = _clean_message(
            raw_line
        )

        if not line:
            continue

        if _is_non_error_line(line):
            continue

        # 跳过 traceback 标签本身，优先取实际错误内容。
        if line.lower() == "stack traceback:":
            continue

        return line

    return ""


def _clean_message(
    message: str,
) -> str:
    """
    清理错误消息首尾空格和重复空白。
    """
    return " ".join(
        message.strip().split()
    )


def _contains_any(
    text: str,
    markers: tuple[str, ...],
) -> bool:
    """
    判断文本中是否包含任意一个错误标记。
    """
    return any(
        marker in text
        for marker in markers
    )


def _is_non_error_line(
    line: str,
) -> bool:
    """
    判断一行是否明确表示“没有错误”。
    """
    return any(
        pattern.search(line)
        is not None
        for pattern in _NON_ERROR_PATTERNS
    )