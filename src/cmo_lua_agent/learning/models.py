"""
Phase 7 不可变契约模型。刻意剔除 Lua 代码与原始 CMO 日志，
向上层学习组件屏蔽底层仿真原始细节，约束输入边界、抑制语义漂移。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CandidateLearningView:
    """
    单条候选方案标准化学习视图
    不可变数据模型：承载经过清洗、筛选后的客观仿真事实，不包含原始交战日志、指令代码
    """
    candidate_id: str                      # 候选唯一标识
    is_baseline: bool                      # 是否为基线对照方案
    strategy_summary: dict[str, Any]       # 策略精简概要（攻击数量、出动架次等聚合指标）
    strategy_diff: tuple[str, ...]         # 相对基线的策略差异描述
    planned_vs_actual: dict[str, str]      # 计划方案与实际执行完备性标记
    official_score: int | None             # 官方最终得分
    score_source: str | None               # 得分来源文件路径锚点，用于审计溯源
    scoreable: bool                        # 是否具备有效计分条件
    semantic_valid: bool                   # 策略语义校验是否通过
    execution_success: bool                # 仿真执行是否成功完成
    losses: dict[str, Any]                 # 兵力损失汇总
    target_damage: Any                     # 目标毁伤汇总
    weapon_expenditures: Any               # 武器消耗汇总
    timing_summary: dict[str, Any]         # 时序事件可用性摘要
    execution_fidelity: str                # 仿真证据保真度标记(unknown/partial/failed/verified)
    evidence_integrity: dict[str, Any]     # 证据完整性校验结果
    environment: dict[str, str]            # 运行环境版本契约
    evidence_refs: tuple[str, ...]         # 依赖原始证据文件相对路径，用于审计溯源

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典，用于送入LLM"""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class GenerationLearningBundle:
    """
    单代优化任务完整学习数据包
    聚合基线方案 + 全部候选视图，作为 Phase7 对比学习Agent标准输入
    """
    optimization_id: str                              # 本轮优化任务ID
    scenario_features: tuple[str, ...]                # 想定特征标签
    comparison_contract: dict[str, str]               # 对比契约：锁定运行环境版本，保证可比
    baseline_view: CandidateLearningView              # 基线方案学习视图
    candidate_views: tuple[CandidateLearningView, ...] # 本轮所有候选方案视图集合
    leaderboard: tuple[dict[str, Any], ...]           # 本轮候选排名榜单
    pairwise_strategy_diffs: dict[str, tuple[str, ...]] # 各候选相对基线的策略差异映射
    valid_tactical_candidates: tuple[str, ...]        # 通过完整性、有效性校验的可信候选ID
    invalid_candidates: tuple[str, ...]               # 存在缺陷、应当过滤的候选ID
    evidence_refs: tuple[str, ...]                    # 本轮全部证据文件汇总路径

    def to_dict(self) -> dict[str, Any]:
        """递归序列化，嵌套视图对象展开为普通字典"""
        return {
            **asdict(self),
            "baseline_view": self.baseline_view.to_dict(),
            "candidate_views": [x.to_dict() for x in self.candidate_views]
        }


@dataclass(frozen=True, slots=True)
class ExperienceProposal:
    """
    LLM输出的经验提案（Phase7 LLM标准输出结构）
    仅代表假设/待验证猜想，并非固化经验
    """
    experience_key: str                     # 经验唯一标识键
    experience_type: str                    # 经验类型（进攻/防御/分配/时机等）
    hypothesis: str                         # 核心假设陈述
    applicable_conditions: tuple[str, ...]  # 假设生效适用条件
    recommended_pattern: dict[str, Any]     # 推荐采用的策略模式
    counter_conditions: tuple[str, ...]     # 该经验不适用的反向条件
    supporting_candidate_ids: tuple[str, ...] # 支撑该假设的候选案例ID
    contradicting_candidate_ids: tuple[str, ...] # 与假设冲突的候选案例ID
    model_confidence: float                 # LLM给出置信度 [0,1]


@dataclass(frozen=True, slots=True)
class ComparativeAnalysis:
    """
    多候选仿真结果对比分析文本集合
    客观观测结论，不直接生成改进方案，作为提案生成依据
    """
    observed_strategy_differences: tuple[str, ...] # 观测到的策略层面差异
    observed_execution_differences: tuple[str, ...]# 观测到的执行层面差异
    observed_outcome_differences: tuple[str, ...]  # 观测到的战果/得分差异
    evidence_limitations: tuple[str, ...]          # 当前证据存在的局限、数据缺口
    possible_random_factors: tuple[str, ...]       # 可能造成结果波动的随机因素
    next_testable_hypotheses: tuple[str, ...]      # 后续可设计试验验证的假说


@dataclass(frozen=True, slots=True)
class ExperienceCandidate:
    """
    待验证经验候选体
    将LLM输出的ExperienceProposal提升为系统可持久化、可调度验证的实体
    """
    experience_id: str                       # 经验实体唯一ID
    experience_key: str                      # 经验业务键（多条同源提案可复用key）
    experience_type: str                     # 经验分类
    status: str                              # 生命周期状态（草案/待验证/验证中/生效/废弃）
    consumer: str                            # 消费方模块标识
    source_optimization_id: str              # 来源优化轮次ID
    hypothesis: str                          # 经验核心假设
    applicable_conditions: tuple[str, ...]   # 适用场景条件
    recommended_pattern: dict[str, Any]      # 推荐策略模板
    counter_conditions: tuple[str, ...]      # 不适用反向条件
    observed_effect: dict[str, Any]          # 当前观测到的预期效果摘要
    environment: dict[str, str]              # 经验生效环境契约
    evidence_refs: tuple[str, ...]           # 支撑证据溯源路径
    created_from: tuple[str, ...]            # 生成该经验依赖的候选ID列表
    evidence_quality: float                  # 证据综合质量评分 [0,1]
    model_confidence: float                  # LLM原始置信度
    strategy_dimensions: tuple[str, ...]     # 该经验影响的策略维度

    def to_dict(self) -> dict[str, Any]:
        """Return the stable persisted form consumed by ``ExperienceStore``."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ExperienceCard:
    """
    轻量化经验卡片，用于下游策略生成模块快速读取、匹配场景
    剔除审计冗余字段，仅保留推理必需信息
    """
    experience_key: str
    experience_type: str
    source_optimization_id: str
    confidence: float                     # 综合置信度
    evidence_quality: float               # 证据质量
    applicable_when: tuple[str, ...]      # 适用条件
    suggestion: str                       # 简洁行动建议
    counter_conditions: tuple[str, ...]  # 失效条件
    evidence_count: int                   # 支撑案例数量
    status: str                           # 经验生效状态
