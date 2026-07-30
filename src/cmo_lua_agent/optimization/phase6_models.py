"""Phase 6 immutable contracts for one deterministic optimization generation.
Phase6 单轮优化全套不可变数据契约定义
所有dataclass全部冻结、禁止运行时随意篡改；统一规范一轮优化从入参、策略生成上下文、候选、多样性报告、评估指纹、排行榜、最终输出结果的数据格式；
隔离底层CMO执行、计分内部实现，传给LLM的上下文做裁剪，保证接口边界清晰、全流程可序列化存档、实验可复现。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

# 顶层业务模型：场景、基线策略、标准作战策略
from cmo_lua_agent.contract.strategy_models import BaselineStrategy, ScenarioDefinition, StrategySpec
# 运行时配置、哈希工具
from cmo_lua_agent.generation.runtime_models import LuaRuntimeProfile, canonical_sha256
# 计分编译对象
from cmo_lua_agent.scoring.native_score_compiler import CmoNativeScoreCompilation


def _text(value: str, name: str) -> str:
    """通用字符串校验工具：非空、去除首尾空白，非法直接抛异常"""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


@dataclass(frozen=True, slots=True)
class BootstrapSkillSnapshot:
    """引导战术经验快照
    加载后的战术技能完整快照，用于策略生成参考，携带校验哈希方便溯源版本
    """
    skill_id: str                  # 技能唯一标识
    version: str                   # 版本号
    status: str                    # 状态
    source: str                    # 来源
    evidence_level: str            # 经验可信度等级
    consumer: tuple[str, ...]      # 适用消费模块
    source_path: str               # 文件路径
    content: str                   # 技能文本内容
    checksum: str                  # 文件哈希

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典用于写入JSON存档，content不落地（减少文件体积）"""
        return {
            "skill_id": self.skill_id, "version": self.version, "status": self.status,
            "source": self.source, "evidence_level": self.evidence_level,
            "consumer": list(self.consumer), "source_path": self.source_path,
            "checksum": self.checksum,
        }


@dataclass(frozen=True, slots=True)
class PlanningRequest:
    """一轮优化顶层入口请求（Phase6工作流入参契约）"""
    optimization_id: str                          # 本轮优化唯一ID
    scenario: ScenarioDefinition                  # 固定作战场景
    baseline: BaselineStrategy                    # 基线基准策略
    user_objective: str                           # 用户作战目标
    allowed_strategy_paths: tuple[str, ...]       # 允许LLM修改的策略字段白名单（JSON指针）
    diversity_dimensions: tuple[str, ...]         # 要求覆盖的战术多样性维度
    runtime: LuaRuntimeProfile                    # 运行时版本配置
    native_score_compilation: CmoNativeScoreCompilation # 计分规则配置
    timeout_seconds: int                          # CMO单次仿真超时时间
    optimization_dir: Path                        # 本轮产物根目录
    bootstrap_skill_path: str = "src/cmo_lua_agent/skills/bootstrap/cmo_naval_air_strategy_proposal_v1.md"
    candidate_count: int = 4                      # 固定一轮生成4条候选
    bootstrap_skill_required: bool = True          # 强制要求加载战术经验
    max_repairs: int = 0                          # 最大自动修复次数
    retrieved_experience_cards: tuple[dict[str, Any], ...] = ()
    # Phase 9 only supplies bounded role hints and prior-generation facts.
    # It never carries CMO configuration, score fragments, or arbitrary Lua.
    generation_context: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """实例创建时自动强校验所有参数合法性，拦截非法入参"""
        _text(self.optimization_id, "optimization_id")
        # ID禁止路径符号，防止目录穿越
        if any(token in self.optimization_id for token in ("/", "\\", "..")):
            raise ValueError("optimization_id must be a safe identifier")
        _text(self.user_objective, "user_objective")
        # Phase6强制一轮4候选
        if self.candidate_count != 4:
            raise ValueError("Phase 6 requires exactly four candidates")
        # 必须启用引导战术经验
        if not self.bootstrap_skill_required:
            raise ValueError("bootstrap_skill_required must be true")
        # 修改路径必须以/开头，标准JSON指针格式
        if not self.allowed_strategy_paths or not all(path.startswith("/") for path in self.allowed_strategy_paths):
            raise ValueError("allowed_strategy_paths must contain JSON Pointer paths")
        # 仿真时长、修复次数数值合法校验
        if self.timeout_seconds <= 0 or self.max_repairs < 0:
            raise ValueError("invalid execution limits")
        # 基线策略、场景、计分规则三者scenario_id必须统一，禁止跨场景混用
        if self.baseline.scenario_id != self.scenario.scenario_id:
            raise ValueError("baseline and scenario must match")
        if self.native_score_compilation.score_spec.scenario_id != self.scenario.scenario_id:
            raise ValueError("score compilation and scenario must match")

    def to_dict(self) -> dict[str, Any]:
        """序列化用于持久化存档"""
        return {
            "optimization_id": self.optimization_id,
            "scenario": self.scenario.to_dict(), "baseline": self.baseline.to_dict(),
            "user_objective": self.user_objective,
            "allowed_strategy_paths": list(self.allowed_strategy_paths),
            "diversity_dimensions": list(self.diversity_dimensions),
            "runtime": self.runtime.to_dict(),
            "timeout_seconds": self.timeout_seconds, "max_repairs": self.max_repairs,
            "bootstrap_skill_path": self.bootstrap_skill_path,
            "candidate_count": self.candidate_count,
            "retrieved_experience_cards": [
                dict(card) for card in self.retrieved_experience_cards
            ],
            "generation_context": dict(self.generation_context or {}),
        }


@dataclass(frozen=True, slots=True)
class StrategyProposalContext:
    """交给LLM生成候选策略的唯一上下文载荷
    刻意剔除CMO底层执行、计分内部实现，隔离敏感系统逻辑，不让大模型接触底层内部机制
    """
    scenario: ScenarioDefinition
    baseline: StrategySpec
    user_objective: str
    allowed_strategy_paths: tuple[str, ...]
    diversity_dimensions: tuple[str, ...]
    runtime_id: str
    runtime_version: str
    bootstrap: BootstrapSkillSnapshot
    # Phase 7 supplies only compact, read-only cards.  An empty value preserves
    # the original Phase 6 proposal prompt exactly in behavior.
    retrieved_experience_cards: tuple[dict[str, Any], ...] = ()
    active_curated_skill: dict[str, Any] | None = None
    generation_context: dict[str, Any] | None = None
    # C3 compact deterministic projection. It deliberately excludes complete
    # StrategySpec, Lua, score implementation, and execution artifacts.
    proposal_tactical_context: dict[str, Any] | None = None

    def to_prompt_dict(self) -> dict[str, Any]:
        """整理成可以直接喂给LLM的结构化字典"""
        value = {
            "user_objective": self.user_objective,
            "allowed_strategy_paths": list(self.allowed_strategy_paths),
            "diversity_dimensions": list(self.diversity_dimensions),
            "runtime": {"runtime_id": self.runtime_id, "runtime_version": self.runtime_version},
            "bootstrap_skill": {"skill_id": self.bootstrap.skill_id, "version": self.bootstrap.version,
                                "checksum": self.bootstrap.checksum, "content": self.bootstrap.content},
            "retrieved_experience_cards": [dict(card) for card in self.retrieved_experience_cards],
        }
        if self.active_curated_skill is not None:
            value["active_curated_skill"] = dict(self.active_curated_skill)
        if self.generation_context is not None:
            value["generation_context"] = dict(self.generation_context)
        if self.proposal_tactical_context is not None:
            value["proposal_tactical_context"] = dict(self.proposal_tactical_context)
        return value


@dataclass(frozen=True, slots=True)
class StrategyCandidate:
    """单条待评估候选策略实体"""
    candidate_id: str                     # 候选ID candidate_00/candidate_01...
    strategy_spec: StrategySpec           # 作战策略主体
    proposal_summary: str                 # LLM生成本条策略的简要思路说明
    intended_difference: tuple[str, ...]  # LLM预期相对基线的改动路径

    @property
    def strategy_checksum(self) -> str:
        """策略哈希，用于快速判断两条策略是否完全一致"""
        return canonical_sha256(self.strategy_spec.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id, "strategy": self.strategy_spec.to_dict(),
            "proposal_summary": self.proposal_summary,
            "intended_difference": list(self.intended_difference),
            "strategy_checksum": self.strategy_checksum
        }


@dataclass(frozen=True, slots=True)
class DiversityReport:
    """候选批次多样性校验报告（CandidateSetValidator输出）"""
    valid: bool                                     # 整批候选是否合规
    dimensions_covered: tuple[str, ...]             # 实际覆盖了哪些战术维度
    candidate_diffs: dict[str, tuple[str, ...]]     # key:候选ID value:实际改动路径
    duplicates: tuple[str, ...] = ()                # 重复策略哈希列表
    violations: tuple[str, ...] = ()                # 违规项文本
    warnings: tuple[str, ...] = ()                  # 警告信息

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid, "dimensions_covered": list(self.dimensions_covered),
            "candidate_diffs": {key: list(value) for key, value in self.candidate_diffs.items()},
            "duplicates": list(self.duplicates), "violations": list(self.violations),
            "warnings": list(self.warnings)
        }


@dataclass(frozen=True, slots=True)
class StrategyCandidateSet:
    """一整批候选集合封装对象"""
    baseline_strategy: StrategySpec
    candidates: tuple[StrategyCandidate, ...]
    diversity_report: DiversityReport


@dataclass(frozen=True, slots=True)
class EvaluationIdentity:
    """本轮评估唯一指纹标识
    场景、计分规则、运行时版本全部打包哈希标识；
    保证基线和所有候选在完全一致环境对比，禁止跨批次、跨配置混合排名
    """
    scenario_checksum: str
    score_spec_checksum: str
    score_fragment_checksum: str
    runtime_version: str
    scoring_side_id: str


@dataclass(frozen=True, slots=True)
class LeaderboardEntry:
    """排行榜单条记录（CandidateComparator排序结果）"""
    candidate_id: str
    is_baseline: bool                  # 是否为基线策略
    category: str                      # 分类：ranked_success / semantic_invalid ...
    rank: int | None                   # 名次，无资格参与排名则为空
    raw_score: int | None              # 原始总分
    execution_success: bool            # Phase5流程是否正常跑完
    semantic_valid: bool               # 仿真行为是否符合策略意图
    scoreable: bool                    # 是否产出有效得分
    repair_invocations: int            # 调用修复Agent次数
    execution_attempts: int            # CMO仿真执行轮次
    failure_reason: str                # 标准化失败原因字符串
    outcome_path: str                  # candidate_outcome.json文件路径
    contract_consistent: bool          # 是否和本轮EvaluationIdentity匹配

    def to_dict(self) -> dict[str, Any]:
        """序列化输出"""
        return {field: getattr(self, field) for field in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class GenerationResult:
    """一轮优化最终对外输出结果（Phase6工作流返回给上层）"""
    optimization_id: str                              # 本轮优化ID
    workflow_completed: bool                          # 整个流水线正常走完（无顶层异常崩溃）
    has_ranked_result: bool                           # 是否存在优于基线的有效候选
    baseline_available: bool                          # 基线是否有效、具备参与排名资格
    baseline_outcome_path: str | None                 # 基线结果文件路径
    candidate_outcome_paths: tuple[str, ...]          # 4条候选结果文件路径
    leaderboard: tuple[LeaderboardEntry, ...]         # 完整排行榜
    bootstrap_skill_id: str                           # 使用的战术技能ID
    bootstrap_skill_version: str                      # 技能版本
    bootstrap_skill_checksum: str                     # 技能哈希
    artifact_paths: dict[str, str]                    # 关键产物目录索引
    failure_reason: str | None = None                 # 顶层异常失败原因，正常完成为空

    def to_dict(self) -> dict[str, Any]:
        return {
            "optimization_id": self.optimization_id, "workflow_completed": self.workflow_completed,
            "has_ranked_result": self.has_ranked_result, "baseline_available": self.baseline_available,
            "baseline_outcome_path": self.baseline_outcome_path,
            "candidate_outcome_paths": list(self.candidate_outcome_paths),
            "leaderboard": [entry.to_dict() for entry in self.leaderboard],
            "bootstrap_skill": {"skill_id": self.bootstrap_skill_id, "version": self.bootstrap_skill_version,
                                "checksum": self.bootstrap_skill_checksum},
            "artifact_paths": dict(self.artifact_paths), "failure_reason": self.failure_reason,
        }
