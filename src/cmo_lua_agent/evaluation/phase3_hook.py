"""将 scored Lua 的 CMO 完成事件自动接入 Phase 3 最小评估。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cmo_lua_agent.contract.strategy_models import ScenarioDefinition
from cmo_lua_agent.execution.cmo_runner import CmoExecutionRecord
from cmo_lua_agent.evaluation.phase3_evaluation import (
    Phase3EvaluationResult,
    Phase3EvaluationService,
)
from cmo_lua_agent.generation.runtime_models import ExecutionPlan
from cmo_lua_agent.scoring.native_score_compiler import CmoNativeScoreCompilation


@dataclass(frozen=True, slots=True)
class Phase3EvaluationHook:
    """CmoRunner 完成后评估一个已评分、确定性生成的 Lua。"""

    scenario: ScenarioDefinition
    plan: ExecutionPlan
    score_compilation: CmoNativeScoreCompilation
    generation_manifest: dict[str, Any]
    service: Phase3EvaluationService

    def __call__(self, record: CmoExecutionRecord) -> Phase3EvaluationResult:
        output_dir = record.run_paths.run_dir / "phase3"
        try:
            return self.service.evaluate(
                run_result=record.result,
                run_id=record.run_paths.run_id,
                scenario=self.scenario,
                plan=self.plan,
                score_compilation=self.score_compilation,
                generation_manifest=self.generation_manifest,
                output_dir=output_dir,
            )
        except Exception as exc:
            return self.service.record_unscorable(
                run_result=record.result,
                output_dir=output_dir,
                reason=f"Phase 3 evaluation hook failed: {exc}",
            )
