"""冻结候选集的一代正式执行器。

由 EvolutionCampaignService 的 Worker 调用。输入是已经写盘的 FrozenCandidateSet；
执行 baseline 与候选评估、写入 Phase 6 Artifact，并在本代完成后调用 Phase 7。
它不重新调用策略 LLM，也不自行授权 CMO 或修改 Campaign 控制状态。
"""

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
    """执行一代冻结的 baseline/候选，并把结果交给既有排序与学习链路。

Phase 8 不在这里按候选或按代聚合；TrainingRunner 在所有 Generation 的正式结果
完成后统一调用它，避免 Experience 集合在聚合时继续变化。
    """

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
        # 执行身份由固定 slot 目录和 candidate_id 决定；Preview 中保留的 checksum
        # 用于审阅定位，不作为运行阻断条件，符合轻量化训练流程的设计。
        self._frozen = frozen_provider or FrozenCandidateSetProvider(
            verify_checksum_metadata=False,
        )
        self._artifact_provenance = artifact_provenance
        self._comparator = candidate_comparator or CandidateComparator()
        self._completion_gate = GenerationCompletionGate()

    def run(self, context: GenerationWorkerContext) -> GenerationExecutionResult:
        """执行一代并返回给 Worker 的标准化结果。

已完成且通过 CompletionGate 的候选会复用正式 Artifact；失败的外部 CMO 结果不复用，
以便修复外部条件后获得新的尝试。暂停、停止和授权过期会在候选安全边界返回，交给
Campaign Worker 持久化，而不是在 Executor 内猜测后续状态。
        """
        preview = context.preview
        frozen_path = Path(preview.frozen_candidate_set_ref)
        if not frozen_path.is_file():
            raise ValueError("frozen_candidate_set_missing")
        frozen = FrozenCandidateSet.from_dict(
            json.loads(frozen_path.read_text(encoding="utf-8")),
            verify_checksums=False,
        )
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
                # 仅复用已成功且完整的正式 Artifact。CMO 进程失败常由外部条件导致，
                # 修复环境后必须重新尝试，不能把旧失败永久视作该候选的最终结论。
                if bool(existing.get("execution_success")) and self._completion_gate.evaluate(
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
        if context.spec.budget.max_comparative_learning_calls == 0:
            phase7_result = {"status": "not_run", "reason": "budget_disabled"}
        elif self._completed_phase7_result(phase6_root) is not None:
            phase7_result = self._completed_phase7_result(phase6_root)
        else:
            phase7_result = self._phase7.run(
                generation_index=preview.generation_index,
                optimization_dir=phase6_root,
                outcomes=tuple(outcomes),
            )
        if getattr(context.spec, "phase8_mode", "per_generation") == "after_all_generations":
            phase8_result = {"status": "not_run", "reason": "deferred_to_training_phase8"}
        elif context.spec.budget.max_skill_author_calls == 0:
            phase8_result = {"status": "not_run", "reason": "budget_disabled"}
        elif phase7_result.get("status") != "completed":
            phase8_result = {"status": "not_run", "reason": "phase7_not_completed"}
        else:
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
            and item.get("scoreable")
            and isinstance(item.get("native_score"), (int, float))
            and not isinstance(item.get("native_score"), bool)
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
        # Ranking consumes the five slot outcomes directly.  Contract hashes
        # remain on disk for audit but are not an execution or ranking gate.
        return self._rank(outcomes)

    @staticmethod
    def _completed_phase7_result(phase6_root: Path) -> dict[str, Any] | None:
        """Reuse a complete generation-level learning result during recovery."""
        learning_root = phase6_root / "learning"
        required = (
            learning_root / "candidate-learning-views.json",
            learning_root / "comparative-analysis.json",
            learning_root / "experience-candidates.json",
        )
        if not all(path.is_file() for path in required):
            return None
        candidates = json.loads(required[2].read_text(encoding="utf-8"))
        if not isinstance(candidates, list):
            return None
        return {
            "status": "completed",
            "reused": True,
            "experience_candidate_count": len(candidates),
        }


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
