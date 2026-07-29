"""Immutable contracts for the constrained two-stage strategy proposal flow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias


JsonScalar: TypeAlias = str | int | float | bool
CANDIDATE_IDS = tuple(f"candidate_{index:02d}" for index in range(4))
CANDIDATE_ROLES = ("exploit", "repair", "explore", "conservative")
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

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(detail or code)


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
        required = tuple(self.required_dimensions)
        if any(dimension not in dimensions for dimension in required):
            raise ProposalContractError("repair_dimension_not_declared")
        object.__setattr__(self, "objective", self.objective.strip())
        object.__setattr__(self, "strategy_dimensions", dimensions)
        object.__setattr__(self, "required_dimensions", required)


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
