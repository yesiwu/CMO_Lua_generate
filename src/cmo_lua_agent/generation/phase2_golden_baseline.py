"""Parallel Golden entry point for Phase 2 deterministic Lua rendering.完整跑完 Phase2 全链路，产出标准化可执行 Lua、执行计划、校验报告、生成溯源清单，用于回归测试、基线比对、复现验证。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cmo_lua_agent.contract import (
    StrategyValidator,
    load_baseline_strategy,
    load_scenario_definition,
)
from cmo_lua_agent.generation.capability_validator import (
    CapabilityValidationResult,
    CapabilityValidator,
)
from cmo_lua_agent.generation.execution_plan_compiler import ExecutionPlanCompiler
from cmo_lua_agent.generation.lua_renderer import LuaRenderer
from cmo_lua_agent.generation.runtime_models import (
    ExecutionPlan,
    LuaRuntimeProfile,
    RenderedLua,
    canonical_sha256,
)
from cmo_lua_agent.generation.runtime_primitives import (
    RUNTIME_ID,
    RUNTIME_VERSION,
    default_runtime_primitive_registry,
)


@dataclass(frozen=True, slots=True)
class Phase2GoldenBaselineResult:
    plan: ExecutionPlan
    validation: CapabilityValidationResult
    rendered: RenderedLua
    generation_manifest: dict[str, Any]


class Phase2GoldenBaselineService:
    def __init__(
        self,
        *,
        compiler: ExecutionPlanCompiler | None = None,
        renderer: LuaRenderer | None = None,
        runtime: LuaRuntimeProfile | None = None,
    ) -> None:
        self._compiler = compiler or ExecutionPlanCompiler()
        self._renderer = renderer or LuaRenderer()
        self._runtime = runtime or LuaRuntimeProfile(RUNTIME_ID, RUNTIME_VERSION)

    def render(
        self,
        *,
        scenario_definition_path: Path,
        baseline_strategy_path: Path,
    ) -> Phase2GoldenBaselineResult:
        scenario = load_scenario_definition(scenario_definition_path)
        baseline = load_baseline_strategy(baseline_strategy_path)

        strategy_validation = StrategyValidator().validate(
            strategy=baseline.strategy,
            scenario_definition=scenario,
        )
        if not strategy_validation.valid:
            messages = "; ".join(issue.message for issue in strategy_validation.issues)
            raise ValueError(f"baseline strategy is invalid: {messages}")

        compile_result = self._compiler.compile(
            scenario=scenario,
            strategy=baseline.strategy,
            runtime=self._runtime,
        )
        if compile_result.plan is None:
            gap = compile_result.capability_gaps[0]
            raise ValueError(f"capability gap: {gap.capability}: {gap.reason}")

        registry = default_runtime_primitive_registry()
        validation = CapabilityValidator(registry).validate(
            plan=compile_result.plan,
            runtime=self._runtime,
        )
        rendered = self._renderer.render(
            plan=compile_result.plan,
            runtime=self._runtime,
        )

        generation_manifest = {
            **rendered.to_manifest_dict(),
            "scenario_id": scenario.scenario_id,
            "scenario_source": _relative_source(scenario_definition_path),
            "baseline_strategy_source": _relative_source(baseline_strategy_path),
            "source_lua": baseline.source_lua,
            "scenario_checksum": canonical_sha256(scenario.to_dict()),
            "strategy_checksum": canonical_sha256(baseline.strategy.to_dict()),
            "plan_checksum": compile_result.plan.checksum,
            "lua_checksum": rendered.lua_checksum,
        }
        return Phase2GoldenBaselineResult(
            plan=compile_result.plan,
            validation=validation,
            rendered=rendered,
            generation_manifest=generation_manifest,
        )


def _relative_source(path: Path) -> str:
    resolved = Path(path).resolve()
    for parent in resolved.parents:
        if (parent / "src" / "cmo_lua_agent").is_dir():
            return resolved.relative_to(parent).as_posix()
    return resolved.as_posix()
