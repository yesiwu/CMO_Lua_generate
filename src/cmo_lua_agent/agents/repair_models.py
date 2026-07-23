"""Phase 4 单次修复的受限结果模型与 Runtime Patch 注册表
作用：对CMO仿真产生的各类错误自动分类路由，区分「可改策略修复」「运行时兼容补丁修复」「底层引擎缺陷」「完全不可修复」四大类；
同时提供运行时补丁注册表，严格限制允许修改的原语操作，禁止篡改计分逻辑，保证修复流程受控、不破坏确定性主链路。


以下有点问题，不应该是llm来修改吗？怎么是确定性runtime代码修改？这样的话我系统还运不运行了？：
问题1
    RUNTIME_DEFECT_REPORT
    确定性 Lua 渲染器 / 原语代码自身 bug（语法错误、内部逻辑异常）；
    不能通过改策略 / 临时补丁修复，需要开发修改底层 Runtime 代码，直接上报缺陷，不重试。
问题2
    规则硬编码，完全不依赖 LLM 判断，保证分类结果稳定可复现
    真的能够分类而不报错吗？难道只有这四种分类吗?
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

# CMO仿真统一错误模型
from cmo_lua_agent.execution.models import CmoError
# Phase2执行计划模型（每条操作原语载体）
from cmo_lua_agent.generation.runtime_models import ExecutionPlan


# 错误修复四大分类枚举
class RepairKind(str, Enum):
    STRATEGY_PATCH = "strategy_patch"                # 修复方案：修改StrategySpec策略参数
    RUNTIME_PATCH_PROPOSAL = "runtime_patch_proposal"# 修复方案：运行时兼容临时补丁
    RUNTIME_DEFECT_REPORT = "runtime_defect_report"  # 问题：Runtime/渲染器底层缺陷，无法靠用户策略修复
    NOT_APPLICABLE = "not_applicable"               # 完全不可修复，基础设施/能力缺口类错误


# 修复路由结果载体：标记错误类型、原因、是否允许重试
@dataclass(frozen=True, slots=True)
class RepairRoute:
    kind: RepairKind       # 修复分类
    reason: str            # 分类说明文本
    retry_eligible: bool   # 是否允许重试本轮实验

    @classmethod
    def runtime_patch_eligible(cls) -> "RepairRoute":
        """可使用运行时兼容补丁修复，允许重试"""
        return cls(RepairKind.RUNTIME_PATCH_PROPOSAL, "registered dynamic compatibility may apply", True)

    @classmethod
    def strategy_patch_eligible(cls, reason: str) -> "RepairRoute":
        """修改策略参数即可修复，允许重试"""
        return cls(RepairKind.STRATEGY_PATCH, reason, True)

    @classmethod
    def runtime_defect(cls, reason: str) -> "RepairRoute":
        """底层Runtime代码缺陷，不能靠改策略修复，禁止重试"""
        return cls(RepairKind.RUNTIME_DEFECT_REPORT, reason, False)

    @classmethod
    def not_applicable(cls, reason: str) -> "RepairRoute":
        """完全不可修复的致命错误，禁止重试"""
        return cls(RepairKind.NOT_APPLICABLE, reason, False)


# 错误分类路由核心类：纯前置判断，不执行修复，只输出修复方案建议
class RepairErrorRouter:
    """在调用任何LLM修复Agent之前，先对仿真错误做可信分类。
    本路由仅提供修复建议，最终重试/修复决策权属于Phase5候选流水线。
    """
    # 定义完全不可修复的错误大类
    _NOT_APPLICABLE = {
        "capability_gap",              # 当前Runtime不支持该战法（无对应原语）
        "process_timeout",             # CMO进程超时
        "process_start_error",         # CMO启动失败
        "infrastructure_error",        # 底层基础设施异常
        "configuration_restore_failed",# 仿真环境恢复失败
        "result_integrity_failed",     # 仿真数据冲突、计分不一致
    }

    def route(self, error: CmoError) -> RepairRoute:
        category = error.category.lower()
        message = error.message.lower()

        # 1. 匹配完全不可修复错误
        if category in self._NOT_APPLICABLE:
            return RepairRoute.not_applicable(f"{category} is not repairable by an agent")

        # 2. Lua语法错误 = Runtime底层缺陷（渲染器产出非法代码）
        if category == "lua_syntax_error":
            return RepairRoute.runtime_defect("trusted renderer produced Lua syntax error")

        # 3. 日志包含primitive/runtime/计分相关关键词 = Runtime内部bug
        if any(token in message for token in ("primitive", "renderer", "runtime helper", "score registration")):
            return RepairRoute.runtime_defect("runtime implementation defect")

        # 4. 运行时兼容类问题 → 可打Runtime临时补丁修复
        if "runtime compatibility" in message:
            return RepairRoute.runtime_patch_eligible()

        # 5. 策略参数类报错（航路、射程、延时、失联、起飞失败）→ 修改StrategySpec即可修复
        if category in {"strategy_validation_error", "lua_runtime_error"} and any(
            token in message
            for token in ("route", "range", "delay", "timeout", "contact unavailable", "launch")
        ):
            return RepairRoute.strategy_patch_eligible("existing StrategySpec parameters may resolve the error")

        # 其余未知错误统一判定为底层Runtime问题
        return RepairRoute.runtime_defect("error is not safely repairable by the candidate")


# 运行时兼容补丁提案模型：描述要修改哪条执行操作、改哪些参数
@dataclass(frozen=True, slots=True)
class RuntimePatchProposal:
    patch_kind: str               # 补丁类型（注册表内注册标识）
    operation_id: str             # 目标ExecutionPlan操作ID
    expected_lua_checksum: str    # 补丁适用的Lua基线哈希（保证确定性）
    parameters: dict[str, Any]   # 需要调整的参数键值
    evidence_refs: tuple[str, ...]# 关联报错证据文件路径


# Runtime底层缺陷报告：用于上报渲染器/原语代码bug，不做修复
@dataclass(frozen=True, slots=True)
class RuntimeDefectReport:
    diagnosis: str               # 缺陷诊断描述
    evidence_refs: tuple[str, ...]# 报错证据索引


# Runtime补丁注册表：白名单管控，只允许预设类型、预设原语打补丁
class RuntimePatchRegistry:
    def __init__(self, allowed: dict[str, tuple[str, ...]] | None = None) -> None:
        # key：补丁类型；value：该补丁允许作用的primitive原语列表
        self._allowed = allowed or {"retry_missing_contact_once": ("prepare_target_contact",)}

    @classmethod
    def default(cls) -> "RuntimePatchRegistry":
        # 默认仅开放「重新探测目标contact」这一类补丁
        return cls()

    def validate(self, *, proposal: RuntimePatchProposal, plan: ExecutionPlan | None) -> None:
        """校验补丁是否合法，非法直接抛异常，禁止执行"""
        # 1 补丁类型未注册
        if proposal.patch_kind not in self._allowed:
            raise ValueError("runtime patch kind is not registered")
        # 2 无执行计划无法定位操作
        if plan is None:
            raise ValueError("runtime patch requires an execution plan")
        # 3 执行计划中不存在目标operation_id
        operation = next((item for item in plan.operations if item.operation_id == proposal.operation_id), None)
        if operation is None:
            raise ValueError("runtime patch operation does not exist")
        # 4 该补丁不允许作用于当前原语类型
        if operation.primitive_type not in self._allowed[proposal.patch_kind]:
            raise ValueError("runtime patch does not apply to operation primitive")
        # 5 禁止修改计分相关系统操作，保护Phase3计分确定性
        if proposal.operation_id == "system.native_score":
            raise ValueError("runtime patch cannot touch scoring instrumentation")
