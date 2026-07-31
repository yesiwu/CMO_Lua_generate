"""System-owned instrumentation bundles for deterministic Lua assembly."""

from __future__ import annotations

from dataclasses import dataclass

from cmo_lua_agent.contract.strategy_models import ScenarioDefinition
from cmo_lua_agent.generation.runtime_models import ExecutionPlan, LuaRuntimeProfile, canonical_sha256
from cmo_lua_agent.scoring.native_score_compiler import CmoNativeScoreCompilation


class SystemInstrumentationError(ValueError):
    """Structured rejection for an untrusted or incompatible system bundle."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class SystemInstrumentationBundle:
    """Typed, system-generated CMO native scoring instrumentation only."""

    native_score_compilation: CmoNativeScoreCompilation
    scenario_checksum: str
    runtime_id: str
    runtime_version: str
    renderer_version: str

    @classmethod
    def from_native_score_compilation(
        cls,
        *,
        scenario: ScenarioDefinition,
        runtime: LuaRuntimeProfile,
        renderer_version: str,
        native_score_compilation: CmoNativeScoreCompilation,
    ) -> "SystemInstrumentationBundle":
        return cls(
            native_score_compilation=native_score_compilation,
            scenario_checksum=canonical_sha256(scenario.to_dict()),
            runtime_id=runtime.runtime_id,
            runtime_version=runtime.runtime_version,
            renderer_version=renderer_version,
        )

    @property
    def content(self) -> str:
        return self.native_score_compilation.fragment.content

    def validate(
        self,
        *,
        scenario: ScenarioDefinition,
        plan: ExecutionPlan,
        runtime: LuaRuntimeProfile,
        renderer_version: str,
    ) -> None:
        compilation = self.native_score_compilation
        if plan.scenario_id != scenario.scenario_id or compilation.score_spec.scenario_id != scenario.scenario_id:
            raise SystemInstrumentationError("scenario_id_mismatch", "scenario, plan, and score specification must share scenario_id")
        # Checksums and version values are retained in manifests for audit only.
        # The execution gate is limited to the semantic scenario identifier.
