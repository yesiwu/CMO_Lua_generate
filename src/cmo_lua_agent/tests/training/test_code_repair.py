from __future__ import annotations

from pathlib import Path
import subprocess
from types import SimpleNamespace

from cmo_lua_agent.training.failures import FailureKind, FailureRecord
from cmo_lua_agent.training.repair import CodeRepairCoordinator


def _init_repository(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=root, check=True)
    source = root / "src" / "cmo_lua_agent" / "worker.py"
    source.parent.mkdir(parents=True)
    source.write_text("VALUE = 'before'\n", encoding="utf-8")
    subprocess.run(["git", "add", "src"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=root, check=True, capture_output=True)


def _record() -> FailureRecord:
    return FailureRecord(FailureKind.CODE, "ImportError", "cannot import Worker")


def test_repair_coordinator_runs_repair_then_verifies_and_writes_log(tmp_path: Path) -> None:
    _init_repository(tmp_path)
    calls: list[str] = []

    def repair_command(prompt: str) -> str:
        calls.append(prompt)
        return "updated src/cmo_lua_agent/example.py"

    def tests(command: str) -> bool:
        calls.append(command)
        return True

    coordinator = CodeRepairCoordinator(
        project_root=tmp_path,
        repair_command=repair_command,
        test_runner=tests,
    )
    result = coordinator.repair(
        workflow_id="training-001",
        record=_record(),
        test_command="python -m pytest src/cmo_lua_agent/tests/training -q",
    )

    assert result.succeeded
    assert calls[1] == "python -m pytest src/cmo_lua_agent/tests/training -q"
    assert "ImportError" in calls[0]
    assert (tmp_path / "runs" / "training" / "training-001" / "code-repair-report.md").is_file()


def test_repair_coordinator_delegates_adaptive_change_generation_to_agent(
    tmp_path: Path,
) -> None:
    _init_repository(tmp_path)
    prompts: list[str] = []
    agent = SimpleNamespace(repair=lambda prompt: prompts.append(prompt) or "no change")
    coordinator = CodeRepairCoordinator(
        project_root=tmp_path,
        system_repair_agent=agent,
        test_runner=lambda _command: True,
    )

    result = coordinator.repair(
        workflow_id="training-001",
        record=_record(),
        test_command="python -m pytest test_worker.py -q",
    )

    assert result.succeeded is True
    assert len(prompts) == 1
    assert "ImportError" in prompts[0]


def test_repair_coordinator_commits_verified_clean_source_changes(tmp_path: Path) -> None:
    _init_repository(tmp_path)

    def repair_command(_prompt: str) -> str:
        (tmp_path / "src" / "cmo_lua_agent" / "worker.py").write_text(
            "VALUE = 'after'\n", encoding="utf-8"
        )
        return "fixed worker"

    coordinator = CodeRepairCoordinator(
        project_root=tmp_path,
        repair_command=repair_command,
        test_runner=lambda _command: True,
    )

    result = coordinator.repair(
        workflow_id="training-001",
        record=_record(),
        test_command="python -m pytest test_worker.py -q",
    )

    assert result.succeeded is True
    assert result.commit_id is not None
    assert subprocess.run(["git", "diff", "--quiet"], cwd=tmp_path).returncode == 0


def test_repair_coordinator_restores_changes_when_verification_fails(tmp_path: Path) -> None:
    _init_repository(tmp_path)
    source = tmp_path / "src" / "cmo_lua_agent" / "worker.py"

    def repair_command(_prompt: str) -> str:
        source.write_text("VALUE = 'broken'\n", encoding="utf-8")
        return "attempted fix"

    coordinator = CodeRepairCoordinator(
        project_root=tmp_path,
        repair_command=repair_command,
        test_runner=lambda _command: False,
    )

    result = coordinator.repair(
        workflow_id="training-001",
        record=_record(),
        test_command="python -m pytest test_worker.py -q",
    )

    assert result.succeeded is False
    assert source.read_text(encoding="utf-8") == "VALUE = 'before'\n"
    assert subprocess.run(["git", "diff", "--quiet"], cwd=tmp_path).returncode == 0
