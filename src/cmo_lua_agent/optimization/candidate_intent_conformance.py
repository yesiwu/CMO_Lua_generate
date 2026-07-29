"""Deterministic conformance between a frozen CandidateIntent and one assembled Patch."""

from __future__ import annotations

from cmo_lua_agent.optimization.proposal_models import CandidateIntent, ProposalContractError
from cmo_lua_agent.optimization.strategy_dimensions import semantic_dimensions


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
    ) -> None:
        self.required_dimensions = required_dimensions
        self.actual_dimensions = actual_dimensions
        self.changed_paths = changed_paths
        self.preferred_dimension_hits = preferred_dimension_hits
        self.catalog_paths = catalog_paths
        self.violations = ({
            "code": code,
            "path": list(changed_paths),
            "actual_value": list(actual_dimensions),
            "constraint_summary": {
                "required_dimensions": list(required_dimensions),
                "preferred_dimension_hits": list(preferred_dimension_hits),
            },
        },)
        super().__init__(code)


class CandidateIntentConformanceValidator:
    """Reject an assembled candidate before batch validation when it violates its frozen Intent."""

    def validate(
        self,
        *,
        intent: CandidateIntent,
        changed_paths: tuple[str, ...],
        catalog_paths: tuple[str, ...],
    ) -> None:
        actual_dimensions = semantic_dimensions(changed_paths)
        preferred_hits = tuple(
            dimension
            for dimension in actual_dimensions
            if dimension in intent.preferred_dimensions
        )
        if any(path not in set(catalog_paths) for path in changed_paths):
            raise CandidateIntentConformanceError(
                code="candidate_intent_path_not_cataloged",
                required_dimensions=intent.preferred_dimensions,
                actual_dimensions=actual_dimensions,
                changed_paths=changed_paths,
                preferred_dimension_hits=preferred_hits,
                catalog_paths=catalog_paths,
            )
        if not intent.min_changes <= len(changed_paths) <= intent.max_changes:
            raise CandidateIntentConformanceError(
                code="candidate_intent_change_count_invalid",
                required_dimensions=tuple(intent.required_dimensions),
                actual_dimensions=actual_dimensions,
                changed_paths=changed_paths,
                preferred_dimension_hits=preferred_hits,
                catalog_paths=catalog_paths,
            )
        if len(actual_dimensions) < intent.minimum_distinct_dimensions:
            raise CandidateIntentConformanceError(
                code="candidate_intent_dimension_missing",
                required_dimensions=(
                    f"minimum_distinct_dimensions={intent.minimum_distinct_dimensions}",
                ),
                actual_dimensions=actual_dimensions,
                changed_paths=changed_paths,
                preferred_dimension_hits=preferred_hits,
                catalog_paths=catalog_paths,
            )
        if intent.required_dimensions and not set(intent.required_dimensions).issubset(actual_dimensions):
            raise CandidateIntentConformanceError(
                code="candidate_intent_required_dimension_missing",
                required_dimensions=intent.required_dimensions,
                actual_dimensions=actual_dimensions,
                changed_paths=changed_paths,
                preferred_dimension_hits=preferred_hits,
                catalog_paths=catalog_paths,
            )
        if not preferred_hits:
            raise CandidateIntentConformanceError(
                code="candidate_intent_dimension_missing",
                required_dimensions=intent.preferred_dimensions,
                actual_dimensions=actual_dimensions,
                changed_paths=changed_paths,
                preferred_dimension_hits=preferred_hits,
                catalog_paths=catalog_paths,
            )
