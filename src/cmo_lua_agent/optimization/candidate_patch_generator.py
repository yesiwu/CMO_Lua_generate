"""One-candidate constrained patch generator."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Protocol

from cmo_lua_agent.llm.json_client import JsonCompletionError
from cmo_lua_agent.optimization.proposal_models import AcceptedCandidateSummary, CandidateIntent, CandidatePatch, ProposalContractError, StrategyPatchOperation
from cmo_lua_agent.optimization.strategy_patch import PatchableLeaf


class PatchJsonClient(Protocol):
    def complete_json(self, *, system: str, prompt: str) -> object: ...


class CandidatePatchGenerator:
    def __init__(self, client: PatchJsonClient) -> None:
        self._client = client

    def generate(self, *, intent: CandidateIntent, catalog: tuple[PatchableLeaf, ...], accepted: tuple[AcceptedCandidateSummary, ...], error: ProposalContractError | None = None) -> CandidatePatch:
        try:
            response = self._client.complete_json(
                system=_SYSTEM,
                prompt=json.dumps({
                "candidate_id": intent.candidate_id,
                "role": intent.role,
                "objective": intent.objective,
                "strategy_dimensions": list(intent.strategy_dimensions),
                "required_dimensions": list(intent.required_dimensions),
                "change_count": {"minimum": intent.min_changes, "maximum": intent.max_changes},
                "patchable_leaves": [leaf.to_prompt_dict() for leaf in catalog],
                "accepted_candidates": [
                    {"candidate_id": item.candidate_id, "changed_paths": list(item.changed_paths), "strategy_dimensions": list(item.strategy_dimensions)}
                    for item in accepted
                ],
                "previous_error": _repair_error(error),
                }, ensure_ascii=False, sort_keys=True),
            )
        except JsonCompletionError as error:
            raise ProposalContractError(
                "proposal_json_invalid", diagnostics=error.diagnostics
            ) from error
        if not isinstance(response, Mapping) or set(response) != {"proposal_summary", "changes"}:
            raise ProposalContractError("invalid_patch_response_shape")
        summary, changes = response["proposal_summary"], response["changes"]
        if not isinstance(summary, str) or not isinstance(changes, list):
            raise ProposalContractError("invalid_patch_response_value")
        operations: list[StrategyPatchOperation] = []
        for row in changes:
            if not isinstance(row, Mapping) or set(row) != {"path", "value"}:
                raise ProposalContractError("invalid_patch_change_fields")
            operations.append(StrategyPatchOperation(row["path"], row["value"]))
        patch = CandidatePatch(intent.candidate_id, summary, tuple(operations))
        if not intent.min_changes <= len(patch.changes) <= intent.max_changes:
            raise ProposalContractError("candidate_change_count_out_of_bounds")
        known = {leaf.path for leaf in catalog}
        if any(change.path not in known for change in patch.changes):
            raise ProposalContractError("patch_path_not_offered")
        return patch


def _repair_error(error: ProposalContractError | None) -> dict[str, object] | None:
    if error is None:
        return None
    violations = getattr(error, "violations", ())
    return {
        "code": error.code,
        "changed_paths": list(getattr(error, "changed_paths", ())),
        "violations": [
            {
                "code": item.get("code"),
                "path": item.get("path"),
                "actual_value": item.get("actual_value"),
                "constraint_summary": item.get("constraint_summary"),
            }
            for item in violations
            if isinstance(item, Mapping)
        ],
    }


_SYSTEM = """You are CandidatePatchGenerator. Return exactly one JSON object with proposal_summary and changes.
changes is a non-empty JSON array of {path, value}; replace only listed scalar leaves. Do not output a full strategy, Lua, CMO commands, scoring, IDs, markdown, or extra fields.
Respect the exact candidate ID, change-count bounds, allowed leaf constraints, and any previous structured error."""
