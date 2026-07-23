"""Phase 3.2 assembly service that reuses the sole deterministic Lua renderer.
带计分功能的 Lua 总组装服务， 把【作战执行计划】+【自动计分 Lua 片段】拼接成一份完整可运行 CMO 脚本
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cmo_lua_agent.contract.strategy_models import ScenarioDefinition, StrategySpec
from cmo_lua_agent.generation.lua_renderer import LuaRenderer
from cmo_lua_agent.generation.runtime_models import ExecutionPlan, LuaRuntimeProfile, RenderedLua, canonical_sha256
from cmo_lua_agent.generation.system_instrumentation import SystemInstrumentationBundle, SystemInstrumentationError
from cmo_lua_agent.scoring.native_score_compiler import CmoNativeScoreCompilation


SCORED_RUNTIME_ID = "cmo_naval_air_anti_surface_scored"
SCORED_RUNTIME_VERSION = "2.0.0"
SCORED_RENDERER_VERSION = "2.0.0"
SCORED_ASSEMBLY_VERSION = "1.0.0"


class ScoredLuaAssemblyError(SystemInstrumentationError):
    pass


@dataclass(frozen=True, slots=True)
class ScoredLuaAssemblyResult:
    plan: ExecutionPlan
    rendered: RenderedLua
    generation_manifest: dict[str, Any]


class ScoredLuaAssemblyService:
    """Compose system scoring with the existing renderer; never render primitives itself."""

    def __init__(self, *, renderer: LuaRenderer | None = None) -> None:
        self._renderer = renderer or LuaRenderer(renderer_version=SCORED_RENDERER_VERSION)

    def render(
        self,
        *,
        scenario: ScenarioDefinition,
        strategy: StrategySpec,
        plan: ExecutionPlan,
        runtime: LuaRuntimeProfile,
        native_score_compilation: CmoNativeScoreCompilation,
    ) -> ScoredLuaAssemblyResult:
        if not isinstance(native_score_compilation, CmoNativeScoreCompilation):
            raise ScoredLuaAssemblyError(
                "native_score_compilation_type",
                "system instrumentation requires CmoNativeScoreCompilation, not custom Lua text",
            )
        normalized_plan = normalize_scored_execution_plan(plan)
        if strategy.scenario_id != scenario.scenario_id:
            raise ScoredLuaAssemblyError("strategy_scenario_id_mismatch", "strategy and scenario must share scenario_id")
        bundle = SystemInstrumentationBundle.from_native_score_compilation(
            scenario=scenario,
            runtime=runtime,
            renderer_version=SCORED_RENDERER_VERSION,
            native_score_compilation=native_score_compilation,
        )
        try:
            bundle.validate(scenario=scenario, plan=normalized_plan, runtime=runtime, renderer_version=SCORED_RENDERER_VERSION)
        except SystemInstrumentationError as exc:
            raise ScoredLuaAssemblyError(exc.code, exc.message) from exc
        rendered = self._renderer.render(plan=normalized_plan, runtime=runtime, instrumentation=bundle)
        compilation = native_score_compilation
        return ScoredLuaAssemblyResult(
            plan=normalized_plan,
            rendered=rendered,
            generation_manifest={
                **rendered.to_manifest_dict(),
                "scenario_id": scenario.scenario_id,
                "scenario_checksum": compilation.scenario_checksum,
                "strategy_checksum": canonical_sha256(strategy.to_dict()),
                "execution_plan_checksum": normalized_plan.checksum,
                "runtime_id": runtime.runtime_id,
                "runtime_version": runtime.runtime_version,
                "compiler_version": plan.compiler_version,
                "renderer_version": SCORED_RENDERER_VERSION,
                "assembly_version": SCORED_ASSEMBLY_VERSION,
                "role_catalog_checksum": compilation.role_catalog_checksum,
                "score_profile_checksum": compilation.score_profile_checksum,
                "objectives_checksum": compilation.objectives_checksum,
                "score_spec_checksum": compilation.score_spec_checksum,
                "native_score_fragment_checksum": compilation.fragment_checksum,
                "lua_checksum": rendered.lua_checksum,
                "instrumentation_enabled": True,
            },
        )


_INITIALIZATION_PRIMITIVES = frozenset(
    {
        "ensure_sides", "configure_side_state", "ensure_ship", "ensure_aircraft",
        "prepare_target_contact", "configure_ship_inventory", "configure_aircraft",
    }
)


def normalize_scored_execution_plan(plan: ExecutionPlan) -> ExecutionPlan:
    """Topologically order the scored runtime plan without altering its operations.

    The legacy Phase 2 renderer preserves compiler insertion order for its Golden
    compatibility.  The scored runtime has a stricter invariant: all unit and
    aircraft setup must finish before native UnitDestroyed rules are registered.
    """
    pending = {operation.operation_id: operation for operation in plan.operations}
    ordered = []
    satisfied: set[str] = set()
    while pending:
        ready = [
            operation for operation in pending.values()
            if all(dependency in satisfied for dependency in operation.depends_on)
        ]
        if not ready:
            raise ScoredLuaAssemblyError("plan_dependency_cycle", "scored execution plan has unsatisfied dependencies")
        ready.sort(key=lambda operation: (_operation_phase(operation.primitive_type), operation.operation_id))
        operation = ready[0]
        ordered.append(operation)
        satisfied.add(operation.operation_id)
        del pending[operation.operation_id]
    return ExecutionPlan(
        plan_schema_version=plan.plan_schema_version,
        compiler_version=plan.compiler_version,
        scenario_id=plan.scenario_id,
        runtime_id=plan.runtime_id,
        runtime_version=plan.runtime_version,
        operations=tuple(ordered),
    )


def _operation_phase(primitive_type: str) -> int:
    return 0 if primitive_type in _INITIALIZATION_PRIMITIVES else 1
