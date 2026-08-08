from __future__ import annotations

from pathlib import Path

from cmo_lua_agent.training.failures import FailureKind, FailureRecord
from cmo_lua_agent.training.repair import CodeRepairCoordinator


def test_repair_coordinator_runs_repair_then_verifies_and_writes_log(tmp_path: Path) -> None:
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
    record = FailureRecord(FailureKind.CODE, "ImportError", "cannot import Worker")

    result = coordinator.repair(
        workflow_id="training-001",
        record=record,
        test_command="python -m pytest src/cmo_lua_agent/tests/training -q",
    )

    assert result.succeeded
    assert calls[1] == "python -m pytest src/cmo_lua_agent/tests/training -q"
    assert "ImportError" in calls[0]
    assert (tmp_path / "runs" / "training" / "training-001" / "code-repair-report.md").is_file()
