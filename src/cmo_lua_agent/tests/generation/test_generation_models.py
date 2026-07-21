from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from cmo_lua_agent.contract import (
    ResolvedScenarioManifest,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)
from cmo_lua_agent.generation import (
    LuaGenerationRequest,
    LuaGenerationResult,
    LuaPreflightReport,
)


def _manifest() -> ResolvedScenarioManifest:
    return ResolvedScenarioManifest(
        data={
            "manifestVersion": "resolved-scenario-manifest-v1",
            "scenario": {
                "id": "scenario-001",
                "name": "测试场景",
            },
            "sides": {
                "red": {"name": "红方", "units": []},
                "blue": {"name": "蓝方", "units": []},
            },
            "strikePlan": [],
        }
    )


def _valid_preflight() -> LuaPreflightReport:
    return LuaPreflightReport(
        validation=ValidationResult()
    )


def _invalid_preflight() -> LuaPreflightReport:
    return LuaPreflightReport(
        validation=ValidationResult(
            issues=(
                ValidationIssue(
                    code="preflight.forbidden_api",
                    message="Lua 使用了禁止 API",
                    path="$.lua",
                    severity=ValidationSeverity.ERROR,
                ),
            )
        )
    )


def test_request_normalizes_paths_and_serializes_manifest(
    tmp_path: Path,
) -> None:
    request = LuaGenerationRequest(
        manifest=_manifest(),
        manifest_path=tmp_path / "contract" / "resolved.json",
        output_path=tmp_path / "generation" / "original.lua",
    )

    assert request.manifest_path.is_absolute()
    assert request.output_path.is_absolute()
    assert request.to_dict() == {
        "manifest": _manifest().to_dict(),
        "manifest_path": str(
            (tmp_path / "contract" / "resolved.json").resolve()
        ),
        "output_path": str(
            (tmp_path / "generation" / "original.lua").resolve()
        ),
    }


def test_request_rejects_non_manifest(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="ResolvedScenarioManifest"):
        LuaGenerationRequest(
            manifest={},  # type: ignore[arg-type]
            manifest_path=tmp_path / "resolved.json",
            output_path=tmp_path / "original.lua",
        )


def test_preflight_report_delegates_validation_state() -> None:
    report = _invalid_preflight()

    assert report.valid is False
    assert len(report.errors) == 1
    assert report.warnings == ()
    assert report.to_dict() == {
        "valid": False,
        "issues": [
            {
                "code": "preflight.forbidden_api",
                "message": "Lua 使用了禁止 API",
                "path": "$.lua",
                "severity": "error",
            }
        ],
    }


def test_preflight_report_rejects_non_validation_result() -> None:
    with pytest.raises(TypeError, match="ValidationResult"):
        LuaPreflightReport(
            validation={},  # type: ignore[arg-type]
        )


def test_success_result_is_stable_and_json_serializable(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "generation" / "original.lua"
    result = LuaGenerationResult(
        success=True,
        lua_text="  print('ok')\n",
        output_path=output_path,
        generator_warnings=(" first warning ", "second warning"),
        preflight=_valid_preflight(),
    )

    assert result.lua_text == "  print('ok')\n"
    assert result.output_path == output_path.resolve()
    assert result.generator_warnings == (
        "first warning",
        "second warning",
    )
    assert result.to_dict() == {
        "success": True,
        "lua_text": "  print('ok')\n",
        "output_path": str(output_path.resolve()),
        "generator_warnings": [
            "first warning",
            "second warning",
        ],
        "preflight": {
            "valid": True,
            "issues": [],
        },
    }


@pytest.mark.parametrize(
    ("lua_text", "output_path", "preflight", "message"),
    [
        (None, Path("original.lua"), _valid_preflight(), "lua_text"),
        ("print('ok')", None, _valid_preflight(), "output_path"),
        (
            "print('ok')",
            Path("original.lua"),
            _invalid_preflight(),
            "preflight",
        ),
    ],
)
def test_success_result_rejects_inconsistent_state(
    lua_text: str | None,
    output_path: Path | None,
    preflight: LuaPreflightReport,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        LuaGenerationResult(
            success=True,
            lua_text=lua_text,
            output_path=output_path,
            generator_warnings=(),
            preflight=preflight,
        )


def test_failed_result_can_keep_candidate_lua_without_written_path() -> None:
    result = LuaGenerationResult(
        success=False,
        lua_text="print('candidate')",
        output_path=None,
        generator_warnings=("warning",),
        preflight=_invalid_preflight(),
    )

    assert result.success is False
    assert result.lua_text == "print('candidate')"
    assert result.output_path is None
    assert result.preflight.valid is False


def test_result_rejects_blank_warning() -> None:
    with pytest.raises(ValueError, match="generator_warnings"):
        LuaGenerationResult(
            success=False,
            lua_text=None,
            output_path=None,
            generator_warnings=("   ",),
            preflight=_invalid_preflight(),
        )


def test_generation_models_are_frozen(tmp_path: Path) -> None:
    request = LuaGenerationRequest(
        manifest=_manifest(),
        manifest_path=tmp_path / "resolved.json",
        output_path=tmp_path / "original.lua",
    )

    with pytest.raises(FrozenInstanceError):
        request.output_path = tmp_path / "changed.lua"  # type: ignore[misc]