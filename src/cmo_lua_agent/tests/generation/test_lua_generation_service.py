# from __future__ import annotations

# import json
# from pathlib import Path
# from typing import Any

# import pytest

# from cmo_lua_agent.contract import (
#     ResolvedScenarioManifest,
#     ScenarioContract,
#     ValidationIssue,
#     ValidationResult,
#     ValidationSeverity,
# )
# from cmo_lua_agent.generation import (
#     LuaGenerationPersistenceError,
#     LuaGenerationService,
#     LuaPreflightReport,
# )
# from cmo_lua_agent.integrations.cmolua.generator_adapter import (
#     CmoLuaGenerationError,
#     GeneratorRawResult,
# )


# class RecordingAdapter:
#     def __init__(
#         self,
#         *,
#         lua_text: str = "print('generated')",
#         warnings: tuple[str, ...] = (),
#         error: Exception | None = None,
#     ) -> None:
#         self.lua_text = lua_text
#         self.warnings = warnings
#         self.error = error
#         self.calls: list[Path] = []
#         self.manifest_documents: list[dict[str, Any]] = []

#     def generate(self, manifest_path: Path) -> GeneratorRawResult:
#         resolved = Path(manifest_path).resolve()
#         self.calls.append(resolved)
#         assert resolved.is_file()
#         self.manifest_documents.append(
#             json.loads(resolved.read_text(encoding="utf-8"))
#         )
#         if self.error is not None:
#             raise self.error
#         return GeneratorRawResult(
#             lua_text=self.lua_text,
#             warnings=self.warnings,
#         )


# class RecordingPreflightValidator:
#     def __init__(self, report: LuaPreflightReport) -> None:
#         self.report = report
#         self.calls: list[dict[str, Any]] = []

#     def validate(self, lua_text: str, **kwargs: Any) -> LuaPreflightReport:
#         self.calls.append({"lua_text": lua_text, **kwargs})
#         return self.report


# def _manifest() -> ResolvedScenarioManifest:
#     return ResolvedScenarioManifest(
#         data={
#             "manifestVersion": "resolved-scenario-manifest-v1",
#             "scenario": {
#                 "id": "demo",
#                 "name": "中文场景",
#             },
#             "sides": {
#                 "red": {"name": "红方", "units": []},
#                 "blue": {"name": "蓝方", "units": []},
#             },
#             "strikePlan": [],
#         }
#     )


# def _contract() -> ScenarioContract:
#     return ScenarioContract(
#         scenario_id="demo",
#         unit_ids=(),
#         unit_names=(),
#         shooter_ids=(),
#         target_ids=(),
#     )


# def _valid_report() -> LuaPreflightReport:
#     return LuaPreflightReport(validation=ValidationResult())


# def _invalid_report() -> LuaPreflightReport:
#     return LuaPreflightReport(
#         validation=ValidationResult(
#             issues=(
#                 ValidationIssue(
#                     code="preflight.forbidden_api",
#                     message="禁止 API",
#                     path="$.lua",
#                     severity=ValidationSeverity.ERROR,
#                 ),
#             )
#         )
#     )


# def test_generate_persists_manifest_before_adapter_and_writes_lua(
#     tmp_path: Path,
# ) -> None:
#     workspace = tmp_path / "workspace"
#     adapter = RecordingAdapter(lua_text="print('ok')")
#     preflight = RecordingPreflightValidator(_valid_report())
#     service = LuaGenerationService(
#         adapter=adapter,  # type: ignore[arg-type]
#         preflight_validator=preflight,  # type: ignore[arg-type]
#         workspace_root=workspace,
#     )
#     manifest_path = workspace / "runs/run-1/contract/resolved_manifest.json"
#     output_path = workspace / "runs/run-1/generation/original.lua"

#     result = service.generate(
#         manifest=_manifest(),
#         contract=_contract(),
#         manifest_path=manifest_path,
#         output_path=output_path,
#     )

#     assert result.success is True
#     assert result.lua_text == "print('ok')"
#     assert result.output_path == output_path.resolve()
#     assert output_path.read_text(encoding="utf-8") == "print('ok')"
#     assert adapter.calls == [manifest_path.resolve()]
#     assert adapter.manifest_documents == [_manifest().to_dict()]
#     assert json.loads(manifest_path.read_text(encoding="utf-8")) == (
#         _manifest().to_dict()
#     )
#     # ensure_ascii=False keeps the artifact readable, not merely decodable.
#     assert "中文场景" in manifest_path.read_text(encoding="utf-8")


# def test_generate_passes_all_inputs_and_generator_warnings_to_preflight(
#     tmp_path: Path,
# ) -> None:
#     workspace = tmp_path / "workspace"
#     adapter = RecordingAdapter(
#         lua_text="print('candidate')",
#         warnings=("first warning", "second warning"),
#     )
#     preflight = RecordingPreflightValidator(_valid_report())
#     service = LuaGenerationService(
#         adapter=adapter,  # type: ignore[arg-type]
#         preflight_validator=preflight,  # type: ignore[arg-type]
#         workspace_root=workspace,
#     )
#     manifest = _manifest()
#     contract = _contract()
#     output_path = workspace / "generation/original.lua"

#     result = service.generate(
#         manifest=manifest,
#         contract=contract,
#         manifest_path=workspace / "contract/resolved_manifest.json",
#         output_path=output_path,
#     )

#     assert result.generator_warnings == (
#         "first warning",
#         "second warning",
#     )
#     assert len(preflight.calls) == 1
#     call = preflight.calls[0]
#     assert call["lua_text"] == "print('candidate')"
#     assert call["manifest"] is manifest
#     assert call["contract"] is contract
#     assert call["output_path"] == output_path.resolve()
#     assert call["workspace_root"] == workspace.resolve()
#     assert call["generator_warnings"] == (
#         "first warning",
#         "second warning",
#     )


# def test_invalid_preflight_returns_failed_result_and_does_not_write_lua(
#     tmp_path: Path,
# ) -> None:
#     workspace = tmp_path / "workspace"
#     adapter = RecordingAdapter(
#         lua_text="DumpAmmo('unsafe')",
#         warnings=("advisory",),
#     )
#     preflight = RecordingPreflightValidator(_invalid_report())
#     service = LuaGenerationService(
#         adapter=adapter,  # type: ignore[arg-type]
#         preflight_validator=preflight,  # type: ignore[arg-type]
#         workspace_root=workspace,
#     )
#     output_path = workspace / "generation/original.lua"

#     result = service.generate(
#         manifest=_manifest(),
#         contract=_contract(),
#         manifest_path=workspace / "contract/resolved_manifest.json",
#         output_path=output_path,
#     )

#     assert result.success is False
#     assert result.lua_text == "DumpAmmo('unsafe')"
#     assert result.output_path is None
#     assert result.preflight.valid is False
#     assert result.generator_warnings == ("advisory",)
#     assert output_path.exists() is False
#     assert (workspace / "contract/resolved_manifest.json").is_file()


# def test_existing_manifest_is_not_overwritten_and_adapter_is_not_called(
#     tmp_path: Path,
# ) -> None:
#     workspace = tmp_path / "workspace"
#     manifest_path = workspace / "contract/resolved_manifest.json"
#     manifest_path.parent.mkdir(parents=True)
#     manifest_path.write_text('{"existing": true}', encoding="utf-8")
#     adapter = RecordingAdapter()
#     service = LuaGenerationService(
#         adapter=adapter,  # type: ignore[arg-type]
#         preflight_validator=RecordingPreflightValidator(_valid_report()),  # type: ignore[arg-type]
#         workspace_root=workspace,
#     )

#     with pytest.raises(
#         LuaGenerationPersistenceError,
#         match="Manifest.*已存在",
#     ):
#         service.generate(
#             manifest=_manifest(),
#             contract=_contract(),
#             manifest_path=manifest_path,
#             output_path=workspace / "generation/original.lua",
#         )

#     assert manifest_path.read_text(encoding="utf-8") == '{"existing": true}'
#     assert adapter.calls == []


# def test_exclusive_lua_write_is_second_defense_against_overwrite(
#     tmp_path: Path,
# ) -> None:
#     workspace = tmp_path / "workspace"
#     output_path = workspace / "generation/original.lua"
#     output_path.parent.mkdir(parents=True)
#     output_path.write_text("existing Lua", encoding="utf-8")
#     service = LuaGenerationService(
#         adapter=RecordingAdapter(),  # type: ignore[arg-type]
#         # Simulate a stale/incorrect preflight result. Service must still use x.
#         preflight_validator=RecordingPreflightValidator(_valid_report()),  # type: ignore[arg-type]
#         workspace_root=workspace,
#     )

#     with pytest.raises(
#         LuaGenerationPersistenceError,
#         match="Lua 输出文件已存在",
#     ):
#         service.generate(
#             manifest=_manifest(),
#             contract=_contract(),
#             manifest_path=workspace / "contract/resolved_manifest.json",
#             output_path=output_path,
#         )

#     assert output_path.read_text(encoding="utf-8") == "existing Lua"


# def test_adapter_error_propagates_as_typed_external_error(
#     tmp_path: Path,
# ) -> None:
#     workspace = tmp_path / "workspace"
#     adapter_error = CmoLuaGenerationError("generator failed")
#     service = LuaGenerationService(
#         adapter=RecordingAdapter(error=adapter_error),  # type: ignore[arg-type]
#         preflight_validator=RecordingPreflightValidator(_valid_report()),  # type: ignore[arg-type]
#         workspace_root=workspace,
#     )
#     manifest_path = workspace / "contract/resolved_manifest.json"

#     with pytest.raises(CmoLuaGenerationError, match="generator failed"):
#         service.generate(
#             manifest=_manifest(),
#             contract=_contract(),
#             manifest_path=manifest_path,
#             output_path=workspace / "generation/original.lua",
#         )

#     assert manifest_path.is_file()
#     assert not (workspace / "generation/original.lua").exists()


# def test_output_parent_is_created_only_after_preflight_passes(
#     tmp_path: Path,
# ) -> None:
#     workspace = tmp_path / "workspace"
#     output_parent = workspace / "deep/generation"
#     service = LuaGenerationService(
#         adapter=RecordingAdapter(),  # type: ignore[arg-type]
#         preflight_validator=RecordingPreflightValidator(_invalid_report()),  # type: ignore[arg-type]
#         workspace_root=workspace,
#     )

#     result = service.generate(
#         manifest=_manifest(),
#         contract=_contract(),
#         manifest_path=workspace / "contract/resolved_manifest.json",
#         output_path=output_parent / "original.lua",
#     )

#     assert result.success is False
#     assert output_parent.exists() is False


# def test_generate_rejects_wrong_contract_types(tmp_path: Path) -> None:
#     workspace = tmp_path / "workspace"
#     service = LuaGenerationService(
#         adapter=RecordingAdapter(),  # type: ignore[arg-type]
#         preflight_validator=RecordingPreflightValidator(_valid_report()),  # type: ignore[arg-type]
#         workspace_root=workspace,
#     )

#     with pytest.raises(TypeError, match="manifest"):
#         service.generate(
#             manifest={},  # type: ignore[arg-type]
#             contract=_contract(),
#             manifest_path=workspace / "manifest.json",
#             output_path=workspace / "original.lua",
#         )

#     with pytest.raises(TypeError, match="contract"):
#         service.generate(
#             manifest=_manifest(),
#             contract={},  # type: ignore[arg-type]
#             manifest_path=workspace / "manifest.json",
#             output_path=workspace / "original.lua",
#         )

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from cmo_lua_agent.contract import (
    ResolvedScenarioManifest,
    ScenarioContract,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)
from cmo_lua_agent.generation import (
    LuaGenerationService,
    LuaPreflightReport,
)
from cmo_lua_agent.integrations.cmolua.generator_adapter import (
    CmoLuaGenerationError,
    GeneratorRawResult,
)


class RecordingAdapter:
    def __init__(
        self,
        *,
        lua_text: str = "print('ok')",
        warnings: tuple[str, ...] = (),
        error: Exception | None = None,
    ) -> None:
        self.lua_text = lua_text
        self.warnings = warnings
        self.error = error
        self.calls: list[Path] = []
        self.manifest_documents: list[dict[str, Any]] = []

    def generate(self, manifest_path: Path) -> GeneratorRawResult:
        resolved = Path(manifest_path).resolve()
        self.calls.append(resolved)
        self.manifest_documents.append(
            json.loads(resolved.read_text(encoding="utf-8"))
        )
        if self.error is not None:
            raise self.error
        return GeneratorRawResult(
            lua_text=self.lua_text,
            warnings=self.warnings,
        )


class RecordingPreflightValidator:
    def __init__(self, report: LuaPreflightReport) -> None:
        self.report = report
        self.calls: list[dict[str, Any]] = []

    def validate(
        self,
        lua_text: str,
        **kwargs: Any,
    ) -> LuaPreflightReport:
        self.calls.append({"lua_text": lua_text, **kwargs})
        return self.report


def _manifest() -> ResolvedScenarioManifest:
    return ResolvedScenarioManifest(
        data={
            "manifestVersion": "resolved-scenario-manifest-v1",
            "scenario": {
                "id": "demo",
                "name": "中文场景",
            },
            "sides": {
                "red": {"name": "红方", "units": []},
                "blue": {"name": "蓝方", "units": []},
            },
            "strikePlan": [],
        }
    )


def _contract() -> ScenarioContract:
    return ScenarioContract(
        scenario_id="demo",
        unit_ids=(),
        unit_names=(),
        shooter_ids=(),
        target_ids=(),
    )


def _valid_report() -> LuaPreflightReport:
    return LuaPreflightReport(validation=ValidationResult())


def _invalid_report() -> LuaPreflightReport:
    return LuaPreflightReport(
        validation=ValidationResult(
            issues=(
                ValidationIssue(
                    code="preflight.forbidden_api",
                    message="禁止 API",
                    path="$.lua",
                    severity=ValidationSeverity.ERROR,
                ),
            )
        )
    )


def _write_manifest(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            _manifest().to_dict(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_generate_reads_existing_manifest_and_performs_no_writes(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    manifest_path = workspace / "contract/resolved_manifest.json"
    output_path = workspace / "generation/original.lua"
    _write_manifest(manifest_path)

    adapter = RecordingAdapter(lua_text="print('ok')")
    preflight = RecordingPreflightValidator(_valid_report())
    service = LuaGenerationService(
        adapter=adapter,  # type: ignore[arg-type]
        preflight_validator=preflight,  # type: ignore[arg-type]
        workspace_root=workspace,
    )

    result = service.generate(
        manifest=_manifest(),
        contract=_contract(),
        manifest_path=manifest_path,
        output_path=output_path,
    )

    assert result.success is True
    assert result.lua_text == "print('ok')"
    assert result.output_path == output_path.resolve()
    assert adapter.calls == [manifest_path.resolve()]
    assert adapter.manifest_documents == [_manifest().to_dict()]
    assert output_path.exists() is False
    assert output_path.parent.exists() is False
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == (
        _manifest().to_dict()
    )


def test_generate_requires_an_existing_manifest_file(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    adapter = RecordingAdapter()
    service = LuaGenerationService(
        adapter=adapter,  # type: ignore[arg-type]
        preflight_validator=RecordingPreflightValidator(
            _valid_report()
        ),  # type: ignore[arg-type]
        workspace_root=workspace,
    )

    with pytest.raises(FileNotFoundError, match="Manifest"):
        service.generate(
            manifest=_manifest(),
            contract=_contract(),
            manifest_path=workspace / "missing.json",
            output_path=workspace / "original.lua",
        )

    assert adapter.calls == []
    assert workspace.exists() is False


def test_generate_passes_all_inputs_and_warnings_to_preflight(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    manifest_path = workspace / "contract/resolved_manifest.json"
    _write_manifest(manifest_path)
    output_path = workspace / "generation/original.lua"
    adapter = RecordingAdapter(
        lua_text="print('candidate')",
        warnings=("first warning", "second warning"),
    )
    preflight = RecordingPreflightValidator(_valid_report())
    service = LuaGenerationService(
        adapter=adapter,  # type: ignore[arg-type]
        preflight_validator=preflight,  # type: ignore[arg-type]
        workspace_root=workspace,
    )
    manifest = _manifest()
    contract = _contract()

    result = service.generate(
        manifest=manifest,
        contract=contract,
        manifest_path=manifest_path,
        output_path=output_path,
    )

    assert result.generator_warnings == (
        "first warning",
        "second warning",
    )
    assert len(preflight.calls) == 1
    call = preflight.calls[0]
    assert call["lua_text"] == "print('candidate')"
    assert call["manifest"] is manifest
    assert call["contract"] is contract
    assert call["output_path"] == output_path.resolve()
    assert call["workspace_root"] == workspace.resolve()
    assert call["generator_warnings"] == (
        "first warning",
        "second warning",
    )
    assert output_path.exists() is False


def test_invalid_preflight_returns_rejected_candidate_without_writing(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    manifest_path = workspace / "contract/resolved_manifest.json"
    _write_manifest(manifest_path)
    output_path = workspace / "generation/original.lua"
    service = LuaGenerationService(
        adapter=RecordingAdapter(
            lua_text="DumpAmmo('unsafe')",
            warnings=("advisory",),
        ),  # type: ignore[arg-type]
        preflight_validator=RecordingPreflightValidator(
            _invalid_report()
        ),  # type: ignore[arg-type]
        workspace_root=workspace,
    )

    result = service.generate(
        manifest=_manifest(),
        contract=_contract(),
        manifest_path=manifest_path,
        output_path=output_path,
    )

    assert result.success is False
    assert result.lua_text == "DumpAmmo('unsafe')"
    assert result.output_path is None
    assert result.preflight.valid is False
    assert result.generator_warnings == ("advisory",)
    assert output_path.exists() is False


def test_adapter_error_propagates_without_modifying_artifacts(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    manifest_path = workspace / "contract/resolved_manifest.json"
    output_path = workspace / "generation/original.lua"
    _write_manifest(manifest_path)
    before = manifest_path.read_bytes()
    adapter_error = CmoLuaGenerationError("generator failed")
    service = LuaGenerationService(
        adapter=RecordingAdapter(error=adapter_error),  # type: ignore[arg-type]
        preflight_validator=RecordingPreflightValidator(
            _valid_report()
        ),  # type: ignore[arg-type]
        workspace_root=workspace,
    )

    with pytest.raises(CmoLuaGenerationError, match="generator failed"):
        service.generate(
            manifest=_manifest(),
            contract=_contract(),
            manifest_path=manifest_path,
            output_path=output_path,
        )

    assert manifest_path.read_bytes() == before
    assert output_path.exists() is False


def test_generate_rejects_wrong_contract_types(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    manifest_path = workspace / "manifest.json"
    _write_manifest(manifest_path)
    service = LuaGenerationService(
        adapter=RecordingAdapter(),  # type: ignore[arg-type]
        preflight_validator=RecordingPreflightValidator(
            _valid_report()
        ),  # type: ignore[arg-type]
        workspace_root=workspace,
    )

    with pytest.raises(TypeError, match="manifest"):
        service.generate(
            manifest={},  # type: ignore[arg-type]
            contract=_contract(),
            manifest_path=manifest_path,
            output_path=workspace / "original.lua",
        )

    with pytest.raises(TypeError, match="contract"):
        service.generate(
            manifest=_manifest(),
            contract={},  # type: ignore[arg-type]
            manifest_path=manifest_path,
            output_path=workspace / "original.lua",
        )