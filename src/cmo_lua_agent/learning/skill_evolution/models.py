"""
Phase 8 技能演化流程的不可变契约模型。
定义经验聚合、经验校验、晋升决策全套强类型数据结构；所有实体冻结不可修改，保障跨模块数据确定性与一致性，作为经验晋升为技能的标准数据契约。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from cmo_lua_agent.learning.models import EvidenceStance


class PromotionAction(StrEnum):
    """
    经验晋升动作枚举
    基于经验聚合评估结果，决定本轮对经验采取何种处理动作
    """
    CREATE_PENDING_SKILL = "create_pending_skill"    # 创建全新待审核技能包
    REVISE_EXISTING_SKILL = "revise_existing_skill"  # 修订已有技能，生成新版本待审核包
    CONTINUE_ACCUMULATING = "continue_accumulating"  # 暂不晋升，继续收集更多仿真证据
    REQUIRE_REVIEW = "require_review"                # 存在冲突证据，需要人工介入复核
    REJECT = "reject"                                # 否定该经验，不允许晋升为技能规则


@dataclass(frozen=True, slots=True)
class CompatibilityCohort:
    """
    环境兼容分组契约
    用于隔离不同仿真运行环境；只有相同分组下的经验、技能才能互通，防止跨版本环境混用数据导致结论失真
    """
    cohort_id: str                      # 兼容分组唯一ID，由环境参数哈希生成
    score_spec_major: int               # 评分规范主版本号
    score_spec_checksum: str            # 评分规范文件校验和
    runtime_major: int                  # 仿真引擎主版本号
    renderer_major: int                # 渲染模块主版本号
    scenario_schema_version: str        # 想定文件结构版本
    score_source: str                   # 得分数据源标识

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典，用于JSON持久化与LLM输入"""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AggregateEvidence:
    """
    单轮优化聚合证据单元
    同一轮优化内多条同源经验合并后的证据单元，是经验聚合结果的基础组成单元
    """
    evidence_key: str                  # 证据标识：优化轮ID:经验键
    stance: EvidenceStance             # 证据立场（支持/矛盾/限定）
    source_optimization_id: str        # 来源优化轮ID
    scenario_id: str                   # 仿真想定标识
    experience_ids: tuple[str, ...]    # 本轮包含的原始经验ID列表
    supporting_candidates: tuple[str, ...] # 支撑该证据的候选方案ID
    evidence_quality: float            # 本轮证据综合质量 [0,1]
    score_delta: float | None          # 相对基线得分变化均值
    execution_success: bool            # 本轮所有案例是否全部执行成功
    semantic_valid: bool               # 本轮所有案例策略语义是否合法
    fidelity_verified: bool           # 本轮所有案例仿真证据是否完整可信
    evidence_refs: tuple[str, ...]     # 原始仿真证据文件溯源路径

    def to_dict(self) -> dict[str, Any]:
        """序列化，将枚举转为字符串值"""
        value = asdict(self)
        value["stance"] = self.stance.value
        return value


@dataclass(frozen=True, slots=True)
class ExperienceAggregate:
    """
    经验聚合视图
    多条独立优化轮次的同源经验汇总聚合结果；Phase7聚合器最终输出实体，
    量化统计支持/矛盾/限定证据数量、各类可信度指标，作为能否晋升技能的评估依据
    """
    aggregate_id: str                          # 聚合结果唯一ID
    experience_key: str                        # 归一化经验键
    mission_type: str                          # 任务类型
    family: str                                # 归属技能家族
    canonical_hypothesis: str                  # 该经验标准规范假说
    compatibility_cohort: CompatibilityCohort  # 所属环境兼容分组
    supporting_evidence: tuple[AggregateEvidence, ...]   # 全部支持类证据
    contradicting_evidence: tuple[AggregateEvidence, ...]# 全部矛盾类证据
    qualifying_evidence: tuple[AggregateEvidence, ...]   # 全部限定条件类证据
    excluded_experience_ids: tuple[str, ...]   # 被排除不参与聚合的经验ID
    independent_optimization_count: int        # 参与聚合的独立优化轮总数
    independent_scenario_count: int            # 涉及的独立想定数量
    support_count: int                         # 支持证据条数
    contradict_count: int                      # 矛盾证据条数
    qualify_count: int                         # 限定条件证据条数
    contradiction_ratio: float                 # 矛盾率：矛盾证据/(支持+矛盾证据)
    mean_evidence_quality: float               # 证据质量平均值
    mean_score_delta: float | None             # 得分变化均值
    median_score_delta: float | None           # 得分变化中位数
    execution_success_rate: float              # 执行成功率
    semantic_valid_rate: float                # 策略语义合法率
    execution_fidelity_rate: float            # 仿真证据完整可信比率
    stance_conflicts: tuple[str, ...]          # 单轮内部存在立场冲突的优化轮ID列表
    score_sources: tuple[str, ...]             # 得分数据源集合
    aggregate_status: str                     # 聚合状态标识
    checksum: str                              # 聚合实体整体校验和，用于确定性比对

    def to_dict(self) -> dict[str, Any]:
        """递归序列化，嵌套对象展开为字典"""
        return {
            **asdict(self),
            "compatibility_cohort": self.compatibility_cohort.to_dict(),
            "supporting_evidence": [
                item.to_dict() for item in self.supporting_evidence
            ],
            "contradicting_evidence": [
                item.to_dict() for item in self.contradicting_evidence
            ],
            "qualifying_evidence": [
                item.to_dict() for item in self.qualifying_evidence
            ],
        }


@dataclass(frozen=True, slots=True)
class AggregationExclusion:
    experience_id: str
    error_code: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ExperienceAggregationResult:
    aggregates: tuple[ExperienceAggregate, ...]
    exclusions: tuple[AggregationExclusion, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "aggregates": [item.to_dict() for item in self.aggregates],
            "exclusions": [item.to_dict() for item in self.exclusions],
        }


@dataclass(frozen=True, slots=True)
class ValidatedExperience:
    """
    经过晋升资格校验的有效经验
    在ExperienceAggregate基础上，完成晋升准入校验；划分证据插槽，为后续组装技能包提供插槽映射
    """
    validation_id: str                          # 本次校验唯一ID
    aggregate_id: str                           # 来源经验聚合ID
    experience_key: str                         # 归一化经验键
    mission_type: str                           # 任务类型
    family: str                                 # 归属技能家族
    canonical_hypothesis: str                   # 标准经验假说
    compatibility_cohort: CompatibilityCohort   # 兼容分组
    eligible: bool                              # 是否具备晋升为技能规则的资格
    validation_status: str                     # 校验状态
    validation_reasons: tuple[str, ...]         # 校验结论理由
    deterministic_confidence: float            # 综合可信置信度 [0,1]
    supporting_slots: tuple[str, ...]          # 支持类证据对应的插槽名称
    contradicting_slots: tuple[str, ...]       # 矛盾类证据对应的插槽名称
    qualifying_slots: tuple[str, ...]           # 限定类证据对应的插槽名称
    evidence_slot_map: dict[str, tuple[str, ...]]# 插槽名称 → 绑定经验ID映射
    aggregate_checksum: str                    # 来源聚合实体校验和
    checksum: str                               # 本校验实体自身校验和

    def to_dict(self) -> dict[str, Any]:
        """序列化，元组列表转为普通数组"""
        return {
            **asdict(self),
            "compatibility_cohort": self.compatibility_cohort.to_dict(),
            "evidence_slot_map": {
                key: list(value)
                for key, value in sorted(self.evidence_slot_map.items())
            },
        }


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    """
    经验晋升决策单据
    基于ValidatedExperience产出的最终决策，指导SkillPackageAssembler组装待审核技能包
    """
    decision_id: str                  # 决策单据唯一ID
    eligible: bool                    # 是否允许生成 Pending Package
    validated_experience_ids: tuple[str, ...] # 绑定的验证经验 ID
    family_id: str                    # 目标 Skill Family
    cohort_id: str                    # 目标兼容分组ID
    action: PromotionAction           # 本次执行动作（新建/修订/继续积累等）
    target_version: str | None        # 技能目标版本；新建/修订时赋值
    reasons: tuple[str, ...]          # 做出该决策的依据说明
    profile_id: str                   # 使用的晋升评估策略配置ID
    provenance: str                   # production / test_fixture
    checksum: str                     # 决策单据校验和，防篡改

    def to_dict(self) -> dict[str, Any]:
        """序列化，枚举转为字符串"""
        value = asdict(self)
        value["action"] = self.action.value
        return value
