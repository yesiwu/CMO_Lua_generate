from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from cmo_lua_agent.optimization.candidate_artifact_store import CandidateArtifactStore
from cmo_lua_agent.optimization.candidate_evaluation_workflow import (
    CandidateEvaluationWorkflow,
)
from cmo_lua_agent.execution.models import CmoError, CmoProcessResult, CmoRunResult


def _record(results: Path) -> SimpleNamespace:
    return SimpleNamespace(
        result=SimpleNamespace(
            batch_result_dir=results,
            process_result=SimpleNamespace(batch_result_dir=results),
            success=True,
        )
    )


def test_simplified_slot_score_reads_numeric_final_from_its_own_results(
    tmp_path: Path,
) -> None:
    results = tmp_path / "slot-results" / "001_slot"
    results.mkdir(parents=True)
    (results / "execution-summary.json").write_text(
        json.dumps({"official_score": {"final": 35}}),
        encoding="utf-8",
    )
    store = CandidateArtifactStore(tmp_path / "candidate_00", "candidate_00")

    evaluation = CandidateEvaluationWorkflow._official_score_only_evaluation(
        record=_record(results.parent),
        store=store,
        attempt_dir="attempts/attempt_00",
    )

    assert evaluation.native_snapshot.native_score_final == 35
    assert evaluation.semantic_validation.scoreable is True
    assert evaluation.attack_episodes == ()
    assert (store.root / "attempts" / "attempt_00" / "execution-summary.json").is_file()


def test_simplified_slot_score_rejects_non_numeric_final(
    tmp_path: Path,
) -> None:
    results = tmp_path / "slot-results" / "001_slot"
    results.mkdir(parents=True)
    (results / "execution-summary.json").write_text(
        json.dumps({"official_score": {"final": "35"}}),
        encoding="utf-8",
    )
    store = CandidateArtifactStore(tmp_path / "candidate_00", "candidate_00")

    evaluation = CandidateEvaluationWorkflow._official_score_only_evaluation(
        record=_record(results.parent),
        store=store,
        attempt_dir="attempts/attempt_00",
    )

    assert evaluation.native_snapshot.native_score_final is None
    assert evaluation.semantic_validation.scoreable is False


def test_execution_failure_uses_cmo_run_result_not_execution_record() -> None:
    result = CmoRunResult(
        success=False,
        lua_path=Path("candidate.lua"),
        log_path=Path("cmo.log"),
        process_result=CmoProcessResult(
            exit_code=2,
            timed_out=False,
            duration_seconds=0.1,
            console_output="configuration error",
        ),
        restore_succeeded=True,
        error=CmoError("process_exit_error", "configuration error"),
    )

    assert CandidateEvaluationWorkflow._execution_reason(result).value == "lua_runtime_error"


def test_reused_candidate_allocates_next_attempt_directory(tmp_path: Path) -> None:
    store = CandidateArtifactStore(tmp_path / "candidate_00", "candidate_00")
    store.path("attempts/attempt_00").mkdir(parents=True)
    store.path("attempts/attempt_03").mkdir(parents=True)

    assert CandidateEvaluationWorkflow._next_attempt_index(store) == 4
