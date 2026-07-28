"""
轻量化生产适配层；所有脚本渲染、CMO仿真、策略学习、优胜筛选逻辑仍归属Phase6–8模块。
本适配器仅做封装调用、结果标准化转换，不承载核心推演业务。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from cmo_lua_agent.evolution.models import CandidateScore, Phase6GenerationArtifact


@dataclass
class FormalPhase6Adapter:
    """
    Phase6工作流标准适配器
    一次性调用已有的优化迭代工作流 OptimizationGenerationWorkflow，
    读取持久化输出文件，并把结果统一映射为上层Phase9可识别的标准化结果载体。
    """
    workflow: object                          # Phase6原生迭代工作流实例
    request_factory: Callable[..., object]    # 请求构造工厂函数，生成传入Phase6的请求对象

    def run(self, *, generation_index: int, rolling_baseline_id: str, **kwargs: object) -> Phase6GenerationArtifact:
        """
        执行一轮完整的Phase6策略种群推演评估
        :param generation_index: 当前世代编号
        :param rolling_baseline_id: 当前滚动基线策略ID
        :param kwargs: 透传给请求工厂的扩展参数
        :return: Phase9标准化世代产物对象
        """
        # 构造发给Phase6工作流的请求
        request = self.request_factory(generation_index=generation_index, rolling_baseline_id=rolling_baseline_id, **kwargs)
        # 调用底层Phase6核心推演工作流
        result = self.workflow.run(request)

        # 工作流未正常完成，抛出异常中断世代
        if not result.workflow_completed:
            raise RuntimeError(f"phase6_failed:{result.failure_reason or 'unknown'}")

        # 收集基线策略 + 全部候选策略输出产物文件路径
        paths = [Path(result.baseline_outcome_path), *(Path(path) for path in result.candidate_outcome_paths)]
        # 批量读取所有产物JSON结果
        outcomes = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
        # 将每条结果转为统一CandidateScore打分对象
        scores = tuple(self._score(item) for item in outcomes)
        # 统计全体策略总仿真尝试次数
        attempts = sum(int(item.get("execution_attempts", 0)) for item in outcomes)
        # 统计仿真执行失败的策略数量
        failed = sum(1 for item in outcomes if not item.get("execution_success", False))

        # 封装为Phase9上层统一识别的世代产物：
        # scores[0] = 基线策略打分；scores[1:] = 各个候选策略打分
        return Phase6GenerationArtifact(scores[0], scores[1:], str(request.optimization_dir), attempts, failed)

    @staticmethod
    def _score(outcome: dict[str, object]) -> CandidateScore:
        """
        静态转换工具：将Phase6输出原始字典，映射为标准化CandidateScore打分模型
        统一字段规范，消除底层Phase6输出结构变动对Phase9控制平面的影响
        """
        return CandidateScore(
            candidate_id=str(outcome["candidate_id"]),
            official_score=outcome.get("native_score"),                # 综合官方得分
            execution_success=bool(outcome.get("execution_success")),  # 仿真是否执行成功
            scoreable=bool(outcome.get("scoreable")),                  # 是否具备打分资格
            semantic_valid=bool(outcome.get("semantic_valid")),        # 策略语义校验是否通过
            artifact_provenance=str(outcome.get("artifact_provenance", "formal_renderer")), # 产物来源标记
            score_source=outcome.get("score_source"),                 # 分数计算来源
            execution_fidelity=str(outcome.get("execution_fidelity", "unknown")), # 推演可信度标记
        )