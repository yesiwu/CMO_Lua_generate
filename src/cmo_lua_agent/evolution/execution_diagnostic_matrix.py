"""Read-only Phase 9C diagnostics for isolated Lua, job, and scenario experiments."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import itertools
import json
from pathlib import Path
from typing import Any, Mapping


class ExecutionDiagnosticError(ValueError):
    """Raised when an explicit attempt directory lacks trusted diagnostic artifacts."""


def _canonical_checksum(value: object) -> str:
    serialized = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return sha256(serialized.encode("utf-8")).hexdigest()


def _file_checksum(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class AttemptExecutionDiagnostic:
    """Stable, score-source-safe diagnostic projection for one explicit Attempt."""

    label: str
    artifact_root: str
    lua_checksum: str
    scenario_checksum: str
    batch_job_checksum: str
    execution_summary_checksum: str
    output_directory: str | None
    simulation: Mapping[str, object]
    official_initial_score: int
    official_final_score: int
    execution_fidelity: str
    runtime_execution: Mapping[str, object]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ExecutionDiagnosticReport:
    """A deterministic comparison report for one A/B/C diagnostic experiment."""

    experiment_id: str
    attempts: Mapping[str, AttemptExecutionDiagnostic]
    comparisons: Mapping[str, Mapping[str, object]]
    checksum: str

    def to_dict(self) -> dict[str, object]:
        return {
            "experiment_id": self.experiment_id,
            "attempts": {label: value.to_dict() for label, value in self.attempts.items()},
            "comparisons": {label: dict(value) for label, value in self.comparisons.items()},
            "checksum": self.checksum,
        }


class ExecutionDiagnosticMatrix:
    """Compare declared Attempt directories without discovering or executing artifacts.

    It deliberately reads the authoritative official score only from the reviewed
    ``execution-summary.json`` contract. SQLite, CSV, and text logs are excluded.
    """

    def compare(
        self,
        *,
        experiment_id: str,
        attempts: Mapping[str, Path],
    ) -> ExecutionDiagnosticReport:
        if not experiment_id or not attempts:
            raise ExecutionDiagnosticError("execution_diagnostic_inputs_required")
        if len(set(attempts)) != len(attempts):
            raise ExecutionDiagnosticError("execution_diagnostic_duplicate_label")
        diagnostics = {
            label: self._read_attempt(label, Path(root))
            for label, root in sorted(attempts.items())
        }
        comparisons = self._comparisons(diagnostics)
        payload = {
            "experiment_id": experiment_id,
            "attempts": {label: item.to_dict() for label, item in diagnostics.items()},
            "comparisons": comparisons,
        }
        return ExecutionDiagnosticReport(
            experiment_id=experiment_id,
            attempts=diagnostics,
            comparisons=comparisons,
            checksum=_canonical_checksum(payload),
        )

    def _read_attempt(self, label: str, root: Path) -> AttemptExecutionDiagnostic:
        if not root.is_dir():
            raise ExecutionDiagnosticError("execution_diagnostic_attempt_missing")
        files = {
            "lua": root / "candidate.lua",
            "scenario": root / "scenario.scen",
            "job": root / "batch-job.json",
            "summary": root / "execution-summary.json",
        }
        if any(not path.is_file() for path in files.values()):
            raise ExecutionDiagnosticError("execution_diagnostic_artifact_missing")
        job = self._object(files["job"], "execution_diagnostic_batch_job_invalid")
        summary = self._object(files["summary"], "execution_summary_score_contract_invalid")
        score = summary.get("official_score")
        events = summary.get("score_events")
        integrity = summary.get("evidence_integrity")
        if (
            not isinstance(score, dict)
            or score.get("stable_side_id") != "red"
            or score.get("cmo_side_id") != "red"
            or score.get("status") != "VALID"
            or not isinstance(score.get("initial"), int)
            or not isinstance(score.get("final"), int)
            or not isinstance(events, list)
            or summary.get("score_event_chain_status") != "VALID"
            or not isinstance(integrity, dict)
            or integrity.get("status") != "VALID"
            or score["initial"] + sum(item.get("delta", 0) for item in events if isinstance(item, dict)) != score["final"]
        ):
            raise ExecutionDiagnosticError("execution_summary_score_contract_invalid")
        runtime = summary.get("runtime_execution")
        if not isinstance(runtime, dict):
            runtime = {}
        fidelity = runtime.get("execution_fidelity", "unknown")
        if fidelity == "complete":
            fidelity = "complete"
        elif fidelity == "partial":
            fidelity = "partial"
        else:
            fidelity = "unknown"
        simulation = job.get("simulation") if isinstance(job.get("simulation"), dict) else {}
        normalized_simulation = {
            "enabled": simulation.get("enabled"),
            "pulse_seconds": simulation.get("pulseSeconds"),
            "stop_when_scenario_ends": simulation.get("stopWhenScenarioEnds"),
            "wall_timeout_seconds": simulation.get("wallTimeoutSeconds"),
        }
        return AttemptExecutionDiagnostic(
            label=label,
            artifact_root=str(root.resolve()),
            lua_checksum=_file_checksum(files["lua"]),
            scenario_checksum=_file_checksum(files["scenario"]),
            batch_job_checksum=_file_checksum(files["job"]),
            execution_summary_checksum=_file_checksum(files["summary"]),
            output_directory=job.get("outputDirectory") if isinstance(job.get("outputDirectory"), str) else None,
            simulation=normalized_simulation,
            official_initial_score=score["initial"],
            official_final_score=score["final"],
            execution_fidelity=fidelity,
            runtime_execution={
                key: runtime.get(key)
                for key in (
                    "simulation_elapsed_seconds", "stop_reason", "last_runtime_event_time",
                    "last_scheduled_operation_time", "scheduled_operation_count",
                    "started_operation_count", "completed_operation_count", "pending_operation_count",
                    "lua_bootstrap_seen", "score_fragment_registered", "execution_fidelity",
                )
                if key in runtime
            },
        )

    @staticmethod
    def _object(path: Path, error_code: str) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ExecutionDiagnosticError(error_code) from error
        if not isinstance(payload, dict):
            raise ExecutionDiagnosticError(error_code)
        return payload

    @staticmethod
    def _comparisons(
        attempts: Mapping[str, AttemptExecutionDiagnostic],
    ) -> dict[str, dict[str, object]]:
        result: dict[str, dict[str, object]] = {}
        for left_label, right_label in itertools.combinations(sorted(attempts), 2):
            left = attempts[left_label]
            right = attempts[right_label]
            values: dict[str, object] = {}
            for field in (
                "lua_checksum", "scenario_checksum", "batch_job_checksum", "output_directory",
                "simulation", "official_final_score", "execution_fidelity", "runtime_execution",
            ):
                left_value = getattr(left, field)
                right_value = getattr(right, field)
                if left_value != right_value:
                    values[field] = {"left": left_value, "right": right_value}
            result[f"{left_label}::{right_label}"] = values
        return result
