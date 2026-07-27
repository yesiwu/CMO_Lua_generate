"""
1. 在 Phase8 完整流水线位置
    ExperienceAggregate（经验聚合结果）
    → ExperienceValidationService.validate()
    → ValidatedExperience
    → SkillPromotionPolicy.decide()（晋升决策）


对照 PromotionProfile 阈值逐条校验：对经验聚合结果 ExperienceAggregate 执行全套指标校验，
输出 ValidatedExperience 实体，判定该经验是否具备晋升为技能规则的资格，并自动生成证据插槽映射，为后续技能包组装提供数据源绑定关系。
"""
from __future__ import annotations

from .aggregation import canonical_sha256
from .models import ExperienceAggregate, ValidatedExperience
from .promotion import PromotionProfile


class ExperienceValidationService:
    """
    经验聚合结果校验服务
    输入：经验聚合视图 ExperienceAggregate
    输出：资格校验实体 ValidatedExperience
    属于Phase8流水线关键环节：经验聚合 → 资格校验 → 晋升决策
    """
    def __init__(self, profile: PromotionProfile) -> None:
        """
        :param profile: 晋升阈值配置模板，定义各项指标最低/最高约束
        """
        self._profile = profile

    def validate(self, aggregate: ExperienceAggregate) -> ValidatedExperience:
        """
        执行全套经验资格校验
        :param aggregate: 同源经验聚合汇总结果
        :return: 带校验结论、插槽映射的标准化已校验经验实体
        """
        reasons: list[str] = []
        # 指标校验清单：(判断条件, 失败标识)
        checks = (
            (
                aggregate.independent_scenario_count
                < self._profile.minimum_independent_scenarios,
                "insufficient_independent_scenarios",
            ),
            (
                aggregate.independent_optimization_count
                < self._profile.minimum_independent_optimizations,
                "insufficient_independent_optimizations",
            ),
            (
                aggregate.support_count < self._profile.minimum_support,
                "insufficient_support",
            ),
            (
                aggregate.mean_evidence_quality
                < self._profile.minimum_mean_evidence_quality,
                "evidence_quality_below_minimum",
            ),
            (
                aggregate.execution_success_rate
                < self._profile.minimum_execution_success_rate,
                "execution_success_rate_below_minimum",
            ),
            (
                aggregate.semantic_valid_rate
                < self._profile.minimum_semantic_valid_rate,
                "semantic_valid_rate_below_minimum",
            ),
            (
                aggregate.execution_fidelity_rate
                < self._profile.minimum_execution_fidelity_rate,
                "execution_fidelity_rate_below_minimum",
            ),
            (
                aggregate.contradiction_ratio
                > self._profile.maximum_contradiction_ratio,
                "contradiction_ratio_above_maximum",
            ),
        )
        # 收集所有不满足阈值的失败原因
        reasons.extend(reason for failed, reason in checks if failed)

        # 额外校验：只认可 execution_summary 作为可信得分数据源
        if aggregate.score_sources != ("execution_summary",):
            reasons.append("untrusted_score_source")
        # 额外校验：是否存在单轮优化内部证据立场冲突
        if aggregate.stance_conflicts:
            reasons.append("stance_conflict_present")

        # 综合置信度计算公式
        # 证据质量 × 执行成功率 × 语义合法率 × 保真验证率 × (1 - 矛盾占比)
        confidence = round(
            aggregate.mean_evidence_quality
            * aggregate.execution_success_rate
            * aggregate.semantic_valid_rate
            * aggregate.execution_fidelity_rate
            * (1 - aggregate.contradiction_ratio),
            6,
        )
        # 综合置信度低于阈值，追加失败理由
        if confidence < self._profile.minimum_deterministic_confidence:
            reasons.append("deterministic_confidence_below_minimum")

        # 提取经验键后缀，作为插槽名称前缀
        slot_prefix = aggregate.experience_key.rsplit(".", 1)[-1]
        # 自动生成三类证据对应的唯一插槽名称
        support_slots = tuple(
            f"{slot_prefix}_support_{index:02d}"
            for index in range(1, len(aggregate.supporting_evidence) + 1)
        )
        contradict_slots = tuple(
            f"{slot_prefix}_contradict_{index:02d}"
            for index in range(
                1, len(aggregate.contradicting_evidence) + 1
            )
        )
        qualify_slots = tuple(
            f"{slot_prefix}_qualify_{index:02d}"
            for index in range(1, len(aggregate.qualifying_evidence) + 1)
        )

        # 构建插槽映射：插槽名称 → 绑定的原始经验ID列表
        slot_map = {
            slot: evidence.experience_ids
            for slot, evidence in zip(
                support_slots, aggregate.supporting_evidence, strict=True
            )
        }
        slot_map.update({
            slot: evidence.experience_ids
            for slot, evidence in zip(
                contradict_slots,
                aggregate.contradicting_evidence,
                strict=True,
            )
        })
        slot_map.update({
            slot: evidence.experience_ids
            for slot, evidence in zip(
                qualify_slots, aggregate.qualifying_evidence, strict=True
            )
        })

        # 用于生成校验实体唯一哈希载荷
        body = {
            "aggregate_id": aggregate.aggregate_id,
            "reasons": reasons,
            "confidence": confidence,
            "slots": slot_map,
        }
        checksum = canonical_sha256(body)

        return ValidatedExperience(
            validation_id=f"validated_{checksum[:20]}",
            aggregate_id=aggregate.aggregate_id,
            experience_key=aggregate.experience_key,
            mission_type=aggregate.mission_type,
            family=aggregate.family,
            canonical_hypothesis=aggregate.canonical_hypothesis,
            compatibility_cohort=aggregate.compatibility_cohort,
            # 无任何失败理由 → 具备晋升资格
            eligible=not reasons,
            validation_status="eligible" if not reasons else "ineligible",
            validation_reasons=tuple(reasons),
            deterministic_confidence=confidence,
            supporting_slots=support_slots,
            contradicting_slots=contradict_slots,
            qualifying_slots=qualify_slots,
            evidence_slot_map=slot_map,
            aggregate_checksum=aggregate.checksum,
            checksum=checksum,
        )