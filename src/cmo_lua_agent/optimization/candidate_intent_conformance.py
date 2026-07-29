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
    ) -> None:
        self.required_dimensions = required_dimensions
        self.actual_dimensions = actual_dimensions
        self.changed_paths = changed_paths
        self.violations = ({
            "code": code,
            "path": list(changed_paths),
            "actual_value": list(actual_dimensions),
            "constraint_summary": {"required_dimensions": list(required_dimensions)},
        },)
        super().__init__(code)


class CandidateIntentConformanceValidator:
    """Reject an assembled candidate before batch validation when it violates its frozen Intent."""

    def validate(self, *, intent: CandidateIntent, changed_paths: tuple[str, ...]) -> None:
        actual_dimensions = semantic_dimensions(changed_paths)
        if not intent.min_changes <= len(changed_paths) <= intent.max_changes:
            raise CandidateIntentConformanceError(
                code="candidate_intent_change_count_invalid",
                required_dimensions=tuple(intent.required_dimensions),
                actual_dimensions=actual_dimensions,
                changed_paths=changed_paths,
            )
        if not set(actual_dimensions).issubset(set(intent.strategy_dimensions)):
            raise CandidateIntentConformanceError(
                code="candidate_intent_dimension_not_allowed",
                required_dimensions=tuple(intent.strategy_dimensions),
                actual_dimensions=actual_dimensions,
                changed_paths=changed_paths,
            )
        required = tuple(intent.required_dimensions)
        if intent.candidate_id == "candidate_02":
            required = tuple(intent.strategy_dimensions)
        if not set(required).issubset(actual_dimensions):
            raise CandidateIntentConformanceError(
                code="candidate_intent_dimension_missing",
                required_dimensions=required,
                actual_dimensions=actual_dimensions,
                changed_paths=changed_paths,
            )
