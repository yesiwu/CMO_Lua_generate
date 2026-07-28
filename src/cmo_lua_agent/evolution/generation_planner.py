"""Build bounded Phase 9 generation context; never generate StrategySpec."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json

from cmo_lua_agent.evolution.knowledge_snapshot import KnowledgeSnapshot


@dataclass(frozen=True, slots=True)
class GenerationPlan:
    campaign_id: str
    generation_index: int
    optimization_id: str
    anchor_strategy_ref: str
    rolling_strategy_ref: str
    parent_strategy_ref: str
    knowledge_snapshot_ref: str
    context: dict[str, object]
    checksum: str


class GenerationPlanner:
    _ROLES = {
        "candidate_00": "exploit",
        "candidate_01": "repair",
        "candidate_02": "explore",
        "candidate_03": "conservative_control",
    }

    def plan(self, *, campaign_id: str, generation_index: int, anchor_strategy_ref: str,
             rolling_strategy_ref: str, knowledge_snapshot_ref: str, snapshot: KnowledgeSnapshot,
             objective: str, allowed_strategy_paths: tuple[str, ...], history_fingerprints: tuple[str, ...],
             previous_generation_failures: tuple[str, ...]) -> GenerationPlan:
        body = {
            "generation_index": generation_index,
            "candidate_roles": self._ROLES,
            "objective": objective,
            "allowed_strategy_paths": list(allowed_strategy_paths),
            "history_fingerprints": list(history_fingerprints),
            "previous_generation_failures": list(previous_generation_failures),
            "retrieved_experience_cards": [dict(item) for item in snapshot.experience_cards],
            "active_curated_skills": [dict(item) for item in snapshot.active_skills],
            "knowledge_snapshot_checksum": snapshot.checksum,
            "conservative_max_changed_leaves": 1,
        }
        checksum = sha256(json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        return GenerationPlan(
            campaign_id=campaign_id, generation_index=generation_index,
            optimization_id=f"{campaign_id}_generation_{generation_index:03d}",
            anchor_strategy_ref=anchor_strategy_ref, rolling_strategy_ref=rolling_strategy_ref,
            parent_strategy_ref=rolling_strategy_ref, knowledge_snapshot_ref=knowledge_snapshot_ref,
            context=body, checksum=checksum,
        )
