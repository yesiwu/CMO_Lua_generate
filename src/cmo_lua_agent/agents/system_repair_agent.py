"""Adaptive source-code repair agent used by persistent training workflows."""

from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Callable


class SystemRepairAgent:
    """Ask a Codex-compatible backend to make the requested source change."""

    def __init__(
        self,
        *,
        project_root: Path,
        backend: Callable[[str], str] | None = None,
    ) -> None:
        self._root = Path(project_root).resolve()
        self._backend = backend or self._run_codex

    def repair(self, prompt: str) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("system_repair_prompt_required")
        return self._backend(prompt)

    def _run_codex(self, prompt: str) -> str:
        completed = subprocess.run(
            ["codex", "exec", "--full-auto", prompt],
            cwd=self._root,
            text=True,
            capture_output=True,
            check=True,
        )
        return completed.stdout.strip()
