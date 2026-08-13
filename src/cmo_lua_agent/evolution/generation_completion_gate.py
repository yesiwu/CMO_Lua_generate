"""一代全局副作用的确定性放行闸门。

排序、学习聚合等代级动作只能在预期候选方案全部到达终态后执行；本模块只根据
已记录的结果作判断，不触发执行、不修改状态，确保重试与恢复仍沿用同一规则。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


_TERMINAL_STATES = frozenset(
    {
        "completed",
        "semantic_invalid",
        "unscorable",
        "execution_failed",
        "failed",
        "runtime_defect",
        "repair_budget_exhausted",
        "cancelled_after_start",
    }
)


@dataclass(frozen=True, slots=True)
class GenerationCompletionDecision:
    """描述本代候选结果是否已足以作为完整正式结果的确定性判定。"""
    complete: bool
    code: str
    pending_candidate_ids: tuple[str, ...]


class GenerationCompletionGate:
    """只有全部预期对象进入终态后，才允许排序和学习。"""

    def evaluate(
        self,
        *,
        expected_candidate_ids: Sequence[str],
        outcomes: Sequence[Mapping[str, object]],
    ) -> GenerationCompletionDecision:
        state_by_id = {
            str(item.get("candidate_id")): self._state(item)
            for item in outcomes
        }
        pending = tuple(
            candidate_id
            for candidate_id in expected_candidate_ids
            if state_by_id.get(candidate_id, "not_started") not in _TERMINAL_STATES
        )
        return GenerationCompletionDecision(
            complete=not pending,
            code="generation_complete" if not pending else "generation_incomplete",
            pending_candidate_ids=pending,
        )

    @staticmethod
    def _state(outcome: Mapping[str, object]) -> str:
        state = outcome.get("final_state")
        if isinstance(state, str) and state:
            return state.lower()
        # Compatibility for pre-gate Phase 6 adapters.  A false or absent
        # success flag remains non-terminal and therefore blocks side effects.
        return "completed" if outcome.get("success") is True else "not_started"
