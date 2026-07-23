"""Deterministic application of the single registered Phase 5 runtime patch.
系统现在只允许一种底层修复方案：目标探测失败时，再多尝试搜一次目标。
它专门修改执行计划里那条「搜寻目标」的指令参数。
"""
from __future__ import annotations

from dataclasses import dataclass

# 运行时补丁提案、补丁白名单注册表
from cmo_lua_agent.agents.repair_models import RuntimePatchProposal, RuntimePatchRegistry
# 执行计划、单条操作、渲染后Lua、哈希工具
from cmo_lua_agent.generation.runtime_models import ExecutionPlan, Operation, RenderedLua


# 已应用运行时补丁记录实体：记录修改前后哈希，用于溯源清单
@dataclass(frozen=True, slots=True)
class AppliedRuntimePatch:
    patch_id: str               # 补丁类型标识
    operation_id: str           # 被修改的原语操作ID
    old_plan_checksum: str      # 修改前执行计划哈希
    new_plan_checksum: str      # 修改后执行计划哈希
    old_lua_checksum: str       # 修改前Lua脚本哈希


# 运行时补丁应用工具类
class RuntimePatchApplier:
    # 系统唯一允许的运行时补丁类型
    PATCH_KIND = "retry_missing_contact_once"

    def __init__(self, registry: RuntimePatchRegistry | None = None) -> None:
        # 注入补丁白名单注册表，无则使用默认注册表
        self._registry = registry or RuntimePatchRegistry.default()

    def apply(
        self,
        *,
        candidate_id: str,
        proposal: RuntimePatchProposal,
        plan: ExecutionPlan,
        rendered: RenderedLua,
        applied_keys: set[tuple[str, str]]
    ) -> tuple[ExecutionPlan, AppliedRuntimePatch]:
        """
        校验并执行探测重试补丁，返回修改后的全新执行计划 + 补丁应用记录
        :param candidate_id: 当前候选唯一ID
        :param proposal: LLM生成的运行时补丁提案
        :param plan: 原始未修改执行计划
        :param rendered: 原始渲染完成Lua
        :param applied_keys: 全局已打补丁集合，防止同一操作重复打补丁
        :return: (修改后新执行计划, 补丁变更记录)
        """
        # 第一层校验：注册表白名单校验补丁类型、目标原语是否合法
        self._registry.validate(proposal=proposal, plan=plan)

        # 第二层校验：仅允许探测重试补丁，且该补丁无自定义入参
        if proposal.patch_kind != self.PATCH_KIND or proposal.parameters:
            raise ValueError("runtime patch parameters are invalid")

        # 第三层校验：补丁绑定Lua哈希和当前Lua匹配，防止跨版本乱打补丁
        if proposal.expected_lua_checksum != rendered.lua_checksum:
            raise ValueError("runtime patch Lua checksum mismatch")

        # 第四层校验：目标操作ID存在于Lua源码映射表，确保能定位对应代码
        if proposal.operation_id not in rendered.source_map:
            raise ValueError("runtime patch source map mismatch")

        # 构造唯一标识：候选ID+操作ID，用于防重复打补丁
        key = (candidate_id, proposal.operation_id)
        if key in applied_keys:
            raise ValueError("runtime_patch_already_applied")

        # 遍历执行计划所有操作，复制未修改条目
        patched: list[Operation] = []
        for operation in plan.operations:
            # 非目标操作直接原样保留
            if operation.operation_id != proposal.operation_id:
                patched.append(operation)
                continue
            # 校验目标原语必须是目标探测准备操作
            if operation.primitive_type != "prepare_target_contact":
                raise ValueError("runtime patch operation is not prepare_target_contact")
            # 拷贝原操作参数，新增探测重试次数=1
            parameters = dict(operation.parameters)
            parameters["contact_retry_attempts"] = 1
            # 构造修改后的Operation对象
            patched.append(Operation(
                operation.operation_id,
                operation.primitive_type,
                parameters,
                operation.depends_on,
                operation.source_strategy_path
            ))
        # 使用修改后的操作列表生成全新执行计划（原plan不可变，不原地修改）
        new_plan = ExecutionPlan(
            plan.plan_schema_version,
            plan.compiler_version,
            plan.scenario_id,
            plan.runtime_id,
            plan.runtime_version,
            tuple(patched)
        )
        # 标记该操作已打过补丁，禁止再次应用
        applied_keys.add(key)
        # 返回新计划与补丁变更快照
        return new_plan, AppliedRuntimePatch(
            self.PATCH_KIND,
            proposal.operation_id,
            plan.checksum,
            new_plan.checksum,
            rendered.lua_checksum
        )

    @staticmethod
    def manifest_entry(applied: AppliedRuntimePatch, new_lua_checksum: str, source_error: str) -> dict[str, str]:
        """生成补丁溯源清单条目，写入generation_manifest用于审计"""
        return {
            "patch_id": applied.patch_id,
            "operation_id": applied.operation_id,
            "old_plan_checksum": applied.old_plan_checksum,
            "new_plan_checksum": applied.new_plan_checksum,
            "old_lua_checksum": applied.old_lua_checksum,
            "new_lua_checksum": new_lua_checksum,
            "source_error": source_error
        }
