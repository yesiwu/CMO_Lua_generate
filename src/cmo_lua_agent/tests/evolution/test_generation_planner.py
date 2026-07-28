from __future__ import annotations

from cmo_lua_agent.evolution.generation_planner import GenerationPlanner
from cmo_lua_agent.evolution.knowledge_snapshot import KnowledgeSnapshot


def _snapshot() -> KnowledgeSnapshot:
    return KnowledgeSnapshot("campaign", 1, "bootstrap", (), (), "rev", "index", (), "query", {"runtime": "2"}, "parent", "snapshot")


def test_planner_only_emits_context_and_stable_role_hints() -> None:
    plan = GenerationPlanner().plan(
        campaign_id="campaign", generation_index=1, anchor_strategy_ref="anchor.json",
        rolling_strategy_ref="champion.json", knowledge_snapshot_ref="snapshot.json", snapshot=_snapshot(),
        objective="improve", allowed_strategy_paths=("/attacks/0/fire_quantity",),
        history_fingerprints=("old",), previous_generation_failures=("missing_contact",),
    )
    assert plan.parent_strategy_ref == "champion.json"
    assert plan.context["candidate_roles"] == {
        "candidate_00": "exploit", "candidate_01": "repair",
        "candidate_02": "explore", "candidate_03": "conservative_control",
    }
    assert "strategy" not in plan.context
