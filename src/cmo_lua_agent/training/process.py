"""Small background-process supervisor for a persistent training workflow."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable

from cmo_lua_agent.training.store import TrainingStore


class TrainingProcessManager:
    """Launch one hidden runtime process and retain only resumable PID metadata."""

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
        path = TrainingStore(self._project_root, workflow_id).root / "runner-process.json"
        if not path.is_file():
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
        return dict(value) if isinstance(value, dict) else {}

    def is_running(self, workflow_id: str) -> bool:
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
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, path)
