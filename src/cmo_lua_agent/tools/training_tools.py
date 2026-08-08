"""High-level tools for unattended persistent training workflows."""

from __future__ import annotations

import json
from typing import Any

from cmo_lua_agent.tools.tool_base.base import BaseTool, ToolResult
from cmo_lua_agent.tools.tool_base.context import ToolContext


class _TrainingTool(BaseTool):
    toolset = "training"

    def __init__(self, *, service: object) -> None:
        self._service = service

    @staticmethod
    def _result(value: object, *, is_error: bool = False) -> ToolResult:
        return ToolResult(json.dumps(value, ensure_ascii=False, sort_keys=True), is_error=is_error)


class StartTrainingTool(_TrainingTool):
    name = "start_training"
    description = "Start an unattended multi-generation training workflow from a ScenarioIR JSON path."
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "input_path": {"type": "string"},
            "objective": {"type": "string"},
            "generation_count": {"type": "integer", "minimum": 1},
        },
        "required": ["input_path", "objective", "generation_count"],
        "additionalProperties": False,
    }

    def execute(self, arguments: dict[str, Any], context: ToolContext | None = None) -> ToolResult:
        try:
            return self._result(self._service.start(
                input_path=str(arguments["input_path"]),
                objective=str(arguments["objective"]),
                generation_count=int(arguments["generation_count"]),
            ))
        except Exception as exc:
            return self._result({"error_code": "training_start_failed", "message": str(exc)}, is_error=True)


class InspectTrainingTool(_TrainingTool):
    name = "inspect_training"
    description = "Read persisted training progress without starting CMO or calling the LLM."
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"workflow_id": {"type": "string"}},
        "required": ["workflow_id"],
        "additionalProperties": False,
    }

    def execute(self, arguments: dict[str, Any], context: ToolContext | None = None) -> ToolResult:
        try:
            return self._result(self._service.inspect(str(arguments["workflow_id"])))
        except Exception as exc:
            return self._result({"error_code": "training_inspect_failed", "message": str(exc)}, is_error=True)


class ControlTrainingTool(_TrainingTool):
    name = "control_training"
    description = "Request a safe-boundary pause, resume, or stop for a training workflow."
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "workflow_id": {"type": "string"},
            "action": {"type": "string", "enum": ["pause", "resume", "stop"]},
        },
        "required": ["workflow_id", "action"],
        "additionalProperties": False,
    }

    def execute(self, arguments: dict[str, Any], context: ToolContext | None = None) -> ToolResult:
        try:
            return self._result(self._service.control(
                str(arguments["workflow_id"]), str(arguments["action"]),
            ))
        except Exception as exc:
            return self._result({"error_code": "training_control_failed", "message": str(exc)}, is_error=True)


def training_tools(*, service: object) -> tuple[BaseTool, ...]:
    return (StartTrainingTool(service=service), InspectTrainingTool(service=service), ControlTrainingTool(service=service))
