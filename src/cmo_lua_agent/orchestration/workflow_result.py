"""完整场景 Workflow 的可序列化终态结果。

Workflow任务结束后，总结“最后结果是什么”。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cmo_lua_agent.contract import ValidationResult
from cmo_lua_agent.generation import LuaGenerationResult
from cmo_lua_agent.orchestration.workflow_state import (
    WorkflowStage,
    WorkflowState,
    WorkflowStatus,
)


@dataclass(frozen=True, slots=True)
class ScenarioWorkflowResult:
    """一次 JSON-to-Lua Workflow 运行的最终结构化结果。"""

    success: bool
    state: WorkflowState
    failed_stage: WorkflowStage | None
    validation: ValidationResult | None
    generation: LuaGenerationResult | None

    def __post_init__(self) -> None:
        if not isinstance(self.success, bool):
            raise TypeError("success must be a bool")
        if not isinstance(self.state, WorkflowState):
            raise TypeError("state must be a WorkflowState")
        if self.failed_stage is not None and not isinstance(
            self.failed_stage,
            WorkflowStage,
        ):
            raise TypeError(
                "failed_stage must be a WorkflowStage or None"
            )
        if self.validation is not None and not isinstance(
            self.validation,
            ValidationResult,
        ):
            raise TypeError(
                "validation must be a ValidationResult or None"
            )
        if self.generation is not None and not isinstance(
            self.generation,
            LuaGenerationResult,
        ):
            raise TypeError(
                "generation must be a LuaGenerationResult or None"
            )

        if self.success:
            if self.state.status is not WorkflowStatus.COMPLETED:
                raise ValueError(
                    "successful result requires completed workflow state"
                )
            if self.failed_stage is not None:
                raise ValueError(
                    "successful result cannot contain failed_stage"
                )
            if self.validation is not None and not self.validation.valid:
                raise ValueError(
                    "successful result cannot contain invalid validation"
                )
        else:
            if self.state.status not in {
                WorkflowStatus.FAILED,
                WorkflowStatus.NEEDS_USER_INPUT,
            }:
                raise ValueError(
                    "unsuccessful result requires failed or needs-user-input state"
                )
            if self.failed_stage is None:
                raise ValueError(
                    "failed result requires failed_stage"
                )
            if self.state.stage is not self.failed_stage:
                raise ValueError(
                    "failed_stage must match workflow state stage"
                )

    def to_dict(self) -> dict[str, Any]:
        """转换为 CLI、日志与 JSON 输出可复用的稳定字典。"""
        return {
            "success": self.success,
            "state": self.state.to_dict(),
            "failed_stage": (
                self.failed_stage.value
                if self.failed_stage is not None
                else None
            ),
            "validation": (
                self.validation.to_dict()
                if self.validation is not None
                else None
            ),
            "generation": (
                self.generation.to_dict()
                if self.generation is not None
                else None
            ),
        }
