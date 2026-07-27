"""将 scored Lua 的 CMO 完成事件自动接入 Phase 3 最小评估。
钩子类：CMO仿真执行完毕后自动触发Phase3评估流程，捕获异常并输出不可评分结果
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

# 场景事实契约
from cmo_lua_agent.contract.strategy_models import ScenarioDefinition
# CMO仿真执行记录模型（runner跑完产出）
from cmo_lua_agent.execution.cmo_runner import CmoExecutionRecord
# Phase3评估核心服务与结果模型
from cmo_lua_agent.evaluation.phase3_evaluation import (
    Phase3EvaluationResult,
    Phase3EvaluationService,
)
# 执行计划（Phase2输出）
from cmo_lua_agent.generation.runtime_models import ExecutionPlan
# Phase3计分编译产物（带计分Lua片段）
from cmo_lua_agent.scoring.native_score_compiler import CmoNativeScoreCompilation


@dataclass(frozen=True, slots=True)
class Phase3EvaluationHook:
    """CmoRunner 完成后评估一个已评分、确定性生成 Lua 的钩子。
    存储评估所需全部静态上下文，实现可调用接口，挂载到CMO执行器回调
    """
    # 全局场景事实（不变）
    scenario: ScenarioDefinition
    # 当前作战执行计划
    plan: ExecutionPlan
    # 计分规则+计分Lua编译结果
    score_compilation: CmoNativeScoreCompilation
    # Lua生成全链路哈希清单（校验版本一致性）
    generation_manifest: dict[str, Any]
    # Phase3评估核心服务实例
    service: Phase3EvaluationService

    def __call__(self, record: CmoExecutionRecord) -> Phase3EvaluationResult:
        """钩子入口：CMO执行完成传入执行记录，自动执行评估"""
        # 评估产物输出目录：run目录下/phase3文件夹
        output_dir = record.run_paths.run_dir / "phase3"
        try:
            # 正常执行Phase3完整评估流程，生成全套证据/指标/得分JSON
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
            # 评估过程任意异常，捕获并生成【不可评分】标准产物
            return self.service.record_unscorable(
                run_result=record.result,
                output_dir=output_dir,
                reason=f"Phase 3 evaluation hook failed: {exc}",
            )