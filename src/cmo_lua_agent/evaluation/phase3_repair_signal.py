"""Map already parsed Phase 3 telemetry to deterministic repair signals."""

from __future__ import annotations

from dataclasses import dataclass

from cmo_lua_agent.evaluation.phase3_evaluation import Phase3EvaluationResult
from cmo_lua_agent.generation.runtime_models import ExecutionPlan


@dataclass(frozen=True, slots=True)
class RepairSignal:
    kind: str
    operation_id: str
    message: str
    repairable: bool


class Phase3RepairSignalMapper:
    def map(self, *, result: Phase3EvaluationResult, plan: ExecutionPlan) -> RepairSignal | None:
        if result.reconciliation.status != "valid" or not result.semantic_validation.semantic_valid or not result.semantic_validation.scoreable:
            return None
        # AttackEpisode errors are structured Phase 3 evidence; no log re-read occurs here.
        for episode in result.attack_episodes:
            for error in episode.important_errors:
                lowered = error.lower()
                if "missing_contact" in lowered or "contact unavailable" in lowered:
                    operation_id = self._contact_operation(plan, episode.target_id)
                    if operation_id:
                        return RepairSignal("missing_contact", operation_id, error, True)
                if "launch timeout" in lowered:
                    return RepairSignal("launch_timeout", episode.operation_id or "", error, False)
                if "attack command" in lowered:
                    return RepairSignal("attack_command_failed", episode.operation_id or "", error, False)
                if "range timeout" in lowered:
                    return RepairSignal("attack_range_timeout", episode.operation_id or "", error, False)
        return None

    @staticmethod
    def _contact_operation(plan: ExecutionPlan, target_id: str) -> str | None:
        for operation in plan.operations:
            if operation.primitive_type == "prepare_target_contact" and str(operation.parameters.get("target_id")) == target_id:
                return operation.operation_id
        return None
