"""
CMO 控制台错误解析器测试。

主要覆盖：
1. 单行 Internal ERROR；
2. 跨行 Internal ERROR；
3. Lua 运行时错误；
4. Lua 文件路径形式的错误位置；
5. 无错误输出；
6. 无法精确分类的 CMO Internal ERROR；
7. 避免把“0 errors”误判成失败。
"""
from __future__ import annotations
import sys
from pathlib import Path

# 修复层级：往上5层到达项目根目录 CMO_Lua_generate
root_dir = Path(__file__).parents[5]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pytest

from cmo_lua_agent.execution.cmo_error_parser import parse_cmo_error

def test_parse_single_line_lua_syntax_error() -> None:
    console_output = (
        'Internal ERROR: [string "Console"]:229: '
        'unfinished string near \'"\''
    )

    error = parse_cmo_error(console_output)

    assert error is not None
    assert error.category == "lua_syntax_error"
    assert error.source == "Console"
    assert error.line == 229
    assert error.message == 'unfinished string near \'"\''


def test_parse_multiline_lua_syntax_error() -> None:
    console_output = """
CMO Batch Runner started.
Internal ERROR: [string "Console"]:229:
unfinished string near '"'
Simulation stopped.
"""

    error = parse_cmo_error(console_output)

    assert error is not None
    assert error.category == "lua_syntax_error"
    assert error.source == "Console"
    assert error.line == 229
    assert error.message == 'unfinished string near \'"\''


def test_parse_lua_runtime_error() -> None:
    console_output = """
Internal ERROR: [string "Console"]:87:
attempt to index a nil value (local 'unit')
stack traceback:
    [string "Console"]:87: in main chunk
"""

    error = parse_cmo_error(console_output)

    assert error is not None
    assert error.category == "lua_runtime_error"
    assert error.source == "Console"
    assert error.line == 87
    assert (
        error.message
        == "attempt to index a nil value (local 'unit')"
    )


def test_parse_lua_file_path_location() -> None:
    console_output = (
        r"D:\CMO\Lua\generated.lua:42: "
        "unexpected symbol near ')'"
    )

    error = parse_cmo_error(console_output)

    assert error is not None
    assert error.category == "lua_syntax_error"
    assert error.source == r"D:\CMO\Lua\generated.lua"
    assert error.line == 42
    assert error.message == "unexpected symbol near ')'"


def test_parse_returns_none_when_output_has_no_error() -> None:
    console_output = """
CMO Batch Runner started.
Scenario loaded successfully.
Lua script completed successfully.
Simulation completed.
"""

    error = parse_cmo_error(console_output)

    assert error is None


def test_parse_unknown_internal_error() -> None:
    console_output = """
Internal ERROR: scenario database is unavailable
Simulation stopped.
"""

    error = parse_cmo_error(console_output)

    assert error is not None
    assert error.category == "cmo_internal_error"
    assert error.source is None
    assert error.line is None
    assert error.message == "scenario database is unavailable"


@pytest.mark.parametrize(
    "console_output",
    [
        "Error count: 0",
        "0 errors detected",
        "No errors were found.",
        "Completed without error.",
    ],
)
def test_parse_does_not_treat_zero_error_messages_as_failure(
    console_output: str,
) -> None:
    error = parse_cmo_error(console_output)

    assert error is None


def test_parse_generic_error_line() -> None:
    console_output = """
[INFO] Loading scenario.
[ERROR] Failed to load scenario database.
"""

    error = parse_cmo_error(console_output)

    assert error is not None
    assert error.category == "unknown_error"
    assert error.source is None
    assert error.line is None
    assert error.message == "Failed to load scenario database."