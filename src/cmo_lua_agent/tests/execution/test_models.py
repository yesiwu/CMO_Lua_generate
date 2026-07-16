"""
CMO 执行数据模型测试。

验证：
1. CMO 错误可以转换为 JSON 兼容字典；
2. CMO 进程结果能够保存退出码、超时和原始输出；
3. CMO 最终执行结果能够转换为 result.json 所需结构；
4. 执行成功且没有错误时，error 字段应为 None。
"""
from __future__ import annotations

import sys
from pathlib import Path
# 新增：把项目根目录加入模块搜索路径
ROOT_DIR = Path(__file__).parents[4]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import json

from src.cmo_lua_agent.execution.models import (
    CmoError,
    CmoProcessResult,
    CmoRunResult,
)

# 下面原有测试函数不变
def test_cmo_error_to_dict() -> None:
    error = CmoError(
        category="lua_syntax_error",
        message='unfinished string near \'"\'',
        source="Console",
        line=229,
    )

    assert error.to_dict() == {
        "category": "lua_syntax_error",
        "message": 'unfinished string near \'"\'',
        "source": "Console",
        "line": 229,
    }


def test_cmo_process_result_stores_raw_execution_data() -> None:
    result = CmoProcessResult(
        exit_code=0,
        timed_out=False,
        duration_seconds=18.42,
        console_output=(
            "Internal ERROR: "
            '[string "Console"]:229: '
            'unfinished string near \'"\''
        ),
    )

    assert result.exit_code == 0
    assert result.timed_out is False
    assert result.duration_seconds == 18.42
    assert "Internal ERROR" in result.console_output


def test_cmo_run_result_to_dict_is_json_compatible(
    tmp_path,
) -> None:
    lua_path = tmp_path / "original.lua"
    log_path = tmp_path / "cmo_output.txt"

    process_result = CmoProcessResult(
        exit_code=0,
        timed_out=False,
        duration_seconds=18.42,
        console_output="Internal ERROR",
    )

    error = CmoError(
        category="lua_syntax_error",
        message='unfinished string near \'"\'',
        source="Console",
        line=229,
    )

    result = CmoRunResult(
        success=False,
        lua_path=lua_path,
        log_path=log_path,
        process_result=process_result,
        restore_succeeded=True,
        error=error,
    )

    payload = result.to_dict()

    assert payload == {
        "success": False,
        "exit_code": 0,
        "timed_out": False,
        "duration_seconds": 18.42,
        "lua_path": str(lua_path),
        "log_path": str(log_path),
            "restore_succeeded": True,
            "batch_result_dir": None,
            "batch_success_count": None,
            "batch_failure_count": None,
            "error": {
            "category": "lua_syntax_error",
            "message": 'unfinished string near \'"\'',
            "source": "Console",
            "line": 229,
        },
    }

    # 确认结果能够直接写入 result.json。
    json.dumps(
        payload,
        ensure_ascii=False,
    )

    # 原始控制台输出单独保存在 cmo_output.txt，
    # 不应重复写入 result.json。
    assert "console_output" not in payload


def test_success_result_has_null_error(
    tmp_path,
) -> None:
    process_result = CmoProcessResult(
        exit_code=0,
        timed_out=False,
        duration_seconds=5.25,
        console_output="CMO execution completed",
    )

    result = CmoRunResult(
        success=True,
        lua_path=tmp_path / "valid.lua",
        log_path=tmp_path / "cmo_output.txt",
        process_result=process_result,
        restore_succeeded=True,
        error=None,
    )

    payload = result.to_dict()

    assert payload["success"] is True
    assert payload["exit_code"] == 0
    assert payload["error"] is None
