"""Controlled automatic source repair for classified training code failures."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Callable

from cmo_lua_agent.agents.system_repair_agent import SystemRepairAgent
from cmo_lua_agent.training.failures import FailureKind, FailureRecord


@dataclass(frozen=True, slots=True)
class RepairResult:
    succeeded: bool
    summary: str
    report_path: Path
    commit_id: str | None = None


class CodeRepairCoordinator:
    """Invoke an injected repair backend, verify it, and persist a concise repair log."""

    def __init__(
        self,
        *,
        project_root: Path,
        system_repair_agent: object | None = None,
        repair_command: Callable[[str], str] | None = None,
        test_runner: Callable[[str], bool] | None = None,
    ) -> None:
        self._root = Path(project_root).resolve()
        self._agent = system_repair_agent or SystemRepairAgent(
            project_root=self._root,
            backend=repair_command,
        )
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
        snapshot = self._snapshot_repair_scope()
        dirty_paths = self._dirty_paths()
        try:
            summary = self._agent.repair(prompt)
        except Exception as exc:
            return self._write_report(report_path, False, f"Repair backend failed: {type(exc).__name__}: {exc}")
        if not self._test_runner(test_command):
            self._restore_snapshot(snapshot)
            return self._write_report(report_path, False, f"Repair verification failed; source changes restored.\n\n{summary}")
        changed_paths = self._changed_paths(snapshot)
        if any(path in dirty_paths for path in changed_paths):
            self._restore_snapshot(snapshot)
            return self._write_report(
                report_path,
                False,
                "Repair touched source files that were already modified before training; source changes restored.",
            )
        try:
            commit_id = self._commit_repair(workflow_id, changed_paths)
        except Exception as exc:
            self._restore_snapshot(snapshot)
            return self._write_report(
                report_path,
                False,
                f"Repair commit failed; source changes restored: {type(exc).__name__}: {exc}",
            )
        detail = summary if commit_id is None else f"{summary}\n\nGit commit: {commit_id}"
        return self._write_report(report_path, True, detail, commit_id=commit_id)

    def _write_report(
        self,
        path: Path,
        succeeded: bool,
        body: str,
        *,
        commit_id: str | None = None,
    ) -> RepairResult:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"# Code repair\n\n- Status: {'completed' if succeeded else 'failed'}\n\n{body}\n",
            encoding="utf-8",
        )
        return RepairResult(succeeded=succeeded, summary=body, report_path=path, commit_id=commit_id)

    def _snapshot_repair_scope(self) -> dict[Path, bytes | None]:
        snapshot: dict[Path, bytes | None] = {}
        for relative_root in (Path("src"), Path("scripts")):
            root = self._root / relative_root
            if not root.is_dir():
                continue
            for path in root.rglob("*"):
                if path.is_file():
                    snapshot[path.relative_to(self._root)] = path.read_bytes()
        return snapshot

    def _changed_paths(self, snapshot: dict[Path, bytes | None]) -> tuple[Path, ...]:
        current = self._snapshot_repair_scope()
        changed = [
            path
            for path in sorted(set(snapshot) | set(current))
            if snapshot.get(path) != current.get(path)
        ]
        return tuple(changed)

    def _restore_snapshot(self, snapshot: dict[Path, bytes | None]) -> None:
        current = self._snapshot_repair_scope()
        for relative_path in set(snapshot) | set(current):
            original = snapshot.get(relative_path)
            path = self._root / relative_path
            if original is None:
                if path.is_file():
                    path.unlink()
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(original)

    def _dirty_paths(self) -> set[Path]:
        output = self._run_git("status", "--porcelain", "--", "src", "scripts")
        paths: set[Path] = set()
        for line in output.splitlines():
            if len(line) < 4:
                continue
            paths.add(Path(line[3:].replace("\\", "/")))
        return paths

    def _commit_repair(self, workflow_id: str, paths: tuple[Path, ...]) -> str | None:
        if not paths:
            return None
        relative_paths = [path.as_posix() for path in paths]
        self._run_git(
            "commit",
            "--only",
            "-m",
            f"fix(training): repair {workflow_id}",
            "--",
            *relative_paths,
        )
        return self._run_git("rev-parse", "HEAD").strip()

    def _run_git(self, *arguments: str) -> str:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=self._root,
            text=True,
            capture_output=True,
            check=True,
        )
        return completed.stdout

    def _run_tests(self, command: str) -> bool:
        completed = subprocess.run(
            command,
            cwd=self._root,
            shell=True,
            text=True,
            capture_output=True,
        )
        return completed.returncode == 0
