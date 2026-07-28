"""Phase 9C production contracts with deterministic serialization."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any, Mapping


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def canonical_checksum(value: object) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class FrozenCandidateSet:
    campaign_id: str
    generation_index: int
    preview_revision: int
    baseline: Mapping[str, Any]
    baseline_checksum: str
    candidates: tuple[Mapping[str, Any], ...]
    candidate_checksums: tuple[str, ...]
    candidate_set_checksum: str
    source_proposal_operation_id: str

    @classmethod
    def create(
        cls,
        *,
        campaign_id: str,
        generation_index: int,
        preview_revision: int,
        baseline: Mapping[str, Any],
        candidates: tuple[Mapping[str, Any], ...],
        source_proposal_operation_id: str,
    ) -> "FrozenCandidateSet":
        baseline_value = json.loads(canonical_json(dict(baseline)))
        candidate_values = tuple(json.loads(canonical_json(dict(item))) for item in candidates)
        ids = [item.get("candidate_id") for item in candidate_values]
        if ids != [f"candidate_{index:02d}" for index in range(4)]:
            raise ValueError("frozen_candidate_ids_invalid")
        baseline_checksum = canonical_checksum(baseline_value)
        candidate_checksums = tuple(
            canonical_checksum(item["strategy"]) for item in candidate_values
        )
        identity = {
            "campaign_id": campaign_id,
            "generation_index": generation_index,
            "preview_revision": preview_revision,
            "baseline_checksum": baseline_checksum,
            "candidate_ids": ids,
            "candidate_checksums": list(candidate_checksums),
            "source_proposal_operation_id": source_proposal_operation_id,
        }
        return cls(
            campaign_id=campaign_id,
            generation_index=generation_index,
            preview_revision=preview_revision,
            baseline=baseline_value,
            baseline_checksum=baseline_checksum,
            candidates=candidate_values,
            candidate_checksums=candidate_checksums,
            candidate_set_checksum=canonical_checksum(identity),
            source_proposal_operation_id=source_proposal_operation_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "generation_index": self.generation_index,
            "preview_revision": self.preview_revision,
            "baseline": dict(self.baseline),
            "baseline_checksum": self.baseline_checksum,
            "candidates": [dict(item) for item in self.candidates],
            "candidate_checksums": list(self.candidate_checksums),
            "candidate_set_checksum": self.candidate_set_checksum,
            "source_proposal_operation_id": self.source_proposal_operation_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FrozenCandidateSet":
        candidate = cls.create(
            campaign_id=str(value["campaign_id"]),
            generation_index=int(value["generation_index"]),
            preview_revision=int(value["preview_revision"]),
            baseline=dict(value["baseline"]),
            candidates=tuple(dict(item) for item in value["candidates"]),
            source_proposal_operation_id=str(value["source_proposal_operation_id"]),
        )
        if candidate.baseline_checksum != value.get("baseline_checksum"):
            raise ValueError("frozen_baseline_checksum_mismatch")
        if tuple(value.get("candidate_checksums", ())) != candidate.candidate_checksums:
            raise ValueError("frozen_candidate_checksum_mismatch")
        if candidate.candidate_set_checksum != value.get("candidate_set_checksum"):
            raise ValueError("frozen_candidate_set_checksum_mismatch")
        return candidate


@dataclass(frozen=True, slots=True)
class GenerationApprovalGrant:
    approval_id: str
    campaign_id: str
    generation_index: int
    preview_revision: int
    snapshot_checksum: str
    candidate_set_checksum: str
    baseline_checksum: str
    contract_checksum: str
    budget_revision: int
    approved_operation_ids: tuple[str, ...]
    maximum_cmo_attempts: int
    actor: str
    actor_source: str
    identity_strength: str
    hostname: str
    process_id: int
    approved_at: str
    expires_at: str
    receipt_checksum: str
    checksum: str
    valid: bool = True

    @classmethod
    def issue(cls, **values: Any) -> "GenerationApprovalGrant":
        body = {
            **values,
            "approved_operation_ids": list(values["approved_operation_ids"]),
            "actor_source": "local_os_user",
            "identity_strength": "local_os_attribution",
        }
        checksum = canonical_checksum(body)
        approval_id = f"approval_{checksum[:24]}"
        return cls(
            approval_id=approval_id,
            checksum=checksum,
            actor_source="local_os_user",
            identity_strength="local_os_attribution",
            **values,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "GenerationApprovalGrant":
        data = dict(value)
        data["approved_operation_ids"] = tuple(data["approved_operation_ids"])
        grant = cls(**data)
        body = grant.to_dict()
        expected_id = body.pop("approval_id")
        expected_checksum = body.pop("checksum")
        body.pop("valid", None)
        if canonical_checksum(body) != expected_checksum or expected_id != f"approval_{expected_checksum[:24]}":
            raise ValueError("generation_approval_checksum_mismatch")
        return grant


@dataclass(frozen=True, slots=True)
class ControlledScenarioAsset:
    asset_id: str
    scenario_id: str
    absolute_path: str
    sha256: str
    size_bytes: int
    verification_record_path: str
    verified_clean_initial_state: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ScenarioAssetVerificationRecord:
    schema_version: str
    asset_id: str
    scenario_id: str
    absolute_path: str
    sha256: str
    size_bytes: int
    modified_time_ns: int
    verified_clean_initial_state: bool
    actor: str
    actor_source: str
    identity_strength: str
    hostname: str
    process_id: int
    verified_at: str
    record_checksum: str

    @classmethod
    def create(cls, **values: Any) -> "ScenarioAssetVerificationRecord":
        body = {
            "schema_version": "1.0",
            **values,
            "actor_source": "local_os_user",
            "identity_strength": "local_os_attribution",
        }
        return cls(**body, record_checksum=canonical_checksum(body))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(
        cls, value: Mapping[str, Any]
    ) -> "ScenarioAssetVerificationRecord":
        record = cls(**dict(value))
        body = record.to_dict()
        checksum = body.pop("record_checksum")
        if canonical_checksum(body) != checksum:
            raise ValueError("scenario_asset_verification_record_invalid")
        return record


@dataclass(frozen=True, slots=True)
class AttemptSlot:
    operation_id: str
    candidate_id: str
    attempt_index: int
    status: str

    @property
    def remaining(self) -> bool:
        return self.status == "available"


@dataclass(frozen=True, slots=True)
class GenerationApprovalUsage:
    approval_id: str
    maximum_cmo_attempts: int
    consumed_operation_ids: tuple[str, ...] = ()

    @property
    def remaining_cmo_attempts(self) -> int:
        return max(
            0,
            self.maximum_cmo_attempts - len(self.consumed_operation_ids),
        )


@dataclass(frozen=True, slots=True)
class BaselineFailureProfile:
    schema_version: str
    run_id: str
    official_score: int | float
    semantic_valid: bool
    execution_fidelity: str
    failure_indicators: tuple[str, ...]
    deviations: tuple[Mapping[str, Any], ...]
    source_checksums: Mapping[str, str]
    checksum: str

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        official_score: int | float,
        semantic_valid: bool,
        execution_fidelity: str,
        failure_indicators: tuple[str, ...],
        deviations: tuple[Mapping[str, Any], ...],
        source_checksums: Mapping[str, str],
    ) -> "BaselineFailureProfile":
        body = {
            "schema_version": "1.0",
            "run_id": run_id,
            "official_score": official_score,
            "semantic_valid": semantic_valid,
            "execution_fidelity": execution_fidelity,
            "failure_indicators": list(failure_indicators),
            "deviations": [dict(item) for item in deviations],
            "source_checksums": dict(source_checksums),
        }
        return cls(
            schema_version="1.0",
            run_id=run_id,
            official_score=official_score,
            semantic_valid=semantic_valid,
            execution_fidelity=execution_fidelity,
            failure_indicators=failure_indicators,
            deviations=tuple(
                json.loads(canonical_json(dict(item))) for item in deviations
            ),
            source_checksums=json.loads(canonical_json(dict(source_checksums))),
            checksum=canonical_checksum(body),
        )
