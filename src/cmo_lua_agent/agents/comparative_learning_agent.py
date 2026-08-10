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
            raise ValueError("comparative response schema is invalid")

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
            raise ValueError("analysis schema is invalid")
        if not isinstance(comparisons_raw, list) or len(comparisons_raw) != len(expected_ids):
            raise ValueError("candidate_comparisons must contain every candidate exactly once")
        comparisons: list[CandidateComparison] = []
        for candidate_id, item in zip(expected_ids, comparisons_raw, strict=True):
            # Candidate IDs come from frozen Python input order. Legacy wrapper
            # IDs are ignored so a model cannot mis-bind an analysis.
            candidate_analysis = item
            if isinstance(item, Mapping) and set(item) == {"candidate_id", "analysis"}:
                candidate_analysis = item["analysis"]
            if not isinstance(candidate_analysis, Mapping):
                raise ValueError("candidate comparison schema is invalid")
            if not isinstance(candidate_analysis, Mapping) or set(candidate_analysis) != set(analysis_fields):
                raise ValueError("candidate comparison analysis schema is invalid")
            comparisons.append(CandidateComparison(
                candidate_id,
                ComparativeAnalysis(*(tuple(str(value) for value in candidate_analysis[field]) for field in analysis_fields)),
            ))
        # 提案必须为列表，数量限制0~5条，控制假说规模，防止上下文爆炸
        if not isinstance(proposals_raw, list) or len(proposals_raw) > 5:
            raise ValueError("proposals must contain 0..5 items")

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
            raise ValueError("proposal contains forbidden or missing fields")

        confidence = ComparativeLearningAgent._confidence(value["model_confidence"])
        # 置信度值域校验：必须是0~1之间数字
        if confidence is None:
            raise ValueError("model_confidence must be within 0..1")
        # 推荐策略模板必须为对象（字典）
        pattern_value = value["recommended_pattern"]
        if isinstance(pattern_value, str) and pattern_value.strip():
            pattern = {"summary": pattern_value.strip()}
        elif isinstance(pattern_value, Mapping):
            pattern = dict(pattern_value)
        else:
            raise ValueError("recommended_pattern must be a non-empty object or string")
        try:
            stance = EvidenceStance(str(value["evidence_stance"]))
        except ValueError as exc:
            raise ValueError("evidence_stance is invalid") from exc

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
            raise ValueError(f"{field_name} must be an array of strings")
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
    "Return exactly one JSON object, with no Markdown or surrounding text. "
    "The root object must contain exactly candidate_comparisons, cross_candidate_analysis, and proposals. "
    "candidate_comparisons must contain one analysis object for every input candidate in response_contract.candidate_comparison_order. "
    "Never output candidate_id in candidate_comparisons; Python binds each array position to the frozen order. "
    "cross_candidate_analysis and every candidate comparison analysis must contain exactly "
    "observed_strategy_differences, observed_execution_differences, "
    "observed_outcome_differences, evidence_limitations, possible_random_factors, and "
    "next_testable_hypotheses; every analysis field must be an array of strings. "
    "proposals must be an array of zero to five objects. Each proposal must contain exactly: "
    "experience_key, experience_type, evidence_stance, hypothesis, applicable_conditions, "
    "recommended_pattern, counter_conditions, supporting_candidate_ids, "
    "contradicting_candidate_ids, model_confidence. applicable_conditions, counter_conditions, "
    "supporting_candidate_ids, and contradicting_candidate_ids must each be JSON arrays of strings. "
    "model_confidence must be a JSON number from 0.0 to 1.0, never a percentage or confidence level. "
    "Allowed experience_key values are naval_air_anti_surface.target_deconfliction, "
    "naval_air_anti_surface.target_concentration, naval_air_anti_surface.salvo_timing, "
    "naval_air_anti_surface.fire_quantity, naval_air_anti_surface.aircraft_route, "
    "naval_air_anti_surface.aircraft_early_loss, and naval_air_anti_surface.ammunition_reserve. "
    "Allowed experience_type values are tactical_positive, tactical_negative, counterexample, "
    "execution_failure, runtime_diagnostic, and evidence_limitation. recommended_pattern must be a JSON object, for example "
    "{\"summary\": \"...\"}; it must never be a string. evidence_stance is support, contradict, or qualify. "
    "For support, supporting_candidate_ids must be non-empty. For contradict, contradicting_candidate_ids must be non-empty. "
    "For qualify, at least one candidate reference and at least one counter_condition are required. Otherwise return no proposal. "
    "Do not output experience IDs, status, evidence references, environment details, scores, Lua, "
    "CMO commands, or ranking changes. candidate_quality is a deterministic quality report and may be used "
    "only to qualify the scope of a hypothesis. COMPLETE and DERIVED scoring evidence may support a normal "
    "proposal. When scoring_evidence_status is MISSING or CONFLICTING but official_score is valid and the "
    "candidate executed successfully, every proposal must use experience_type=evidence_limitation and must "
    "be an explicitly testable black-box hypothesis. It may say only that changed StrategySpec fields may be "
    "associated with an observed outcome. Do not state or invent missile quantities, platform-specific kills, "
    "weapon release, damage attribution, or direct causal mechanisms unless that exact fact appears in the "
    "input view. recommended_pattern must describe a controlled follow-up experiment, not a tactical "
    "recommendation. State missing evidence and plausible alternatives in counter_conditions. Such a proposal "
    "is not Skill-promotion evidence. DERIVED evidence must be described as reconstructed and lower confidence."
)

_REPAIR_SYSTEM = (
    _SYSTEM
    + " This is a repair attempt. Return a complete replacement response. "
    "candidate_comparisons is an ordered array of analysis objects only; never include candidate_id."
)
