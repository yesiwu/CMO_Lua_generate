"""Phase 9 推演任务控制专用的六项受限对话工具集合

世代 = 一轮完整迭代周期
流程标准顺序：
    基于上一代最优策略，LLM 生成一批候选战术方案（多条 Lua 作战脚本）
    预览（preview）：展示候选策略、策略差异，人工审核
    启动仿真：把多条策略送入 CMO 兵棋进行对抗推演
    收集所有推演分数，排序，选出表现最好的策略（冠军策略）
    基于冠军策略变异、重组，生成下一代候选方案
"""

from __future__ import annotations

import json
from typing import Any

from cmo_lua_agent.evolution.control_plane import EvolutionCampaignService
from cmo_lua_agent.tools.tool_base.base import BaseTool, ToolResult
from cmo_lua_agent.tools.tool_base.context import ToolContext


class _CampaignTool(BaseTool):
    """推演任务工具基类，统一归属 campaign 工具集"""
    toolset = "campaign"

    def __init__(self, *, service: EvolutionCampaignService) -> None:
        # 注入推演演化核心服务
        self._service = service

    @staticmethod
    def _result(value: object, *, is_error: bool = False) -> ToolResult:
        """统一封装工具返回结果，序列化为格式化JSON"""
        return ToolResult(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=str), is_error=is_error)

    @staticmethod
    def _progress(context: ToolContext | None, message: str) -> None:
        """向上层推送工具执行进度消息"""
        if context is not None:
            context.progress.tool_started(message)


class PrepareEvolutionCampaignTool(_CampaignTool):
    """创建并初始化演化推演任务"""
    name = "prepare_evolution_campaign"
    description = "校验固化契约与算力预算后，创建持久化的Phase 9推演任务。本工具不会启动CMO仿真。"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "campaign_id": {"type": "string"},
            "input_package_id": {
                "type": "string",
                "enum": ["red_blue_6v4_liaoning_v1"],
            },
            "generation_objective": {"type": "string"},
            "budget": {"type": "object"},
            "minimum_improvement_delta": {"type": "integer"},
            "no_improvement_patience": {"type": "integer", "minimum": 1},
        },
        "required": [
            "campaign_id",
            "input_package_id",
            "generation_objective",
            "budget",
            "minimum_improvement_delta",
            "no_improvement_patience",
        ],
        "additionalProperties": False
    }

    def execute(self, arguments: dict[str, Any], context: ToolContext | None = None) -> ToolResult:
        self._progress(context, "正在准备演化推演任务")
        try:
            resp = self._service.prepare_campaign_request(
                campaign_id=str(arguments["campaign_id"]),
                input_package_id=str(arguments["input_package_id"]),
                generation_objective=str(arguments["generation_objective"]),
                budget=dict(arguments["budget"]),
                minimum_improvement_delta=int(arguments["minimum_improvement_delta"]),
                no_improvement_patience=int(arguments["no_improvement_patience"]),
            )
            return self._result(resp)
        except Exception as exc:
            return self._result({"error_code": "campaign_prepare_failed", "message": str(exc)}, is_error=True)


class PreviewEvolutionGenerationTool(_CampaignTool):
    """生成/读取单世代策略预览快照"""
    name = "preview_evolution_generation"
    description = "生成或读取世代预览快照：包含知识快照、4份候选策略与策略差异对比。不会编译Lua脚本、不启动CMO仿真。"
    input_schema = {
        "type": "object",
        "properties": {
            "campaign_id": {"type": "string", "description": "推演任务唯一标识"},
            "generation_index": {"type": "integer", "minimum": 0, "description": "世代编号"},
            "regenerate_preview": {"type": "boolean", "default": False, "description": "是否强制重新生成预览"}
        },
        "required": ["campaign_id", "generation_index"],
        "additionalProperties": False
    }

    def execute(self, arguments: dict[str, Any], context: ToolContext | None = None) -> ToolResult:
        self._progress(context, "正在生成演化世代预览")
        try:
            preview = self._service.preview_generation(
                campaign_id=arguments["campaign_id"],
                generation_index=arguments["generation_index"],
                regenerate_preview=bool(arguments.get("regenerate_preview", False))
            )
            return self._result({
                "campaign_id": preview.campaign_id,
                "generation_index": preview.generation_index,
                "preview_revision": preview.preview_revision,
                "snapshot_checksum": preview.snapshot_checksum,
                "candidate_set_checksum": preview.candidate_set_checksum,
                "baseline_checksum": preview.baseline_checksum,
                "strategy_diffs": [
                    dict(item) for item in preview.strategy_diffs
                ],
                "proposal_operation_id": preview.proposal_operation_id,
                "checksum": preview.checksum,
            })
        except Exception as exc:
            return self._result({"error_code": "generation_preview_failed", "message": str(exc)}, is_error=True)


class ExecuteEvolutionGenerationTool(_CampaignTool):
    """启动单个世代推演执行器"""
    name = "execute_evolution_generation"
    description = "需人工审批通过后，为已完成预览的世代启动持久化工作节点。立即返回操作ID，不会阻塞对话。"
    input_schema = {
        "type": "object",
        "properties": {
            "campaign_id": {"type": "string", "description": "推演任务唯一标识"},
            "generation_index": {"type": "integer", "minimum": 0, "description": "世代编号"}
        },
        "required": ["campaign_id", "generation_index"],
        "additionalProperties": False
    }
    requires_approval = True  # 调用该工具必须经过人工审批

    def execute(self, arguments: dict[str, Any], context: ToolContext | None = None) -> ToolResult:
        self._progress(context, "正在授权并启动世代工作节点")
        try:
            approval_id = getattr(
                context.approval_receipt if context else None,
                "approval_id",
                None,
            )
            if not approval_id:
                raise ValueError("trusted_generation_approval_required")
            worker = self._service.execute_generation(
                campaign_id=arguments["campaign_id"],
                generation_index=arguments["generation_index"],
                approval_id=approval_id,
            )
            return self._result({
                "campaign_id": worker.campaign_id,
                "generation_index": worker.generation_index,
                "operation_id": worker.operation_id,
                "status": worker.status
            })
        except Exception as exc:
            return self._result({"error_code": "generation_execute_failed", "message": str(exc)}, is_error=True)


class InspectEvolutionCampaignTool(_CampaignTool):
    """查询推演任务整体状态"""
    name = "inspect_evolution_campaign"
    description = "获取推演任务精简状态：任务概况、预算信息、控制指令、契约摘要。"
    input_schema = {
        "type": "object",
        "properties": {
            "campaign_id": {"type": "string", "description": "推演任务唯一标识"}
        },
        "required": ["campaign_id"],
        "additionalProperties": False
    }

    def execute(self, arguments: dict[str, Any], context: ToolContext | None = None) -> ToolResult:
        try:
            data = self._service.inspect_campaign(arguments["campaign_id"])
            return self._result(data)
        except Exception as exc:
            return self._result({"error_code": "campaign_inspect_failed", "message": str(exc)}, is_error=True)


class InspectEvolutionGenerationTool(_CampaignTool):
    """查询单个世代详细信息"""
    name = "inspect_evolution_generation"
    description = "查询指定世代完整信息：预览快照、工作节点状态、推演结果、排行榜与迭代学习状态。"
    input_schema = {
        "type": "object",
        "properties": {
            "campaign_id": {"type": "string", "description": "推演任务唯一标识"},
            "generation_index": {"type": "integer", "minimum": 0, "description": "世代编号"}
        },
        "required": ["campaign_id", "generation_index"],
        "additionalProperties": False
    }

    def execute(self, arguments: dict[str, Any], context: ToolContext | None = None) -> ToolResult:
        try:
            data = self._service.inspect_generation(arguments["campaign_id"], arguments["generation_index"])
            return self._result(data)
        except Exception as exc:
            return self._result({"error_code": "generation_inspect_failed", "message": str(exc)}, is_error=True)


class ControlEvolutionCampaignTool(_CampaignTool):
    """推演任务运维控制（暂停/恢复/终止）"""
    name = "control_evolution_campaign"
    description = "向推演任务下发边界安全指令：暂停、恢复对账流程、终止任务。本工具不会直接运行CMO仿真。"
    input_schema = {
        "type": "object",
        "properties": {
            "campaign_id": {"type": "string", "description": "推演任务唯一标识"},
            "action": {"type": "string", "enum": ["pause", "resume", "stop"], "description": "控制动作：pause暂停 / resume恢复 / stop终止"}
        },
        "required": ["campaign_id", "action"],
        "additionalProperties": False
    }
    requires_approval = True  # 运维控制指令需要人工审批

    def execute(self, arguments: dict[str, Any], context: ToolContext | None = None) -> ToolResult:
        try:
            action = arguments["action"]
            if action == "pause":
                value = self._service.pause_campaign(arguments["campaign_id"])
            elif action == "resume":
                value = self._service.resume_campaign(arguments["campaign_id"])
            else:
                value = self._service.stop_campaign(arguments["campaign_id"])
            return self._result(value)
        except Exception as exc:
            return self._result({"error_code": "campaign_control_failed", "message": str(exc)}, is_error=True)


def campaign_tools(*, service: EvolutionCampaignService) -> tuple[BaseTool, ...]:
    """构造全部六项推演任务工具实例，注入演化服务依赖"""
    return (
        PrepareEvolutionCampaignTool(service=service),
        PreviewEvolutionGenerationTool(service=service),
        ExecuteEvolutionGenerationTool(service=service),
        InspectEvolutionCampaignTool(service=service),
        InspectEvolutionGenerationTool(service=service),
        ControlEvolutionCampaignTool(service=service),
    )
