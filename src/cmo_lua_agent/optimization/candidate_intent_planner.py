"""One-call planner that turns an objective into four bounded candidate intents."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Protocol

from cmo_lua_agent.optimization.phase6_models import StrategyProposalContext
from cmo_lua_agent.optimization.proposal_models import CANDIDATE_IDS, CandidateIntent, ProposalContractError, STRATEGY_DIMENSIONS


class IntentJsonClient(Protocol):
    def complete_json(self, *, system: str, prompt: str) -> object: ...


_ROLE_SPECS = (
    ("exploit", 1, 2),
    ("repair", 1, 2),
    ("explore", 2, 3),
    ("conservative", 1, 1),
)
_FAILURE_DIMENSIONS = {
    "missing_contact": "target_assignment",
    "launch_timeout": "attack_timing",
    "attack_command_failed": "fire_quantity",
    "attack_range_timeout": "attack_timing",
}


class CandidateIntentPlanner:
    def __init__(self, client: IntentJsonClient) -> None:
        self._client = client

    def plan(self, context: StrategyProposalContext) -> tuple[CandidateIntent, ...]:
        allowed_dimensions = _supported_dimensions(context)
        response = self._client.complete_json(
            system=_SYSTEM,
            prompt=json.dumps({
                "user_objective": context.user_objective,
                "allowed_strategy_dimensions": sorted(allowed_dimensions),
                "bootstrap_skill": {"skill_id": context.bootstrap.skill_id, "content": context.bootstrap.content},
                "retrieved_experience_cards": [dict(card) for card in context.retrieved_experience_cards],
                "generation_context": dict(context.generation_context or {}),
            }, ensure_ascii=False, sort_keys=True),
        )
        if not isinstance(response, Mapping) or set(response) != {"intents"}:
            raise ProposalContractError("invalid_intent_response_shape")
        rows = response["intents"]
        if not isinstance(rows, list) or len(rows) != 4:
            raise ProposalContractError("intent_count_must_be_four")
        required_repair = _repair_dimensions(context, allowed_dimensions)
        intents: list[CandidateIntent] = []
        for index, row in enumerate(rows):
            if not isinstance(row, Mapping) or set(row) != {"objective", "strategy_dimensions"}:
                raise ProposalContractError("invalid_intent_fields")
            objective, dimensions = row["objective"], row["strategy_dimensions"]
            if not isinstance(objective, str) or not isinstance(dimensions, list) or not all(isinstance(item, str) for item in dimensions):
                raise ProposalContractError("invalid_intent_value")
            if any(dimension not in allowed_dimensions for dimension in dimensions):
                raise ProposalContractError("intent_dimension_not_allowed")
            role, minimum, maximum = _ROLE_SPECS[index]
            intent = CandidateIntent(
                CANDIDATE_IDS[index], role, objective, tuple(dimensions), minimum, maximum,
                required_repair if index == 1 else (),
            )
            if index == 1 and not set(required_repair).issubset(intent.strategy_dimensions):
                raise ProposalContractError("repair_failure_profile_not_covered")
            intents.append(intent)
        if len({dimension for intent in intents for dimension in intent.strategy_dimensions}) < 2:
            raise ProposalContractError("intent_diversity_dimensions_insufficient")
        return tuple(intents)


def _supported_dimensions(context: StrategyProposalContext) -> set[str]:
    values = {dimension for dimension in context.diversity_dimensions if dimension in STRATEGY_DIMENSIONS}
    if not values:
        raise ProposalContractError("no_supported_strategy_dimension")
    return values


def _repair_dimensions(context: StrategyProposalContext, allowed: set[str]) -> tuple[str, ...]:
    failures = (context.generation_context or {}).get("previous_generation_failures", [])
    if not isinstance(failures, list):
        return ()
    mapped = {_FAILURE_DIMENSIONS[value] for value in failures if isinstance(value, str) and value in _FAILURE_DIMENSIONS}
    return tuple(sorted(mapped & allowed))


_SYSTEM = """You are CandidateIntentPlanner. Return exactly one JSON object with an intents array of four items.
Each item has only objective and strategy_dimensions. Do not include candidate IDs, roles, patches, strategies, Lua, CMO commands, scores, or extra fields.
Choose only supplied dimensions. The system assigns fixed candidate roles and validates all patches later."""
