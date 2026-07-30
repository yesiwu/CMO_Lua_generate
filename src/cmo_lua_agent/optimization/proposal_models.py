"""Immutable contracts for the constrained two-stage strategy proposal flow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias


JsonScalar: TypeAlias = str | int | float | bool
CANDIDATE_IDS = tuple(f"candidate_{index:02d}" for index in range(4))
CANDIDATE_ROLES = (
    "exploit",
    "robust_repair",
    "coordinated_explore",
    "conservative_control",
    # These legacy names remain valid for persisted Phase 9C preview traces.
    "repair",
    "explore",
    "conservative",
)
STRATEGY_DIMENSIONS = (
    "target_assignment",
    "attack_timing",
    "fire_quantity",
    "ammunition_reserve",
    "air_route",
    "risk_policy",
)


class ProposalContractError(ValueError):
    """Stable, user-safe proposal contract failure."""

    def __init__(
        self,
        code: str,
        detail: str | None = None,
        *,
        diagnostics: dict[str, object] | None = None,
    ) -> None:
        self.code = code
        self.diagnostics = dict(diagnostics or {})
        super().__init__(detail or code)


class CandidateProposalError(ProposalContractError):
    """A proposal failure bound to one fixed candidate and bounded stage."""

    def __init__(self, *, candidate_id: str, stage: str, cause: ProposalContractError) -> None:
        self.candidate_id = candidate_id
        self.stage = stage
        self.cause_code = cause.code
        self.violations = tuple(getattr(cause, "violations", ()))
        self.changed_paths = tuple(getattr(cause, "changed_paths", ()))
        self.required_dimensions = tuple(getattr(cause, "required_dimensions", ()))
        self.actual_dimensions = tuple(getattr(cause, "actual_dimensions", ()))
        super().__init__(
            cause.code,
            f"{candidate_id}:{stage}:{cause.code}",
            diagnostics=getattr(cause, "diagnostics", {}),
        )


class StrategyValidationProposalError(ProposalContractError):
    """Structured StrategyValidator result suitable for a bounded repair."""

    def __init__(self, *, violations: tuple[dict[str, object], ...], changed_paths: tuple[str, ...]) -> None:
        self.violations = violations
        self.changed_paths = changed_paths
        super().__init__("assembled_strategy_invalid")


def _scalar(value: object, *, code: str) -> JsonScalar:
    if type(value) not in (str, int, float, bool):
        raise ProposalContractError(code)
    return value  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class CandidateIntent:
    candidate_id: str
    role: str
    objective: str
    strategy_dimensions: tuple[str, ...]
    min_changes: int
    max_changes: int
    required_dimensions: tuple[str, ...] = ()
    min_operations: int = 1
    min_dimensions: int = 1
    require_surface: bool = False
    require_sortie: bool = False
    max_operations: int | None = None
    max_dimensions: int | None = None
    failure_profile_mode: str = "unavailable"
    failure_operation_ids: tuple[str, ...] = ()
    failure_semantic_dimensions: tuple[str, ...] = ()
    failure_profile_source_checksum: str | None = None

    @property
    def preferred_dimensions(self) -> tuple[str, ...]:
        """Planner recommendations, not an exact implementation checklist."""
        return self.strategy_dimensions

    @property
    def minimum_changed_leaves(self) -> int:
        return self.min_changes

    @property
    def minimum_distinct_dimensions(self) -> int:
        # Preserve the old standalone ``explore`` intent contract. Formal C2
        # coordinated exploration supplies its explicit floor of three.
        return max(
            self.min_dimensions,
            2 if self.candidate_id == "candidate_02" and self.role == "explore" else 1,
        )

    def __post_init__(self) -> None:
        if self.candidate_id not in CANDIDATE_IDS:
            raise ProposalContractError("invalid_candidate_id")
        if self.role not in CANDIDATE_ROLES:
            raise ProposalContractError("invalid_candidate_role")
        if not isinstance(self.objective, str) or not self.objective.strip():
            raise ProposalContractError("invalid_intent_objective")
        dimensions = tuple(self.strategy_dimensions)
        if not dimensions or len(set(dimensions)) != len(dimensions):
            raise ProposalContractError("invalid_strategy_dimensions")
        if any(dimension not in STRATEGY_DIMENSIONS for dimension in dimensions):
            raise ProposalContractError("unknown_strategy_dimension")
        if self.min_changes < 1 or self.max_changes < self.min_changes:
            raise ProposalContractError("invalid_change_bounds")
        if self.min_operations < 1 or self.min_dimensions < 1:
            raise ProposalContractError("invalid_role_constraint")
        if self.max_operations is not None and self.max_operations < self.min_operations:
            raise ProposalContractError("invalid_role_constraint")
        if self.max_dimensions is not None and self.max_dimensions < self.min_dimensions:
            raise ProposalContractError("invalid_role_constraint")
        required = tuple(self.required_dimensions)
        if any(dimension not in dimensions for dimension in required):
            raise ProposalContractError("repair_dimension_not_declared")
        failure_dimensions = tuple(self.failure_semantic_dimensions)
        if any(dimension not in STRATEGY_DIMENSIONS for dimension in failure_dimensions):
            raise ProposalContractError("unknown_strategy_dimension")
        if self.failure_profile_mode not in {"unavailable", "required"}:
            raise ProposalContractError("invalid_failure_profile_mode")
        failure_operations = tuple(self.failure_operation_ids)
        if self.failure_profile_mode == "required":
            if not (failure_operations or failure_dimensions):
                raise ProposalContractError("invalid_failure_profile")
            if not isinstance(self.failure_profile_source_checksum, str) or not self.failure_profile_source_checksum:
                raise ProposalContractError("invalid_failure_profile")
        elif failure_operations or failure_dimensions or self.failure_profile_source_checksum is not None:
            raise ProposalContractError("invalid_failure_profile")
        object.__setattr__(self, "objective", self.objective.strip())
        object.__setattr__(self, "strategy_dimensions", dimensions)
        object.__setattr__(self, "required_dimensions", required)
        object.__setattr__(self, "failure_operation_ids", failure_operations)
        object.__setattr__(self, "failure_semantic_dimensions", failure_dimensions)


@dataclass(frozen=True, slots=True)
class CandidateRoleSpec:
    """System-owned role constraints; these cannot be weakened by an LLM intent."""

    candidate_id: str
    role: str
    min_changed_leaves: int
    max_changed_leaves: int
    min_operations: int
    min_dimensions: int
    require_surface: bool = False
    require_sortie: bool = False
    max_operations: int | None = None
    max_dimensions: int | None = None
    failure_profile_mode: str = "unavailable"
    failure_operation_ids: tuple[str, ...] = ()
    failure_semantic_dimensions: tuple[str, ...] = ()
    failure_profile_source_checksum: str | None = None


def candidate_role_specs(generation_context: object | None = None) -> tuple[CandidateRoleSpec, ...]:
    """Return the fixed Phase 9C role contract with an optional frozen repair profile."""
    profile = generation_context.get("failure_profile") if isinstance(generation_context, dict) else None
    operation_ids: tuple[str, ...] = ()
    dimensions: tuple[str, ...] = ()
    source_checksum: str | None = None
    if isinstance(profile, dict):
        raw_operations = profile.get("operation_ids")
        raw_dimensions = profile.get("semantic_dimensions")
        raw_checksum = profile.get("source_checksum")
        if (
            isinstance(raw_operations, (list, tuple))
            and all(isinstance(value, str) and value for value in raw_operations)
            and isinstance(raw_dimensions, (list, tuple))
            and all(value in STRATEGY_DIMENSIONS for value in raw_dimensions)
            and isinstance(raw_checksum, str)
            and raw_checksum
        ):
            operation_ids = tuple(sorted(set(raw_operations)))
            dimensions = tuple(sorted(set(raw_dimensions)))
            source_checksum = raw_checksum
    failure_mode = "required" if operation_ids or dimensions else "unavailable"
    return (
        CandidateRoleSpec("candidate_00", "exploit", 3, 5, 2, 2),
        CandidateRoleSpec(
            "candidate_01", "robust_repair", 3, 5, 2, 2,
            failure_profile_mode=failure_mode,
            failure_operation_ids=operation_ids,
            failure_semantic_dimensions=dimensions,
            failure_profile_source_checksum=source_checksum,
        ),
        CandidateRoleSpec("candidate_02", "coordinated_explore", 5, 8, 3, 3, True, True),
        CandidateRoleSpec("candidate_03", "conservative_control", 1, 2, 1, 1, max_operations=1, max_dimensions=1),
    )


@dataclass(frozen=True, slots=True)
class StrategyPatchOperation:
    path: str
    value: JsonScalar

    def __post_init__(self) -> None:
        if not isinstance(self.path, str) or not self.path.startswith("/"):
            raise ProposalContractError("invalid_patch_pointer")
        if self.path == "/":
            raise ProposalContractError("invalid_patch_pointer")
        object.__setattr__(self, "value", _scalar(self.value, code="invalid_patch_scalar"))


@dataclass(frozen=True, slots=True)
class CandidatePatch:
    candidate_id: str
    proposal_summary: str
    changes: tuple[StrategyPatchOperation, ...]

    def __post_init__(self) -> None:
        if self.candidate_id not in CANDIDATE_IDS:
            raise ProposalContractError("invalid_candidate_id")
        if not isinstance(self.proposal_summary, str) or not self.proposal_summary.strip():
            raise ProposalContractError("invalid_patch_summary")
        changes = tuple(self.changes)
        if not changes:
            raise ProposalContractError("empty_patch")
        if not all(isinstance(change, StrategyPatchOperation) for change in changes):
            raise ProposalContractError("invalid_patch_operation")
        paths = [change.path for change in changes]
        if len(paths) != len(set(paths)):
            raise ProposalContractError("duplicate_patch_path")
        object.__setattr__(self, "proposal_summary", self.proposal_summary.strip())
        object.__setattr__(self, "changes", changes)


@dataclass(frozen=True, slots=True)
class AcceptedCandidateSummary:
    candidate_id: str
    strategy_checksum: str
    changed_paths: tuple[str, ...]
    strategy_dimensions: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.candidate_id not in CANDIDATE_IDS:
            raise ProposalContractError("invalid_candidate_id")
        if not isinstance(self.strategy_checksum, str) or not self.strategy_checksum:
            raise ProposalContractError("invalid_strategy_checksum")
        if not self.changed_paths or any(not path.startswith("/") for path in self.changed_paths):
            raise ProposalContractError("invalid_accepted_changed_paths")
        if any(dimension not in STRATEGY_DIMENSIONS for dimension in self.strategy_dimensions):
            raise ProposalContractError("unknown_strategy_dimension")


@dataclass(frozen=True, slots=True)
class StrategyProposalUsage:
    intent_calls: int = 0
    patch_calls: int = 0
    repair_calls: int = 0

    def __post_init__(self) -> None:
        if any(value < 0 for value in (self.intent_calls, self.patch_calls, self.repair_calls)):
            raise ProposalContractError("negative_proposal_usage")

    @property
    def total_calls(self) -> int:
        return self.intent_calls + self.patch_calls + self.repair_calls


@dataclass(frozen=True, slots=True)
class AssembledStrategyPatch:
    strategy: object
    changed_paths: tuple[str, ...]
