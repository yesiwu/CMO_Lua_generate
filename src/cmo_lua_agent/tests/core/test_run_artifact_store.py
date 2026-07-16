"""
运行产物存储测试。

验证：
1. 创建一次完整 Run；
2. 保存原始 Lua 快照；
3. 创建 repair_rounds/round_00；
4. 保存 CMO 原始输出；
5. 保存结构化 result.json；
6. 防止覆盖已有 Run；
7. 拒绝非法轮次。
"""
from __future__ import annotations
import sys
from pathlib import Path

# 注入项目根目录，解决 ModuleNotFoundError
root_dir = Path(__file__).parents[5]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import json
from pathlib import Path

import pytest

from cmo_lua_agent.core.run_artifact_store import RunArtifactStore
from cmo_lua_agent.execution.models import CmoError, CmoProcessResult, CmoRunResult


def test_create_run_creates_directories_and_copies_original_lua(
    tmp_path: Path,
) -> None:
    source_lua = tmp_path / "generated.lua"
    source_lua.write_text(
        "-- original lua\nprint('hello')\n",
        encoding="utf-8",
    )

    store = RunArtifactStore(
        runs_dir=tmp_path / "runs",
    )

    run_paths = store.create_run(
        original_lua=source_lua,
        run_id="run_test_001",
    )

    assert run_paths.run_id == "run_test_001"

    assert run_paths.run_dir == (
        tmp_path / "runs" / "run_test_001"
    )

    assert run_paths.generation_dir.is_dir()
    assert run_paths.repair_rounds_dir.is_dir()
    assert run_paths.original_lua_path.is_file()

    copied_text = (
        run_paths.original_lua_path.read_text(
            encoding="utf-8",
        )
    )

    assert copied_text == (
        "-- original lua\n"
        "print('hello')\n"
    )

    # 原始输入文件不能被移动或删除。
    assert source_lua.is_file()


def test_prepare_round_creates_expected_paths(
    tmp_path: Path,
) -> None:
    source_lua = tmp_path / "generated.lua"
    source_lua.write_text(
        "-- lua",
        encoding="utf-8",
    )

    store = RunArtifactStore(
        runs_dir=tmp_path / "runs",
    )

    run_paths = store.create_run(
        original_lua=source_lua,
        run_id="run_test_002",
    )

    round_paths = store.prepare_round(
        run_paths=run_paths,
        round_number=0,
    )

    assert round_paths.round_number == 0

    assert round_paths.round_dir == (
        run_paths.repair_rounds_dir
        / "round_00"
    )

    assert round_paths.round_dir.is_dir()

    assert round_paths.cmo_output_path == (
        round_paths.round_dir
        / "cmo_output.txt"
    )

    assert round_paths.result_path == (
        round_paths.round_dir
        / "result.json"
    )


def test_save_console_output_and_result(
    tmp_path: Path,
) -> None:
    source_lua = tmp_path / "generated.lua"
    source_lua.write_text(
        "-- lua",
        encoding="utf-8",
    )

    store = RunArtifactStore(
        runs_dir=tmp_path / "runs",
    )

    run_paths = store.create_run(
        original_lua=source_lua,
        run_id="run_test_003",
    )

    round_paths = store.prepare_round(
        run_paths=run_paths,
        round_number=0,
    )

    console_output = (
        '[1/1] 失败，原因=LuaFailed，'
        '错误=[string "Console"]:132: '
        "'in' expected near '('"
    )

    log_path = store.save_console_output(
        round_paths=round_paths,
        console_output=console_output,
    )

    process_result = CmoProcessResult(
        exit_code=0,
        timed_out=False,
        duration_seconds=5.2,
        console_output=console_output,
    )

    error = CmoError(
        category="lua_syntax_error",
        message="'in' expected near '('",
        source="Console",
        line=132,
    )

    run_result = CmoRunResult(
        success=False,
        lua_path=(
            run_paths.original_lua_path
        ),
        log_path=log_path,
        process_result=process_result,
        restore_succeeded=True,
        error=error,
    )

    result_path = store.save_result(
        round_paths=round_paths,
        result=run_result,
    )

    saved_output = log_path.read_text(
        encoding="utf-8-sig",
    )

    assert saved_output == console_output

    payload = json.loads(
        result_path.read_text(
            encoding="utf-8",
        )
    )

    assert payload["success"] is False
    assert payload["exit_code"] == 0
    assert payload["timed_out"] is False
    assert payload["restore_succeeded"] is True

    assert payload["error"] == {
        "category": "lua_syntax_error",
        "message": "'in' expected near '('",
        "source": "Console",
        "line": 132,
    }

    # 完整日志单独保存在 cmo_output.txt，
    # 不重复写入 result.json。
    assert "console_output" not in payload


def test_create_run_rejects_existing_run_id(
    tmp_path: Path,
) -> None:
    source_lua = tmp_path / "generated.lua"
    source_lua.write_text(
        "-- lua",
        encoding="utf-8",
    )

    store = RunArtifactStore(
        runs_dir=tmp_path / "runs",
    )

    store.create_run(
        original_lua=source_lua,
        run_id="run_duplicate",
    )

    with pytest.raises(
        FileExistsError,
    ):
        store.create_run(
            original_lua=source_lua,
            run_id="run_duplicate",
        )


@pytest.mark.parametrize(
    "round_number",
    [
        -1,
        True,
        1.5,
        "1",
    ],
)
def test_prepare_round_rejects_invalid_round_number(
    tmp_path: Path,
    round_number: object,
) -> None:
    source_lua = tmp_path / "generated.lua"
    source_lua.write_text(
        "-- lua",
        encoding="utf-8",
    )

    store = RunArtifactStore(
        runs_dir=tmp_path / "runs",
    )

    run_paths = store.create_run(
        original_lua=source_lua,
        run_id="run_invalid_round",
    )

    with pytest.raises(
        ValueError,
        match="round_number",
    ):
        store.prepare_round(
            run_paths=run_paths,
            round_number=round_number,  # type: ignore[arg-type]
        )