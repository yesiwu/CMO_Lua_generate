"""
Phase7 用于保守对比分析的唯一LLM边界组件。
核心约束：仅输出经验提案；所有客观事实由确定性Phase7业务代码提供，不允许LLM自主生成事实。
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Protocol

from cmo_lua_agent.learning.models import (
    CandidateComparison,
    ComparativeAnalysis,
    ComparativeLearningResponse,
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
        self._last_attempts: tuple[dict[str, object], ...] = ()

    @property
    def last_attempts(self) -> tuple[dict[str, object], ...]:
        """Bounded response-validation audit; model response text is never retained."""
        return self._last_attempts

    def analyze(
        self,
        bundle: GenerationLearningBundle,
    ) -> ComparativeLearningResponse:
        """
        执行多候选仿真案例对比分析
        :param bundle: 标准化一代学习数据包
        :return: (对比观测分析结果, 经验提案元组)
        :raises ValueError: LLM返回JSON结构不符合约定Schema时抛出异常
        """
        # 将学习数据包序列化为有序JSON送入大模型
        expected_ids = tuple(item.candidate_id for item in bundle.candidate_views)
        attempts: list[dict[str, object]] = []
        error: ValueError | None = None
        for attempt_index in range(4):
            try:
                raw = self._client.complete_json(
                    system=_SYSTEM if error is None else _REPAIR_SYSTEM,
                    prompt=_prompt(
                        bundle=bundle,
                        expected_ids=expected_ids,
                        repair_error=None if error is None else str(error),
                    ),
                )
                response = self._parse(raw=raw, expected_ids=expected_ids)
            except ValueError as exc:
                error = exc
                attempts.append({
                    "attempt": attempt_index + 1,
                    "status": "invalid",
                    "error_code": _error_code(exc),
                })
                continue
            attempts.append({"attempt": attempt_index + 1, "status": "accepted"})
            self._last_attempts = tuple(attempts)
            return response

        self._last_attempts = tuple(attempts)
        assert error is not None
        raise error

    @staticmethod
    def _parse(
        *, raw: object, expected_ids: tuple[str, ...],
    ) -> ComparativeLearningResponse:

        # 校验顶层结构：根字典仅允许 analysis、proposals 两个字段
        if not isinstance(raw, Mapping) or set(raw) != {"candidate_comparisons", "cross_candidate_analysis", "proposals"}:
            raise ValueError("对比学习响应的结构不合法")

        comparisons_raw = raw["candidate_comparisons"]
        analysis_raw = raw["cross_candidate_analysis"]
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
            raise ValueError("分析结果的结构不合法")
        if not isinstance(comparisons_raw, list) or len(comparisons_raw) != len(expected_ids):
            raise ValueError("candidate_comparisons 必须恰好包含每个候选方案一次")
        comparisons: list[CandidateComparison] = []
        for candidate_id, item in zip(expected_ids, comparisons_raw, strict=True):
            # 候选方案 ID 由 Python 的冻结输入顺序决定；即使兼容旧包装格式中的 ID
            # 不正确，也不能让模型把分析结果绑定到错误候选方案。
            candidate_analysis = item
            if isinstance(item, Mapping) and set(item) == {"candidate_id", "analysis"}:
                candidate_analysis = item["analysis"]
            if not isinstance(candidate_analysis, Mapping):
                raise ValueError("候选方案对比项的结构不合法")
            if not isinstance(candidate_analysis, Mapping) or set(candidate_analysis) != set(analysis_fields):
                raise ValueError("候选方案对比分析的结构不合法")
            comparisons.append(CandidateComparison(
                candidate_id,
                ComparativeAnalysis(*(tuple(str(value) for value in candidate_analysis[field]) for field in analysis_fields)),
            ))
        # 提案必须为列表，数量限制0~5条，控制假说规模，防止上下文爆炸
        if not isinstance(proposals_raw, list) or len(proposals_raw) > 5:
            raise ValueError("proposals 必须包含 0 到 5 项")

        # 组装标准化对比分析实体
        analysis = ComparativeAnalysis(*(tuple(str(item) for item in analysis_raw[field]) for field in analysis_fields))
        # 逐条校验并转换为经验提案实体
        proposals = tuple(ComparativeLearningAgent._proposal(item) for item in proposals_raw)
        return ComparativeLearningResponse(tuple(comparisons), analysis, proposals)

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
            raise ValueError("经验提案包含缺失字段或不允许的字段")

        confidence = ComparativeLearningAgent._confidence(value["model_confidence"])
        # 置信度值域校验：必须是0~1之间数字
        if confidence is None:
            raise ValueError("model_confidence 必须位于 0 到 1 之间")
        # 推荐策略模板必须为对象（字典）
        pattern_value = value["recommended_pattern"]
        if isinstance(pattern_value, str) and pattern_value.strip():
            pattern = {"summary": pattern_value.strip()}
        elif isinstance(pattern_value, Mapping):
            pattern = dict(pattern_value)
        else:
            raise ValueError("recommended_pattern 必须是非空对象或字符串")
        try:
            stance = EvidenceStance(str(value["evidence_stance"]))
        except ValueError as exc:
            raise ValueError("evidence_stance 不合法") from exc

        applicable_conditions = ComparativeLearningAgent._string_array(
            value["applicable_conditions"], "applicable_conditions"
        )
        counter_conditions = ComparativeLearningAgent._string_array(
            value["counter_conditions"], "counter_conditions"
        )
        supporting_candidate_ids = ComparativeLearningAgent._string_array(
            value["supporting_candidate_ids"], "supporting_candidate_ids"
        )
        contradicting_candidate_ids = ComparativeLearningAgent._string_array(
            value["contradicting_candidate_ids"], "contradicting_candidate_ids"
        )
        return ExperienceProposal(
            str(value["experience_key"]), str(value["experience_type"]), stance,
            str(value["hypothesis"]),
            applicable_conditions, pattern, counter_conditions,
            supporting_candidate_ids, contradicting_candidate_ids, confidence,
        )

    @staticmethod
    def _string_array(value: object, field_name: str) -> tuple[str, ...]:
        """Reject scalar strings rather than iterating them character by character."""
        if not isinstance(value, list) or not all(
            isinstance(item, str) and item.strip() for item in value
        ):
            raise ValueError(f"{field_name} 必须是字符串数组")
        return tuple(item.strip() for item in value)

    @staticmethod
    def _confidence(value: object) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            if 0 <= value <= 1:
                return float(value)
            if 1 < value <= 100:
                return float(value) / 100
        if not isinstance(value, str):
            return None
        text = value.strip()
        if re.fullmatch(r"(?:0(?:\.\d+)?|1(?:\.0+)?)", text):
            return float(text)
        if re.fullmatch(r"(?:\d{1,2}|100)%", text):
            return float(text[:-1]) / 100
        if re.fullmatch(r"(?:\d{1,2}|100)", text):
            return float(text) / 100
        return None


# LLM系统提示词（中文正式约束版本）
def _prompt(
    *,
    bundle: GenerationLearningBundle,
    expected_ids: tuple[str, ...],
    repair_error: str | None,
) -> str:
    payload: dict[str, object] = {
        "generation_bundle": bundle.to_dict(),
        "response_contract": {
            "candidate_comparison_order": list(expected_ids),
            "candidate_comparisons_item": "analysis_object_only",
        },
    }
    if repair_error is not None:
        payload["repair"] = {
            "previous_error": repair_error,
            "instruction": "Return a complete replacement response that satisfies the response_contract.",
        }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _error_code(error: ValueError) -> str:
    value = str(error).strip().lower().replace(" ", "_")
    return value or error.__class__.__name__.lower()


_SYSTEM = (
    "只能返回一个 JSON 对象，不得包含 Markdown 或其他包裹文本。"
    "根对象必须且只能包含 candidate_comparisons、cross_candidate_analysis 与 proposals。"
    "candidate_comparisons 必须按 response_contract.candidate_comparison_order 中的顺序，为每个输入候选方案提供一个分析对象。"
    "不得在 candidate_comparisons 中输出 candidate_id；Python 会按冻结顺序绑定数组位置。"
    "cross_candidate_analysis 及每个候选方案的比较分析必须且只能包含 "
    "observed_strategy_differences、observed_execution_differences、"
    "observed_outcome_differences、evidence_limitations、possible_random_factors 与 "
    "next_testable_hypotheses；每个分析字段必须是字符串数组。"
    "proposals 必须是包含零到五个对象的数组。每个对象必须且只能包含："
    "experience_key, experience_type, evidence_stance, hypothesis, applicable_conditions, "
    "recommended_pattern, counter_conditions, supporting_candidate_ids, "
    "contradicting_candidate_ids、model_confidence。applicable_conditions、counter_conditions、"
    "supporting_candidate_ids 与 contradicting_candidate_ids 均必须是 JSON 字符串数组。"
    "model_confidence 必须是 0.0 到 1.0 的 JSON 数字，不能使用百分比或置信等级。"
    "允许的 experience_key 值为 naval_air_anti_surface.target_deconfliction、"
    "naval_air_anti_surface.target_concentration, naval_air_anti_surface.salvo_timing, "
    "naval_air_anti_surface.fire_quantity, naval_air_anti_surface.aircraft_route, "
    "naval_air_anti_surface.aircraft_early_loss 与 naval_air_anti_surface.ammunition_reserve。"
    "允许的 experience_type 值为 tactical_positive、tactical_negative、counterexample、"
    "execution_failure、runtime_diagnostic 与 evidence_limitation。recommended_pattern 必须是 JSON 对象，例如 "
    "{\"summary\": \"...\"}，绝不能是字符串。evidence_stance 只能是 support、contradict 或 qualify。"
    "当 evidence_stance 为 support 时，supporting_candidate_ids 不能为空；为 contradict 时，contradicting_candidate_ids 不能为空。"
    "当 evidence_stance 为 qualify 时，至少需要一个候选方案引用和一个 counter_condition，否则不要输出该 proposal。"
    "不得输出经验 ID、状态、证据引用、环境细节、分数、Lua、CMO 命令或排名变化。candidate_quality 是确定性的质量报告，"
    "只能用于限定假设适用范围。COMPLETE 与 DERIVED 的计分证据可以支撑普通 proposal。"
    "当 scoring_evidence_status 为 MISSING 或 CONFLICTING、但 official_score 有效且候选方案成功执行时，"
    "每个 proposal 都必须使用 experience_type=evidence_limitation，并且必须是可明确验证的黑箱假设。"
    "它只能说明变动过的 StrategySpec 字段可能与观察到的结果相关。除非输入视图中明确给出了相同事实，"
    "不得陈述或虚构导弹数量、特定平台击杀、武器释放、毁伤归因或直接因果机制。recommended_pattern 必须描述受控的后续实验，"
    "而非战术建议。请在 counter_conditions 中说明缺失证据和可能的替代解释。此类 proposal 不能作为 Skill 晋升证据。"
    "DERIVED 证据必须说明为重建结果，并降低置信度。"
)

_REPAIR_SYSTEM = (
    _SYSTEM
    + "这是一次修复尝试；请返回完整的替换响应。"
    "candidate_comparisons 只能是有序分析对象数组，绝不能包含 candidate_id。"
)
