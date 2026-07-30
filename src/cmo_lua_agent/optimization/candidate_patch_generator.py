"""One-candidate constrained patch generator."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Protocol

from cmo_lua_agent.llm.json_client import JsonCompletionError
from cmo_lua_agent.optimization.proposal_models import AcceptedCandidateSummary, CandidateIntent, CandidatePatch, ProposalContractError, StrategyPatchOperation, MAX_EFFECTIVE_PATCH_LEAVES, MIN_EFFECTIVE_PATCH_LEAVES
from cmo_lua_agent.optimization.strategy_patch import (
    PatchableLeaf,
    validate_patch_paths_executable,
)
from cmo_lua_agent.optimization.strategy_dimensions import semantic_dimension


class PatchJsonClient(Protocol):
    def complete_json(self, *, system: str, prompt: str) -> object: ...


class CandidatePatchGenerator:
    def __init__(self, client: PatchJsonClient) -> None:
        self._client = client

    def generate(
        self,
        *,
        intent: CandidateIntent,
        catalog: tuple[PatchableLeaf, ...],
        accepted: tuple[AcceptedCandidateSummary, ...],
        tactical_context: dict[str, object] | None = None,
        error: ProposalContractError | None = None,
    ) -> CandidatePatch:
        grouped_catalog = _catalog_by_dimension(catalog)
        try:
            response = self._client.complete_json(
                system=_SYSTEM,
                prompt=json.dumps({
                "candidate_id": intent.candidate_id,
                "role": intent.role,
                "objective": intent.objective,
                "preferred_dimensions": list(intent.preferred_dimensions),
                "required_dimensions": list(intent.required_dimensions),
                "hard_change_count": {"minimum": MIN_EFFECTIVE_PATCH_LEAVES, "maximum": MAX_EFFECTIVE_PATCH_LEAVES},
                "role_change_preference": {"minimum": intent.min_changes, "maximum": intent.max_changes},
                "operation_count": {"minimum": intent.min_operations, "maximum": intent.max_operations},
                "dimension_count": {"minimum": intent.min_dimensions, "maximum": intent.max_dimensions},
                "require_surface": intent.require_surface,
                "require_sortie": intent.require_sortie,
                "failure_profile_available": intent.failure_profile_mode == "required",
                "failure_operation_ids": list(intent.failure_operation_ids),
                "failure_semantic_dimensions": list(intent.failure_semantic_dimensions),
                "candidate_instruction": (
                    _candidate_instruction(intent)
                ),
                "repair_instruction": _repair_instruction(intent, error),
                "patchable_leaves": [leaf.to_prompt_dict() for leaf in catalog],
                "patchable_leaves_by_dimension": grouped_catalog,
                "accepted_candidates": [
                    {"candidate_id": item.candidate_id, "changed_paths": list(item.changed_paths), "strategy_dimensions": list(item.strategy_dimensions)}
                    for item in accepted
                ],
                "proposal_tactical_context": tactical_context,
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
        validate_patch_paths_executable(patch)
        if not MIN_EFFECTIVE_PATCH_LEAVES <= len(patch.changes) <= MAX_EFFECTIVE_PATCH_LEAVES:
            raise ProposalContractError(
                "candidate_change_count_out_of_bounds",
                diagnostics={
                    "actual_change_count": len(patch.changes),
                    "required_min_changes": MIN_EFFECTIVE_PATCH_LEAVES,
                    "required_max_changes": MAX_EFFECTIVE_PATCH_LEAVES,
                    "proposed_paths": [change.path for change in patch.changes],
                },
            )
        known = {leaf.path for leaf in catalog}
        if any(change.path not in known for change in patch.changes):
            raise ProposalContractError("patch_path_not_offered")
        return patch


def _repair_error(error: ProposalContractError | None) -> dict[str, object] | None:
    if error is None:
        return None
    violations = getattr(error, "violations", ())
    payload: dict[str, object] = {
        "code": error.code,
        "diagnostics": dict(error.diagnostics),
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
    for key in (
        "previous_patch",
        "actual_change_count",
        "actual_dimensions",
        "minimum_dimension_count",
        "required_change_range",
        "required_operation_range",
        "required_dimension_range",
        "changed_paths",
        "actual_operation_count",
    ):
        if key in error.diagnostics:
            payload[key] = error.diagnostics[key]
    return payload


def _repair_instruction(
    intent: CandidateIntent,
    error: ProposalContractError | None,
) -> str | None:
    if error is None:
        return None
    return (
        "Return one complete replacement Patch. Preserve legal initial changes where possible, "
        "fix every hard validation error, and use the role-quality warnings as preferences. "
        "changes must contain every corrected change, not only incremental additions."
    )


def _candidate_instruction(intent: CandidateIntent) -> str:
    if intent.candidate_id == "candidate_02":
        return (
            "Prefer 5 to 8 unique changes across at least 3 operations and 3 semantic dimensions, "
            "including surface and sortie operations when useful. These are quality goals, not hard "
            "schema requirements. Select every path from patchable_leaves."
        )
    if intent.candidate_id == "candidate_03":
        return (
            "Prefer one or two changes focused on one operation and one semantic dimension so the "
            "result remains easy to interpret. This is a quality preference, not a hard schema rule."
        )
    return "Use role preferences to make the experiment useful, while keeping every change inside the offered executable leaves."


_SYSTEM = """You are CandidatePatchGenerator. Return exactly one JSON object with proposal_summary and changes.
changes is a non-empty JSON array of {path, value}; replace only listed scalar leaves. Do not output a full strategy, Lua, CMO commands, scoring, IDs, markdown, or extra fields.
Respect the exact candidate ID, change-count bounds, allowed leaf constraints, and any previous structured error. When repairing, return a complete replacement Patch whose changes array contains every corrected change, never only an incremental delta."""


def _catalog_by_dimension(catalog: tuple[PatchableLeaf, ...]) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for leaf in catalog:
        grouped.setdefault(semantic_dimension(leaf.path), []).append(leaf.to_prompt_dict())
    return {dimension: grouped[dimension] for dimension in sorted(grouped)}
