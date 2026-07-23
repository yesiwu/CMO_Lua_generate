"""Sandboxed persistence for one Phase 5 candidate.
Phase5
功能：为每一条候选策略创建独立隔离目录

"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


class CandidateArtifactStore:
    """单候选产物隔离存储容器
    沙箱约束：所有文件路径强制限定在candidate_xxx根目录内，禁止向外逃逸；
    写入采用临时文件原子替换，防止中途断电/程序崩溃产生损坏的半截文件；
    禁止复用已存在的候选目录，保证每条候选数据完全隔离互不干扰。
    """
    def __init__(self, root: Path, candidate_id: str) -> None:
        # 规范化候选根目录绝对路径
        self.root = Path(root).resolve()
        # 校验目录名规范：必须以 candidate_候选ID 结尾
        if self.root.name != f"candidate_{candidate_id}":
            raise ValueError("candidate_dir 必须是以 candidate_<id> 命名的文件夹")
        # 禁止覆盖已有候选（目录非空则报错，防止误删旧实验数据）
        if self.root.exists() and any(self.root.iterdir()):
            raise ValueError("候选目录已存在且不为空，禁止覆盖已有候选数据")
        # 递归创建候选根目录
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, relative: str) -> Path:
        """拼接相对路径并做沙箱逃逸校验
        :param relative: 目录内相对文件路径，如 "phase3/combat_metrics.json"
        :return: 校验通过后的绝对路径
        """
        # 拼接并转为绝对路径
        value = (self.root / relative).resolve()
        # 安全校验：生成的路径父级必须包含候选根目录，防止../等路径穿越
        if value != self.root and self.root not in value.parents:
            raise ValueError("文件路径超出候选目录沙箱范围，禁止访问外部文件")
        return value

    def write_json(self, relative: str, value: Any) -> Path:
        """序列化对象并写入标准格式化JSON文件
        :param relative: 相对文件路径
        :param value: 任意可JSON序列化对象
        :return: 写入完成的文件绝对路径
        """
        file_path = self.path(relative)
        json_str = json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n"
        return self._write(file_path, json_str)

    def write_text(self, relative: str, value: str) -> Path:
        """写入纯文本文件（用于存储Lua脚本、日志文本等）
        :param relative: 相对文件路径
        :param value: 纯文本字符串
        :return: 写入完成的文件绝对路径
        """
        file_path = self.path(relative)
        return self._write(file_path, value)

    def append_jsonl(self, relative: str, value: Any) -> Path:
        """追加一行JSON到jsonl行日志文件（流式日志、事件记录专用）
        :param relative: jsonl文件相对路径
        :param value: 单行要存储的数据对象
        :return: 文件绝对路径
        """
        path = self.path(relative)
        # 父目录不存在则自动创建
        path.parent.mkdir(parents=True, exist_ok=True)
        # 追加模式写入单行JSON
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, default=str) + "\n")
        return path

    @staticmethod
    def _write(path: Path, value: str) -> Path:
        """原子写入底层工具：临时文件中转+重命名替换，防止文件损坏
        流程：新建临时文件写入内容 → 关闭 → 原子替换目标文件 → 清理临时文件
        """
        # 自动创建父文件夹
        path.parent.mkdir(parents=True, exist_ok=True)
        # 在目标目录创建临时文件，避免跨磁盘重命名失败
        handle = tempfile.NamedTemporaryFile("w", delete=False, dir=path.parent, encoding="utf-8", newline="\n")
        try:
            handle.write(value)
            handle.close()
            # 原子替换：操作系统级重写，不会出现半截损坏文件
            os.replace(handle.name, path)
        finally:
            # 兜底清理临时文件
            if not handle.closed:
                handle.close()
            if os.path.exists(handle.name):
                os.unlink(handle.name)
        return path
