"""保存主 Agent 工具无法直接内联的大型文本输出。

搜索和读取工具把完整结果写到 ``runs/agent-artifacts``，只向模型返回摘要和
相对路径。该目录只承载诊断文本，不参与 Workflow 状态恢复；模型需要细节时可
继续通过 ``read_file`` 分页读取，避免因简单截断丢失真正的报错位置。
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4


class WorkspaceArtifactStore:
    """为一次工具实例创建非隐藏 Artifact 目录并原子保存完整文本。"""

    def __init__(self, workdir: Path, *, max_inline_chars: int = 12_000) -> None:
        self._workdir = Path(workdir).resolve()
        self._max_inline_chars = max_inline_chars
        self._session_dir = (
            self._workdir / "runs" / "agent-artifacts" / uuid4().hex
        )

    def inline_or_store(self, content: str, *, kind: str) -> str:
        if len(content) <= self._max_inline_chars:
            return content
        self._session_dir.mkdir(parents=True, exist_ok=True)
        target = self._session_dir / f"{kind}-{uuid4().hex}.txt"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(target)
        relative = target.relative_to(self._workdir).as_posix()
        summary = self._summarize(content)
        return json.dumps(
            {
                "summary": summary,
                "truncated": True,
                "artifact_path": relative,
                "characters": len(content),
                "lines": len(content.splitlines()),
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _summarize(content: str) -> str:
        lines = content.splitlines()
        if not lines:
            return "输出为空。"
        head = lines[:3]
        tail = lines[-3:] if len(lines) > 3 else []
        preview = "\n".join(head + (["..."] if tail else []) + tail)
        return f"完整输出共 {len(lines)} 行；首尾摘要：\n{preview}"


__all__ = ["WorkspaceArtifactStore"]
