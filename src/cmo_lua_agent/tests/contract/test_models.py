from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from cmo_lua_agent.contract.models import (
    ResolvedScenarioManifest,
    ScenarioContract,
    ScenarioIR,
    ScenarioInput,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)


def test_validation_result_is_valid_when_it_has_no_error() -> None:
    result = ValidationResult(
        issues=(
            ValidationIssue(
                code="schema.recommended_field_missing",
                message="建议提供 scenario.description",
                path="$.scenario.description",
                severity=ValidationSeverity.WARNING,
            ),
        )
    )

    assert result.valid is True
    assert result.errors == ()
    assert len(result.warnings) == 1


def test_validation_result_is_invalid_when_it_has_an_error() -> None:
    error = ValidationIssue(
        code="schema.missing_field",
        message="缺少 scenario 字段",
        path="$.scenario",
        severity=ValidationSeverity.ERROR,
    )
    result = ValidationResult(issues=(error,))

    assert result.valid is False
    assert result.errors == (error,)
    assert result.warnings == ()


def test_validation_models_produce_json_ready_dictionaries() -> None:
    result = ValidationResult(
        issues=(
            ValidationIssue(
                code="semantic.unknown_target",
                message="目标不存在",
                path="$.strikePlan[0].targets[0]",
                severity=ValidationSeverity.ERROR,
            ),
        )
    )

    assert result.to_dict() == {
        "valid": False,
        "issues": [
            {
                "code": "semantic.unknown_target",
                "message": "目标不存在",
                "path": "$.strikePlan[0].targets[0]",
                "severity": "error",
            }
        ],
    }


def test_scenario_input_normalizes_source_path_and_serializes() -> None:
    scenario = ScenarioInput(
        source_path=Path("inputs") / "scenario.json",
        raw={"scenario": {"id": "scenario-001"}},
    )

    assert scenario.source_path.is_absolute()
    assert scenario.to_dict() == {
        "source_path": str(scenario.source_path),
        "raw": {"scenario": {"id": "scenario-001"}},
    }


def test_contract_models_expose_stable_json_ready_shapes() -> None:
    ir = ScenarioIR(data={"unit_by_id": {"red-1": {"name": "Red-1"}}})
    contract = ScenarioContract(
        scenario_id="scenario-001",
        unit_ids=("red-1", "blue-1"),
        unit_names=("Red-1", "Blue-1"),
        shooter_ids=("red-1",),
        target_ids=("blue-1",),
    )
    manifest = ResolvedScenarioManifest(
        data={"scenario": {"id": "scenario-001"}}
    )

    assert ir.to_dict() == {
        "unit_by_id": {"red-1": {"name": "Red-1"}}
    }
    assert contract.to_dict() == {
        "scenario_id": "scenario-001",
        "unit_ids": ["red-1", "blue-1"],
        "unit_names": ["Red-1", "Blue-1"],
        "shooter_ids": ["red-1"],
        "target_ids": ["blue-1"],
    }
    assert manifest.to_dict() == {
        "scenario": {"id": "scenario-001"}
    }


def test_contract_models_are_frozen() -> None:
    issue = ValidationIssue(
        code="schema.missing_field",
        message="缺少字段",
        path="$.scenario",
        severity=ValidationSeverity.ERROR,
    )

    with pytest.raises(FrozenInstanceError):
        issue.code = "changed"  # type: ignore[misc]


def test_validation_issue_rejects_blank_machine_fields() -> None:
    with pytest.raises(ValueError, match="code"):
        ValidationIssue(
            code=" ",
            message="缺少字段",
            path="$.scenario",
            severity=ValidationSeverity.ERROR,
        )

    with pytest.raises(ValueError, match="path"):
        ValidationIssue(
            code="schema.missing_field",
            message="缺少字段",
            path=" ",
            severity=ValidationSeverity.ERROR,
        )