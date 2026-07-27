"""The sole Phase 6 StrategyProposalAgent implementation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Protocol

from cmo_lua_agent.contract.strategy_models import strategy_spec_from_dict
from cmo_lua_agent.optimization.phase6_models import StrategyCandidate, StrategyProposalContext


class StrategyProposalJsonClient(Protocol):
    def complete_json(self, *, system: str, prompt: str) -> object: ...


class StrategyProposalAgent:
    def __init__(self, client: StrategyProposalJsonClient) -> None:
        self._client = client

    def propose(self, context: StrategyProposalContext) -> tuple[StrategyCandidate, ...]:
        response = self._client.complete_json(system=_SYSTEM, prompt=json.dumps(context.to_prompt_dict(), ensure_ascii=False, sort_keys=True))
        if not isinstance(response, Mapping) or set(response) != {"candidates"}:
            raise ValueError("proposal response must contain only candidates")
        rows = response["candidates"]
        if not isinstance(rows, list) or len(rows) != 4:
            raise ValueError("proposal response must contain exactly four candidates")
        candidates: list[StrategyCandidate] = []
        for index, row in enumerate(rows):
            if not isinstance(row, Mapping) or set(row) != {"candidate_id", "strategy", "proposal_summary", "intended_difference"}:
                raise ValueError("candidate response contains unsupported fields")
            candidate_id = row["candidate_id"]
            if candidate_id != f"candidate_{index:02d}":
                raise ValueError("candidate ids must be ordered candidate_00 through candidate_03")
            if not isinstance(row["strategy"], Mapping) or not isinstance(row["proposal_summary"], str):
                raise ValueError("candidate strategy and summary are invalid")
            differences = row["intended_difference"]
            if not isinstance(differences, list) or not all(isinstance(value, str) for value in differences):
                raise ValueError("intended_difference must be a string list")
            candidates.append(StrategyCandidate(candidate_id, strategy_spec_from_dict(dict(row["strategy"])), row["proposal_summary"], tuple(differences)))
        return tuple(candidates)


_SYSTEM = """You are StrategyProposalAgent. Return exactly one JSON object with candidates only.
Generate exactly four complete StrategySpec variants using the supplied human Bootstrap Skill as guidance.
Do not output Lua, CMO commands, execution plans, score predictions, scoring rules, skill edits, experience, or extra fields.
You may only modify existing strategy leaf values permitted by allowed_strategy_paths. Do not add, remove, reorder, or rename strategy objects or their stable IDs."""
