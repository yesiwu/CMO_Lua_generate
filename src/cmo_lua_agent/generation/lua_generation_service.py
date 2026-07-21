# """Application service for deterministic manifest-to-Lua generation."""

# from __future__ import annotations

# import json
# from pathlib import Path

# from cmo_lua_agent.contract import (
#     ResolvedScenarioManifest,
#     ScenarioContract,
# )
# from cmo_lua_agent.generation.lua_preflight_validator import (
#     LuaPreflightValidator,
# )
# from cmo_lua_agent.generation.models import LuaGenerationResult
# from cmo_lua_agent.integrations.cmolua.generator_adapter import (
#     CmoLuaGeneratorAdapter,
# )


# class LuaGenerationPersistenceError(RuntimeError):
#     """Manifest or accepted Lua could not be persisted safely."""


# class LuaGenerationService:
#     """Persist a manifest, generate Lua, validate it, and persist if accepted.

#     The service deliberately does not perform scenario validation, database
#     resolution, artifact-directory allocation, or CMO execution. Those belong
#     to earlier/later workflow stages.
#     """

#     def __init__(
#         self,
#         *,
#         adapter: CmoLuaGeneratorAdapter,
#         preflight_validator: LuaPreflightValidator,
#         workspace_root: Path,
#     ) -> None:
#         self._adapter = adapter
#         self._preflight_validator = preflight_validator
#         self._workspace_root = _normalize_path(
#             workspace_root,
#             field_name="workspace_root",
#         )

#     def generate(
#         self,
#         *,
#         manifest: ResolvedScenarioManifest,
#         contract: ScenarioContract,
#         manifest_path: Path,
#         output_path: Path,
#     ) -> LuaGenerationResult:
#         """Run the fixed manifest → generator → preflight → write sequence."""

#         if not isinstance(manifest, ResolvedScenarioManifest):
#             raise TypeError(
#                 "manifest must be a ResolvedScenarioManifest"
#             )
#         if not isinstance(contract, ScenarioContract):
#             raise TypeError(
#                 "contract must be a ScenarioContract"
#             )

#         resolved_manifest_path = _normalize_path(
#             manifest_path,
#             field_name="manifest_path",
#         )
#         resolved_output_path = _normalize_path(
#             output_path,
#             field_name="output_path",
#         )

#         _write_json_exclusive(
#             resolved_manifest_path,
#             manifest.to_dict(),
#         )

#         raw_result = self._adapter.generate(
#             resolved_manifest_path
#         )

#         preflight = self._preflight_validator.validate(
#             raw_result.lua_text,
#             manifest=manifest,
#             contract=contract,
#             output_path=resolved_output_path,
#             workspace_root=self._workspace_root,
#             generator_warnings=raw_result.warnings,
#         )

#         if not preflight.valid:
#             return LuaGenerationResult(
#                 success=False,
#                 lua_text=raw_result.lua_text,
#                 output_path=None,
#                 generator_warnings=raw_result.warnings,
#                 preflight=preflight,
#             )

#         _write_text_exclusive(
#             resolved_output_path,
#             raw_result.lua_text,
#         )

#         return LuaGenerationResult(
#             success=True,
#             lua_text=raw_result.lua_text,
#             output_path=resolved_output_path,
#             generator_warnings=raw_result.warnings,
#             preflight=preflight,
#         )


# def _write_json_exclusive(
#     path: Path,
#     value: object,
# ) -> None:
#     path.parent.mkdir(parents=True, exist_ok=True)

#     try:
#         with path.open(
#             "x",
#             encoding="utf-8",
#             newline="\n",
#         ) as file_handle:
#             json.dump(
#                 value,
#                 file_handle,
#                 ensure_ascii=False,
#                 indent=2,
#                 sort_keys=True,
#             )
#             file_handle.write("\n")
#     except FileExistsError as exc:
#         raise LuaGenerationPersistenceError(
#             f"Manifest 文件已存在，禁止覆盖：{path}"
#         ) from exc
#     except (OSError, TypeError, ValueError) as exc:
#         _remove_partial_file(path)
#         raise LuaGenerationPersistenceError(
#             f"无法保存 Manifest：{path}：{exc}"
#         ) from exc


# def _write_text_exclusive(
#     path: Path,
#     text: str,
# ) -> None:
#     path.parent.mkdir(parents=True, exist_ok=True)

#     try:
#         with path.open(
#             "x",
#             encoding="utf-8",
#             newline="",
#         ) as file_handle:
#             file_handle.write(text)
#     except FileExistsError as exc:
#         raise LuaGenerationPersistenceError(
#             f"Lua 输出文件已存在，禁止覆盖：{path}"
#         ) from exc
#     except OSError as exc:
#         _remove_partial_file(path)
#         raise LuaGenerationPersistenceError(
#             f"无法保存 Lua 输出：{path}：{exc}"
#         ) from exc


# def _remove_partial_file(path: Path) -> None:
#     try:
#         if path.is_file():
#             path.unlink()
#     except OSError:
#         # Preserve the original persistence failure. Artifact cleanup is best
#         # effort and must not hide the root cause.
#         pass


# def _normalize_path(
#     value: Path,
#     *,
#     field_name: str,
# ) -> Path:
#     try:
#         return Path(value).expanduser().resolve(strict=False)
#     except TypeError as exc:
#         raise TypeError(
#             f"{field_name} must be path-like"
#         ) from exc

"""Computation-only service for deterministic manifest-to-Lua generation.

Filesystem ownership belongs to ``RunArtifactStore``. This service reads an
already persisted manifest, invokes the external generator, performs Lua
preflight validation, and returns a candidate result. It never creates
folders or writes artifacts.
"""

from __future__ import annotations

from pathlib import Path

from cmo_lua_agent.contract import (
    ResolvedScenarioManifest,
    ScenarioContract,
)
from cmo_lua_agent.generation.lua_preflight_validator import (
    LuaPreflightValidator,
)
from cmo_lua_agent.generation.models import LuaGenerationResult
from cmo_lua_agent.integrations.cmolua.generator_adapter import (
    CmoLuaGeneratorAdapter,
)


class LuaGenerationService:
    """Generate and validate a Lua candidate without persisting artifacts."""

    def __init__(
        self,
        *,
        adapter: CmoLuaGeneratorAdapter,
        preflight_validator: LuaPreflightValidator,
        workspace_root: Path,
    ) -> None:
        self._adapter = adapter
        self._preflight_validator = preflight_validator
        self._workspace_root = _normalize_path(
            workspace_root,
            field_name="workspace_root",
        )

    def generate(
        self,
        *,
        manifest: ResolvedScenarioManifest,
        contract: ScenarioContract,
        manifest_path: Path,
        output_path: Path,
    ) -> LuaGenerationResult:
        """Generate Lua from an existing manifest and run preflight checks.

        ``output_path`` is the canonical destination the orchestration layer
        will use after a successful preflight. This method does not create or
        write that file.
        """

        if not isinstance(manifest, ResolvedScenarioManifest):
            raise TypeError(
                "manifest must be a ResolvedScenarioManifest"
            )
        if not isinstance(contract, ScenarioContract):
            raise TypeError(
                "contract must be a ScenarioContract"
            )

        resolved_manifest_path = _require_existing_file(
            manifest_path,
            field_name="manifest_path",
        )
        resolved_output_path = _normalize_path(
            output_path,
            field_name="output_path",
        )

        raw_result = self._adapter.generate(
            resolved_manifest_path
        )
        preflight = self._preflight_validator.validate(
            raw_result.lua_text,
            manifest=manifest,
            contract=contract,
            output_path=resolved_output_path,
            workspace_root=self._workspace_root,
            generator_warnings=raw_result.warnings,
        )

        return LuaGenerationResult(
            success=preflight.valid,
            lua_text=raw_result.lua_text,
            output_path=(
                resolved_output_path
                if preflight.valid
                else None
            ),
            generator_warnings=raw_result.warnings,
            preflight=preflight,
        )


def _require_existing_file(
    value: Path,
    *,
    field_name: str,
) -> Path:
    path = _normalize_path(value, field_name=field_name)
    if not path.is_file():
        raise FileNotFoundError(
            f"Manifest 文件不存在或不是普通文件：{path}"
        )
    return path


def _normalize_path(
    value: Path,
    *,
    field_name: str,
) -> Path:
    try:
        return Path(value).expanduser().resolve(strict=False)
    except TypeError as exc:
        raise TypeError(
            f"{field_name} must be path-like"
        ) from exc