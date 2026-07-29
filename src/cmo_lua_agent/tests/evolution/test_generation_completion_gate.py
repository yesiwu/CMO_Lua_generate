from __future__ import annotations

from cmo_lua_agent.evolution.generation_completion_gate import (
    GenerationCompletionGate,
)


def test_gate_rejects_generation_with_candidate_awaiting_approval() -> None:
    decision = GenerationCompletionGate().evaluate(
        expected_candidate_ids=(
            "baseline", "candidate_00", "candidate_01", "candidate_02", "candidate_03",
        ),
        outcomes=(
            {"candidate_id": "baseline", "final_state": "completed"},
            {"candidate_id": "candidate_00", "final_state": "completed"},
            {"candidate_id": "candidate_01", "final_state": "semantic_invalid"},
            {"candidate_id": "candidate_02", "final_state": "unscorable"},
            {"candidate_id": "candidate_03", "final_state": "awaiting_approval"},
        ),
    )

    assert decision.complete is False
    assert decision.pending_candidate_ids == ("candidate_03",)
    assert decision.code == "generation_incomplete"


def test_gate_accepts_all_explicit_candidate_terminal_states() -> None:
    decision = GenerationCompletionGate().evaluate(
        expected_candidate_ids=("baseline", "candidate_00"),
        outcomes=(
            {"candidate_id": "baseline", "final_state": "completed"},
            {"candidate_id": "candidate_00", "final_state": "execution_failed"},
        ),
    )

    assert decision.complete is True
    assert decision.pending_candidate_ids == ()
