"""一键加载所有计分配置、编译CMO计分Lua片段"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cmo_lua_agent.contract import load_scenario_definition
from cmo_lua_agent.contract.strategy_models import ScenarioDefinition
from cmo_lua_agent.scoring.models import (
    ScenarioObjective,
    ScenarioObjectives,
    ScoreProfile,
    ScoreRole,
    UnitRoleAssignment,
    UnitRoleCatalog,
)
from cmo_lua_agent.scoring.native_score_compiler import (
    CmoNativeScoreCompilation,
    CmoNativeScoreCompiler,
)


@dataclass(frozen=True, slots=True)
class ScoreBaselineResult:
    compilation: CmoNativeScoreCompilation
    manifest: dict[str, str]

    @property
    def score_spec(self):
        return self.compilation.score_spec

    @property
    def fragment(self):
        return self.compilation.fragment


def compile_score_baseline(
    baseline_root: Path,
    *,
    scenario: ScenarioDefinition | None = None,
) -> ScoreBaselineResult:
    root = Path(baseline_root)
    scenario = scenario or load_scenario_definition(root / "scenario_definition.json")
    role_catalog = _load_role_catalog(root / "unit_role_catalog.json")
    score_profile = _load_score_profile(root / "score_profile.json")
    objectives = _load_objectives(root / "scenario_objectives.json")
    compilation = CmoNativeScoreCompiler().compile(
        scenario=scenario,
        role_catalog=role_catalog,
        score_profile=score_profile,
        objectives=objectives,
    )
    return ScoreBaselineResult(
        compilation=compilation,
        manifest={
            "compiler_version": compilation.compiler_version,
            "scenario_checksum": compilation.scenario_checksum,
            "role_catalog_checksum": compilation.role_catalog_checksum,
            "score_profile_checksum": compilation.score_profile_checksum,
            "objectives_checksum": compilation.objectives_checksum,
            "score_spec_checksum": compilation.score_spec_checksum,
            "fragment_checksum": compilation.fragment_checksum,
        },
    )


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _load_role_catalog(path: Path) -> UnitRoleCatalog:
    data = _read_json(path)
    return UnitRoleCatalog(
        catalog_id=data["catalog_id"],
        catalog_version=data["catalog_version"],
        scenario_id=data["scenario_id"],
        assignments=tuple(UnitRoleAssignment(**item) for item in data["assignments"]),
    )


def _load_score_profile(path: Path) -> ScoreProfile:
    data = _read_json(path)
    return ScoreProfile(
        profile_id=data["profile_id"],
        profile_version=data["profile_version"],
        score_side_id=data["score_side_id"],
        roles=tuple(ScoreRole(**item) for item in data["roles"]),
    )


def _load_objectives(path: Path) -> ScenarioObjectives:
    data = _read_json(path)
    return ScenarioObjectives(
        scenario_id=data["scenario_id"],
        objectives_version=data["objectives_version"],
        objectives=tuple(ScenarioObjective(**item) for item in data["objectives"]),
    )
