from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from cmo_lua_agent.integrations.cmolua.config import (
    CmoLuaConfigurationError,
    CmoLuaIntegrationConfig,
)
from cmo_lua_agent.integrations.cmolua.generator_adapter import (
    CmoLuaGeneratorAdapter,
)


def _is_project_root(candidate: Path) -> bool:
    return (
        (candidate / "src" / "cmo_lua_agent").is_dir()
        and (candidate / "CMOLua-main" / "tools" / "json_to_lua.py").is_file()
    )


def _find_project_root(anchor: Path) -> Path:
    configured = os.environ.get("CMO_LUA_PROJECT_ROOT")
    if configured:
        configured_root = Path(configured).expanduser().resolve()
        if not _is_project_root(configured_root):
            raise RuntimeError(
                "CMO_LUA_PROJECT_ROOT is not a valid project root: "
                f"{configured_root}"
            )
        return configured_root

    resolved = anchor.resolve()
    for candidate in (resolved, *resolved.parents):
        if _is_project_root(candidate):
            return candidate

    raise RuntimeError(f"Unable to locate project root from {anchor}")


_PROJECT_ROOT = _find_project_root(Path(__file__).resolve().parent)
_GOLDEN_ROOT = (
    _PROJECT_ROOT
    / "src"
    / "cmo_lua_agent"
    / "tests"
    / "fixtures"
    / "cmolua"
    / "golden"
)
_SOURCE_PATH = _GOLDEN_ROOT / "source.json"
_ASSERTIONS_PATH = _GOLDEN_ROOT / "expected_assertions.json"


def _load_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise AssertionError(f"Golden 文件顶层必须是对象：{path}")
    return data


def _source_unit_names(source: Mapping[str, Any]) -> tuple[str, ...]:
    names: list[str] = []
    sides = source.get("sides")
    if not isinstance(sides, Mapping):
        return ()

    for side_key in ("red", "blue"):
        side = sides.get(side_key)
        if not isinstance(side, Mapping):
            continue
        units = side.get("units")
        if not isinstance(units, Sequence) or isinstance(units, (str, bytes)):
            continue
        for unit in units:
            if isinstance(unit, Mapping) and isinstance(unit.get("name"), str):
                names.append(unit["name"])

    return tuple(names)


def _assert_lua_matches_contract(
    lua_text: str,
    assertions: Mapping[str, Any],
) -> None:
    minimum_length = assertions.get("minimum_length")
    assert isinstance(minimum_length, int) and minimum_length > 0
    assert len(lua_text) >= minimum_length, (
        f"Lua 长度 {len(lua_text)} 小于 Golden 下限 {minimum_length}"
    )

    for fragment in assertions.get("required_fragments", []):
        assert fragment in lua_text, f"缺少必要 Lua 片段：{fragment}"

    for unit_name in assertions.get("required_unit_names", []):
        assert unit_name in lua_text, f"缺少单位名称：{unit_name}"

    for dbid in assertions.get("required_dbids", []):
        assert str(dbid) in lua_text, f"缺少 DBID/LoadoutID：{dbid}"

    any_groups = assertions.get("required_any_groups", {})
    assert isinstance(any_groups, Mapping)
    for label, alternatives in any_groups.items():
        assert isinstance(alternatives, Sequence)
        assert any(str(item) in lua_text for item in alternatives), (
            f"缺少 {label} 段，候选片段：{list(alternatives)}"
        )

    for fragment in assertions.get("forbidden_fragments", []):
        assert fragment not in lua_text, f"出现禁止 Lua 片段：{fragment}"


def _real_config_or_skip() -> CmoLuaIntegrationConfig:
    try:
        return CmoLuaIntegrationConfig.from_project_root(_PROJECT_ROOT)
    except CmoLuaConfigurationError as exc:
        pytest.skip(f"本机未配置完整 CMOLua-main，跳过真实 Golden 测试：{exc}")


def test_golden_fixture_describes_the_complete_source_scenario() -> None:
    source = _load_json_object(_SOURCE_PATH)
    assertions = _load_json_object(_ASSERTIONS_PATH)

    assert assertions["schema_version"] == 1
    assert assertions["scenario_id"] == source["scenario"]["id"]
    assert assertions["required_unit_names"] == list(_source_unit_names(source))
    assert assertions["required_dbids"] == [
        3883,
        4936,
        2007,
        2496,
        4299,
        2862,
        3551,
        2137,
        9682,
    ]


def test_find_project_root_from_nested_test_directory() -> None:
    assert _find_project_root(Path(__file__).resolve().parent) == _PROJECT_ROOT


def test_real_generator_matches_golden_semantic_contract() -> None:
    config = _real_config_or_skip()
    assertions = _load_json_object(_ASSERTIONS_PATH)

    result = CmoLuaGeneratorAdapter(config).generate(_SOURCE_PATH)

    _assert_lua_matches_contract(result.lua_text, assertions)
    assert isinstance(result.warnings, tuple)


def test_real_generator_is_deterministic_for_golden_source() -> None:
    config = _real_config_or_skip()
    adapter = CmoLuaGeneratorAdapter(config)

    first = adapter.generate(_SOURCE_PATH)
    second = adapter.generate(_SOURCE_PATH)

    assert first.lua_text == second.lua_text
    assert first.warnings == second.warnings
