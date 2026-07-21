from __future__ import annotations

import json
from pathlib import Path

import pytest

from cmo_lua_agent.contract import ScenarioInput
from cmo_lua_agent.ingest import JsonLoadError, JsonLoader


def test_load_returns_scenario_input_with_absolute_source_path(tmp_path: Path) -> None:
    source = tmp_path / "scenario.json"
    payload = {
        "scenario": {"id": "scenario-001"},
        "sides": {"red": {}, "blue": {}},
        "strikePlan": [],
    }
    source.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    result = JsonLoader().load(source)

    assert isinstance(result, ScenarioInput)
    assert result.source_path == source.resolve()
    assert result.raw == payload


def test_load_accepts_utf8_bom(tmp_path: Path) -> None:
    source = tmp_path / "scenario.json"
    source.write_text(
        '{"scenario": {"name": "测试场景"}}',
        encoding="utf-8-sig",
    )

    result = JsonLoader().load(source)

    assert result.raw["scenario"]["name"] == "测试场景"


def test_load_accepts_uppercase_json_suffix(tmp_path: Path) -> None:
    source = tmp_path / "scenario.JSON"
    source.write_text('{"scenario": {}}', encoding="utf-8")

    result = JsonLoader().load(source)

    assert result.source_path == source.resolve()


def test_load_rejects_missing_file(tmp_path: Path) -> None:
    source = tmp_path / "missing.json"

    with pytest.raises(JsonLoadError) as exc_info:
        JsonLoader().load(source)

    error = exc_info.value
    assert error.code == "json.file_not_found"
    assert error.source_path == source.resolve()
    assert error.line is None
    assert error.column is None


def test_load_rejects_directory(tmp_path: Path) -> None:
    source = tmp_path / "scenario.json"
    source.mkdir()

    with pytest.raises(JsonLoadError) as exc_info:
        JsonLoader().load(source)

    assert exc_info.value.code == "json.not_file"


def test_load_rejects_non_json_extension(tmp_path: Path) -> None:
    source = tmp_path / "scenario.txt"
    source.write_text("{}", encoding="utf-8")

    with pytest.raises(JsonLoadError) as exc_info:
        JsonLoader().load(source)

    assert exc_info.value.code == "json.invalid_extension"


def test_load_reports_json_line_and_column(tmp_path: Path) -> None:
    source = tmp_path / "broken.json"
    source.write_text(
        '{\n  "scenario": {},\n  "strikePlan": [\n}',
        encoding="utf-8",
    )

    with pytest.raises(JsonLoadError) as exc_info:
        JsonLoader().load(source)

    error = exc_info.value
    assert error.code == "json.invalid_json"
    assert error.line == 4
    assert error.column == 1
    assert str(source.resolve()) in str(error)
    assert "line 4" in str(error)
    assert "column 1" in str(error)
    assert error.to_dict() == {
        "code": "json.invalid_json",
        "message": error.message,
        "source_path": str(source.resolve()),
        "line": 4,
        "column": 1,
    }


def test_load_rejects_invalid_utf8(tmp_path: Path) -> None:
    source = tmp_path / "invalid.json"
    source.write_bytes(b'{"name": "\xff"}')

    with pytest.raises(JsonLoadError) as exc_info:
        JsonLoader().load(source)

    error = exc_info.value
    assert error.code == "json.invalid_encoding"
    assert error.line is None
    assert error.column is None


@pytest.mark.parametrize(
    "document",
    [
        "[]",
        '"text"',
        "123",
        "true",
        "null",
    ],
)
def test_load_requires_top_level_object(
    tmp_path: Path,
    document: str,
) -> None:
    source = tmp_path / "scenario.json"
    source.write_text(document, encoding="utf-8")

    with pytest.raises(JsonLoadError) as exc_info:
        JsonLoader().load(source)

    error = exc_info.value
    assert error.code == "json.root_not_object"
    assert error.line == 1
    assert error.column == 1