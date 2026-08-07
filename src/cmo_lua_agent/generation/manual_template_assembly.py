"""Assembly adapter for an operator-authored active-strike Lua template.

The template owns the CMO state machine and its proven native CMO scoring
rules. This adapter projects approved StrategySpec leaf changes into declared
slots without replacing that score block.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cmo_lua_agent.contract.strategy_models import ScenarioDefinition, StrategySpec
from cmo_lua_agent.generation.manual_lua_template import ManualLuaTemplatePackage
from cmo_lua_agent.generation.runtime_models import ExecutionPlan, LuaRuntimeProfile, LuaSourceSpan, RenderedLua, canonical_sha256
from cmo_lua_agent.generation.scored_lua_assembly import ScoredLuaAssemblyResult
from cmo_lua_agent.optimization.candidate_set_validator import strategy_leaf_diff
from cmo_lua_agent.scoring.native_score_compiler import CmoNativeScoreCompilation


class ManualTemplateAssemblyError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ManualTemplateAssemblyService:
    """Render the active-strike baseline without changing its fixed Lua logic."""

    template_root: Any
    baseline_strategy: StrategySpec
    _template: ManualLuaTemplatePackage = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_template", ManualLuaTemplatePackage.load(self.template_root))

    def render(
        self,
        *,
        scenario: ScenarioDefinition,
        strategy: StrategySpec,
        plan: ExecutionPlan,
        runtime: LuaRuntimeProfile,
        native_score_compilation: CmoNativeScoreCompilation,
        candidate_id: str | None = None,
    ) -> ScoredLuaAssemblyResult:
        if strategy.scenario_id != scenario.scenario_id:
            raise ManualTemplateAssemblyError("strategy_scenario_id_mismatch")
        if plan.scenario_id != scenario.scenario_id:
            raise ManualTemplateAssemblyError("plan_scenario_id_mismatch")
        score_sides = {rule.score_side_id for rule in native_score_compilation.score_spec.rules}
        if score_sides != {"red"}:
            raise ManualTemplateAssemblyError("manual_template_scoring_side_invalid")

        candidate_name = candidate_id or "baseline"
        if strategy == self.baseline_strategy:
            template_strategy = self._template.baseline_strategy().with_parameters(
                candidate_id=candidate_name,
                updates={},
            )
            changed_paths: tuple[str, ...] = ()
        else:
            # First collect all scalar diffs while preserving the StrategySpec
            # structural guard.  The template mapping then rejects any path it
            # does not explicitly own, instead of turning it into a generic
            # formal patch-whitelist error.
            allowed_paths = ("/attacks", "/sorties")
            changed_paths = strategy_leaf_diff(
                self.baseline_strategy,
                strategy,
                allowed_paths,
            )
            try:
                template_strategy = self._template.strategy_overlay(
                    candidate_id=candidate_name,
                    baseline_strategy=self.baseline_strategy.to_dict(),
                    candidate_strategy=strategy.to_dict(),
                    changed_paths=changed_paths,
                )
            except ValueError as exc:
                raise ManualTemplateAssemblyError(str(exc)) from exc

        rendered_template = self._template.render(template_strategy)
        # The operator template remains the only source of tactical behavior
        # and native CMO Points scoring. The experimental Lua damage poller is
        # intentionally not installed: Batch CMO does not expose reliable
        # per-unit damage through that wrapper, while UnitDestroyed + Points is
        # a verified scoring path.
        rendered_content = rendered_template.content
        line_count = max(1, rendered_content.count("\n") + 1)
        rendered = RenderedLua(
            content=rendered_content,
            metadata={
                "artifact_provenance": "manual_template",
                "template_id": self._template.template_id,
                "template_fixed_logic_checksum": rendered_template.fixed_logic_checksum,
                "template_changed_slots": list(rendered_template.changed_slots),
                "native_score_fragment_checksum": native_score_compilation.fragment_checksum,
                "score_spec_version": "destroyed_unit_native_points",
            },
            source_map={
                operation.operation_id: LuaSourceSpan(1, line_count)
                for operation in plan.operations
            },
        )
        manifest = {
            **rendered.to_manifest_dict(),
            "scenario_id": scenario.scenario_id,
            "strategy_checksum": canonical_sha256(strategy.to_dict()),
            "execution_plan_checksum": plan.checksum,
            "runtime_id": runtime.runtime_id,
            "runtime_version": runtime.runtime_version,
            "compiler_version": plan.compiler_version,
            "renderer_version": "manual_template_v1",
            "assembly_version": "manual_template_v1",
            "score_spec_checksum": native_score_compilation.score_spec_checksum,
            "native_score_fragment_checksum": native_score_compilation.fragment_checksum,
            "changed_paths": list(changed_paths),
            "artifact_provenance": "manual_template",
        }
        return ScoredLuaAssemblyResult(plan=plan, rendered=rendered, generation_manifest=manifest)
