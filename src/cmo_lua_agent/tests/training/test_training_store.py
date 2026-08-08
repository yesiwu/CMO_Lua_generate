from __future__ import annotations

import json
from pathlib import Path

import pytest

from cmo_lua_agent.training.models import (
    TrainingAction,
    TrainingRequest,
    TrainingStage,
    TrainingStatus,
)
from cmo_lua_agent.training.store import TrainingStore
from cmo_lua_agent.training.store import TrainingWorkflowLockError


def _request() -> TrainingRequest:
    return TrainingRequest.create(
        workflow_id="training-001",
        session_id="session-001",
        input_path="baseline/6v4/manual-template/6v4ScenarioIR_baseline_v3.json",
        objective="improve official red score",
        generation_count=3,
    )


def test_training_store_creates_minimal_resumable_workflow_files(
    tmp_path: Path,
) -> None:
    store = TrainingStore(tmp_path, "training-001")
    request = _request()

    state = store.create(request)

    assert state.status is TrainingStatus.CREATED
    assert state.stage is TrainingStage.PREPARE
    assert state.action is TrainingAction.VALIDATE_INPUT
    assert state.completed_generations == ()
    assert store.load_request() == request
    assert store.load_state() == state
    assert (store.root / "request.json").is_file()
    assert (store.root / "state.json").is_file()
    assert (store.root / "summary.json").is_file()
    assert (store.root / "TODO.md").is_file()
    journal = (store.root / "journal.jsonl").read_text(encoding="utf-8")
    assert json.loads(journal) == {
        "event": "workflow_created",
        "sequence": 1,
        "workflow_id": "training-001",
    }


def test_training_store_transitions_state_with_monotonic_revision(tmp_path: Path) -> None:
    store = TrainingStore(tmp_path, "training-001")
    initial = store.create(_request())

    changed = store.transition(
        status=TrainingStatus.RUNNING,
        stage=TrainingStage.EVOLUTION,
        action=TrainingAction.PREVIEW,
        current_generation=0,
    )

    assert changed.revision == initial.revision + 1
    assert changed.status is TrainingStatus.RUNNING
    assert changed.stage is TrainingStage.EVOLUTION
    assert changed.action is TrainingAction.PREVIEW
    assert changed.current_generation == 0
    assert json.loads((store.root / "journal.jsonl").read_text(encoding="utf-8").splitlines()[-1]) == {
        "event": "state_transition",
        "revision": 1,
        "sequence": 2,
        "workflow_id": "training-001",
    }


def test_training_store_transition_persists_campaign_and_completed_generations(
    tmp_path: Path,
) -> None:
    store = TrainingStore(tmp_path, "training-001")
    store.create(_request())

    changed = store.transition(
        campaign_id="training-001-campaign",
        completed_generations=(0,),
        action=TrainingAction.SUMMARIZE,
    )

    assert changed.campaign_id == "training-001-campaign"
    assert changed.completed_generations == (0,)
    assert store.load_state() == changed


def test_training_store_allows_only_one_runner_lock(tmp_path: Path) -> None:
    store = TrainingStore(tmp_path, "training-001")
    store.create(_request())
    first = store.lock()
    second = TrainingStore(tmp_path, "training-001").lock()

    first.acquire()

    try:
        with pytest.raises(TrainingWorkflowLockError):
            second.acquire()
    finally:
        first.release()
