"""Production generation orchestration over a frozen candidate set."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from cmo_lua_agent.evolution.control_plane import (
    GenerationExecutionResult,
    GenerationWorkerContext,
)
from cmo_lua_agent.evolution.production_models import FrozenCandidateSet
from cmo_lua_agent.evolution.production_preview import FrozenCandidateSetProvider
from cmo_lua_agent.evolution.generation_completion_gate import GenerationCompletionGate
from cmo_lua_agent.evolution.formal_adapters import FormalPhase6Adapter
from cmo_lua_agent.optimization.candidate_comparator import CandidateComparator
from cmo_lua_agent.optimization.candidate_models import (
    CandidateFailureReason,
    CandidateOutcome,
    CandidateState,
)
from cmo_lua_agent.optimization.phase6_models import EvaluationIdentity


class ProductionGenerationExecutor:
    """Run baseline and four frozen candidates, then Phase 7 and Phase 8."""

    def __init__(
        self,
        *,
        package,
        candidate_evaluator,
        phase7_adapter,
        phase8_adapter,
        champion_policy,
        stop_policy,
        frozen_provider: FrozenCandidateSetProvider | None = None,
        artifact_provenance: str = "formal_renderer",
        candidate_comparator: CandidateComparator | None = None,
    ) -> None:
        self._package = package
        self._evaluate = candidate_evaluator
        self._phase7 = phase7_adapter
        self._phase8 = phase8_adapter
        self._champion = champion_policy
        self._stop = stop_policy
        self._frozen = frozen_provider or FrozenCandidateSetProvider()
        self._artifact_provenance = artifact_provenance
        self._comparator = candidate_comparator or CandidateComparator()
        self._completion_gate = GenerationCompletionGate()

    def run(self, context: GenerationWorkerContext) -> GenerationExecutionResult:
        preview = context.preview
        frozen_path = Path(preview.frozen_candidate_set_ref)
        if not frozen_path.is_file():
            raise ValueError("frozen_candidate_set_missing")
        frozen = FrozenCandidateSet.from_dict(
            json.loads(frozen_path.read_text(encoding="utf-8"))
        )
        if (
            frozen.campaign_id != context.spec.campaign_id
            or frozen.generation_index != preview.generation_index
            or frozen.preview_revision != preview.preview_revision
            or frozen.candidate_set_checksum != preview.candidate_set_checksum
            or frozen.baseline_checksum != preview.baseline_checksum
        ):
            raise ValueError("frozen_candidate_set_preview_mismatch")
        baseline, candidates = self._frozen.load(frozen)
        ordered = (("baseline", baseline), *candidates)
        generation_root = (
            context.campaign_root
            / "generations"
            / f"generation_{preview.generation_index:03d}"
        )
        phase6_root = generation_root / "phase6"
        outcomes: list[dict[str, Any]] = []
        for candidate_id, strategy in ordered:
            existing_path = phase6_root / self.candidate_root_name(candidate_id) / "candidate_outcome.json"
            if existing_path.is_file():
                existing = json.loads(existing_path.read_text(encoding="utf-8"))
                if self._completion_gate.evaluate(
                    expected_candidate_ids=(candidate_id,),
                    outcomes=(existing,),
                ).complete:
                    outcomes.append(existing)
                    continue
            action = context.control_action()
            if action == "stop":
                self._atomic_json(
                    generation_root / "cancelled-incomplete.json",
                    {
                        "status": "cancelled_incomplete",
                        "completed_candidate_ids": [
                            item["candidate_id"] for item in outcomes
                        ],
                    },
                )
                return GenerationExecutionResult.cancelled_incomplete(
                    "manual_stop_requested"
                )
            if action == "pause":
                return GenerationExecutionResult.paused("manual_pause_requested")
            candidate_dir = phase6_root / self.candidate_root_name(candidate_id)
            try:
                outcome = self._evaluate(
                    candidate_id=candidate_id,
                    strategy=strategy,
                    candidate_dir=candidate_dir,
                    generation_index=preview.generation_index,
                    context=context,
                    package=self._package,
                )
            except ValueError as exc:
                if str(exc) in {
                    "generation_approval_expired",
                    "generation_approval_required",
                    "generation_approval_cap_exhausted",
                    "attempt_slot_not_available",
                }:
                    self._write_awaiting_approval(
                        generation_root=generation_root,
                        outcomes=outcomes,
                        pending_candidate_id=candidate_id,
                        reason=str(exc),
                    )
                    return GenerationExecutionResult.awaiting_approval(str(exc))
                raise
            normalized_outcome = {
                **dict(outcome),
                "artifact_provenance": self._artifact_provenance,
            }
            self._atomic_json(
                candidate_dir / "candidate_outcome.json",
                normalized_outcome,
            )
            outcomes.append(normalized_outcome)
            boundary_action = context.control_action()
            if boundary_action == "stop":
                self._atomic_json(
                    generation_root / "cancelled-incomplete.json",
                    {
                        "status": "cancelled_incomplete",
                        "completed_candidate_ids": [
                            item["candidate_id"] for item in outcomes
                        ],
                    },
                )
                return GenerationExecutionResult.cancelled_incomplete(
                    "manual_stop_requested"
                )
            if boundary_action == "pause":
                return GenerationExecutionResult.paused(
                    "manual_pause_requested"
                )
        completion = self._completion_gate.evaluate(
            expected_candidate_ids=tuple(candidate_id for candidate_id, _ in ordered),
            outcomes=outcomes,
        )
        if not completion.complete:
            incomplete = {
                "status": "awaiting_approval",
                "code": completion.code,
                "pending_candidate_ids": list(completion.pending_candidate_ids),
                "completed_candidate_ids": [item["candidate_id"] for item in outcomes],
            }
            self._atomic_json(generation_root / "generation-incomplete.json", incomplete)
            self._atomic_json(generation_root / "awaiting-approval.json", incomplete)
            return GenerationExecutionResult.paused(completion.code)

        strategy_by_id = {candidate_id: strategy for candidate_id, strategy in ordered}
        leaderboard = self._build_leaderboard(
            outcomes,
            phase6_root,
            strategy_by_id,
        )
        ranks = {
            item["candidate_id"]: item["rank"] for item in leaderboard
        }
        outcomes = [
            {**item, "rank": ranks.get(item["candidate_id"])}
            for item in outcomes
        ]
        for item in outcomes:
            self._atomic_json(
                phase6_root
                / self.candidate_root_name(str(item["candidate_id"]))
                / "candidate_outcome.json",
                item,
            )
        self._atomic_json(phase6_root / "leaderboard.json", leaderboard)
        outcome_paths = [
            str(
                phase6_root
                / self.candidate_root_name(item["candidate_id"])
                / "candidate_outcome.json"
            )
            for item in outcomes
        ]
        strategy_diff = {
            str(item["candidate_id"]): tuple(
                next(
                    (
                        diff.get("changed_paths", ())
                        for diff in preview.strategy_diffs
                        if diff.get("candidate_id") == item["candidate_id"]
                    ),
                    (),
                )
            )
            for item in outcomes
            if item["candidate_id"] != "baseline"
        }
        self._atomic_json(
            phase6_root / "generation_result.json",
            {
                "optimization_id": (
                    f"{context.spec.campaign_id}_g{preview.generation_index:03d}"
                ),
                "workflow_completed": True,
                "baseline_outcome_path": outcome_paths[0],
                "candidate_outcome_paths": outcome_paths[1:],
            },
        )
        self._atomic_json(phase6_root / "strategy_diff.json", strategy_diff)
        phase7_result = self._phase7.run(
            generation_index=preview.generation_index,
            optimization_dir=phase6_root,
            outcomes=tuple(outcomes),
        )
        phase8_result = self._phase8.run(
            generation_index=preview.generation_index,
            phase7_result=phase7_result,
        )
        if phase8_result.get("status") == "pending_regression_failed":
            return GenerationExecutionResult.paused("require_review")
        scores = tuple(FormalPhase6Adapter._score(item) for item in outcomes)
        champion = self._champion.select(
            rolling_baseline=scores[0],
            candidates=scores[1:],
        )
        stop = self._stop.evaluate(
            require_human_review=(
                phase8_result.get("status") == "pending_regression_failed"
            ),
            max_generations_reached=(
                preview.generation_index + 1 >= context.spec.budget.max_generations
            ),
        )
        result = {
            "artifact_provenance": self._artifact_provenance,
            "candidate_order": [item[0] for item in ordered],
            "outcomes": outcomes,
            "leaderboard": leaderboard,
            "phase7": phase7_result,
            "phase8": phase8_result,
            "champion_decision": {
                "best_candidate_id": champion.best_candidate_id,
                "selected_champion_id": champion.selected_champion_id,
                "selected_score": champion.selected_score,
                "improved": champion.improved,
                "exclusion_reasons": champion.exclusion_reasons,
            },
            "stop_decision": {
                "should_stop": stop.should_stop,
                "reason": stop.reason.value,
                "details": stop.details,
            },
            "process_restart_recovery": "not_validated",
        }
        self._atomic_json(generation_root / "generation-result.json", result)
        return GenerationExecutionResult.completed(result)

    @staticmethod
    def _write_awaiting_approval(
        *,
        generation_root: Path,
        outcomes: list[dict[str, Any]],
        pending_candidate_id: str,
        reason: str,
    ) -> None:
        payload = {
            "status": "awaiting_approval",
            "code": reason,
            "pending_candidate_ids": [pending_candidate_id],
            "completed_candidate_ids": [item["candidate_id"] for item in outcomes],
        }
        ProductionGenerationExecutor._atomic_json(
            generation_root / "generation-incomplete.json",
            payload,
        )
        ProductionGenerationExecutor._atomic_json(
            generation_root / "awaiting-approval.json",
            payload,
        )

    @staticmethod
    def candidate_root_name(candidate_id: str) -> str:
        return candidate_id if candidate_id.startswith("candidate_") else f"candidate_{candidate_id}"

    @staticmethod
    def _rank(outcomes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        eligible = [
            item
            for item in outcomes
            if item.get("execution_success")
            and item.get("semantic_valid")
            and item.get("scoreable")
            and item.get("native_score") is not None
            and item.get("artifact_provenance") in {
                "formal_renderer",
                "test_fixture",
            }
        ]
        ranked = sorted(
            eligible,
            key=lambda item: (-int(item["native_score"]), item["candidate_id"]),
        )
        ranks = {
            item["candidate_id"]: index + 1 for index, item in enumerate(ranked)
        }
        return [
            {
                "candidate_id": item["candidate_id"],
                "raw_score": item.get("native_score"),
                "rank": ranks.get(item["candidate_id"]),
            }
            for item in outcomes
        ]

    def _build_leaderboard(
        self,
        outcomes: list[dict[str, Any]],
        phase6_root: Path,
        strategy_by_id: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if self._artifact_provenance == "test_fixture":
            return self._rank(outcomes)
        identity = EvaluationIdentity(
            scenario_checksum=self._package.checksums["scenario_definition_derived"],
            score_spec_checksum=(
                self._package.native_score_compilation.score_spec_checksum
            ),
            score_fragment_checksum=(
                self._package.native_score_compilation.fragment_checksum
            ),
            runtime_version=self._package.runtime.runtime_version,
            scoring_side_id=(
                self._package.native_score_compilation.score_spec.rules[
                    0
                ].score_side_id
            ),
        )
        values = []
        for index, item in enumerate(outcomes):
            candidate_id = str(item["candidate_id"])
            candidate_dir = (
                phase6_root / self.candidate_root_name(candidate_id)
            )
            failure_value = str(
                item.get("failure_reason", CandidateFailureReason.COMPLETED.value)
            )
            try:
                failure_reason = CandidateFailureReason(failure_value)
            except ValueError:
                failure_reason = CandidateFailureReason.INTERNAL_WORKFLOW_ERROR
            final_state_value = str(
                item.get(
                    "final_state",
                    (
                        CandidateState.COMPLETED.value
                        if item.get("success")
                        else CandidateState.FAILED.value
                    ),
                )
            )
            try:
                final_state = CandidateState(final_state_value)
            except ValueError:
                final_state = CandidateState.FAILED
            outcome = CandidateOutcome(
                candidate_id=candidate_id,
                generation_index=int(item.get("generation_index", 0)),
                strategy_spec=strategy_by_id[candidate_id],
                success=bool(item.get("success")),
                executable=bool(item.get("executable")),
                semantic_valid=bool(item.get("semantic_valid")),
                scoreable=bool(item.get("scoreable")),
                original_lua_path=(
                    Path(str(item["original_lua_path"]))
                    if item.get("original_lua_path")
                    else None
                ),
                final_lua_path=(
                    Path(str(item["final_lua_path"]))
                    if item.get("final_lua_path")
                    else None
                ),
                repair_count=int(item.get("repair_count", 0)),
                execution_attempts=int(item.get("execution_attempts", 0)),
                repair_invocations=int(item.get("repair_invocations", 0)),
                repairs_applied=int(item.get("repairs_applied", 0)),
                combat_metrics=None,
                reward_breakdown=None,
                failed_stage=None,
                failure_reason=failure_reason,
                final_state=final_state,
                candidate_dir=candidate_dir,
                trajectory_path=candidate_dir / "trajectory.jsonl",
                artifact_provenance=str(item.get("artifact_provenance", "")),
                scenario_reset=item.get("scenario_reset"),
                execution_success=bool(item.get("execution_success")),
                native_score=item.get("native_score"),
                score_source=item.get("score_source"),
            )
            values.append((outcome, identity, index == 0))
        return [
            entry.to_dict()
            for entry in self._comparator.compare(outcomes=values)
        ]


    @staticmethod
    def _atomic_json(path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=str)
            + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
