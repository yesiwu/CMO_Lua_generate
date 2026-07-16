"""
CMO 任务配置临时切换测试。

验证：
1. 进入上下文时切换 jobs[index].script；
2. 离开上下文后恢复执行前的原始值；
3. 执行代码抛异常时仍然恢复；
4. job_index 越界时不修改配置；
5. Lua 文件不存在时不修改配置；
6. 恢复时只修改 script，不覆盖执行期间产生的其他配置变化；
7. 支持带 BOM 的 UTF-8 JSON 文件。
"""
from __future__ import annotations
import sys
from pathlib import Path

# 自动注入项目根目录，修复 ModuleNotFound
root_dir = Path(__file__).parents[5]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import json
from pathlib import Path

import pytest

from cmo_lua_agent.execution.cmo_job_config import (
    CmoJobConfig,
    CmoJobConfigError,
)


def write_config(
    config_path: Path,
    *,
    encoding: str = "utf-8",
) -> None:
    config = {
        "name": "CMO batch test",
        "jobs": [
            {
                "name": "job-0",
                "script": r"D:\original\job_0.lua",
                "scenario": "scenario-0.scen",
            },
            {
                "name": "job-1",
                "script": r"D:\original\job_1.lua",
                "scenario": "scenario-1.scen",
            },
        ],
    }

    config_path.write_text(
        json.dumps(
            config,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding=encoding,
    )


def read_config(
    config_path: Path,
) -> dict:
    return json.loads(
        config_path.read_text(
            encoding="utf-8-sig",
        )
    )


def test_use_script_temporarily_replaces_and_restores(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "jobs.json"
    lua_path = tmp_path / "generated.lua"

    write_config(config_path)
    lua_path.write_text(
        "-- generated lua",
        encoding="utf-8",
    )

    manager = CmoJobConfig(config_path)

    with manager.use_script(
        lua_path=lua_path,
        job_index=0,
    ) as session:
        active_config = read_config(
            config_path
        )

        assert (
            active_config["jobs"][0]["script"]
            == str(lua_path.resolve())
        )

        assert (
            active_config["jobs"][1]["script"]
            == r"D:\original\job_1.lua"
        )

        assert (
            session.original_script
            == r"D:\original\job_0.lua"
        )

        assert (
            session.active_script
            == str(lua_path.resolve())
        )

        assert (
            session.restore_succeeded
            is False
        )

    restored_config = read_config(
        config_path
    )

    assert (
        restored_config["jobs"][0]["script"]
        == r"D:\original\job_0.lua"
    )

    assert session.restore_succeeded is True
    assert session.restore_error is None


def test_use_script_restores_when_body_raises(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "jobs.json"
    lua_path = tmp_path / "broken.lua"

    write_config(config_path)
    lua_path.write_text(
        "-- broken lua",
        encoding="utf-8",
    )

    manager = CmoJobConfig(config_path)

    with pytest.raises(
        RuntimeError,
        match="模拟 CMO 执行失败",
    ):
        with manager.use_script(
            lua_path=lua_path,
            job_index=0,
        ):
            assert (
                read_config(
                    config_path
                )["jobs"][0]["script"]
                == str(lua_path.resolve())
            )

            raise RuntimeError(
                "模拟 CMO 执行失败"
            )

    restored_config = read_config(
        config_path
    )

    assert (
        restored_config["jobs"][0]["script"]
        == r"D:\original\job_0.lua"
    )


def test_invalid_job_index_does_not_modify_config(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "jobs.json"
    lua_path = tmp_path / "generated.lua"

    write_config(config_path)
    lua_path.write_text(
        "-- lua",
        encoding="utf-8",
    )

    before = config_path.read_bytes()

    manager = CmoJobConfig(config_path)

    with pytest.raises(
        IndexError,
        match="job_index=5",
    ):
        with manager.use_script(
            lua_path=lua_path,
            job_index=5,
        ):
            pass

    assert config_path.read_bytes() == before


def test_missing_lua_file_does_not_modify_config(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "jobs.json"
    missing_lua = tmp_path / "missing.lua"

    write_config(config_path)

    before = config_path.read_bytes()

    manager = CmoJobConfig(config_path)

    with pytest.raises(
        FileNotFoundError,
        match="Lua 文件不存在",
    ):
        with manager.use_script(
            lua_path=missing_lua,
            job_index=0,
        ):
            pass

    assert config_path.read_bytes() == before


def test_invalid_jobs_structure_does_not_modify_config(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "jobs.json"
    lua_path = tmp_path / "generated.lua"

    config_path.write_text(
        json.dumps(
            {
                "jobs": {},
            }
        ),
        encoding="utf-8",
    )

    lua_path.write_text(
        "-- lua",
        encoding="utf-8",
    )

    before = config_path.read_bytes()

    manager = CmoJobConfig(config_path)

    with pytest.raises(
        CmoJobConfigError,
        match="jobs 必须是数组",
    ):
        with manager.use_script(
            lua_path=lua_path,
            job_index=0,
        ):
            pass

    assert config_path.read_bytes() == before


def test_restore_preserves_other_runtime_changes(
    tmp_path: Path,
) -> None:
    """
    恢复时只恢复 script 字段。

    如果 CMO 执行期间 JSON 的其他字段发生变化，
    不应使用执行前的整个旧 JSON 将这些变化覆盖掉。
    """
    config_path = tmp_path / "jobs.json"
    lua_path = tmp_path / "generated.lua"

    write_config(config_path)
    lua_path.write_text(
        "-- lua",
        encoding="utf-8",
    )

    manager = CmoJobConfig(config_path)

    with manager.use_script(
        lua_path=lua_path,
        job_index=0,
    ):
        current = read_config(
            config_path
        )

        current["runtime_note"] = (
            "CMO execution completed"
        )

        config_path.write_text(
            json.dumps(
                current,
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    restored = read_config(
        config_path
    )

    assert (
        restored["jobs"][0]["script"]
        == r"D:\original\job_0.lua"
    )

    assert (
        restored["runtime_note"]
        == "CMO execution completed"
    )


def test_supports_utf8_bom_config(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "jobs.json"
    lua_path = tmp_path / "generated.lua"

    write_config(
        config_path,
        encoding="utf-8-sig",
    )

    lua_path.write_text(
        "-- lua",
        encoding="utf-8",
    )

    manager = CmoJobConfig(config_path)

    with manager.use_script(
        lua_path=lua_path,
        job_index=0,
    ):
        active = read_config(
            config_path
        )

        assert (
            active["jobs"][0]["script"]
            == str(lua_path.resolve())
        )

    restored = read_config(
        config_path
    )

    assert (
        restored["jobs"][0]["script"]
        == r"D:\original\job_0.lua"
    )


def test_temporary_files_are_cleaned_up(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "jobs.json"
    lua_path = tmp_path / "generated.lua"

    write_config(config_path)
    lua_path.write_text(
        "-- lua",
        encoding="utf-8",
    )

    manager = CmoJobConfig(config_path)

    with manager.use_script(
        lua_path=lua_path,
        job_index=0,
    ):
        pass

    temporary_files = list(
        tmp_path.glob(
            f".{config_path.name}.*.tmp"
        )
    )

    assert temporary_files == []