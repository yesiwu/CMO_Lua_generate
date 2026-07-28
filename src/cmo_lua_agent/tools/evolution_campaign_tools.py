"""The six bounded Chat tools for Phase 9 campaign control."""

from __future__ import annotations

from dataclasses import asdict
import json
from typing import Any

from cmo_lua_agent.evolution.control_plane import CampaignPermissionReceipt, EvolutionCampaignService
from cmo_lua_agent.evolution.models import CampaignBudget, CampaignExecutionMode, EvolutionCampaignSpec
from cmo_lua_agent.tools.tool_base.base import BaseTool, ToolResult
from cmo_lua_agent.tools.tool_base.context import ToolContext


class _CampaignTool(BaseTool):
    toolset = "campaign"

    def __init__(self, *, service: EvolutionCampaignService) -> None:
        self._service = service

    @staticmethod
    def _result(value: object, *, is_error: bool = False) -> ToolResult:
        return ToolResult(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=str), is_error=is_error)

    @staticmethod
    def _progress(context: ToolContext | None, message: str) -> None:
        if context is not None:
            context.progress.tool_started(message)


class PrepareEvolutionCampaignTool(_CampaignTool):
    name = "prepare_evolution_campaign"
    description = "Create a persisted Phase 9 campaign after validating its frozen contract and budgets. It never starts CMO."
    input_schema: dict[str, Any] = {"type": "object", "properties": {"campaign": {"type": "object"}}, "required": ["campaign"], "additionalProperties": False}

    def execute(self, arguments: dict[str, Any], context: ToolContext | None = None) -> ToolResult:
        self._progress(context, "Preparing evolution campaign")
        try:
            value = dict(arguments["campaign"])
            value["budget"] = CampaignBudget(**value["budget"])
            value["execution_mode"] = CampaignExecutionMode(value["execution_mode"])
            value["allowed_strategy_paths"] = tuple(value["allowed_strategy_paths"])
            return self._result(self._service.prepare_campaign(EvolutionCampaignSpec(**value)))
        except Exception as exc:
            return self._result({"error_code": "campaign_prepare_failed", "message": str(exc)}, is_error=True)


class PreviewEvolutionGenerationTool(_CampaignTool):
    name = "preview_evolution_generation"
    description = "Freeze or read a generation preview: knowledge snapshot, four candidates, and strategy diffs. It never renders Lua or starts CMO."
    input_schema = {"type": "object", "properties": {"campaign_id": {"type": "string"}, "generation_index": {"type": "integer", "minimum": 0}, "regenerate_preview": {"type": "boolean", "default": False}}, "required": ["campaign_id", "generation_index"], "additionalProperties": False}

    def execute(self, arguments: dict[str, Any], context: ToolContext | None = None) -> ToolResult:
        self._progress(context, "Previewing evolution generation")
        try:
            preview = self._service.preview_generation(campaign_id=arguments["campaign_id"], generation_index=arguments["generation_index"], regenerate_preview=bool(arguments.get("regenerate_preview", False)))
            return self._result(asdict(preview))
        except Exception as exc:
            return self._result({"error_code": "generation_preview_failed", "message": str(exc)}, is_error=True)


class ExecuteEvolutionGenerationTool(_CampaignTool):
    name = "execute_evolution_generation"
    description = "With human approval, start the persisted worker for one already-previewed generation. Returns immediately with an operation ID; it does not block Chat."
    input_schema = {"type": "object", "properties": {"campaign_id": {"type": "string"}, "generation_index": {"type": "integer", "minimum": 0}}, "required": ["campaign_id", "generation_index"], "additionalProperties": False}
    requires_approval = True

    def execute(self, arguments: dict[str, Any], context: ToolContext | None = None) -> ToolResult:
        self._progress(context, "Authorizing and starting generation worker")
        try:
            receipt = CampaignPermissionReceipt.from_hook_receipt(context.approval_receipt if context else None)
            # The only approval scope exposed through Chat is one attempt. Broader caps
            # are issued by the platform control surface, never by model arguments.
            self._service.authorize_generation(campaign_id=arguments["campaign_id"], generation_index=arguments["generation_index"], receipt=receipt)
            worker = self._service.execute_generation(campaign_id=arguments["campaign_id"], generation_index=arguments["generation_index"])
            return self._result({"campaign_id": worker.campaign_id, "generation_index": worker.generation_index, "operation_id": worker.operation_id, "status": worker.status})
        except Exception as exc:
            return self._result({"error_code": "generation_execute_failed", "message": str(exc)}, is_error=True)


class InspectEvolutionCampaignTool(_CampaignTool):
    name = "inspect_evolution_campaign"
    description = "Return a compact persisted campaign state, budget, control request, and contract summary."
    input_schema = {"type": "object", "properties": {"campaign_id": {"type": "string"}}, "required": ["campaign_id"], "additionalProperties": False}

    def execute(self, arguments: dict[str, Any], context: ToolContext | None = None) -> ToolResult:
        try:
            return self._result(self._service.inspect_campaign(arguments["campaign_id"]))
        except Exception as exc:
            return self._result({"error_code": "campaign_inspect_failed", "message": str(exc)}, is_error=True)


class InspectEvolutionGenerationTool(_CampaignTool):
    name = "inspect_evolution_generation"
    description = "Return compact preview, worker, outcome, leaderboard, and learning status for one generation."
    input_schema = {"type": "object", "properties": {"campaign_id": {"type": "string"}, "generation_index": {"type": "integer", "minimum": 0}}, "required": ["campaign_id", "generation_index"], "additionalProperties": False}

    def execute(self, arguments: dict[str, Any], context: ToolContext | None = None) -> ToolResult:
        try:
            return self._result(self._service.inspect_generation(arguments["campaign_id"], arguments["generation_index"]))
        except Exception as exc:
            return self._result({"error_code": "generation_inspect_failed", "message": str(exc)}, is_error=True)


class ControlEvolutionCampaignTool(_CampaignTool):
    name = "control_evolution_campaign"
    description = "Request a safe-boundary pause, resume reconciliation, or stop for a campaign. It never directly runs CMO."
    input_schema = {"type": "object", "properties": {"campaign_id": {"type": "string"}, "action": {"type": "string", "enum": ["pause", "resume", "stop"]}}, "required": ["campaign_id", "action"], "additionalProperties": False}
    requires_approval = True

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
    return (
        PrepareEvolutionCampaignTool(service=service),
        PreviewEvolutionGenerationTool(service=service),
        ExecuteEvolutionGenerationTool(service=service),
        InspectEvolutionCampaignTool(service=service),
        InspectEvolutionGenerationTool(service=service),
        ControlEvolutionCampaignTool(service=service),
    )
