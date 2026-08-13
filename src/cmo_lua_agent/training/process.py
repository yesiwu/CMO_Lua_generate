"""Training Workflow 后台进程启动器。

TrainingService 调用本模块启动 ``training.runtime``。它只保存 pid 和日志路径；
真正可恢复的执行位置仍在 TrainingStore，因此 pid 丢失时可以重新启动而不丢代数。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable

from cmo_lua_agent.training.store import TrainingStore


class TrainingProcessManager:
    """启动隐藏 Runtime 子进程，并保留用于健康检查的最小 PID 元数据。"""

    def __init__(
        self,
        *,
        project_root: Path,
        launcher: Callable[..., Any] = subprocess.Popen,
        python_executable: str | None = None,
    ) -> None:
        self._project_root = Path(project_root).resolve()
        self._launcher = launcher
        self._python = python_executable or sys.executable

    def start(self, workflow_id: str) -> int:
        """启动指定 Workflow 的后台调度进程，并将 stdout/stderr 追加至 runner.log。

请求文件必须已存在；该顺序避免启动一个没有任何可恢复状态的新进程。返回值仅用于
观察进程，不是 Workflow 正确性的来源。
        """
        store = TrainingStore(self._project_root, workflow_id)
        if not store.root.is_dir():
            raise ValueError("training_workflow_not_found")
        log_path = store.root / "runner.log"
        log_path.touch(exist_ok=True)
        command = [
            self._python,
            "-m",
            "cmo_lua_agent.training.runtime",
            "run",
            "--project-root",
            str(self._project_root),
            "--workflow-id",
            workflow_id,
        ]
        environment = os.environ.copy()
        source_root = str(self._project_root / "src")
        environment["PYTHONPATH"] = os.pathsep.join(
            value for value in (source_root, environment.get("PYTHONPATH")) if value
        )
        with log_path.open("a", encoding="utf-8") as log:
            process = self._launcher(
                command,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                cwd=str(self._project_root),
                env=environment,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        metadata = {"pid": int(process.pid), "workflow_id": workflow_id}
        self._write_json(store.root / "runner-process.json", metadata)
        return int(process.pid)

    def process_metadata(self, workflow_id: str) -> dict[str, object]:
        """读取诊断用进程元数据；其缺失不影响 Workflow 从 Store 恢复。"""
        path = TrainingStore(self._project_root, workflow_id).root / "runner-process.json"
        if not path.is_file():
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
        return dict(value) if isinstance(value, dict) else {}

    def is_running(self, workflow_id: str) -> bool:
        """按保存的 PID 做进程存活探测；失败后由上层重新启动并从 Store 恢复。"""
        pid = self.process_metadata(workflow_id).get("pid")
        if not isinstance(pid, int) or pid < 1:
            return False
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    @staticmethod
    def _write_json(path: Path, value: dict[str, object]) -> None:
        """使用同目录临时文件原子替换进程元数据，避免健康检查读到半写入 JSON。"""
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, path)
