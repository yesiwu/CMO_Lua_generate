from __future__ import annotations

from pathlib import Path

import pytest

from cmo_lua_agent.artifacts import RunArtifactStore
from cmo_lua_agent.orchestration import (
    WorkflowStage,
    WorkflowState,
    WorkflowStatus,
    WorkflowTransitionError,
)


def _paths(tmp_path: Path):
    return RunArtifactStore.create(
        tmp_path / "runs",
        run_id="run-state",
    ).paths


def test_initial_state_contains_canonical_artifact_paths(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)

    state = WorkflowState.initial(paths)

    assert state.run_id == "run-state"
    assert state.status is WorkflowStatus.CREATED
    assert state.stage is WorkflowStage.CREATED
    assert state.error_code is None
    assert state.error_message is None
    assert state.artifact_paths == paths.to_dict()
    assert state.to_dict() == {
        "run_id": "run-state",
        "status": "created",
        "stage": "created",
        "artifact_paths": paths.to_dict(),
        "error_code": None,
        "error_message": None,
    }


def test_artifact_paths_are_defensively_immutable(
    tmp_path: Path,
) -> None:
    state = WorkflowState.initial(_paths(tmp_path))

    with pytest.raises(TypeError):
        state.artifact_paths["original_lua"] = "changed"  # type: ignore[index]


def test_state_advances_in_strict_forward_order(
    tmp_path: Path,
) -> None:
    initial = WorkflowState.initial(_paths(tmp_path))

    manifest = initial.advance(WorkflowStage.MANIFEST)
    generation = manifest.advance(WorkflowStage.GENERATION)
    completed = generation.complete()

    assert initial.status is WorkflowStatus.CREATED
    assert manifest.status is WorkflowStatus.RUNNING
    assert manifest.stage is WorkflowStage.MANIFEST
    assert generation.status is WorkflowStatus.RUNNING
    assert generation.stage is WorkflowStage.GENERATION
    assert completed.status is WorkflowStatus.COMPLETED
    assert completed.stage is WorkflowStage.COMPLETED


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (WorkflowStage.CREATED, WorkflowStage.GENERATION),
        (WorkflowStage.MANIFEST, WorkflowStage.CREATED),
        (WorkflowStage.GENERATION, WorkflowStage.MANIFEST),
        (WorkflowStage.GENERATION, WorkflowStage.COMPLETED),
    ],
)
def test_illegal_stage_transition_is_rejected(
    tmp_path: Path,
    current: WorkflowStage,
    target: WorkflowStage,
) -> None:
    state = WorkflowState.initial(_paths(tmp_path))
    if current is WorkflowStage.MANIFEST:
        state = state.advance(WorkflowStage.MANIFEST)
    elif current is WorkflowStage.GENERATION:
        state = state.advance(
            WorkflowStage.MANIFEST
        ).advance(WorkflowStage.GENERATION)

    with pytest.raises(WorkflowTransitionError):
        state.advance(target)


def test_complete_requires_generation_stage(tmp_path: Path) -> None:
    state = WorkflowState.initial(_paths(tmp_path))

    with pytest.raises(WorkflowTransitionError):
        state.complete()


def test_fail_preserves_current_stage_and_requires_metadata(
    tmp_path: Path,
) -> None:
    state = WorkflowState.initial(_paths(tmp_path)).advance(
        WorkflowStage.MANIFEST
    )

    failed = state.fail("generation_failed", "generator failed")

    assert failed.status is WorkflowStatus.FAILED
    assert failed.stage is WorkflowStage.MANIFEST
    assert failed.error_code == "generation_failed"
    assert failed.error_message == "generator failed"

    with pytest.raises(ValueError, match="code"):
        state.fail(" ", "message")
    with pytest.raises(ValueError, match="message"):
        state.fail("code", " ")


def test_completed_and_failed_states_are_terminal(
    tmp_path: Path,
) -> None:
    state = WorkflowState.initial(_paths(tmp_path))
    generation = state.advance(
        WorkflowStage.MANIFEST
    ).advance(WorkflowStage.GENERATION)
    completed = generation.complete()
    failed = generation.fail("failed", "failed")

    for terminal in (completed, failed):
        with pytest.raises(WorkflowTransitionError):
            terminal.advance(WorkflowStage.MANIFEST)
        with pytest.raises(WorkflowTransitionError):
            terminal.complete()
        with pytest.raises(WorkflowTransitionError):
            terminal.fail("again", "again")


def test_needs_user_input_is_a_terminal_auditable_state(
    tmp_path: Path,
) -> None:
    state = WorkflowState.initial(_paths(tmp_path))
    for stage in (
        WorkflowStage.INPUT,
        WorkflowStage.SCHEMA,
        WorkflowStage.SEMANTIC,
        WorkflowStage.IR,
        WorkflowStage.DATABASE,
    ):
        state = state.advance(stage)

    waiting = state.needs_user_input(
        "platform_resolution_required",
        "请选择平台类别",
    )

    assert waiting.status is WorkflowStatus.NEEDS_USER_INPUT
    assert waiting.stage is WorkflowStage.DATABASE
    assert waiting.error_code == "platform_resolution_required"
    with pytest.raises(WorkflowTransitionError):
        waiting.advance(WorkflowStage.MANIFEST)
