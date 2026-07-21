from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import pytest

from cmo_lua_agent.artifacts import (
    ArtifactSerializationError,
    serialize_json,
    serialize_text,
    to_json_compatible,
)
from cmo_lua_agent.contract import (
    ResolvedScenarioManifest,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)


class DemoMode(str, Enum):
    SAFE = "safe"


@dataclass(frozen=True)
class DemoDataclass:
    name: str
    path: Path
    values: tuple[int, ...]


class ToDictObject:
    def __init__(self) -> None:
        self.called = 0

    def to_dict(self) -> dict[str, object]:
        self.called += 1
        return {
            "mode": DemoMode.SAFE,
            "path": Path("runs/demo"),
        }


def test_serialize_json_supports_contract_models_and_unicode() -> None:
    manifest = ResolvedScenarioManifest(
        data={
            "scenario": {
                "id": "demo",
                "name": "中文场景",
            },
            "sides": {},
            "strikePlan": [],
        }
    )

    text = serialize_json(manifest)

    assert text.endswith("\n")
    assert "中文场景" in text
    assert "\\u4e2d" not in text
    assert json.loads(text) == manifest.to_dict()


def test_serialize_json_is_stable_and_sorts_mapping_keys() -> None:
    value = {
        "z": 1,
        "a": {
            "second": 2,
            "first": 1,
        },
    }

    first = serialize_json(value)
    second = serialize_json(value)

    assert first == second
    assert first.index('"a"') < first.index('"z"')
    assert first.index('"first"') < first.index('"second"')


def test_to_json_compatible_supports_paths_enums_tuples_and_dataclasses(
    tmp_path: Path,
) -> None:
    value = DemoDataclass(
        name="demo",
        path=tmp_path / "artifact.json",
        values=(1, 2),
    )

    converted = to_json_compatible(value)

    assert converted == {
        "name": "demo",
        "path": str(tmp_path / "artifact.json"),
        "values": [1, 2],
    }


def test_to_json_compatible_prefers_explicit_to_dict() -> None:
    value = ToDictObject()

    converted = to_json_compatible(value)

    assert converted == {
        "mode": "safe",
        "path": str(Path("runs/demo")),
    }
    assert value.called == 1


def test_validation_result_is_serialized_through_its_contract() -> None:
    result = ValidationResult(
        issues=(
            ValidationIssue(
                code="schema.invalid_type",
                message="字段类型错误",
                path="$.scenario",
                severity=ValidationSeverity.ERROR,
            ),
        )
    )

    assert json.loads(serialize_json(result)) == result.to_dict()


@pytest.mark.parametrize(
    "number",
    [float("nan"), float("inf"), float("-inf")],
)
def test_non_finite_numbers_are_rejected(number: float) -> None:
    with pytest.raises(
        ArtifactSerializationError,
        match="finite",
    ):
        serialize_json({"number": number})


def test_non_string_mapping_key_is_rejected_with_path() -> None:
    with pytest.raises(
        ArtifactSerializationError,
        match=r"\$.*mapping keys",
    ):
        serialize_json({1: "invalid"})


def test_unsupported_values_are_rejected_with_precise_path() -> None:
    with pytest.raises(
        ArtifactSerializationError,
        match=r"\$\.items\[1\]",
    ):
        serialize_json({"items": ["ok", object()]})


def test_sets_are_rejected_instead_of_being_nondeterministically_sorted() -> None:
    with pytest.raises(
        ArtifactSerializationError,
        match="set",
    ):
        serialize_json({"values": {1, 2}})


def test_cycles_are_rejected_instead_of_recursing_forever() -> None:
    value: list[object] = []
    value.append(value)

    with pytest.raises(
        ArtifactSerializationError,
        match="cyclic",
    ):
        serialize_json(value)


def test_serialize_text_normalizes_line_endings_without_trimming() -> None:
    text = "line 1\r\nline 2\rline 3\n\n"

    assert serialize_text(text) == "line 1\nline 2\nline 3\n\n"


def test_serialize_text_preserves_empty_and_non_newline_terminated_text() -> None:
    assert serialize_text("") == ""
    assert serialize_text("print('ok')") == "print('ok')"


def test_serialize_text_rejects_non_string() -> None:
    with pytest.raises(TypeError, match="text"):
        serialize_text(b"bytes")  # type: ignore[arg-type]