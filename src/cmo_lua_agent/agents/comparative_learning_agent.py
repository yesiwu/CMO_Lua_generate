"""
Phase7 用于保守对比分析的唯一LLM边界组件。
核心约束：仅输出经验提案；所有客观事实由确定性Phase7业务代码提供，不允许LLM自主生成事实。
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Protocol

from cmo_lua_agent.learning.models import (
    ComparativeAnalysis,
    EvidenceStance,
    ExperienceProposal,
    GenerationLearningBundle,
)


class ComparativeJsonClient(Protocol):
    """
    LLM结构化输出客户端协议
    定义统一调用接口：传入系统提示词与请求文本，返回解析后的JSON对象
    """
    def complete_json(self, *, system: str, prompt: str) -> object: ...


class ComparativeLearningAgent:
    """
    对比学习智能体
    边界规则：仅产出分析结论与经验提案；全部客观仿真事实由上游确定性代码提供，禁止LLM编造事实。
    """

    def __init__(self, client: ComparativeJsonClient) -> None:
        self._client = client

    def analyze(
        self,
        bundle: GenerationLearningBundle,
    ) -> tuple[ComparativeAnalysis, tuple[ExperienceProposal, ...]]:
        """
        执行多候选仿真案例对比分析
        :param bundle: 标准化一代学习数据包
        :return: (对比观测分析结果, 经验提案元组)
        :raises ValueError: LLM返回JSON结构不符合约定Schema时抛出异常
        """
        # 将学习数据包序列化为有序JSON送入大模型
        raw = self._client.complete_json(
            system=_SYSTEM,
            prompt=json.dumps(bundle.to_dict(), ensure_ascii=False, sort_keys=True),
        )

        # 校验顶层结构：根字典仅允许 analysis、proposals 两个字段
        if not isinstance(raw, Mapping) or set(raw) != {"analysis", "proposals"}:
            raise ValueError("comparative response schema is invalid")

        analysis_raw = raw["analysis"]
        proposals_raw = raw["proposals"]

        # 约定的分析模块固定字段清单
        analysis_fields = (
            "observed_strategy_differences",
            "observed_execution_differences",
            "observed_outcome_differences",
            "evidence_limitations",
            "possible_random_factors",
            "next_testable_hypotheses",
        )
        # 校验analysis内部字段，不允许多字段、缺字段
        if not isinstance(analysis_raw, Mapping) or set(analysis_raw) != set(analysis_fields):
            raise ValueError("analysis schema is invalid")
        # 提案必须为列表，数量限制0~5条，控制假说规模，防止上下文爆炸
        if not isinstance(proposals_raw, list) or len(proposals_raw) > 5:
            raise ValueError("proposals must contain 0..5 items")

        # 组装标准化对比分析实体
        analysis = ComparativeAnalysis(*(tuple(str(item) for item in analysis_raw[field]) for field in analysis_fields))
        # 逐条校验并转换为经验提案实体
        proposals = tuple(self._proposal(item) for item in proposals_raw)
        return analysis, proposals

    @staticmethod
    def _proposal(value: object) -> ExperienceProposal:
        """
        单条经验提案静态校验与实体转换
        :param value: LLM输出单条提案原始字典
        :return: 强类型ExperienceProposal
        """
        # 提案强制要求字段集合，禁止缺失或额外字段
        fields = {
            "experience_key", "experience_type", "evidence_stance",
            "hypothesis", "applicable_conditions",
            "recommended_pattern", "counter_conditions", "supporting_candidate_ids",
            "contradicting_candidate_ids", "model_confidence",
        }
        if not isinstance(value, Mapping) or set(value) != fields:
            raise ValueError("proposal contains forbidden or missing fields")

        confidence = value["model_confidence"]
        # 置信度值域校验：必须是0~1之间数字
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            raise ValueError("model_confidence must be within 0..1")
        # 推荐策略模板必须为对象（字典）
        if not isinstance(value["recommended_pattern"], Mapping):
            raise ValueError("recommended_pattern must be an object")
        try:
            stance = EvidenceStance(str(value["evidence_stance"]))
        except ValueError as exc:
            raise ValueError("evidence_stance is invalid") from exc

        return ExperienceProposal(
            str(value["experience_key"]), str(value["experience_type"]), stance,
            str(value["hypothesis"]),
            tuple(map(str, value["applicable_conditions"])), dict(value["recommended_pattern"]),
            tuple(map(str, value["counter_conditions"])), tuple(map(str, value["supporting_candidate_ids"])),
            tuple(map(str, value["contradicting_candidate_ids"])), float(confidence),
        )


# LLM系统提示词（中文正式约束版本）
_SYSTEM = (
    "只返回一个 JSON 对象；不得输出 Markdown、解释文字或代码围栏。"
    "根对象只能包含 analysis 和 proposals。analysis 必须且只能包含 "
    "observed_strategy_differences、observed_execution_differences、"
    "observed_outcome_differences、evidence_limitations、possible_random_factors、"
    "next_testable_hypotheses，且每个字段均为字符串数组。proposals 必须是 0 到 5 个对象的数组。"
    "每条 proposal 必须显式包含 evidence_stance，且只能是 support、contradict 或 qualify。"
    "基于输入事实开展保守分析。禁止返回实体ID、状态信息、证据引用、环境参数、得分、Lua脚本、"
    "CMO作战指令以及排名变动相关内容。"
)
