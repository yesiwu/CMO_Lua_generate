from __future__ import annotations

import json
from pathlib import Path

import pytest

from cmo_lua_agent.artifacts import (
    ArtifactAlreadyExistsError,
    ArtifactPathError,
    ArtifactPersistenceError,
    RunArtifactStore,
)
from cmo_lua_agent.contract import (
    ResolvedScenarioManifest,
    ScenarioContract,
    ScenarioIR,
    ScenarioInput,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)


def _validation() -> ValidationResult:
    return ValidationResult(
        issues=(
            ValidationIssue(
                code="schema.example",
                message="示例警告",
                path="$.scenario",
                severity=ValidationSeverity.WARNING,
            ),
        )
    )


def _ir() -> ScenarioIR:
    return ScenarioIR(
        data={
            "irVersion": "scenario-ir-v1",
            "scenario": {"id": "demo", "name": "演示场景"},
            "sides": {},
            "unitById": {},
            "strikePlan": [],
        }
    )


def _contract() -> ScenarioContract:
    return ScenarioContract(
        scenario_id="demo",
        unit_ids=("red-1", "blue-1"),
        unit_names=("红方一号", "蓝方一号"),
        shooter_ids=("red-1",),
        target_ids=("blue-1",),
    )


def _manifest() -> ResolvedScenarioManifest:
    return ResolvedScenarioManifest(
        data={
            "manifestVersion": "resolved-scenario-manifest-v1",
            "scenario": {"id": "demo", "name": "演示场景"},
            "sides": {"red": {"units": []}, "blue": {"units": []}},
            "strikePlan": [],
        }
    )


def test_create_builds_standard_run_tree(tmp_path: Path) -> None:
    store = RunArtifactStore.create(
        tmp_path / "runs",
        run_id="run-001",
    )

    assert store.run_id == "run-001"
    assert store.run_root == (tmp_path / "runs/run-001").resolve()
    assert store.paths.input_dir.is_dir()
    assert store.paths.validation_dir.is_dir()
    assert store.paths.contract_dir.is_dir()
    assert store.paths.generation_dir.is_dir()
    assert store.paths.result_dir.is_dir()
    assert store.paths.source_json == store.run_root / "input/source.json"
    assert store.paths.original_lua == store.run_root / "generation/original.lua"
    assert store.paths.workflow_result == store.run_root / "result/workflow_result.json"


def test_create_without_run_id_generates_safe_unique_ids(tmp_path: Path) -> None:
    first = RunArtifactStore.create(tmp_path / "runs")
    second = RunArtifactStore.create(tmp_path / "runs")

    assert first.run_id != second.run_id
    assert first.run_root.is_dir()
    assert second.run_root.is_dir()
    assert "/" not in first.run_id
    assert "\\" not in first.run_id


@pytest.mark.parametrize(
    "run_id",
    ["", "   ", ".", "..", "a/b", r"a\\b", "bad\nname"],
)
def test_invalid_run_id_is_rejected(tmp_path: Path, run_id: str) -> None:
    with pytest.raises(ValueError, match="run_id"):
        RunArtifactStore.create(tmp_path / "runs", run_id=run_id)


def test_duplicate_run_directory_is_rejected(tmp_path: Path) -> None:
    RunArtifactStore.create(tmp_path / "runs", run_id="same")

    with pytest.raises(ArtifactAlreadyExistsError, match="same"):
        RunArtifactStore.create(tmp_path / "runs", run_id="same")


def test_save_source_writes_only_raw_json(tmp_path: Path) -> None:
    source_path = tmp_path / "incoming.json"
    scenario = ScenarioInput(
        source_path=source_path,
        raw={"scenario": {"id": "demo"}, "notes": ["中文"]},
    )
    store = RunArtifactStore.create(tmp_path / "runs", run_id="source")

    saved = store.save_source(scenario)

    assert saved == store.paths.source_json
    assert json.loads(saved.read_text(encoding="utf-8")) == scenario.raw
    assert "source_path" not in saved.read_text(encoding="utf-8")


def test_save_standard_json_artifacts_to_fixed_paths(tmp_path: Path) -> None:
    store = RunArtifactStore.create(tmp_path / "runs", run_id="standard")

    assert store.save_validation("schema", _validation()) == store.paths.schema_report
    assert store.save_validation("semantic", _validation()) == store.paths.semantic_report
    assert store.save_validation("ir", _validation()) == store.paths.ir_report
    assert store.save_validation("database", _validation()) == store.paths.database_report
    assert store.save_validation("lua_preflight", _validation()) == store.paths.lua_preflight_report
    assert store.save_ir(_ir()) == store.paths.scenario_ir
    assert store.save_contract(_contract()) == store.paths.scenario_contract
    assert store.save_manifest(_manifest()) == store.paths.resolved_manifest

    assert json.loads(store.paths.scenario_contract.read_text(encoding="utf-8"))[
        "scenario_id"
    ] == "demo"
    assert json.loads(store.paths.schema_report.read_text(encoding="utf-8"))[
        "issues"
    ][0]["message"] == "示例警告"


def test_unknown_validation_stage_is_rejected(tmp_path: Path) -> None:
    store = RunArtifactStore.create(tmp_path / "runs", run_id="invalid-stage")

    with pytest.raises(ValueError, match="validation stage"):
        store.save_validation("other", _validation())


def test_save_lua_normalizes_line_endings_and_is_exclusive(tmp_path: Path) -> None:
    store = RunArtifactStore.create(tmp_path / "runs", run_id="lua")

    saved = store.save_original_lua("line1\r\nline2\rline3\n")

    assert saved == store.paths.original_lua
    assert saved.read_bytes() == b"line1\nline2\nline3\n"

    with pytest.raises(ArtifactAlreadyExistsError, match="original.lua"):
        store.save_original_lua("replacement")

    assert saved.read_bytes() == b"line1\nline2\nline3\n"


def test_rejected_lua_has_separate_path(tmp_path: Path) -> None:
    store = RunArtifactStore.create(tmp_path / "runs", run_id="rejected")

    saved = store.save_rejected_lua("print('rejected')")

    assert saved == store.paths.rejected_lua
    assert not store.paths.original_lua.exists()


def test_final_result_uses_atomic_replace(tmp_path: Path) -> None:
    store = RunArtifactStore.create(tmp_path / "runs", run_id="result")

    first = store.save_final_result({"status": "running", "step": 1})
    second = store.save_final_result({"status": "completed", "step": 2})

    assert first == second == store.paths.workflow_result
    assert json.loads(second.read_text(encoding="utf-8")) == {
        "status": "completed",
        "step": 2,
    }
    assert list(store.paths.result_dir.glob(".*.tmp")) == []


def test_failed_atomic_serialization_preserves_previous_result(tmp_path: Path) -> None:
    store = RunArtifactStore.create(tmp_path / "runs", run_id="atomic-failure")
    store.save_final_result({"status": "running"})

    with pytest.raises(ArtifactPersistenceError):
        store.save_final_result({"bad": {1, 2, 3}})

    assert json.loads(store.paths.workflow_result.read_text(encoding="utf-8")) == {
        "status": "running"
    }


def test_exclusive_json_failure_leaves_no_partial_target(tmp_path: Path) -> None:
    store = RunArtifactStore.create(tmp_path / "runs", run_id="json-failure")

    with pytest.raises(ArtifactPersistenceError):
        store.write_json("contract/bad.json", {"bad": float("nan")})

    assert not (store.run_root / "contract/bad.json").exists()


def test_generic_writes_reject_absolute_and_escaping_paths(tmp_path: Path) -> None:
    store = RunArtifactStore.create(tmp_path / "runs", run_id="paths")

    with pytest.raises(ArtifactPathError):
        store.write_json(tmp_path / "outside.json", {})

    with pytest.raises(ArtifactPathError):
        store.write_text("../outside.txt", "bad")

    assert not (tmp_path / "runs/outside.txt").exists()


def test_to_dict_exposes_paths_as_strings(tmp_path: Path) -> None:
    store = RunArtifactStore.create(tmp_path / "runs", run_id="dict")

    payload = store.paths.to_dict()

    assert payload["run_id"] == "dict"
    assert payload["run_root"] == str(store.run_root)
    assert payload["resolved_manifest"] == str(store.paths.resolved_manifest)