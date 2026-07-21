"""Finite, deterministic preflight checks for generated CMO Lua.

This module is intentionally not a complete Lua parser. It validates the
generator output against a small set of stable CMO integration invariants:

* required scenario-construction calls exist;
* forbidden APIs are not invoked;
* manifest unit names, DBIDs, and loadouts are represented consistently;
* output paths remain inside the configured workspace and are not overwritten;
* generator warnings are promoted to errors when they describe unsafe input.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from cmo_lua_agent.contract import (
    ResolvedScenarioManifest,
    ScenarioContract,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)
from cmo_lua_agent.generation.models import LuaPreflightReport


_FORBIDDEN_APIS = (
    "DumpAmmo",
    "remove_weapon",
)

_LOADOUT_KEYS = (
    "loadoutid",
    "loadout_id",
    "loadoutdbid",
    "loadout_dbid",
)

_BLOCKING_WARNING_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        # References and identities.
        r"\b(?:unknown|missing|invalid|unresolved)\s+"
        r"(?:unit|shooter|target|reference)\b",
        r"\b(?:unit|shooter|target|reference)\b.*"
        r"\b(?:not\s+found|unknown|missing|invalid)\b",
        r"(?:单位|射手|目标|引用).*(?:不存在|未知|无效|缺失|错误)",
        r"(?:不存在|未知|无效|缺失|错误).*(?:单位|射手|目标|引用)",
        # Database identifiers and loadouts are never advisory here.
        r"\bdbid\b",
        r"\bloadout\b",
        r"(?:数据库\s*ID|挂载|挂载方案|装载方案)",
        # Ammunition consistency.
        r"\b(?:ammo|ammunition|loaded|fired)\b.*"
        r"\b(?:exceed|exceeds|exceeded|insufficient|invalid|"
        r"missing|not\s+enough|mismatch)\b",
        r"\b(?:exceed|exceeds|exceeded|insufficient|invalid|"
        r"missing|not\s+enough|mismatch)\b.*"
        r"\b(?:ammo|ammunition|loaded|fired)\b",
        r"(?:弹药|装载|发射).*(?:不足|超量|超出|超过|无效|错误|不一致)",
        r"(?:不足|超量|超出|超过|无效|错误|不一致).*(?:弹药|装载|发射)",
        # Coordinates and movement values.
        r"\b(?:coordinate|latitude|longitude|heading|speed)\b.*"
        r"\b(?:invalid|missing|illegal|non[- ]?numeric)\b",
        r"\b(?:invalid|missing|illegal|non[- ]?numeric)\b.*"
        r"\b(?:coordinate|latitude|longitude|heading|speed)\b",
        r"(?:坐标|经度|纬度|经纬度|航向|速度).*(?:非法|无效|错误|缺失)",
        r"(?:非法|无效|错误|缺失).*(?:坐标|经度|纬度|经纬度|航向|速度)",
    )
)


class LuaPreflightValidator:
    """Validate generated Lua before it is persisted or executed."""

    def validate(
        self,
        lua_text: str,
        *,
        manifest: ResolvedScenarioManifest,
        contract: ScenarioContract,
        output_path: Path,
        workspace_root: Path,
        generator_warnings: Iterable[str] = (),
    ) -> LuaPreflightReport:
        if not isinstance(lua_text, str):
            raise TypeError("lua_text must be a string")
        if not isinstance(manifest, ResolvedScenarioManifest):
            raise TypeError(
                "manifest must be a ResolvedScenarioManifest"
            )
        if not isinstance(contract, ScenarioContract):
            raise TypeError(
                "contract must be a ScenarioContract"
            )

        output = _normalize_path(
            output_path,
            field_name="output_path",
        )
        workspace = _normalize_path(
            workspace_root,
            field_name="workspace_root",
        )
        warnings = _normalize_warnings(generator_warnings)

        issues: list[ValidationIssue] = []

        self._validate_output_path(
            output=output,
            workspace=workspace,
            issues=issues,
        )

        if not lua_text.strip():
            issues.append(
                _error(
                    code="preflight.empty_lua",
                    message="生成器返回的 Lua 为空",
                    path="$.lua",
                )
            )
            self._append_generator_warnings(
                warnings,
                issues=issues,
            )
            return _report(issues)

        sanitized = _mask_lua_strings_and_comments(lua_text)

        self._validate_required_structure(
            lua_text=lua_text,
            sanitized=sanitized,
            manifest=manifest,
            issues=issues,
        )
        self._validate_forbidden_apis(
            sanitized=sanitized,
            issues=issues,
        )
        self._validate_manifest_alignment(
            lua_text=lua_text,
            sanitized=sanitized,
            manifest=manifest,
            contract=contract,
            issues=issues,
        )
        self._append_generator_warnings(
            warnings,
            issues=issues,
        )
        self._append_advisory_structure_warnings(
            sanitized=sanitized,
            issues=issues,
        )

        return _report(issues)

    @staticmethod
    def _validate_output_path(
        *,
        output: Path,
        workspace: Path,
        issues: list[ValidationIssue],
    ) -> None:
        if not output.is_relative_to(workspace):
            issues.append(
                _error(
                    code="preflight.output_outside_workspace",
                    message=(
                        "Lua 输出路径必须位于工作区内："
                        f"{output}"
                    ),
                    path="$.outputPath",
                )
            )

        if output.suffix.lower() != ".lua":
            issues.append(
                _error(
                    code="preflight.invalid_output_extension",
                    message="Lua 输出文件必须使用 .lua 扩展名",
                    path="$.outputPath",
                )
            )

        if output.exists():
            issues.append(
                _error(
                    code="preflight.output_exists",
                    message=(
                        "Lua 输出路径已存在，禁止覆盖："
                        f"{output}"
                    ),
                    path="$.outputPath",
                )
            )

    @staticmethod
    def _validate_required_structure(
        *,
        lua_text: str,
        sanitized: str,
        manifest: ResolvedScenarioManifest,
        issues: list[ValidationIssue],
    ) -> None:
        side_blocks = _extract_call_blocks(
            lua_text,
            sanitized=sanitized,
            function_name="ScenEdit_AddSide",
        )
        manifest_data = manifest.to_dict()
        sides = manifest_data.get("sides", {})

        if not isinstance(sides, Mapping):
            sides = {}

        side_names: list[tuple[str, str]] = []
        for side_key in ("red", "blue"):
            side = sides.get(side_key)
            if not isinstance(side, Mapping):
                continue
            side_name = side.get("name")
            if isinstance(side_name, str) and side_name.strip():
                side_names.append((side_key, side_name.strip()))

        if not side_blocks:
            issues.append(
                _error(
                    code="preflight.missing_add_side",
                    message="Lua 缺少 ScenEdit_AddSide 调用",
                    path="$.lua",
                )
            )
        else:
            for side_key, side_name in side_names:
                if not _has_side_creation(
                    lua_text=lua_text,
                    side_blocks=side_blocks,
                    side_name=side_name,
                ):
                    issues.append(
                        _error(
                            code="preflight.missing_add_side",
                            message=(
                                f"Lua 未创建 Manifest 阵营 "
                                f"{side_name!r}"
                            ),
                            path=f"$.manifest.sides.{side_key}.name",
                        )
                    )

        unit_blocks = _extract_call_blocks(
            lua_text,
            sanitized=sanitized,
            function_name="ScenEdit_AddUnit",
        )
        if not unit_blocks:
            issues.append(
                _error(
                    code="preflight.missing_add_unit",
                    message="Lua 缺少 ScenEdit_AddUnit 调用",
                    path="$.lua",
                )
            )

    @staticmethod
    def _validate_forbidden_apis(
        *,
        sanitized: str,
        issues: list[ValidationIssue],
    ) -> None:
        for api_name in _FORBIDDEN_APIS:
            pattern = re.compile(
                rf"\b{re.escape(api_name)}\s*\(",
                re.IGNORECASE,
            )
            if not pattern.search(sanitized):
                continue
            issues.append(
                _error(
                    code="preflight.forbidden_api",
                    message=f"Lua 调用了禁止 API：{api_name}",
                    path="$.lua",
                )
            )

    @staticmethod
    def _validate_manifest_alignment(
        *,
        lua_text: str,
        sanitized: str,
        manifest: ResolvedScenarioManifest,
        contract: ScenarioContract,
        issues: list[ValidationIssue],
    ) -> None:
        manifest_data = manifest.to_dict()
        units = _flatten_manifest_units(manifest_data)

        contract_names = set(contract.unit_names)
        unit_blocks = _extract_call_blocks(
            lua_text,
            sanitized=sanitized,
            function_name="ScenEdit_AddUnit",
        )
        manifest_driven = _uses_manifest_driven_units(
            sanitized=sanitized,
            unit_blocks=unit_blocks,
        )

        for unit_index, unit in enumerate(units):
            name = unit.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            name = name.strip()
            unit_path = f"$.manifest.units[{unit_index}]"

            if name not in contract_names:
                issues.append(
                    _error(
                        code="preflight.manifest_contract_mismatch",
                        message=(
                            f"Manifest 单位名称 {name!r} "
                            "不在 ScenarioContract 中"
                        ),
                        path=f"{unit_path}.name",
                    )
                )

            block = next(
                (
                    candidate
                    for candidate in unit_blocks
                    if _contains_lua_string(candidate, name)
                ),
                None,
            )
            if block is None and not manifest_driven:
                issues.append(
                    _error(
                        code="preflight.missing_add_unit",
                        message=(
                            f"Lua 没有为 Manifest 单位 "
                            f"{name!r} 创建 ScenEdit_AddUnit"
                        ),
                        path=f"{unit_path}.name",
                    )
                )
                issues.append(
                    _error(
                        code="preflight.unit_name_missing",
                        message=(
                            f"Lua 中缺少 Manifest 单位名称 "
                            f"{name!r}"
                        ),
                        path=f"{unit_path}.name",
                    )
                )
                continue

            if block is None:
                _validate_manifest_unit_literal(
                    lua_text=lua_text,
                    unit=unit,
                    unit_path=unit_path,
                    issues=issues,
                )
                continue

            expected_dbid = unit.get("dbid")
            if _is_positive_int(expected_dbid):
                actual_dbid = _extract_int_assignment(
                    block,
                    keys=("dbid",),
                )
                if actual_dbid is None:
                    issues.append(
                        _error(
                            code="preflight.unit_dbid_missing",
                            message=(
                                f"单位 {name!r} 的 AddUnit 调用 "
                                f"缺少 DBID {expected_dbid}"
                            ),
                            path=f"{unit_path}.dbid",
                        )
                    )
                elif actual_dbid != expected_dbid:
                    issues.append(
                        _error(
                            code="preflight.unit_dbid_mismatch",
                            message=(
                                f"单位 {name!r} 的 Manifest DBID "
                                f"为 {expected_dbid}，Lua 中为 "
                                f"{actual_dbid}"
                            ),
                            path=f"{unit_path}.dbid",
                        )
                    )

            expected_loadout = unit.get("loadoutId")
            if _is_positive_int(expected_loadout):
                actual_loadout = _extract_int_assignment(
                    block,
                    keys=_LOADOUT_KEYS,
                )
                if actual_loadout is None:
                    issues.append(
                        _error(
                            code="preflight.loadout_missing",
                            message=(
                                f"单位 {name!r} 的 Lua 创建调用 "
                                f"缺少 Loadout {expected_loadout}"
                            ),
                            path=f"{unit_path}.loadoutId",
                        )
                    )
                elif actual_loadout != expected_loadout:
                    issues.append(
                        _error(
                            code="preflight.loadout_mismatch",
                            message=(
                                f"单位 {name!r} 的 Manifest Loadout "
                                f"为 {expected_loadout}，Lua 中为 "
                                f"{actual_loadout}"
                            ),
                            path=f"{unit_path}.loadoutId",
                        )
                    )

        for contract_name in contract.unit_names:
            if manifest_driven and _contains_lua_string(
                lua_text,
                contract_name,
            ):
                continue
            if any(
                _contains_lua_string(block, contract_name)
                for block in unit_blocks
            ):
                continue
            # A matching manifest unit already produced a more precise issue.
            if any(
                unit.get("name") == contract_name
                for unit in units
            ):
                continue
            issues.append(
                _error(
                    code="preflight.unit_name_missing",
                    message=(
                        f"Lua 中缺少 Contract 单位名称 "
                        f"{contract_name!r}"
                    ),
                    path="$.contract.unit_names",
                )
            )

    @staticmethod
    def _append_generator_warnings(
        warnings: tuple[str, ...],
        *,
        issues: list[ValidationIssue],
    ) -> None:
        for index, warning in enumerate(warnings):
            blocking = any(
                pattern.search(warning)
                for pattern in _BLOCKING_WARNING_PATTERNS
            )
            if blocking:
                issues.append(
                    _error(
                        code="preflight.generator_warning_blocking",
                        message=(
                            "生成器报告了阻断性问题："
                            f"{warning}"
                        ),
                        path=f"$.generatorWarnings[{index}]",
                    )
                )
            else:
                issues.append(
                    _warning(
                        code="preflight.generator_warning",
                        message=f"生成器提示：{warning}",
                        path=f"$.generatorWarnings[{index}]",
                    )
                )

    @staticmethod
    def _append_advisory_structure_warnings(
        *,
        sanitized: str,
        issues: list[ValidationIssue],
    ) -> None:
        if not re.search(
            r"\bpcall\s*\(",
            sanitized,
            re.IGNORECASE,
        ):
            issues.append(
                _warning(
                    code="preflight.missing_pcall",
                    message=(
                        "Lua 未检测到 pcall；运行期错误可能直接中断脚本"
                    ),
                    path="$.lua",
                )
            )

        if not _contains_function(sanitized, "clear"):
            issues.append(
                _warning(
                    code="preflight.missing_clear",
                    message="Lua 未检测到 clear 函数",
                    path="$.lua",
                )
            )

        if not _contains_function(sanitized, "reload"):
            issues.append(
                _warning(
                    code="preflight.missing_reload",
                    message="Lua 未检测到 reload 函数",
                    path="$.lua",
                )
            )


def _flatten_manifest_units(
    manifest: Mapping[str, Any],
) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    sides = manifest.get("sides")
    if not isinstance(sides, Mapping):
        return units

    for side_key in ("red", "blue"):
        side = sides.get(side_key)
        if not isinstance(side, Mapping):
            continue
        side_units = side.get("units")
        if not isinstance(side_units, list):
            continue
        for unit in side_units:
            if isinstance(unit, Mapping):
                units.append(dict(unit))
    return units


def _contains_function(sanitized: str, name: str) -> bool:
    escaped = re.escape(name)
    return bool(
        re.search(
            rf"(?:\blocal\s+)?\bfunction\s+{escaped}\s*\("
            rf"|\b{escaped}\s*=\s*function\s*\(",
            sanitized,
            re.IGNORECASE,
        )
    )


def _extract_call_blocks(
    lua_text: str,
    *,
    sanitized: str,
    function_name: str,
) -> tuple[str, ...]:
    direct_pattern = re.compile(
        rf"\b{re.escape(function_name)}\s*\(", re.IGNORECASE
    )
    pcall_pattern = re.compile(
        rf"\bpcall\s*\(\s*{re.escape(function_name)}\s*,",
        re.IGNORECASE,
    )
    blocks: list[str] = []

    matches = [
        (match.start(), sanitized.find("(", match.start()))
        for match in direct_pattern.finditer(sanitized)
    ]
    matches.extend(
        (match.start(), sanitized.find("(", match.start()))
        for match in pcall_pattern.finditer(sanitized)
    )
    for start, opening in sorted(set(matches)):
        if opening < 0:
            continue
        closing = _find_matching_parenthesis(
            sanitized,
            opening,
        )
        if closing is None:
            blocks.append(lua_text[start:])
        else:
            blocks.append(
                lua_text[start : closing + 1]
            )

    return tuple(blocks)


def _has_side_creation(
    *,
    lua_text: str,
    side_blocks: tuple[str, ...],
    side_name: str,
) -> bool:
    if any(_contains_lua_string(block, side_name) for block in side_blocks):
        return True
    return _contains_lua_string(lua_text, side_name) and len(side_blocks) >= 2


def _uses_manifest_driven_units(
    *,
    sanitized: str,
    unit_blocks: tuple[str, ...],
) -> bool:
    return bool(
        unit_blocks
        and re.search(r"\bMANIFEST_[A-Z0-9_]+\b", sanitized)
    )


def _validate_manifest_unit_literal(
    *,
    lua_text: str,
    unit: Mapping[str, Any],
    unit_path: str,
    issues: list[ValidationIssue],
) -> None:
    name = unit.get("name")
    if isinstance(name, str) and name.strip() and not _contains_lua_string(lua_text, name.strip()):
        issues.append(
            _error(
                code="preflight.unit_name_missing",
                message=f"Lua 中缺少 Manifest 单位名称 {name!r}",
                path=f"{unit_path}.name",
            )
        )

    for key, label in (("dbid", "DBID"), ("loadoutId", "Loadout")):
        expected = unit.get(key)
        if not _is_positive_int(expected):
            continue
        pattern = re.compile(
            rf"\b{re.escape(key.lower())}\s*=\s*{expected}\b",
            re.IGNORECASE,
        )
        if not pattern.search(lua_text):
            issues.append(
                _error(
                    code=("preflight.unit_dbid_missing" if key == "dbid" else "preflight.loadout_missing"),
                    message=f"单位 {name!r} 的 Manifest 数据缺少 {label} {expected}",
                    path=f"{unit_path}.{key}",
                )
            )


def _find_matching_parenthesis(
    sanitized: str,
    opening: int,
) -> int | None:
    depth = 0
    for index in range(opening, len(sanitized)):
        char = sanitized[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def _contains_lua_string(block: str, value: str) -> bool:
    double_quoted = (
        '"'
        + value.replace("\\", "\\\\").replace('"', '\\"')
        + '"'
    )
    single_quoted = (
        "'"
        + value.replace("\\", "\\\\").replace("'", "\\'")
        + "'"
    )
    return (
        double_quoted in block
        or single_quoted in block
    )


def _extract_int_assignment(
    block: str,
    *,
    keys: tuple[str, ...],
) -> int | None:
    alternatives = "|".join(
        re.escape(key)
        for key in keys
    )
    match = re.search(
        rf"\b(?:{alternatives})\b\s*=\s*(\d+)",
        block,
        re.IGNORECASE,
    )
    if match is None:
        return None
    return int(match.group(1))


def _mask_lua_strings_and_comments(lua_text: str) -> str:
    """Replace comments and string contents with spaces, preserving offsets."""

    chars = list(lua_text)
    result = list(lua_text)
    index = 0
    length = len(chars)

    while index < length:
        char = chars[index]

        if (
            char == "-"
            and index + 1 < length
            and chars[index + 1] == "-"
        ):
            if (
                index + 3 < length
                and chars[index + 2] == "["
                and chars[index + 3] == "["
            ):
                end = lua_text.find("]]", index + 4)
                if end < 0:
                    end = length - 2
                _blank_range(
                    result,
                    index,
                    min(end + 2, length),
                )
                index = min(end + 2, length)
                continue

            end = lua_text.find("\n", index + 2)
            if end < 0:
                end = length
            _blank_range(result, index, end)
            index = end
            continue

        if char in {'"', "'"}:
            quote = char
            start = index
            index += 1
            while index < length:
                if chars[index] == "\\":
                    index += 2
                    continue
                if chars[index] == quote:
                    index += 1
                    break
                index += 1
            _blank_range(result, start, min(index, length))
            continue

        if (
            char == "["
            and index + 1 < length
            and chars[index + 1] == "["
        ):
            end = lua_text.find("]]", index + 2)
            if end < 0:
                end = length - 2
            _blank_range(
                result,
                index,
                min(end + 2, length),
            )
            index = min(end + 2, length)
            continue

        index += 1

    return "".join(result)


def _blank_range(
    values: list[str],
    start: int,
    end: int,
) -> None:
    for index in range(start, end):
        if values[index] != "\n":
            values[index] = " "


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


def _normalize_warnings(
    values: Iterable[str],
) -> tuple[str, ...]:
    try:
        candidates = tuple(values)
    except TypeError as exc:
        raise TypeError(
            "generator_warnings must be an iterable of strings"
        ) from exc

    normalized: list[str] = []
    for value in candidates:
        if not isinstance(value, str):
            raise TypeError(
                "generator_warnings must contain only strings"
            )
        warning = value.strip()
        if not warning:
            raise ValueError(
                "generator_warnings must not contain blank strings"
            )
        normalized.append(warning)
    return tuple(normalized)


def _is_positive_int(value: Any) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value > 0
    )


def _report(
    issues: list[ValidationIssue],
) -> LuaPreflightReport:
    return LuaPreflightReport(
        validation=ValidationResult(
            issues=tuple(issues)
        )
    )


def _error(
    *,
    code: str,
    message: str,
    path: str,
) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        message=message,
        path=path,
        severity=ValidationSeverity.ERROR,
    )


def _warning(
    *,
    code: str,
    message: str,
    path: str,
) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        message=message,
        path=path,
        severity=ValidationSeverity.WARNING,
    )
