from __future__ import annotations

from pathlib import Path
import subprocess
from types import SimpleNamespace

from cmo_lua_agent.agents.code_repair_agent import RepairAgentResult, RepairAgentStatus
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
    assert any("src/cmo_lua_agent/tests/training" in call for call in calls[1:])
    assert "ImportError" in calls[0]
    assert (tmp_path / "runs" / "training" / "training-001" / "recovery-report.md").is_file()


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
        push_runner=lambda: True,
    )

    result = coordinator.repair(
        workflow_id="training-001",
        record=_record(),
        test_command="python -m pytest test_worker.py -q",
    )

    assert result.succeeded is True
    assert result.commit_id is not None
    assert subprocess.run(["git", "diff", "--quiet"], cwd=tmp_path).returncode == 0
    report = result.report_path.read_text(encoding="utf-8")
    assert "src/cmo_lua_agent/worker.py" in report
    assert "失败 action 对账/重放通过" in report
    assert "Git push：完成" in report


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


def test_repair_coordinator_restores_source_when_original_action_replay_fails(
    tmp_path: Path,
) -> None:
    _init_repository(tmp_path)
    source = tmp_path / "src" / "cmo_lua_agent" / "worker.py"
    initial_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True, capture_output=True, check=True
    ).stdout.strip()

    def repair_command(_prompt: str) -> str:
        source.write_text("VALUE = 'fixed but unreplayable'\n", encoding="utf-8")
        return "fixed worker"

    coordinator = CodeRepairCoordinator(
        project_root=tmp_path,
        repair_command=repair_command,
        test_runner=lambda _command: True,
        push_runner=lambda: True,
    )

    def replay() -> None:
        raise RuntimeError("original action still fails")

    result = coordinator.repair(
        workflow_id="training-001",
        record=_record(),
        test_command="python -m pytest test_worker.py -q",
        replay_task=replay,
    )

    assert result.succeeded is False
    assert source.read_text(encoding="utf-8") == "VALUE = 'before'\n"
    current_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True, capture_output=True, check=True
    ).stdout.strip()
    assert current_head == initial_head


def test_repair_coordinator_keeps_verified_local_commit_when_push_fails(
    tmp_path: Path,
) -> None:
    _init_repository(tmp_path)
    source = tmp_path / "src" / "cmo_lua_agent" / "worker.py"

    def repair_command(_prompt: str) -> str:
        source.write_text("VALUE = 'verified'\n", encoding="utf-8")
        return "fixed worker"

    coordinator = CodeRepairCoordinator(
        project_root=tmp_path,
        repair_command=repair_command,
        test_runner=lambda _command: True,
        push_runner=lambda: False,
    )
    result = coordinator.repair(
        workflow_id="training-001",
        record=_record(),
        test_command="python -m pytest test_worker.py -q",
        replay_task=lambda: None,
    )

    assert result.succeeded is False
    assert result.push_failed is True
    assert result.commit_id is not None
    assert source.read_text(encoding="utf-8") == "VALUE = 'verified'\n"


def test_repair_coordinator_restores_source_when_backend_raises_after_edit(
    tmp_path: Path,
) -> None:
    _init_repository(tmp_path)
    source = tmp_path / "src" / "cmo_lua_agent" / "worker.py"

    def broken_backend(_prompt: str) -> str:
        source.write_text("VALUE = 'half repaired'\n", encoding="utf-8")
        raise RuntimeError("codex process crashed")

    result = CodeRepairCoordinator(
        project_root=tmp_path,
        repair_command=broken_backend,
        test_runner=lambda _command: True,
    ).repair(
        workflow_id="training-001",
        record=_record(),
        test_command="python -m pytest test_worker.py -q",
    )

    assert result.succeeded is False
    assert source.read_text(encoding="utf-8") == "VALUE = 'before'\n"


def test_repair_coordinator_reports_persisted_statuses_and_commits_root_tests(
    tmp_path: Path,
) -> None:
    _init_repository(tmp_path)
    statuses: list[tuple[str, dict[str, object]]] = []

    class Agent:
        def repair_with_result(self, _context: str, *, workflow_id: str, attempt: int):
            assert workflow_id == "training-001"
            assert attempt == 1
            test = tmp_path / "tests" / "test_worker.py"
            test.parent.mkdir()
            test.write_text("def test_worker():\n    assert True\n", encoding="utf-8")
            return RepairAgentResult(
                RepairAgentStatus.COMPLETED,
                "增加回归测试",
                ("tests/test_worker.py",),
                (),
                "model_final",
            )

    result = CodeRepairCoordinator(
        project_root=tmp_path,
        system_repair_agent=Agent(),
        test_runner=lambda _command: True,
        push_runner=lambda: True,
    ).repair(
        workflow_id="training-001",
        record=_record(),
        test_command="python -m pytest tests/test_worker.py -q",
        replay_task=lambda: None,
        attempt=1,
        progress_callback=lambda status, metadata: statuses.append((status, metadata)),
    )

    assert result.succeeded is True
    assert result.changed_files == ("tests/test_worker.py",)
    assert [status for status, _ in statuses] == [
        "REPAIRING",
        "VERIFYING",
        "COMMITTED",
        "COMMITTED",
    ]
    assert statuses[-1][1]["push_completed"] is True
    assert not (tmp_path / "runs" / "training" / "training-001" / "repair-snapshot.zip").exists()


def test_repair_keeps_verified_source_if_commit_fails_after_replay(tmp_path: Path) -> None:
    _init_repository(tmp_path)
    source = tmp_path / "src" / "cmo_lua_agent" / "worker.py"

    class CommitFailingCoordinator(CodeRepairCoordinator):
        def _commit_repair(self, workflow_id, paths):
            raise RuntimeError("commit failed")

    def repair_command(_prompt: str) -> str:
        source.write_text("VALUE = 'verified by replay'\n", encoding="utf-8")
        return "fixed"

    result = CommitFailingCoordinator(
        project_root=tmp_path,
        repair_command=repair_command,
        test_runner=lambda _command: True,
    ).repair(
        workflow_id="training-001",
        record=_record(),
        test_command="python -m pytest tests/test_worker.py -q",
        replay_task=lambda: None,
    )

    assert result.succeeded is False
    assert result.commit_failed_after_replay is True
    assert source.read_text(encoding="utf-8") == "VALUE = 'verified by replay'\n"
    assert result.snapshot_path is not None and result.snapshot_path.is_file()
