"""Immutable contracts for a single-scenario Phase 9 campaign."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from hashlib import sha256
import json
from typing import Any


def _checksum(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(payload.encode("utf-8")).hexdigest()


class CampaignExecutionMode(str, Enum):
    FAKE_FIXTURE = "fake_fixture"
    PRODUCTION_CMO = "production_cmo"


class CampaignStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    AWAITING_APPROVAL = "awaiting_approval"


class OperationKind(str, Enum):
    STRATEGY_PROPOSAL = "strategy_proposal"
    LUA_GENERATION = "lua_generation"
    LUA_REPAIR = "lua_repair"
    CMO = "cmo"
    PHASE6 = "phase6"
    PHASE7 = "phase7"
    PHASE8 = "phase8"


class OperationStatus(str, Enum):
    PREPARED = "prepared"
    AUTHORIZED = "authorized"
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    UNKNOWN = "unknown"


class StopReason(str, Enum):
    NONE = "none"
    MAX_GENERATIONS_REACHED = "max_generations_reached"
    MAX_CMO_RUNS_REACHED = "max_cmo_runs_reached"
    FAILURE_BUDGET_EXHAUSTED = "failure_budget_exhausted"
    NO_IMPROVEMENT_PATIENCE_EXHAUSTED = "no_improvement_patience_exhausted"
    NO_ELIGIBLE_CANDIDATES = "no_eligible_candidates"
    REPEATED_STRATEGY_SPACE = "repeated_strategy_space"
    REQUIRE_HUMAN_REVIEW = "require_human_review"
    MANUAL_STOP_REQUESTED = "manual_stop_requested"
    CONTRACT_CHANGED = "contract_changed"
    CMO_LOCK_UNAVAILABLE = "cmo_lock_unavailable"


class ControlAction(str, Enum):
    PAUSE = "pause"
    STOP = "stop"


@dataclass(frozen=True, slots=True)
class CampaignBudget:
    max_generations: int
    max_cmo_runs: int
    max_cmo_attempts_per_candidate: int
    max_cmo_attempts_for_baseline: int
    max_repair_attempts_per_candidate: int
    max_failed_runs: int
    max_llm_total_calls: int
    max_strategy_proposal_calls: int
    max_lua_generation_calls: int
    max_lua_repair_calls: int
    max_comparative_learning_calls: int
    max_skill_author_calls: int
    max_wall_clock_seconds: int
    per_generation_timeout_seconds: int
    per_candidate_timeout_seconds: int

    def __post_init__(self) -> None:
        if any(value < 0 for value in asdict(self).values()):
            raise ValueError("campaign budget values must be non-negative")
        if not all((self.max_generations, self.max_cmo_runs, self.max_wall_clock_seconds,
                    self.per_generation_timeout_seconds, self.per_candidate_timeout_seconds)):
            raise ValueError("campaign budget requires positive generation, CMO, and timeout limits")
        if not self.max_cmo_attempts_per_candidate or not self.max_cmo_attempts_for_baseline:
            raise ValueError("CMO attempt limits must be positive")

    @property
    def required_cmo_attempts_per_generation(self) -> int:
        return self.max_cmo_attempts_for_baseline + 4 * self.max_cmo_attempts_per_candidate

    def can_reserve_generation(self, *, available_cmo_runs: int) -> bool:
        return available_cmo_runs >= self.required_cmo_attempts_per_generation

    @property
    def checksum(self) -> str:
        return _checksum(asdict(self))


@dataclass(frozen=True, slots=True)
class EvolutionCampaignSpec:
    campaign_id: str
    scenario_id: str
    scenario_ref: str
    scenario_checksum: str
    initial_strategy_ref: str
    runtime_contract_checksum: str
    renderer_contract_checksum: str
    score_contract_checksum: str
    semantic_contract_checksum: str
    code_revision: str
    allowed_strategy_paths: tuple[str, ...]
    generation_objective: str
    budget: CampaignBudget
    execution_mode: CampaignExecutionMode
    candidates_per_generation: int = 4
    no_improvement_patience: int = 2
    minimum_improvement_delta: int = 1

    def __post_init__(self) -> None:
        required = (self.campaign_id, self.scenario_id, self.scenario_ref, self.scenario_checksum,
                    self.initial_strategy_ref, self.runtime_contract_checksum, self.renderer_contract_checksum,
                    self.score_contract_checksum, self.semantic_contract_checksum, self.code_revision,
                    self.generation_objective)
        if any(not isinstance(value, str) or not value.strip() for value in required):
            raise ValueError("campaign spec requires non-empty identifiers and contracts")
        if any(token in self.campaign_id for token in ("/", "\\", "..")):
            raise ValueError("campaign_id must be a safe identifier")
        if self.candidates_per_generation != 4:
            raise ValueError("candidates_per_generation must equal 4")
        if not self.allowed_strategy_paths or not all(path.startswith("/") for path in self.allowed_strategy_paths):
            raise ValueError("allowed_strategy_paths must contain JSON Pointer paths")
        if self.no_improvement_patience < 1:
            raise ValueError("no_improvement_patience must be positive")

    @property
    def contract_checksum(self) -> str:
        return _checksum({
            "scenario_checksum": self.scenario_checksum,
            "runtime_contract_checksum": self.runtime_contract_checksum,
            "renderer_contract_checksum": self.renderer_contract_checksum,
            "score_contract_checksum": self.score_contract_checksum,
            "semantic_contract_checksum": self.semantic_contract_checksum,
            "code_revision": self.code_revision,
        })

    @property
    def checksum(self) -> str:
        value = asdict(self)
        value["execution_mode"] = self.execution_mode.value
        return _checksum(value)


@dataclass(frozen=True, slots=True)
class CampaignState:
    campaign_id: str
    status: CampaignStatus = CampaignStatus.CREATED
    current_generation: int = 0
    completed_generations: int = 0
    cmo_run_count: int = 0
    failed_run_count: int = 0
    llm_call_counts: dict[str, int] = field(default_factory=dict)
    best_champion_ref: str | None = None
    best_official_score: int | None = None
    no_improvement_count: int = 0
    stop_reason: StopReason = StopReason.NONE
    budget_revision: int = 0


@dataclass(frozen=True, slots=True)
class OperationRecord:
    operation_id: str
    generation_index: int
    kind: OperationKind
    input_checksum: str
    status: OperationStatus
    output_ref: str | None = None
    error: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True, slots=True)
class ControlRequest:
    action: ControlAction
    requested_at: str
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class GenerationPreview:
    campaign_id: str
    generation_index: int
    preview_revision: int
    snapshot_checksum: str
    candidate_set_checksum: str
    strategy_diffs: tuple[dict[str, Any], ...]
    proposal_operation_id: str
    checksum: str


@dataclass(frozen=True, slots=True)
class GenerationApproval:
    approval_id: str
    campaign_id: str
    generation_index: int
    preview_revision: int
    snapshot_checksum: str
    candidate_set_checksum: str
    contract_checksum: str
    budget_revision: int
    authorization_mode: str
    max_cmo_attempts: int
    expires_at: str
    receipt_summary: str
    valid: bool = True


@dataclass(frozen=True, slots=True)
class WorkerState:
    operation_id: str
    campaign_id: str
    generation_index: int
    status: str
    worker_id: str
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True, slots=True)
class CandidateScore:
    candidate_id: str
    official_score: int | None
    execution_success: bool
    scoreable: bool
    semantic_valid: bool
    artifact_provenance: str
    score_source: str | None
    execution_fidelity: str
    own_loss_count: int = 0
    high_value_enemy_damage: int = 0
    unexpected_weapon_activity_count: int = 0
    weapon_expenditure: int = 0

    @property
    def eligible(self) -> bool:
        return (
            self.execution_success and self.scoreable and self.semantic_valid
            and self.artifact_provenance == "formal_renderer"
            and self.score_source == "execution-summary.json#/official_score/final"
            and self.execution_fidelity == "verified" and self.official_score is not None
        )


@dataclass(frozen=True, slots=True)
class Phase6GenerationArtifact:
    """Only references/formal outcome facts returned by the existing Phase 6 path."""
    rolling_baseline: CandidateScore
    candidates: tuple[CandidateScore, ...]
    optimization_dir: str
    cmo_attempts: int
    failed_cmo_attempts: int = 0


@dataclass(frozen=True, slots=True)
class ChampionDecision:
    best_candidate_id: str | None
    selected_champion_id: str
    selected_score: int
    improved: bool
    exclusion_reasons: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StopDecision:
    should_stop: bool
    reason: StopReason
    details: str = ""
