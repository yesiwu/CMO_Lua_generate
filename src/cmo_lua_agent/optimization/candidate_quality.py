"""Deterministic batch-quality reporting before Phase 9C candidates freeze."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Any, Mapping

from cmo_lua_agent.evolution.production_models import canonical_checksum
from cmo_lua_agent.optimization.candidate_set_validator import strategy_leaf_diff
from cmo_lua_agent.optimization.phase6_models import StrategyCandidate, StrategySpec
from cmo_lua_agent.optimization.strategy_dimensions import semantic_dimensions


def _operation_key(path: str) -> str | None:
    tokens = path.strip("/").split("/")
    if len(tokens) >= 2 and tokens[0] in {"attacks", "sorties"} and tokens[1].isdecimal():
        return f"{tokens[0]}/{tokens[1]}"
    return None


def _pointer_value(payload: Any, path: str) -> Any:
    current = payload
    for token in path.strip("/").split("/"):
        current = current[int(token)] if isinstance(current, list) else current[token]
    return current


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return 1.0 if not union else len(left & right) / len(union)


@dataclass(frozen=True, slots=True)
class CandidateQualityCandidateReport:
    candidate_id: str
    role: str
    strategy_checksum: str
    changed_leaf_count: int
    changed_paths: tuple[str, ...]
    changed_operation_ids: tuple[str, ...]
    changed_platform_ids: tuple[str, ...]
    semantic_dimensions: tuple[str, ...]
    surface_operation_count: int
    sortie_operation_count: int
    role_conformance: Mapping[str, Any]
    baseline_distance: Mapping[str, int]
    repair_summary: Mapping[str, Any] | None = None

    @property
    def report_checksum(self) -> str:
        return canonical_checksum(self._body())

    def _body(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "candidate_id": self.candidate_id,
            "role": self.role,
            "strategy_checksum": self.strategy_checksum,
            "hard_validation": {"valid": True},
            "actual_changes": {
                "changed_leaf_count": self.changed_leaf_count,
                "changed_paths": list(self.changed_paths),
                "changed_operation_ids": list(self.changed_operation_ids),
                "changed_platform_ids": list(self.changed_platform_ids),
                "semantic_dimensions": list(self.semantic_dimensions),
                "surface_operation_count": self.surface_operation_count,
                "sortie_operation_count": self.sortie_operation_count,
            },
            "role_quality": dict(self.role_conformance),
            "repair_summary": dict(self.repair_summary or {"attempted": False}),
            "interpretability": _interpretability(
                len(self.changed_operation_ids), len(self.semantic_dimensions)
            ),
            "baseline_distance": dict(self.baseline_distance),
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._body(), "report_checksum": self.report_checksum}


@dataclass(frozen=True, slots=True)
class CandidateQualityPairwiseReport:
    left_candidate_id: str
    right_candidate_id: str
    path_jaccard: float
    operation_jaccard: float
    value_difference_count: int
    same_strategy_checksum: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "left_candidate_id": self.left_candidate_id,
            "right_candidate_id": self.right_candidate_id,
            "path_jaccard": self.path_jaccard,
            "operation_jaccard": self.operation_jaccard,
            "value_difference_count": self.value_difference_count,
            "same_strategy_checksum": self.same_strategy_checksum,
        }


@dataclass(frozen=True, slots=True)
class CandidateQualityReport:
    candidate_reports: tuple[CandidateQualityCandidateReport, ...]
    pairwise_reports: tuple[CandidateQualityPairwiseReport, ...]
    batch_coverage: Mapping[str, tuple[str, ...]]
    failed_rules: tuple[str, ...]
    report_checksum: str
    warnings: tuple[str, ...] = ()
    schema_version: str = "1.0"

    @property
    def status(self) -> str:
        return "passed" if not self.failed_rules else "failed"

    @classmethod
    def create(
        cls,
        *,
        candidate_reports: tuple[CandidateQualityCandidateReport, ...],
        pairwise_reports: tuple[CandidateQualityPairwiseReport, ...],
        batch_coverage: Mapping[str, tuple[str, ...]],
        failed_rules: tuple[str, ...],
        warnings: tuple[str, ...] = (),
    ) -> "CandidateQualityReport":
        body = {
            "schema_version": "1.0",
            "status": "passed" if not failed_rules else "failed",
            "candidate_reports": [item.to_dict() for item in candidate_reports],
            "pairwise_reports": [item.to_dict() for item in pairwise_reports],
            "batch_coverage": {key: list(value) for key, value in sorted(batch_coverage.items())},
            "failed_rules": list(failed_rules),
            "warnings": list(warnings),
        }
        return cls(
            candidate_reports=candidate_reports,
            pairwise_reports=pairwise_reports,
            batch_coverage={key: tuple(value) for key, value in sorted(batch_coverage.items())},
            failed_rules=failed_rules,
            warnings=warnings,
            report_checksum=canonical_checksum(body),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "candidate_reports": [item.to_dict() for item in self.candidate_reports],
            "pairwise_reports": [item.to_dict() for item in self.pairwise_reports],
            "batch_coverage": {key: list(value) for key, value in sorted(self.batch_coverage.items())},
            "failed_rules": list(self.failed_rules),
            "warnings": list(self.warnings),
            "report_checksum": self.report_checksum,
        }

    def require_passed(self) -> None:
        if self.failed_rules:
            raise CandidateBatchQualityError(self)


class CandidateBatchQualityError(ValueError):
    code = "candidate_batch_quality_failed"

    def __init__(self, report: CandidateQualityReport) -> None:
        self.report = report
        self.failed_rules = report.failed_rules
        self.covered_operation_ids = report.batch_coverage["operation_ids"]
        self.covered_dimensions = report.batch_coverage["semantic_dimensions"]
        self.covered_platform_types = report.batch_coverage["platform_types"]
        self.pairwise_summary = tuple(item.to_dict() for item in report.pairwise_reports)
        self.candidate_ids = tuple(item.candidate_id for item in report.candidate_reports)
        super().__init__(self.code)


class CandidateQualityEvaluator:
    """Pure quality gate over already assembled candidate strategies."""

    def evaluate(
        self,
        *,
        baseline: StrategySpec,
        candidates: tuple[StrategyCandidate, ...],
        intents: tuple[object, ...],
        proposal_context: Mapping[str, Any],
        repair_summaries: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> CandidateQualityReport:
        intent_by_id = {str(getattr(item, "candidate_id")): item for item in intents}
        operation_metadata = _operation_metadata(baseline, proposal_context)
        patchable_paths = _patchable_paths(proposal_context)
        reports = tuple(
            self._candidate_report(
                baseline=baseline,
                candidate=candidate,
                intent=intent_by_id.get(candidate.candidate_id),
                operation_metadata=operation_metadata,
                patchable_paths=patchable_paths,
                repair_summary=(repair_summaries or {}).get(candidate.candidate_id),
            )
            for candidate in sorted(candidates, key=lambda item: item.candidate_id)
        )
        pairwise = self._pairwise_reports(candidates, reports)
        platform_types_by_operation = {
            str(value["operation_id"]): str(value["platform_type"])
            for value in operation_metadata.values()
        }
        coverage = {
            "operation_ids": tuple(sorted({value for item in reports for value in item.changed_operation_ids})),
            "semantic_dimensions": tuple(sorted({value for item in reports for value in item.semantic_dimensions})),
            "platform_types": tuple(sorted({
                platform_types_by_operation[value]
                for item in reports for value in item.changed_operation_ids
                if value in platform_types_by_operation
            })),
        }
        failed, warnings = self._quality_messages(reports, coverage, pairwise)
        return CandidateQualityReport.create(
            candidate_reports=reports,
            pairwise_reports=pairwise,
            batch_coverage=coverage,
            failed_rules=tuple(sorted(failed)),
            warnings=tuple(sorted(warnings)),
        )

    @staticmethod
    def _candidate_report(*, baseline, candidate, intent, operation_metadata, patchable_paths, repair_summary=None):
        paths = strategy_leaf_diff(
            baseline,
            candidate.strategy_spec,
            patchable_paths,
        )
        operation_ids = tuple(sorted({
            str(operation_metadata[key]["operation_id"])
            for path in paths
            if (key := _operation_key(path)) is not None and key in operation_metadata
        }))
        platform_ids = tuple(sorted({
            str(operation_metadata[key]["platform_id"])
            for path in paths
            if (key := _operation_key(path)) is not None and key in operation_metadata
        }))
        dimensions = semantic_dimensions(paths)
        local_operations = tuple(sorted({
            key for path in paths if (key := _operation_key(path)) is not None
        }))
        surface = sum(
            operation_metadata[key]["operation_type"] == "surface_attack"
            for key in {_operation_key(path) for path in paths}
            if key in operation_metadata
        )
        sortie = sum(
            operation_metadata[key]["operation_type"] == "sortie"
            for key in {_operation_key(path) for path in paths}
            if key in operation_metadata
        )
        role_conformance = _role_conformance(
            candidate_id=candidate.candidate_id,
            intent=intent,
            changed_leaf_count=len(paths),
            operation_count=len(operation_ids),
            local_operations=local_operations,
            dimensions=dimensions,
            surface_count=surface,
            sortie_count=sortie,
        )
        return CandidateQualityCandidateReport(
            candidate_id=candidate.candidate_id,
            role=str(getattr(intent, "role", "unknown")),
            strategy_checksum=candidate.strategy_checksum,
            changed_leaf_count=len(paths),
            changed_paths=paths,
            changed_operation_ids=operation_ids,
            changed_platform_ids=platform_ids,
            semantic_dimensions=dimensions,
            surface_operation_count=surface,
            sortie_operation_count=sortie,
            role_conformance=role_conformance,
            baseline_distance={
                "changed_leaf_count": len(paths),
                "changed_operation_count": len(operation_ids),
                "changed_dimension_count": len(dimensions),
            },
            repair_summary=repair_summary,
        )

    @staticmethod
    def _pairwise_reports(candidates, reports):
        candidate_by_id = {item.candidate_id: item for item in candidates}
        report_by_id = {item.candidate_id: item for item in reports}
        rows = []
        for left_id, right_id in combinations(sorted(candidate_by_id), 2):
            left = candidate_by_id[left_id]
            right = candidate_by_id[right_id]
            left_report = report_by_id[left_id]
            right_report = report_by_id[right_id]
            shared = set(left_report.changed_paths) & set(right_report.changed_paths)
            left_payload = left.strategy_spec.to_dict()
            right_payload = right.strategy_spec.to_dict()
            rows.append(CandidateQualityPairwiseReport(
                left_id, right_id,
                _jaccard(set(left_report.changed_paths), set(right_report.changed_paths)),
                _jaccard(set(left_report.changed_operation_ids), set(right_report.changed_operation_ids)),
                sum(_pointer_value(left_payload, path) != _pointer_value(right_payload, path) for path in shared),
                left.strategy_checksum == right.strategy_checksum,
            ))
        return tuple(rows)

    @staticmethod
    def _quality_messages(reports, coverage, pairwise):
        failed: list[str] = []
        warnings: list[str] = []
        for item in reports:
            if item.role_conformance["role_adherence"] != "full":
                warnings.append(f"{item.candidate_id}_role_{item.role_conformance['role_adherence']}")
        checksums = [item.strategy_checksum for item in reports]
        if len(checksums) != len(set(checksums)):
            failed.append("unique_strategy_checksums_required")
        if len(coverage["operation_ids"]) < 4:
            warnings.append("minimum_batch_operation_coverage")
        if len(coverage["semantic_dimensions"]) < 3:
            warnings.append("minimum_batch_dimension_coverage")
        if len(coverage["platform_types"]) < 2:
            warnings.append("minimum_batch_platform_type_coverage")
        if not any(item.surface_operation_count and item.sortie_operation_count for item in reports):
            warnings.append("surface_sortie_candidate_required")
        first_three = [set(item.changed_operation_ids) for item in reports if item.candidate_id in {"candidate_00", "candidate_01", "candidate_02"}]
        if len(first_three) == 3 and first_three[0] == first_three[1] == first_three[2]:
            warnings.append("candidate_00_01_02_same_operation_set")
        if any(item.path_jaccard >= 0.8 for item in pairwise):
            warnings.append("pairwise_path_jaccard_high")
        return failed, warnings


def _operation_metadata(baseline: StrategySpec, proposal_context: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    context_by_id = {
        str(item.get("operation_id")): item
        for item in proposal_context.get("baseline_operations", ())
        if isinstance(item, Mapping) and isinstance(item.get("operation_id"), str)
    }
    result: dict[str, dict[str, str]] = {}
    for index, attack in enumerate(baseline.attacks):
        operation_id = f"surface_attack:{attack.attack_id}"
        item = context_by_id.get(operation_id, {})
        result[f"attacks/{index}"] = {
            "operation_id": operation_id,
            "operation_type": "surface_attack",
            "platform_id": attack.shooter_id,
            "platform_type": str(item.get("platform_type", "surface")),
        }
    for index, sortie in enumerate(baseline.sorties):
        operation_id = f"sortie:{sortie.sortie_id}"
        item = context_by_id.get(operation_id, {})
        result[f"sorties/{index}"] = {
            "operation_id": operation_id,
            "operation_type": "sortie",
            "platform_id": sortie.aircraft_id,
            "platform_type": str(item.get("platform_type", "aircraft")),
        }
    return result


def _patchable_paths(proposal_context: Mapping[str, Any]) -> tuple[str, ...]:
    """Use the frozen tactical projection, never an LLM change summary."""
    values = {
        str(path)
        for item in proposal_context.get("baseline_operations", ())
        if isinstance(item, Mapping)
        for path in item.get("patchable_paths", ())
        if isinstance(path, str) and path.startswith("/")
    }
    if not values:
        raise ValueError("candidate_quality_context_missing_patchable_paths")
    return tuple(sorted(values))


def _role_conformance(*, candidate_id, intent, changed_leaf_count, operation_count, local_operations, dimensions, surface_count, sortie_count):
    violations: list[str] = []
    if intent is None:
        violations.append("intent_missing")
        return {"role_adherence": "weak", "warnings": violations, "repair_recommended": True}
    minimum = int(getattr(intent, "min_changed_leaves", getattr(intent, "min_changes", 1)))
    maximum = int(getattr(intent, "max_changed_leaves", getattr(intent, "max_changes", changed_leaf_count)))
    min_operations = int(getattr(intent, "min_operations", 1))
    min_dimensions = int(getattr(intent, "min_dimensions", 1))
    max_operations = getattr(intent, "max_operations", None)
    max_dimensions = getattr(intent, "max_dimensions", None)
    if not minimum <= changed_leaf_count <= maximum:
        violations.append("changed_leaf_count")
    if operation_count < min_operations or (max_operations is not None and operation_count > int(max_operations)):
        violations.append("operation_count")
    if len(dimensions) < min_dimensions or (max_dimensions is not None and len(dimensions) > int(max_dimensions)):
        violations.append("dimension_count")
    if bool(getattr(intent, "require_surface", False)) and not surface_count:
        violations.append("surface_required")
    if bool(getattr(intent, "require_sortie", False)) and not sortie_count:
        violations.append("sortie_required")
    preferred = tuple(getattr(intent, "strategy_dimensions", ()))
    if preferred and not set(dimensions) & set(preferred):
        violations.append("preferred_dimension_missing")
    if getattr(intent, "failure_profile_mode", "unavailable") == "required":
        failure_operations = set(getattr(intent, "failure_operation_ids", ()))
        failure_dimensions = set(getattr(intent, "failure_semantic_dimensions", ()))
        if not (failure_operations & set(local_operations) or failure_dimensions & set(dimensions)):
            violations.append("failure_profile_not_covered")
    adherence = "full" if not violations else "partial" if len(violations) == 1 else "weak"
    return {"role_adherence": adherence, "warnings": sorted(violations), "repair_recommended": adherence == "weak", "candidate_id": candidate_id}


def _interpretability(operation_count: int, dimension_count: int) -> dict[str, str]:
    if operation_count == 1 and dimension_count == 1:
        return {"level": "high", "claim_scope": "single_factor_hypothesis"}
    if operation_count > 1 and dimension_count == 1:
        return {"level": "medium", "claim_scope": "same_dimension_pattern"}
    if operation_count == 1:
        return {"level": "medium", "claim_scope": "combined_strategy_hypothesis"}
    return {"level": "low", "claim_scope": "combined_strategy_observation"}
