"""Controlled automatic source repair for classified training code failures."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Callable

from cmo_lua_agent.training.failures import FailureKind, FailureRecord


@dataclass(frozen=True, slots=True)
class RepairResult:
    succeeded: bool
    summary: str
    report_path: Path


class CodeRepairCoordinator:
    """Invoke an injected repair backend, verify it, and persist a concise repair log."""

    def __init__(
        self,
        *,
        project_root: Path,
        repair_command: Callable[[str], str] | None = None,
        test_runner: Callable[[str], bool] | None = None,
    ) -> None:
        self._root = Path(project_root).resolve()
        self._repair_command = repair_command or self._run_codex
        self._test_runner = test_runner or self._run_tests

    def repair(
        self,
        *,
        workflow_id: str,
        record: FailureRecord,
        test_command: str,
    ) -> RepairResult:
        report_path = self._root / "runs" / "training" / workflow_id / "code-repair-report.md"
        if record.kind is not FailureKind.CODE:
            return self._write_report(report_path, False, "Repair skipped: failure is not code.")
        prompt = (
            "Repair this Python training-system failure. Make the smallest correct source and regression-test change. "
            f"Failure type: {record.error_type}\nFailure: {record.message}\n"
            f"Required verification: {test_command}\n"
            "Finish with a short modification log."
        )
        try:
            summary = self._repair_command(prompt)
        except Exception as exc:
            return self._write_report(report_path, False, f"Repair backend failed: {type(exc).__name__}: {exc}")
        if not self._test_runner(test_command):
            return self._write_report(report_path, False, f"Repair verification failed.\n\n{summary}")
        return self._write_report(report_path, True, summary)

    def _write_report(self, path: Path, succeeded: bool, body: str) -> RepairResult:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"# Code repair\n\n- Status: {'completed' if succeeded else 'failed'}\n\n{body}\n",
            encoding="utf-8",
        )
        return RepairResult(succeeded=succeeded, summary=body, report_path=path)

    def _run_codex(self, prompt: str) -> str:
        completed = subprocess.run(
            ["codex", "exec", "--full-auto", prompt],
            cwd=self._root,
            text=True,
            capture_output=True,
            check=True,
        )
        return completed.stdout.strip()

    def _run_tests(self, command: str) -> bool:
        completed = subprocess.run(
            command,
            cwd=self._root,
            shell=True,
            text=True,
            capture_output=True,
        )
        return completed.returncode == 0
