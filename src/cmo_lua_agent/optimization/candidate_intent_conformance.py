"""Deterministic role and intent conformance for assembled candidate patches."""

from __future__ import annotations

from dataclasses import dataclass

from cmo_lua_agent.optimization.proposal_models import (
    CandidateIntent,
    CandidateRoleSpec,
    ProposalContractError,
)
from cmo_lua_agent.optimization.strategy_dimensions import semantic_dimensions


def _operation_key(path: str) -> str | None:
    tokens = path.strip("/").split("/")
    if len(tokens) >= 2 and tokens[0] in {"attacks", "sorties"} and tokens[1].isdecimal():
        return f"{tokens[0]}/{tokens[1]}"
    return None


def _operation_kind(operation: str) -> str:
    return "surface" if operation.startswith("attacks/") else "sortie"


@dataclass(frozen=True, slots=True)
class RoleFeasibilityResult:
    feasible: bool
    candidate_id: str
    available_operation_count: int
    available_dimension_count: int
    surface_operation_count: int
    sortie_operation_count: int
    reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "feasible": self.feasible,
            "candidate_id": self.candidate_id,
            "available_operation_count": self.available_operation_count,
            "available_dimension_count": self.available_dimension_count,
            "surface_operation_count": self.surface_operation_count,
            "sortie_operation_count": self.sortie_operation_count,
            "reason": self.reason,
        }


def check_candidate_role_feasibility(
    *, candidate_id: str, role_spec: CandidateRoleSpec, patch_catalog: tuple[object, ...]
) -> RoleFeasibilityResult:
    """Check catalog capacity before the proposal client can be invoked."""
    paths = tuple(getattr(leaf, "path") for leaf in patch_catalog)
    operations = {operation for path in paths if (operation := _operation_key(path)) is not None}
    dimensions = semantic_dimensions(paths)
    surface_count = sum(_operation_kind(operation) == "surface" for operation in operations)
    sortie_count = sum(_operation_kind(operation) == "sortie" for operation in operations)
    reason: str | None = None
    if len(operations) < role_spec.min_operations:
        reason = "insufficient_patchable_operations"
    elif len(dimensions) < role_spec.min_dimensions:
        reason = "insufficient_patchable_dimensions"
    elif role_spec.require_surface and surface_count == 0:
        reason = "surface_operation_unavailable"
    elif role_spec.require_sortie and sortie_count == 0:
        reason = "sortie_operation_unavailable"
    elif len(paths) < role_spec.min_changed_leaves:
        reason = "insufficient_patchable_leaves"
    return RoleFeasibilityResult(
        feasible=reason is None,
        candidate_id=candidate_id,
        available_operation_count=len(operations),
        available_dimension_count=len(dimensions),
        surface_operation_count=surface_count,
        sortie_operation_count=sortie_count,
        reason=reason,
    )


class CandidateIntentConformanceError(ProposalContractError):
    def __init__(
        self,
        *,
        code: str,
        required_dimensions: tuple[str, ...],
        actual_dimensions: tuple[str, ...],
        changed_paths: tuple[str, ...],
        preferred_dimension_hits: tuple[str, ...] = (),
        catalog_paths: tuple[str, ...] = (),
        actual_operations: tuple[str, ...] = (),
    ) -> None:
        self.required_dimensions = required_dimensions
        self.actual_dimensions = actual_dimensions
        self.changed_paths = changed_paths
        self.preferred_dimension_hits = preferred_dimension_hits
        self.catalog_paths = catalog_paths
        self.actual_operations = actual_operations
        self.violations = ({
            "code": code,
            "path": list(changed_paths),
            "actual_value": {
                "dimensions": list(actual_dimensions),
                "operations": list(actual_operations),
            },
            "constraint_summary": {
                "required_dimensions": list(required_dimensions),
                "preferred_dimension_hits": list(preferred_dimension_hits),
            },
        },)
        super().__init__(code)


class CandidateIntentConformanceValidator:
    """Validate actual executable paths against the system-owned candidate role."""

    def validate(
        self,
        *,
        intent: CandidateIntent,
        changed_paths: tuple[str, ...],
        catalog_paths: tuple[str, ...] = (),
        catalog: tuple[object, ...] | None = None,
    ) -> None:
        if catalog is not None:
            catalog_paths = tuple(getattr(leaf, "path") for leaf in catalog)
        actual_dimensions = semantic_dimensions(changed_paths)
        actual_operations = tuple(sorted({operation for path in changed_paths if (operation := _operation_key(path)) is not None}))
        preferred_hits = tuple(dimension for dimension in actual_dimensions if dimension in intent.preferred_dimensions)
        kwargs = {
            "actual_dimensions": actual_dimensions,
            "changed_paths": changed_paths,
            "preferred_dimension_hits": preferred_hits,
            "catalog_paths": catalog_paths,
            "actual_operations": actual_operations,
        }
        if any(path not in set(catalog_paths) for path in changed_paths):
            raise CandidateIntentConformanceError(
                code="candidate_intent_path_not_cataloged",
                required_dimensions=intent.preferred_dimensions,
                **kwargs,
            )
        if not intent.min_changes <= len(changed_paths) <= intent.max_changes:
            raise CandidateIntentConformanceError(
                code="candidate_intent_change_count_invalid",
                required_dimensions=(),
                **kwargs,
            )
        if intent.require_surface and not any(_operation_kind(item) == "surface" for item in actual_operations):
            raise CandidateIntentConformanceError(
                code="candidate_intent_surface_required", required_dimensions=(), **kwargs
            )
        if intent.require_sortie and not any(_operation_kind(item) == "sortie" for item in actual_operations):
            raise CandidateIntentConformanceError(
                code="candidate_intent_sortie_required", required_dimensions=(), **kwargs
            )
        if len(actual_operations) < intent.min_operations or (
            intent.max_operations is not None and len(actual_operations) > intent.max_operations
        ):
            raise CandidateIntentConformanceError(
                code="candidate_intent_operation_count_invalid",
                required_dimensions=(f"operation_count={intent.min_operations}",),
                **kwargs,
            )
        minimum_dimensions = intent.minimum_distinct_dimensions
        if len(actual_dimensions) < minimum_dimensions or (
            intent.max_dimensions is not None and len(actual_dimensions) > intent.max_dimensions
        ):
            raise CandidateIntentConformanceError(
                code="candidate_intent_dimension_missing",
                required_dimensions=(f"minimum_distinct_dimensions={minimum_dimensions}",),
                **kwargs,
            )
        if intent.required_dimensions and not set(intent.required_dimensions).issubset(actual_dimensions):
            raise CandidateIntentConformanceError(
                code="candidate_intent_required_dimension_missing",
                required_dimensions=intent.required_dimensions,
                **kwargs,
            )
        if intent.failure_profile_mode == "required" and not (
            set(intent.failure_operation_ids).intersection(actual_operations)
            or set(intent.failure_semantic_dimensions).intersection(actual_dimensions)
        ):
            raise CandidateIntentConformanceError(
                code="candidate_intent_failure_profile_not_covered",
                required_dimensions=tuple(intent.failure_semantic_dimensions),
                **kwargs,
            )
        if not preferred_hits:
            raise CandidateIntentConformanceError(
                code="candidate_intent_dimension_missing",
                required_dimensions=intent.preferred_dimensions,
                **kwargs,
            )
