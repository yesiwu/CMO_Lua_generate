from __future__ import annotations

import json
from pathlib import Path

import pytest

from cmo_lua_agent.evolution.execution_diagnostic_matrix import (
    ExecutionDiagnosticError,
    ExecutionDiagnosticMatrix,
)


def _attempt(root: Path, *, score: int, pulse_seconds: int) -> Path:
    root.mkdir(parents=True)
    (root / "candidate.lua").write_text("print('candidate')\n", encoding="utf-8")
    (root / "scenario.scen").write_bytes(b"scenario")
    (root / "batch-job.json").write_text(json.dumps({
        "simulation": {"enabled": True, "pulseSeconds": pulse_seconds, "stopWhenScenarioEnds": False},
        "outputDirectory": "batch-results",
    }), encoding="utf-8")
    (root / "execution-summary.json").write_text(json.dumps({
        "official_score": {"stable_side_id": "red", "cmo_side_id": "red", "status": "VALID", "initial": 0, "final": score},
        "score_events": [{"delta": score}],
        "score_event_chain_status": "VALID",
        "evidence_integrity": {"status": "VALID"},
        "runtime_execution": {
            "simulation_elapsed_seconds": 300,
            "stop_reason": "completed",
            "scheduled_operation_count": 2,
            "started_operation_count": 2,
            "completed_operation_count": 2,
            "pending_operation_count": 0,
            "execution_fidelity": "complete",
        },
    }), encoding="utf-8")
    return root


def test_matrix_compares_formal_attempt_artifacts_without_score_fallback(tmp_path: Path) -> None:
    left = _attempt(tmp_path / "historical", score=260, pulse_seconds=1)
    right = _attempt(tmp_path / "dynamic", score=-40, pulse_seconds=5)

    report = ExecutionDiagnosticMatrix().compare(
        experiment_id="a-fixed-lua-job",
        attempts={"historical_job": left, "dynamic_job": right},
    )

    assert report.experiment_id == "a-fixed-lua-job"
    assert report.attempts["historical_job"].official_final_score == 260
    assert report.attempts["dynamic_job"].official_final_score == -40
    assert report.attempts["dynamic_job"].execution_fidelity == "complete"
    assert report.attempts["dynamic_job"].simulation["pulse_seconds"] == 5
    assert report.comparisons["dynamic_job::historical_job"]["official_final_score"] == {"left": -40, "right": 260}
    assert "lua_checksum" in report.attempts["historical_job"].to_dict()
    assert "sqlite" not in json.dumps(report.to_dict()).lower()


def test_matrix_rejects_summary_that_is_not_the_formal_score_contract(tmp_path: Path) -> None:
    attempt = _attempt(tmp_path / "bad", score=0, pulse_seconds=1)
    payload = json.loads((attempt / "execution-summary.json").read_text(encoding="utf-8"))
    payload["official_score"]["cmo_side_id"] = "blue"
    (attempt / "execution-summary.json").write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ExecutionDiagnosticError, match="execution_summary_score_contract_invalid"):
        ExecutionDiagnosticMatrix().compare(experiment_id="invalid", attempts={"bad": attempt})
