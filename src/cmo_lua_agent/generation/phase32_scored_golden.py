"""Parallel Phase 3.2 Golden entry point for scored deterministic Lua."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cmo_lua_agent.contract import StrategyValidator, load_baseline_strategy, load_scenario_definition
from cmo_lua_agent.generation.capability_validator import CapabilityValidator
from cmo_lua_agent.generation.execution_plan_compiler import ExecutionPlanCompiler
from cmo_lua_agent.generation.runtime_models import ExecutionPlan, LuaRuntimeProfile, RenderedLua
from cmo_lua_agent.generation.runtime_primitives import runtime_primitive_registry_for
from cmo_lua_agent.generation.scored_lua_assembly import (
    SCORED_RUNTIME_ID, SCORED_RUNTIME_VERSION, ScoredLuaAssemblyService,
)
from cmo_lua_agent.scoring.baseline import compile_score_baseline


@dataclass(frozen=True, slots=True)
class Phase32ScoredGoldenResult:
    plan: ExecutionPlan
    rendered: RenderedLua
    generation_manifest: dict[str, Any]


class Phase32ScoredGoldenService:
    def __init__(self) -> None:
        self._runtime = LuaRuntimeProfile(SCORED_RUNTIME_ID, SCORED_RUNTIME_VERSION)

    def render(self, *, baseline_root: Path) -> Phase32ScoredGoldenResult:
        root = Path(baseline_root)
        scenario = load_scenario_definition(root / "scenario_definition.json")
        baseline = load_baseline_strategy(root / "baseline_strategy.json")
        validation = StrategyValidator().validate(strategy=baseline.strategy, scenario_definition=scenario)
        if not validation.valid:
            raise ValueError("baseline strategy is invalid")
        compiled = ExecutionPlanCompiler().compile(scenario=scenario, strategy=baseline.strategy, runtime=self._runtime)
        if compiled.plan is None:
            raise ValueError(f"capability gap: {compiled.capability_gaps[0].capability}")
        plan_validation = CapabilityValidator(
            runtime_primitive_registry_for(self._runtime.runtime_id, self._runtime.runtime_version)
        ).validate(plan=compiled.plan, runtime=self._runtime)
        if not plan_validation.is_valid:
            raise ValueError(f"invalid scored execution plan: {plan_validation.issues}")
        score_compilation = compile_score_baseline(root).compilation
        assembled = ScoredLuaAssemblyService().render(
            scenario=scenario,
            strategy=baseline.strategy,
            plan=compiled.plan,
            runtime=self._runtime,
            native_score_compilation=score_compilation,
        )
        return Phase32ScoredGoldenResult(
            plan=assembled.plan,
            rendered=assembled.rendered,
            generation_manifest=assembled.generation_manifest,
        )
