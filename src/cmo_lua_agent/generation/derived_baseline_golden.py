"""Offline Golden assembly for the ScenarioIR-derived 6v4 baseline."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any

from cmo_lua_agent.contract.baseline_strategy_builder import BaselineStrategyBuilder
from cmo_lua_agent.contract.strategy_models import StrategySpec
from cmo_lua_agent.contract.strategy_validator import StrategyValidator
from cmo_lua_agent.generation.execution_plan_compiler import ExecutionPlanCompiler
from cmo_lua_agent.generation.runtime_models import ExecutionPlan, LuaRuntimeProfile, RenderedLua, canonical_sha256
from cmo_lua_agent.generation.scored_lua_assembly import (
    SCORED_RUNTIME_ID,
    SCORED_RUNTIME_VERSION,
    ScoredLuaAssemblyService,
)
from cmo_lua_agent.scoring.baseline import compile_score_baseline


@dataclass(frozen=True, slots=True)
class DerivedBaselineGolden:
    strategy: StrategySpec
    plan: ExecutionPlan
    rendered: RenderedLua
    derivation_manifest: dict[str, object]
    generation_manifest: dict[str, object]

    @property
    def strategy_checksum(self) -> str:
        return canonical_sha256(self.strategy.to_dict())


class DerivedBaselineGoldenService:
    """Build and explicitly write audited Golden artifacts; never load them as input."""

    def __init__(self, *, project_root: Path) -> None:
        self._root = Path(project_root).resolve()

    def build(self) -> DerivedBaselineGolden:
        scenario_ir = self._read_object(self._root / "json_data" / "6v4ScenarioIR.json")
        derived = BaselineStrategyBuilder().build(scenario_ir)
        validation = StrategyValidator().validate(derived.strategy, derived.scenario)
        if not validation.valid:
            raise ValueError("derived_baseline_strategy_invalid")
        runtime = LuaRuntimeProfile(SCORED_RUNTIME_ID, SCORED_RUNTIME_VERSION)
        compiled = ExecutionPlanCompiler().compile(
            scenario=derived.scenario,
            strategy=derived.strategy,
            runtime=runtime,
        )
        if compiled.plan is None or compiled.capability_gaps:
            raise ValueError("derived_baseline_plan_unavailable")
        score = compile_score_baseline(
            self._root / "baseline" / "6v4",
            scenario=derived.scenario,
        ).compilation
        assembled = ScoredLuaAssemblyService().render(
            scenario=derived.scenario,
            strategy=derived.strategy,
            plan=compiled.plan,
            runtime=runtime,
            native_score_compilation=score,
        )
        derivation_manifest = derived.manifest.to_dict()
        manifest = {
            **assembled.generation_manifest,
            "scenario_ir_checksum": derived.manifest.scenario_ir_checksum,
            "baseline_derivation_manifest_checksum": canonical_sha256(derivation_manifest),
            "baseline_golden_schema_version": "1.0",
        }
        return DerivedBaselineGolden(
            strategy=derived.strategy,
            plan=assembled.plan,
            rendered=assembled.rendered,
            derivation_manifest=derivation_manifest,
            generation_manifest=manifest,
        )

    def write(self, golden: DerivedBaselineGolden, *, output_dir: Path) -> None:
        directory = Path(output_dir).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        self._atomic_json(directory / "derived-baseline-strategy.json", golden.strategy.to_dict())
        self._atomic_json(directory / "baseline-derivation-manifest.json", golden.derivation_manifest)
        self._atomic_json(directory / "baseline-execution-plan.json", golden.plan.to_dict())
        self._atomic_text(directory / "baseline.lua", golden.rendered.content)
        self._atomic_json(directory / "baseline-golden-manifest.json", golden.generation_manifest)

    @staticmethod
    def _read_object(path: Path) -> dict[str, Any]:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("scenario_ir_invalid")
        return value

    @staticmethod
    def _atomic_text(path: Path, content: str) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(content.replace("\r\n", "\n"), encoding="utf-8", newline="\n")
        os.replace(temporary, path)

    @classmethod
    def _atomic_json(cls, path: Path, value: object) -> None:
        cls._atomic_text(
            path,
            json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        )
