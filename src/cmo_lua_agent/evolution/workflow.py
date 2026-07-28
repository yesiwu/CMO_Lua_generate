"""Deterministic Phase 9 orchestration over injected Phase 6/7/8 adapters."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Callable, Protocol

from cmo_lua_agent.evolution.campaign_store import CampaignStore
from cmo_lua_agent.evolution.champion_selection import ChampionSelectionPolicy
from cmo_lua_agent.evolution.cmo_lock import CmoInstanceLock
from cmo_lua_agent.evolution.models import (
    CampaignExecutionMode, CandidateScore, EvolutionCampaignSpec, OperationKind, Phase6GenerationArtifact,
)
from cmo_lua_agent.evolution.stop_policy import StopPolicy


class Phase6Adapter(Protocol):
    def run(self, *, generation_index: int, rolling_baseline_id: str, **kwargs: object) -> tuple[CandidateScore, tuple[CandidateScore, ...]]: ...


class Phase7Adapter(Protocol):
    def run(self, *, generation_index: int, **kwargs: object) -> tuple[dict[str, object], ...]: ...


class Phase8Adapter(Protocol):
    def run(self, *, generation_index: int, **kwargs: object) -> str: ...


@dataclass(frozen=True, slots=True)
class CampaignResult:
    campaign_id: str
    anchor_score: int
    rolling_scores: tuple[int, ...]
    global_best_score: int
    completed_generations: int
    stopped_early: bool = False


class EvolutionWorkflow:
    def __init__(self, *, phase6: Phase6Adapter, phase7: Phase7Adapter, phase8: Phase8Adapter,
                 stop_requested: Callable[[], bool] | None = None) -> None:
        self._phase6 = phase6
        self._phase7 = phase7
        self._phase8 = phase8
        self._stop_requested = stop_requested or (lambda: False)

    def run(self, spec: EvolutionCampaignSpec, *, root: Path) -> CampaignResult:
        root = Path(root).resolve()
        store = CampaignStore(root)
        root.mkdir(parents=True, exist_ok=True)
        provenance = "phase9_fake_fixture" if spec.execution_mode is CampaignExecutionMode.FAKE_FIXTURE else "formal_renderer"
        self._write_json(root / "campaign-spec.json", {"checksum": spec.checksum, "execution_mode": spec.execution_mode.value, "artifact_provenance": provenance})
        lock = CmoInstanceLock(root.parent / ".cmo-instance.lock", campaign_id=spec.campaign_id) if spec.execution_mode is CampaignExecutionMode.PRODUCTION_CMO else None
        if lock is not None:
            lock.acquire()
        try:
            return self._run_locked(spec, root, store, provenance)
        finally:
            if lock is not None:
                lock.release()

    def _run_locked(self, spec: EvolutionCampaignSpec, root: Path, store: CampaignStore, provenance: str) -> CampaignResult:
        available_cmo = spec.budget.max_cmo_runs
        rolling_id, rolling_score, anchor_score = "baseline", 0, 0
        history: list[int] = []
        stopped_early = False
        for generation_index in range(spec.budget.max_generations):
            if self._stop_requested():
                stopped_early = True
                break
            if not spec.budget.can_reserve_generation(available_cmo_runs=available_cmo):
                break
            phase6_operation = store.prepare_operation(generation_index=generation_index, kind=OperationKind.PHASE6, input_checksum=spec.contract_checksum)
            store.mark_operation_started(phase6_operation.operation_id)
            phase6_result = self._phase6.run(generation_index=generation_index, rolling_baseline_id=rolling_id)
            if isinstance(phase6_result, Phase6GenerationArtifact):
                baseline, candidates = phase6_result.rolling_baseline, phase6_result.candidates
                actual_attempts = phase6_result.cmo_attempts
            else:
                baseline, candidates = phase6_result
                actual_attempts = 5
            if actual_attempts > spec.budget.required_cmo_attempts_per_generation:
                raise RuntimeError("phase6_exceeded_reserved_cmo_budget")
            available_cmo -= actual_attempts
            generation = root / "generations" / f"generation_{generation_index:03d}"
            generation.mkdir(parents=True, exist_ok=True)
            phase6_ref = generation / "phase6-ref.json"
            self._write_json(phase6_ref, {"input_checksum": spec.contract_checksum, "baseline": baseline.candidate_id, "candidates": [item.candidate_id for item in candidates]})
            store.reconcile_operation(phase6_operation.operation_id, phase6_ref)
            # A stop after Phase 6 preserves evidence but deliberately skips
            # ranking, learning, and champion changes for this partial generation.
            if self._stop_requested():
                stopped_early = True
                break
            decision = ChampionSelectionPolicy(minimum_improvement_delta=spec.minimum_improvement_delta).select(rolling_baseline=baseline, candidates=candidates)
            if decision.improved:
                rolling_id, rolling_score = decision.selected_champion_id, decision.selected_score
            history.append(rolling_score)
            self._append_jsonl(root / "lineage.jsonl", {"generation_index": generation_index, "selected_champion_id": decision.selected_champion_id, "rolling_baseline_id": baseline.candidate_id, "artifact_provenance": provenance})
            phase7_operation = store.prepare_operation(generation_index=generation_index, kind=OperationKind.PHASE7, input_checksum=spec.contract_checksum)
            store.mark_operation_started(phase7_operation.operation_id)
            self._phase7.run(generation_index=generation_index)
            phase7_ref = generation / "phase7-ref.json"
            self._write_json(phase7_ref, {"input_checksum": spec.contract_checksum, "artifact_provenance": provenance})
            store.reconcile_operation(phase7_operation.operation_id, phase7_ref)
            phase8_operation = store.prepare_operation(generation_index=generation_index, kind=OperationKind.PHASE8, input_checksum=spec.contract_checksum)
            store.mark_operation_started(phase8_operation.operation_id)
            phase8_result = self._phase8.run(generation_index=generation_index)
            phase8_ref = generation / "phase8-ref.json"
            self._write_json(phase8_ref, {"input_checksum": spec.contract_checksum, "result": phase8_result, "artifact_provenance": provenance})
            store.reconcile_operation(phase8_operation.operation_id, phase8_ref)
        result = CampaignResult(spec.campaign_id, anchor_score, tuple(history), max(history, default=anchor_score), len(history), stopped_early)
        self._write_json(root / "campaign-result.json", {"campaign_id": result.campaign_id, "anchor_score": result.anchor_score, "rolling_scores": list(result.rolling_scores), "global_best_score": result.global_best_score, "completed_generations": result.completed_generations, "stopped_early": result.stopped_early, "artifact_provenance": provenance})
        return result

    @staticmethod
    def _write_json(path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8", newline="\n")

    @staticmethod
    def _append_jsonl(path: Path, value: object) -> None:
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
