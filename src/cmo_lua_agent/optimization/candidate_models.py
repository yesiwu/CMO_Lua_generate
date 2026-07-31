"""Phase 5 single-candidate contracts and guarded state transitions.
Phase5 单候选数据契约 + 受约束状态机定义
包含：候选状态枚举、失败原因枚举、入参请求契约、状态事件契约、最终输出结果契约、带合法跳转校验的状态机；
所有数据模型均为不可变冻结结构，状态跳转有严格白名单，禁止非法流转，保证候选流程可追溯、流转逻辑不会错乱。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

# 顶层业务契约：场景、策略、运行时、计分编译产物
from cmo_lua_agent.contract.strategy_models import ScenarioDefinition, StrategySpec
from cmo_lua_agent.generation.runtime_models import LuaRuntimeProfile
from cmo_lua_agent.scoring.native_score_compiler import CmoNativeScoreCompilation


# 候选全生命周期状态枚举
class CandidateState(str, Enum):
    CREATED = "CREATED"                    # 候选刚创建，流程未开始
    STRATEGY_VALIDATED = "STRATEGY_VALIDATED" # 策略校验通过
    PLAN_COMPILED = "PLAN_COMPILED"         # 执行计划编译完成
    LUA_RENDERED = "LUA_RENDERED"           # 带计分Lua渲染完成
    CMO_EXECUTED = "CMO_EXECUTED"           # CMO仿真执行完毕
    REPAIRED = "REPAIRED"                  # 应用策略补丁修复完成
    SEMANTIC_VALIDATED = "SEMANTIC_VALIDATED" # Phase3语义校验通过
    SCORED = "SCORED"                      # 成功计算得分
    COMPLETED = "COMPLETED"                # 整条候选流程全部正常结束（成功）
    FAILED = "FAILED"                      # 流程终止（任意失败场景）


# 所有标准化失败/终止原因枚举
class CandidateFailureReason(str, Enum):
    COMPLETED = "completed"                              # 正常完成，无失败
    STRATEGY_INVALID = "strategy_invalid"                # 策略校验不合法
    CAPABILITY_GAP = "capability_gap"                    # 存在运行时能力缺口
    PLAN_VALIDATION_FAILED = "plan_validation_failed"    # 执行计划原语校验失败
    RENDER_FAILED = "render_failed"                      # Lua渲染报错
    LUA_SYNTAX_ERROR = "lua_syntax_error"                # Lua语法错误
    LUA_RUNTIME_ERROR = "lua_runtime_error"              # Lua运行时报错
    CMO_TIMEOUT = "cmo_timeout"                          # CMO仿真超时
    INFRASTRUCTURE_FAILURE = "infrastructure_failure"    # 底层基础设施故障
    CONFIGURATION_RESTORE_FAILED = "configuration_restore_failed" # 仿真环境恢复失败
    REPAIR_NOT_APPLICABLE = "repair_not_applicable"      # 当前错误不支持自动修复
    REPAIR_BUDGET_EXHAUSTED = "repair_budget_exhausted" # 达到最大修复次数上限
    REPAIR_KIND_MISMATCH = "repair_kind_mismatch"        # 修复类型与错误类型不匹配
    RUNTIME_PATCH_ALREADY_APPLIED = "runtime_patch_already_applied" # 运行时补丁已重复应用
    RUNTIME_DEFECT = "runtime_defect"                    # Runtime底层代码缺陷，无法修复
    RESULT_UNSCORABLE = "result_unscorable"              # 仿真数据缺失，无法打分
    RESULT_INTEGRITY_FAILED = "result_integrity_failed"  # 计分数据冲突不一致
    SEMANTIC_DRIFT = "semantic_drift"                    # 仿真结果偏离原始策略意图
    CANCELLED = "cancelled"                              # 外部手动取消流程
    INTERNAL_WORKFLOW_ERROR = "internal_workflow_error"  # 流水线内部未知异常


# 单候选流程入参契约（不可变）
@dataclass(frozen=True, slots=True)
class CandidateRequest:
    candidate_id: str                          # 候选唯一标识
    generation_index: int                      # 第几代候选（Phase6/10多代进化用）
    scenario: ScenarioDefinition               # 固定场景事实
    strategy: StrategySpec                     # 当前待评估作战策略
    runtime: LuaRuntimeProfile                 # 运行时能力版本
    native_score_compilation: CmoNativeScoreCompilation # 计分编译配置
    max_repairs: int                           # 最大自动修复次数
    timeout_seconds: int                       # CMO仿真超时秒数
    candidate_dir: Path                        # 候选产物沙箱目录
    allowed_strategy_paths: tuple[str, ...]    # 允许补丁修改的策略字段白名单
    reuse_existing_artifacts: bool = False
    official_score_only: bool = False

    def __post_init__(self) -> None:
        """创建时自动强校验，非法入参直接拦截"""
        # 候选ID不能包含路径符号，防止目录穿越
        if not self.candidate_id or any(token in ("/", "\\", "..") for token in self.candidate_id):
            raise ValueError("candidate_id must be a safe identifier")
        # 数值参数必须合法非负/正数
        if self.generation_index < 0 or self.max_repairs < 0 or self.timeout_seconds <= 0:
            raise ValueError("candidate numeric limits are invalid")
        # 策略与场景必须绑定同一个scenario_id，禁止跨场景混用
        if self.strategy.scenario_id != self.scenario.scenario_id:
            raise ValueError("candidate strategy and scenario must match")
        # 必须开放至少一个可修改字段，否则无法修复
        if not self.allowed_strategy_paths:
            raise ValueError("allowed_strategy_paths must not be empty")

    def to_dict(self) -> dict:
        """序列化字典，用于写入JSON存档"""
        return {
            "candidate_id": self.candidate_id,
            "generation_index": self.generation_index,
            "scenario_id": self.scenario.scenario_id,
            "strategy": self.strategy.to_dict(),
            "runtime": self.runtime.to_dict(),
            "max_repairs": self.max_repairs,
            "timeout_seconds": self.timeout_seconds,
            "allowed_strategy_paths": list(self.allowed_strategy_paths),
            "reuse_existing_artifacts": self.reuse_existing_artifacts,
            "official_score_only": self.official_score_only,
        }


# 状态流转事件契约，每一次状态切换生成一条事件记录
@dataclass(frozen=True, slots=True)
class CandidateStateEvent:
    previous_state: CandidateState | None # 切换前状态
    new_state: CandidateState             # 切换后状态
    reason: str                           # 流转文字说明
    attempt_index: int                    # 当前仿真/修复轮次
    artifact_refs: tuple[str, ...] = ()   # 关联产物文件路径
    error_summary: str | None = None      # 流转附带错误信息（失败场景）

    def to_dict(self) -> dict:
        """序列化用于trajectory.jsonl轨迹日志"""
        value = asdict(self)
        # 枚举转字符串存储
        value["previous_state"] = self.previous_state.value if self.previous_state else None
        value["new_state"] = self.new_state.value
        return value


# 整条候选流程最终输出结果契约
@dataclass(frozen=True, slots=True)
class CandidateOutcome:
    candidate_id: str                              # 候选ID
    generation_index: int                          # 代数
    strategy_spec: StrategySpec                    # 迭代后最终策略
    success: bool                                  # 流程是否完整跑完（COMPLETED）
    executable: bool                              # Lua能否正常运行
    semantic_valid: bool                          # 仿真语义是否合规
    scoreable: bool                               # 是否产出有效得分
    original_lua_path: Path | None                # 第一轮原始Lua路径
    final_lua_path: Path | None                   # 最后一轮Lua路径
    repair_count: int                              # 总修复次数
    execution_attempts: int                        # CMO仿真总执行轮次
    repair_invocations: int                        # 调用修复Agent总次数
    repairs_applied: int                           # 实际生效补丁数量
    combat_metrics: object | None                  # Phase3作战指标
    reward_breakdown: object | None                # 得分明细
    failed_stage: CandidateState | None            # 失败停在哪一步
    failure_reason: CandidateFailureReason        # 标准化失败原因
    final_state: CandidateState                    # 流程最终状态
    candidate_dir: Path                            # 沙箱目录
    trajectory_path: Path                          # 轨迹日志文件路径
    artifact_provenance: str = "formal_renderer"  # Phase 6: only formal output can rank
    scenario_reset: object | None = None
    execution_success: bool | None = None
    native_score: int | None = None
    score_source: str | None = None
    rank: int | None = None
    execution_fidelity: str = "unknown"


# 受约束状态机：只允许白名单内状态跳转，杜绝非法流转
#约束效果  禁止 LLM 修改航路数组、武器 ID、攻击条目 ID 等核心结构，只能微调数值类叶子标量。
class CandidateStateMachine:
    # 合法跳转白名单：key=当前状态，value=允许跳转的下一状态集合
    _ALLOWED = {
        CandidateState.CREATED: {CandidateState.STRATEGY_VALIDATED, CandidateState.FAILED},
        CandidateState.STRATEGY_VALIDATED: {CandidateState.PLAN_COMPILED, CandidateState.FAILED},
        CandidateState.PLAN_COMPILED: {CandidateState.LUA_RENDERED, CandidateState.FAILED},
        CandidateState.LUA_RENDERED: {CandidateState.CMO_EXECUTED, CandidateState.FAILED},
        CandidateState.CMO_EXECUTED: {CandidateState.REPAIRED, CandidateState.SEMANTIC_VALIDATED, CandidateState.FAILED},
        CandidateState.REPAIRED: {CandidateState.STRATEGY_VALIDATED, CandidateState.PLAN_COMPILED, CandidateState.FAILED},
        CandidateState.SEMANTIC_VALIDATED: {CandidateState.SCORED, CandidateState.FAILED},
        CandidateState.SCORED: {CandidateState.COMPLETED, CandidateState.FAILED},
        CandidateState.COMPLETED: set(), # 终点，不能再跳转
        CandidateState.FAILED: set(),    # 失败终点，不能再跳转
    }

    def __init__(self) -> None:
        self.state = CandidateState.CREATED # 初始状态：刚创建
        self.events = [CandidateStateEvent(None, self.state, "created", 0)] # 初始化第一条创建事件

    def transition(self, state: CandidateState, *, reason: str, attempt: int, refs: tuple[str, ...] = (), error: str | None = None) -> None:
        """执行状态跳转，非法跳转直接抛异常阻断流程"""
        # 校验是否在允许的跳转列表内
        if state not in self._ALLOWED[self.state]:
            raise ValueError(f"illegal candidate transition {self.state.value}->{state.value}")
        previous = self.state
        # 更新当前状态
        self.state = state
        # 生成一条流转事件存入事件列表
        self.events.append(CandidateStateEvent(previous, state, reason, attempt, refs, error))
