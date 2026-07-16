"""
CMO 运行产物存储。

该模块负责创建一次完整任务的运行目录，并保存：

1. 初始 Lua 快照；
2. 每轮 CMO 原始控制台输出；
3. 每轮结构化执行结果。

目录结构：

    runs/
    └── run_20260715_083012_a31f/
        ├── generation/
        │   └── original.lua
        └── repair_rounds/
            └── round_00/
                ├── cmo_output.txt
                └── result.json

本模块不运行 CMO、不解析错误，也不调用 LLM。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from shutil import copy2
from uuid import uuid4

from cmo_lua_agent.execution.models import (
    CmoRunResult,
)


@dataclass(frozen=True)
class RunPaths:
    """
    一次完整任务的目录路径。

    Attributes:
        run_id:
            本次任务的唯一标识。

        run_dir:
            本次任务的根目录。

        generation_dir:
            Lua 生成阶段目录。

        original_lua_path:
            初始 Lua 快照路径。

        repair_rounds_dir:
            所有执行和修复轮次的父目录。
    """

    run_id: str
    run_dir: Path
    generation_dir: Path
    original_lua_path: Path
    repair_rounds_dir: Path


@dataclass(frozen=True)
class RoundPaths:
    """
    一轮 CMO 执行的产物路径。

    round_00 表示原始 Lua 第一次执行；
    round_01 表示第一次修复后的 Lua 执行。
    """

    round_number: int
    round_dir: Path
    cmo_output_path: Path
    result_path: Path


class RunArtifactStore:
    """
    CMO 运行产物存储器。
    """

    def __init__(
        self,
        *,
        runs_dir: Path,
    ) -> None:
        """
        初始化运行产物存储器。

        Args:
            runs_dir:
                所有任务运行目录的根路径。
        """
        self._runs_dir = Path(
            runs_dir
        )

    @property
    def runs_dir(self) -> Path:
        """
        返回运行产物根目录。
        """
        return self._runs_dir

    def create_run(
        self,
        *,
        original_lua: Path,
        run_id: str | None = None,
    ) -> RunPaths:
        """
        创建一次完整任务的运行目录。

        Args:
            original_lua:
                初始待执行 Lua 文件。

            run_id:
                可选的固定运行 ID。
                测试时可以传入确定值；
                正式运行时留空即可自动生成。

        Returns:
            RunPaths。

        Raises:
            FileNotFoundError:
                初始 Lua 文件不存在。

            FileExistsError:
                run_id 对应目录已经存在。

            ValueError:
                run_id 非法。
        """
        original_lua = Path(
            original_lua
        ).resolve()

        if not original_lua.is_file():
            raise FileNotFoundError(
                "初始 Lua 文件不存在："
                f"{original_lua}"
            )

        actual_run_id = (
            run_id
            if run_id is not None
            else self._generate_run_id()
        )

        self._validate_run_id(
            actual_run_id
        )

        run_dir = (
            self._runs_dir
            / actual_run_id
        )

        generation_dir = (
            run_dir / "generation"
        )

        repair_rounds_dir = (
            run_dir / "repair_rounds"
        )

        # exist_ok=False：
        # 防止意外覆盖之前已经存在的运行记录。
        run_dir.mkdir(
            parents=True,
            exist_ok=False,
        )

        generation_dir.mkdir()
        repair_rounds_dir.mkdir()

        original_lua_path = (
            generation_dir / "original.lua"
        )

        # copy2 保留原文件的基本时间信息，
        # 同时不会删除或移动输入 Lua。
        copy2(
            original_lua,
            original_lua_path,
        )

        return RunPaths(
            run_id=actual_run_id,
            run_dir=run_dir,
            generation_dir=generation_dir,
            original_lua_path=original_lua_path,
            repair_rounds_dir=repair_rounds_dir,
        )

    def prepare_round(
        self,
        *,
        run_paths: RunPaths,
        round_number: int,
    ) -> RoundPaths:
        """
        创建一轮 CMO 执行目录。

        轮次语义：

            round_00：
                初始 Lua 第一次执行。

            round_01：
                第一次修复后的 Lua 执行。

            round_02：
                第二次修复后的 Lua 执行。

        Args:
            run_paths:
                create_run() 返回的路径对象。

            round_number:
                从 0 开始的执行轮次。

        Returns:
            RoundPaths。
        """
        if (
            isinstance(round_number, bool)
            or not isinstance(
                round_number,
                int,
            )
            or round_number < 0
        ):
            raise ValueError(
                "round_number 必须是"
                "大于等于 0 的整数"
            )

        round_dir = (
            run_paths.repair_rounds_dir
            / f"round_{round_number:02d}"
        )

        round_dir.mkdir(
            parents=False,
            exist_ok=False,
        )

        return RoundPaths(
            round_number=round_number,
            round_dir=round_dir,
            cmo_output_path=(
                round_dir
                / "cmo_output.txt"
            ),
            result_path=(
                round_dir
                / "result.json"
            ),
        )

    def save_console_output(
        self,
        *,
        round_paths: RoundPaths,
        console_output: str,
    ) -> Path:
        """
        保存 CMO 原始控制台输出。

        使用 utf-8-sig，便于 Windows 文本工具直接查看中文。
        """
        if not isinstance(
            console_output,
            str,
        ):
            raise TypeError(
                "console_output 必须是字符串"
            )

        round_paths.cmo_output_path.write_text(
            console_output,
            encoding="utf-8-sig",
            errors="replace",
        )

        return round_paths.cmo_output_path

    def save_result(
        self,
        *,
        round_paths: RoundPaths,
        result: CmoRunResult,
    ) -> Path:
        """
        保存本轮结构化执行结果。

        完整控制台输出不写入 result.json，
        因为它已经单独存放在 cmo_output.txt。
        """
        payload = result.to_dict()

        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ) + "\n"

        round_paths.result_path.write_text(
            serialized,
            encoding="utf-8",
            errors="strict",
        )

        return round_paths.result_path

    @staticmethod
    def _generate_run_id() -> str:
        """
        生成运行 ID。

        示例：

            run_20260715_083012_a31f
        """
        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        random_suffix = uuid4().hex[:4]

        return (
            f"run_{timestamp}_"
            f"{random_suffix}"
        )

    @staticmethod
    def _validate_run_id(
        run_id: str,
    ) -> None:
        """
        校验运行 ID，避免目录穿越或非法空名称。
        """
        if (
            not isinstance(run_id, str)
            or not run_id.strip()
        ):
            raise ValueError(
                "run_id 必须是非空字符串"
            )

        if (
            Path(run_id).name != run_id
            or run_id in {".", ".."}
        ):
            raise ValueError(
                f"非法 run_id：{run_id!r}"
            )