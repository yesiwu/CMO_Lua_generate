"""Phase 4：一次结构化诊断，不执行、不重试、不生成自由 Lua。
Lua修复Agent核心实现，仅根据错误类型调用LLM生成**结构化受限补丁**，禁止自由Lua代码；
分「策略补丁」「运行时白名单补丁」两类合法修复，非法/底层错误直接返回诊断报告，无自主执行/重试逻辑。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# 修复分类、补丁注册表、缺陷报告等修复基础模型
from cmo_lua_agent.agents.repair_models import RepairKind, RepairRoute, RuntimeDefectReport, RuntimePatchProposal, RuntimePatchRegistry
# 策略安全补丁模型（仅允许修改指定叶子标量）
from cmo_lua_agent.agents.strategy_change_guard import RestrictedStrategyPatch
# LLM结构化输出客户端，强制返回固定JSON，禁止自由文本
from cmo_lua_agent.agents.structured_strategy_client import StructuredJsonClient, StructuredStrategyClient
# 场景、作战策略契约
from cmo_lua_agent.contract.strategy_models import ScenarioDefinition, StrategySpec
# CMO仿真统一错误对象
from cmo_lua_agent.execution.models import CmoError
# Phase2执行计划、运行时配置模型
from cmo_lua_agent.generation.runtime_models import ExecutionPlan, LuaRuntimeProfile


# 修复入参：单次错误诊断所需全部上下文
@dataclass(frozen=True, slots=True)
class LuaRepairRequest:
    route: RepairRoute                  # 前置错误分类结果（可修复/不可修复/底层缺陷）
    current_lua: str                    # 当前执行失败的Lua完整文本
    current_lua_checksum: str           # 当前Lua哈希，用于运行时补丁校验
    error: CmoError                     # CMO抛出的完整错误信息
    scenario: ScenarioDefinition        # 固定场景事实（不可修改）
    strategy: StrategySpec              # 当前失败的作战策略
    plan: ExecutionPlan | None          # 策略编译后的执行步骤计划
    generation_manifest: dict[str, Any] # Lua生成全链路溯源清单
    runtime: LuaRuntimeProfile         # 当前运行时版本/能力包
    repair_history_summary: tuple[str, ...] # 历史修复记录，避免重复修复
    related_skills: tuple[str, ...]     # 相关战术经验Skill
    allowed_strategy_paths: tuple[str, ...] = () # 允许修改的策略JSON叶子路径（安全限制）


# 修复统一输出结果：结构化诊断+补丁/缺陷报告
@dataclass(frozen=True, slots=True)
class LuaRepairResult:
    repair_kind: RepairKind                     # 本次修复类型
    diagnosis: str                              # 诊断文字说明
    patch: object | None                        # 补丁对象：RestrictedStrategyPatch列表 / RuntimePatchProposal / RuntimeDefectReport
    change_summary: tuple[str, ...]             # 改动文字摘要
    affected_operations: tuple[str, ...]        # 受影响的执行操作ID
    declared_semantic_impact: str               # 本次修改对战法的影响说明
    verified_changed_paths: tuple[str, ...]     # 校验通过的可修改字段路径
    agent_confidence: float | None              # LLM给出修复置信度 0~1
    retry_eligible: bool                        # 是否允许重新仿真重试
    failure_reason: str | None                  # 修复生成失败原因
    evidence_refs: tuple[str, ...]             # 关联报错证据索引


# Phase4 修复核心Agent：仅生成结构化补丁，不执行Lua、不发起CMO仿真
class LuaRepairAgent:
    """基于受限错误证据提出 Lua 候选修复，不直接写入正式 Campaign 状态。

候选评估链调用它取得结构化修复建议，再由确定性校验和 CMO 重跑决定是否接受；它不修
Python 源码，后者属于 SystemRepairAgent/CodeRepairCoordinator。
    """
    def __init__(self, client: StructuredJsonClient, *, patch_registry: RuntimePatchRegistry | None = None) -> None:
        # 封装LLM结构化输出客户端，强制规范JSON返回
        self._client = StructuredStrategyClient(client)
        # 运行时补丁白名单注册表，校验运行时补丁合法性
        self._registry = patch_registry or RuntimePatchRegistry.default()

    def repair(self, request: LuaRepairRequest) -> LuaRepairResult:
        # 分支1：完全不可修复 / Runtime底层缺陷，直接返回诊断，不调用LLM
        route = request.route
        if route.kind in {RepairKind.NOT_APPLICABLE, RepairKind.RUNTIME_DEFECT_REPORT}:
            # 构造底层缺陷报告，无任何修复补丁
            report = RuntimeDefectReport(route.reason, (request.error.category, request.error.message)) if route.kind is RepairKind.RUNTIME_DEFECT_REPORT else None
            return LuaRepairResult(
                repair_kind=route.kind,
                diagnosis=route.reason,
                patch=report,
                change_summary=(),
                affected_operations=(),
                declared_semantic_impact="not applicable",
                verified_changed_paths=(),
                agent_confidence=None,
                retry_eligible=route.retry_eligible,
                failure_reason=None,
                evidence_refs=(request.error.category,)
            )

        try:
            # 分支2：可修复，调用LLM，强制输出结构化修复JSON
            payload = self._client.complete(
                mode=route.kind.value,
                prompt=(
                    f"error={request.error.to_dict()}\n"
                    f"strategy={request.strategy.to_dict()}\n"
                    "Only return one registered structured proposal."
                )
            )

            # 子分支A：运行时兼容补丁（白名单内原语微调）
            if route.kind is RepairKind.RUNTIME_PATCH_PROPOSAL:
                proposal = RuntimePatchProposal(
                    patch_kind=str(payload["patch_kind"]),
                    operation_id=str(payload["operation_id"]),
                    expected_lua_checksum=request.current_lua_checksum,
                    parameters=dict(payload.get("parameters", {})),
                    evidence_refs=(request.error.category, request.error.message),
                )
                # 注册表校验补丁是否合规（禁止篡改计分、仅允许注册原语）
                self._registry.validate(proposal=proposal, plan=request.plan)
                return LuaRepairResult(
                    repair_kind=route.kind,
                    diagnosis="已登记的运行时补丁提案",
                    patch=proposal,
                    change_summary=(),
                    affected_operations=(proposal.operation_id,),
                    declared_semantic_impact=str(payload.get("declared_semantic_impact", "")),
                    verified_changed_paths=(),
                    agent_confidence=_confidence(payload),
                    retry_eligible=True,
                    failure_reason=None,
                    evidence_refs=proposal.evidence_refs
                )

            # 子分支B：策略补丁，修改StrategySpec允许的标量字段
            patches = _strategy_patches(payload, request.allowed_strategy_paths)
            return LuaRepairResult(
                repair_kind=route.kind,
                diagnosis="受限策略补丁提案",
                patch=patches,
                change_summary=tuple(str(x) for x in payload["change_summary"]),
                affected_operations=(),
                declared_semantic_impact=str(payload.get("declared_semantic_impact", "")),
                verified_changed_paths=(),
                agent_confidence=_confidence(payload),
                retry_eligible=route.retry_eligible,
                failure_reason=None,
                evidence_refs=(request.error.category, request.error.message)
            )

        # LLM输出格式错误、补丁非法统一捕获，标记修复失败
        except (KeyError, TypeError, ValueError) as exc:
            return LuaRepairResult(
                repair_kind=RepairKind.RUNTIME_DEFECT_REPORT,
                diagnosis="repair proposal rejected",
                patch=RuntimeDefectReport(str(exc), (request.error.category,)),
                change_summary=(),
                affected_operations=(),
                declared_semantic_impact="",
                verified_changed_paths=(),
                agent_confidence=None,
                retry_eligible=False,
                failure_reason=str(exc),
                evidence_refs=(request.error.category,)
            )


# 工具：提取并校验LLM返回的置信度（0~1有效，否则返回None）
def _confidence(payload: dict[str, Any]) -> float | None:
    value = payload.get("agent_confidence")
    if isinstance(value, (int, float)) and 0 <= value <= 1:
        return float(value)
    return None


# 工具：解析并校验策略补丁JSON，仅允许允许路径的标量替换
def _strategy_patches(
    payload: dict[str, Any], allowed_paths: tuple[str, ...]
) -> tuple[RestrictedStrategyPatch, ...]:
    # 校验LLM返回顶层字段必须固定，不能多/少
    expected = {"patches", "change_summary", "declared_semantic_impact", "agent_confidence"}
    if set(payload) - expected or not isinstance(payload.get("patches"), list):
        raise ValueError("strategy repair response has invalid schema")

    patches: list[RestrictedStrategyPatch] = []
    for item in payload["patches"]:
        # 单条补丁字段严格校验
        if not isinstance(item, dict) or set(item) != {"op", "path", "expected_object_id", "value"}:
            raise ValueError("strategy repair patch has invalid schema")
        patch = RestrictedStrategyPatch(**item)
        # 仅允许替换叶子标量，且路径在白名单内
        if patch.op != "replace" or patch.path not in allowed_paths:
            raise ValueError("strategy repair patch is not an allowed leaf replace")
        patches.append(patch)
    return tuple(patches)
