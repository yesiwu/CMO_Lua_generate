"""
单一兵棋场景下Phase 9推演任务的不可变契约与核心领域模型定义
所有带哈希校验的契约对象，一旦任务启动，关键约束不允许随意篡改，保障实验确定性与可复现性
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from hashlib import sha256
import json
from typing import Any


def _checksum(value: object) -> str:
    """标准化哈希计算工具，用于契约、快照、候选集合完整性校验"""
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(payload.encode("utf-8")).hexdigest()


class CampaignExecutionMode(str, Enum):
    """推演任务运行模式"""
    FAKE_FIXTURE = "fake_fixture"    # 测试模式：虚拟仿真，不启动真实CMO
    PRODUCTION_CMO = "production_cmo"# 生产模式：调用真实CMO兵棋推演


class CampaignStatus(str, Enum):
    """推演任务全局状态机"""
    CREATED = "created"                # 任务已创建，尚未开始迭代
    RUNNING = "running"                # 正常迭代运行中
    PAUSED = "paused"                  # 任务暂停，可断点恢复
    STOPPING = "stopping"              # 收到停止指令，正在收尾
    COMPLETED = "completed"            # 全部迭代正常结束
    FAILED = "failed"                  # 发生致命错误，任务失败终止
    CANCELLED = "cancelled"            # 人工提前终止，未完成迭代
    AWAITING_APPROVAL = "awaiting_approval" # 等待人工审批，无法启动世代执行


class OperationKind(str, Enum):
    """操作账本中各类操作类型"""
    STRATEGY_PROPOSAL = "strategy_proposal" # 策略生成（构建世代预览）
    LUA_GENERATION = "lua_generation"       # Lua战术脚本生成
    LUA_REPAIR = "lua_repair"               # Lua脚本错误修复
    CMO = "cmo"                             # 单次CMO兵棋仿真尝试
    PHASE6 = "phase6"                       # 完整一代Phase6推演执行（世代顶层操作）
    PHASE7 = "phase7"
    PHASE8 = "phase8"


class OperationStatus(str, Enum):
    """操作生命周期状态（operation-ledger.jsonl使用）"""
    PREPARED = "prepared"      # 已登记，等待授权
    AUTHORIZED = "authorized"  # 已获得权限，可以执行
    STARTED = "started"        # 正在运行
    COMPLETED = "completed"   # 正常完成
    FAILED = "failed"          # 执行失败
    UNKNOWN = "unknown"        # 进程失联，需要事后对账


class StopReason(str, Enum):
    """推演任务终止原因枚举"""
    NONE = "none"
    MAX_GENERATIONS_REACHED = "max_generations_reached"                # 达到最大世代上限
    MAX_CMO_RUNS_REACHED = "max_cmo_runs_reached"                      # CMO仿真总次数耗尽
    FAILURE_BUDGET_EXHAUSTED = "failure_budget_exhausted"              # 允许的失败次数耗尽
    NO_IMPROVEMENT_PATIENCE_EXHAUSTED = "no_improvement_patience_exhausted" # 连续多代无分数提升
    NO_ELIGIBLE_CANDIDATES = "no_eligible_candidates"                  # 世代无合法可用候选策略
    REPEATED_STRATEGY_SPACE = "repeated_strategy_space"                # 策略持续重复，收敛停滞
    REQUIRE_HUMAN_REVIEW = "require_human_review"                      # 需要人工介入审查
    MANUAL_STOP_REQUESTED = "manual_stop_requested"                    # 人工下发停止指令
    CONTRACT_CHANGED = "contract_changed"                              # 核心契约发生变更
    CMO_LOCK_UNAVAILABLE = "cmo_lock_unavailable"                      # 无法抢占CMO实例独占锁


class ControlAction(str, Enum):
    """外部运维控制指令类型"""
    PAUSE = "pause"    # 暂停推演
    STOP = "stop"      # 终止推演


@dataclass(frozen=True, slots=True)
class CampaignBudget:
    """算力与时间预算约束，属于推演契约组成部分，不可动态修改"""
    max_generations: int                     # 最大迭代世代总数
    max_cmo_runs: int                        # 全局最大CMO仿真总次数
    max_cmo_attempts_per_candidate: int       # 单条候选策略最大仿真尝试次数
    max_cmo_attempts_for_baseline: int       # 基线策略最大仿真尝试次数
    max_repair_attempts_per_candidate: int   # 单条策略Lua修复最大重试次数
    max_failed_runs: int                     # 允许的最大仿真失败次数
    max_llm_total_calls: int                 # LLM全局总调用上限
    max_strategy_proposal_calls: int         # 策略生成LLM调用上限
    max_lua_generation_calls: int            # Lua脚本生成调用上限
    max_lua_repair_calls: int                # Lua脚本修复调用上限
    max_comparative_learning_calls: int      # 对比学习调用上限
    max_skill_author_calls: int              # 战术技能编排调用上限
    max_wall_clock_seconds: int              # 推演全局总运行时长上限
    per_generation_timeout_seconds: int      # 单个世代执行超时时间
    per_candidate_timeout_seconds: int       # 单条候选仿真超时时间

    def __post_init__(self) -> None:
        """对象构造后校验参数合法性"""
        if any(value < 0 for value in asdict(self).values()):
            raise ValueError("campaign budget values must be non-negative")
        if not all((self.max_generations, self.max_cmo_runs, self.max_wall_clock_seconds,
                    self.per_generation_timeout_seconds, self.per_candidate_timeout_seconds)):
            raise ValueError("campaign budget requires positive generation, CMO, and timeout limits")
        if not self.max_cmo_attempts_per_candidate or not self.max_cmo_attempts_for_baseline:
            raise ValueError("CMO attempt limits must be positive")

    @property
    def required_cmo_attempts_per_generation(self) -> int:
        """单个世代理论最少需要的CMO仿真次数：基线 + 4条候选"""
        return self.max_cmo_attempts_for_baseline + 4 * self.max_cmo_attempts_per_candidate

    def can_reserve_generation(self, *, available_cmo_runs: int) -> bool:
        """判断剩余仿真次数是否足够支撑完整一代运行，防止算力中途枯竭"""
        return available_cmo_runs >= self.required_cmo_attempts_per_generation

    @property
    def checksum(self) -> str:
        """预算哈希，用于契约完整性校验"""
        return _checksum(asdict(self))


@dataclass(frozen=True, slots=True)
class EvolutionCampaignSpec:
    """推演任务顶层契约（核心契约）
    prepare_evolution_campaign传入的campaign对象最终转换为此模型，创建任务后固化
    """
    campaign_id: str                          # 推演任务唯一标识
    scenario_id: str                          # 兵棋场景ID
    scenario_ref: str                         # 场景资源引用路径
    scenario_checksum: str                    # 场景Bundle完整性哈希
    initial_strategy_ref: str                 # 初始基线策略引用
    runtime_contract_checksum: str            # 运行时契约哈希
    renderer_contract_checksum: str           # Lua渲染契约哈希
    score_contract_checksum: str              # 评分流水线契约哈希
    semantic_contract_checksum: str           # 策略语义校验契约哈希
    code_revision: str                        # 代码版本标记
    allowed_strategy_paths: tuple[str, ...]   # 允许加载的历史策略路径
    generation_objective: str                 # 本次演化优化目标描述
    budget: CampaignBudget                    # 全套算力预算约束
    execution_mode: CampaignExecutionMode     # 运行模式：测试/生产兵棋
    candidates_per_generation: int = 4        # 每世代固定4条候选策略（硬约束）
    no_improvement_patience: int = 2          # 连续多少代无提升则终止任务
    minimum_improvement_delta: int = 1        # 判断有效进化所需最小分数提升阈值

    def __post_init__(self) -> None:
        """构造时强校验所有必填字段与业务规则"""
        required = (self.campaign_id, self.scenario_id, self.scenario_ref, self.scenario_checksum,
                    self.initial_strategy_ref, self.runtime_contract_checksum, self.renderer_contract_checksum,
                    self.score_contract_checksum, self.semantic_contract_checksum, self.code_revision,
                    self.generation_objective)
        if any(not isinstance(value, str) or not value.strip() for value in required):
            raise ValueError("campaign spec requires non-empty identifiers and contracts")
        if any(token in self.campaign_id for token in ("/", "\\", "..")):
            raise ValueError("campaign_id must be a safe identifier")
        if self.candidates_per_generation != 4:
            raise ValueError("candidates_per_generation must equal 4")
        if not self.allowed_strategy_paths or not all(path.startswith("/") for path in self.allowed_strategy_paths):
            raise ValueError("allowed_strategy_paths must contain JSON Pointer paths")
        if self.no_improvement_patience < 1:
            raise ValueError("no_improvement_patience must be positive")

    @property
    def contract_checksum(self) -> str:
        """核心契约哈希：场景、各类子契约、代码版本汇总，审批单绑定此哈希用于防篡改校验"""
        return _checksum({
            "scenario_checksum": self.scenario_checksum,
            "runtime_contract_checksum": self.runtime_contract_checksum,
            "renderer_contract_checksum": self.renderer_contract_checksum,
            "score_contract_checksum": self.score_contract_checksum,
            "semantic_contract_checksum": self.semantic_contract_checksum,
            "code_revision": self.code_revision,
        })

    @property
    def checksum(self) -> str:
        """完整Spec对象哈希，包含预算等全部参数"""
        value = asdict(self)
        value["execution_mode"] = self.execution_mode.value
        return _checksum(value)


@dataclass(frozen=True, slots=True)
class CampaignState:
    """推演任务全局运行状态，持久化至campaign-state.json
    记录迭代进度、最优策略、算力消耗、终止相关计数器
    """
    campaign_id: str
    status: CampaignStatus = CampaignStatus.CREATED
    current_generation: int = 0                 # 当前待执行世代编号
    completed_generations: int = 0              # 已完成世代总数
    cmo_run_count: int = 0                      # 累计CMO仿真运行次数
    failed_run_count: int = 0                   # 累计失败仿真次数
    llm_call_counts: dict[str, int] = field(default_factory=dict) # 各类LLM调用统计
    best_champion_ref: str | None = None        # 全局最优策略引用
    best_official_score: int | None = None      # 全局最优分数
    no_improvement_count: int = 0              # 连续无有效提升世代计数
    stop_reason: StopReason = StopReason.NONE   # 终止原因
    budget_revision: int = 0                    # 预算版本号（用于匹配审批单）


@dataclass(frozen=True, slots=True)
class OperationRecord:
    """操作账本operation-ledger.jsonl单条记录模型，所有关键操作永久留存，用于对账审计"""
    operation_id: str
    generation_index: int
    kind: OperationKind
    input_checksum: str          # 本次操作输入素材哈希
    status: OperationStatus
    output_ref: str | None = None# 产物文件路径引用
    error: str | None = None
    updated_at: str | None = None# 状态最后更新UTC时间


@dataclass(frozen=True, slots=True)
class ControlRequest:
    """运维控制指令（暂停/停止）持久化模型"""
    action: ControlAction
    requested_at: str
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class GenerationPreview:
    """世代预览快照，preview_generation工具产出
    固化当前世代候选策略集合、知识快照指纹，人工审批前必须先生成预览
    """
    campaign_id: str
    generation_index: int
    preview_revision: int               # 预览版本号，重生成预览自动递增
    snapshot_checksum: str              # 绑定知识快照哈希
    candidate_set_checksum: str         # 4条候选策略集合哈希
    strategy_diffs: tuple[dict[str, Any], ...] # 策略之间差异对比信息
    proposal_operation_id: str         # 生成预览对应的策略生成操作ID
    checksum: str                       # 预览整体哈希
    baseline_checksum: str = ""
    frozen_candidate_set_ref: str = ""
    strategy_diff_ref: str = ""


@dataclass(frozen=True, slots=True)
class GenerationApproval:
    """世代仿真审批单，内层核心许可凭证
    绑定预览、契约哈希；Worker启动CMO仿真时由CampaignPermissionBroker校验
    """
    approval_id: str
    campaign_id: str
    generation_index: int
    preview_revision: int
    snapshot_checksum: str
    candidate_set_checksum: str
    contract_checksum: str
    budget_revision: int
    authorization_mode: str
    max_cmo_attempts: int               # 本审批单允许的最大CMO尝试次数
    expires_at: str                     # 审批单过期时间
    receipt_summary: str                # 关联上层对话权限凭证ID
    valid: bool = True                  # 是否有效，预览重生成后置为False


@dataclass(frozen=True, slots=True)
class WorkerState:
    """世代Worker持久化状态，记录后台世代执行线程运行信息"""
    operation_id: str
    campaign_id: str
    generation_index: int
    status: str                         # running / completed / paused / failed …
    worker_id: str
    result: dict[str, Any] = field(default_factory=dict) # 世代执行结果
    error: str | None = None


@dataclass(frozen=True, slots=True)
class CandidateScore:
    """单条候选策略仿真完成后的打分结果载体
    送入ChampionSelectionPolicy进行冠军筛选
    """
    candidate_id: str
    official_score: int | None                 # 综合官方得分
    execution_success: bool                    # 仿真进程正常结束
    scoreable: bool                            # 具备打分资格
    semantic_valid: bool                       # 策略语义校验通过
    artifact_provenance: str                   # 产物来源标记
    score_source: str | None                   # 分数来源路径标记
    execution_fidelity: str                    # 推演可信度标记
    own_loss_count: int = 0                    # 我方损失单位数量
    high_value_enemy_damage: int = 0           # 击毁敌方高价值目标数量
    unexpected_weapon_activity_count: int = 0  # 异常武器使用次数
    weapon_expenditure: int = 0                # 弹药消耗总量

    @property
    def eligible(self) -> bool:
        """是否拥有参与冠军竞争的完整参选资格（多重硬条件同时满足）"""
        return (
            self.execution_success and self.scoreable and self.semantic_valid
            and self.artifact_provenance == "formal_renderer"
            and self.score_source == "execution-summary.json#/official_score/final"
            and self.execution_fidelity == "verified" and self.official_score is not None
        )


@dataclass(frozen=True, slots=True)
class Phase6GenerationArtifact:
    """适配器接收Phase6推演结果的标准化载体"""
    rolling_baseline: CandidateScore       # 基线策略打分
    candidates: tuple[CandidateScore, ...] # 当前世代全部候选策略打分
    optimization_dir: str                  # 推演产物根目录
    cmo_attempts: int                      # 本世代总CMO仿真尝试次数
    failed_cmo_attempts: int = 0           # 失败仿真次数


@dataclass(frozen=True, slots=True)
class ChampionDecision:
    """世代冠军筛选输出结果"""
    best_candidate_id: str | None       # 本世代内部最优候选ID
    selected_champion_id: str           # 确定作为下一代基线的策略ID
    selected_score: int                 # 下一代基线对应的分数
    improved: bool                      # 是否产生有效进化（分数提升达到阈值）
    exclusion_reasons: dict[str, str] = field(default_factory=dict) # 不合格候选淘汰原因


@dataclass(frozen=True, slots=True)
class StopDecision:
    """终止判定决策载体，判断是否满足推演停止条件"""
    should_stop: bool
    reason: StopReason
    details: str = ""
