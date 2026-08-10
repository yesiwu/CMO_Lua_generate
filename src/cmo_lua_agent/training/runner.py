"""Deterministic scheduler for a persistent multi-generation training workflow."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol

from cmo_lua_agent.training.models import (
    Phase8Progress,
    Phase8Status,
    TrainingAction,
    TrainingStage,
    TrainingState,
    TrainingStatus,
)
from cmo_lua_agent.training.store import TrainingStore
from cmo_lua_agent.training.failures import FailureClassifier, FailureKind
from cmo_lua_agent.training.reporting import TrainingReportWriter


class CampaignDriver(Protocol):
    """The small Campaign surface used by the TrainingRunner."""

    def prepare(self, request) -> str: ...
    def preview(self, campaign_id: str, generation_index: int) -> None: ...
    def execute(self, campaign_id: str, generation_index: int) -> None: ...
    def inspect_generation(self, campaign_id: str, generation_index: int) -> dict[str, object]: ...
    def pause(self, campaign_id: str) -> None: ...
    def resume(self, campaign_id: str) -> None: ...
    def stop(self, campaign_id: str) -> None: ...
    def reconcile(self, campaign_id: str) -> dict[str, object]: ...
    def run_phase8(self, campaign_id: str, completed_generations: tuple[int, ...]) -> dict[str, object]: ...


class TrainingRunner:
    """Advance exactly one persisted action at a time, without approval callbacks."""

    def __init__(
        self,
        store: TrainingStore,
        driver: CampaignDriver,
        *,
        repair_coordinator: object | None = None,
    ) -> None:
        self._store = store
        self._driver = driver
        self._repair = repair_coordinator
        self._failures = FailureClassifier()

    def run(self) -> TrainingState:
        """Run all immediately schedulable generation actions under one workflow lock."""
        with self._store.lock():
            while True:
                before = self._store.load_state()
                after = self.run_once()
                if after.action is TrainingAction.IDLE or after == before or self._retry_pending(after):
                    return after

    def run_once(self) -> TrainingState:
        try:
            state = self._run_once()
            # A successful persisted action proves that the retryable provider
            # output was replaced.  Do not carry its backoff into later phases.
            if self._retry_pending(state):
                runner = {key: value for key, value in state.runner.items() if key != "retry"}
                return self._store.transition(runner=runner)
            return state
        except Exception as exc:
            record = self._failures.classify(exc)
            self._store.append_event({
                "event": "workflow_failure",
                "kind": record.kind.value,
                "error_type": record.error_type,
                "message": record.message,
            })
            if self._is_retryable_generation_failure(record):
                # Keep the exact persisted action so the background runtime
                # can retry it after a short wait without user intervention.
                # A CandidateProposalError means the model emitted an invalid
                # candidate; the next Preview regenerates that proposal rather
                # than requiring a user to intervene.
                state = self._store.load_state()
                return self._store.transition(runner=self._next_retry(state, record))
            if record.kind is FailureKind.CODE and self._repair is not None:
                self._store.transition(status=TrainingStatus.REPAIRING)
                result = self._repair.repair(
                    workflow_id=self._store.load_state().workflow_id,
                    record=record,
                    test_command="python -m pytest src/cmo_lua_agent/tests/training -q",
                )
                if getattr(result, "succeeded", False):
                    return self._store.transition(
                        status=TrainingStatus.RUNNING,
                        last_good_commit=getattr(result, "commit_id", None),
                    )
                return self._store.transition(status=TrainingStatus.FAILED, action=TrainingAction.IDLE)
            raise

    @staticmethod
    def _is_retryable_generation_failure(record) -> bool:
        return record.kind is FailureKind.TRANSIENT or (
            record.kind is FailureKind.BUSINESS
            and record.error_type == "CandidateProposalError"
        )

    @staticmethod
    def _retry_pending(state: TrainingState) -> bool:
        return isinstance(state.runner.get("retry"), dict)

    @staticmethod
    def _next_retry(state: TrainingState, record) -> dict[str, object]:
        previous = state.runner.get("retry")
        prior_count = previous.get("consecutive_failures", 0) if isinstance(previous, dict) else 0
        count = int(prior_count) + 1
        delay_seconds = min(5 * (2 ** (count - 1)), 60)
        next_retry_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)
        return {
            **state.runner,
            "retry": {
                "kind": record.kind.value,
                "error_type": record.error_type,
                "message": record.message,
                "consecutive_failures": count,
                "next_retry_at": next_retry_at.isoformat(),
            },
        }

    def _run_once(self) -> TrainingState:
        request = self._store.load_request()
        state = self._store.load_state()
        if state.status in {TrainingStatus.PAUSED, TrainingStatus.STOPPED, TrainingStatus.FAILED}:
            return state
        if state.campaign_id is None:
            campaign_id = self._driver.prepare(request)
            self._store.append_event({"event": "campaign_prepared", "campaign_id": campaign_id})
            return self._store.transition(
                campaign_id=campaign_id,
                status=TrainingStatus.RUNNING,
                stage=TrainingStage.EVOLUTION,
                action=TrainingAction.PREVIEW,
            )

        if request.generation_count is None:
            raise ValueError("fixed_generation_count_required")
        if len(state.completed_generations) >= request.generation_count:
            if state.phase8.status is Phase8Status.NOT_STARTED:
                result = self._driver.run_phase8(
                    state.campaign_id,
                    state.completed_generations,
                )
                phase8_job_id = str(result.get("job_id") or result.get("phase8_run_id") or "")
                if not self._phase8_finished(result):
                    return self._store.transition(
                        status=TrainingStatus.FAILED,
                        stage=TrainingStage.PHASE8,
                        action=TrainingAction.IDLE,
                        phase8=Phase8Progress(Phase8Status.FAILED, phase8_job_id),
                    )
                self._store.append_event({"event": "phase8_completed", "campaign_id": state.campaign_id})
                completed = self._store.transition(
                    status=TrainingStatus.COMPLETED,
                    stage=TrainingStage.REPORT,
                    action=TrainingAction.IDLE,
                    phase8=Phase8Progress(Phase8Status.COMPLETED, phase8_job_id),
                )
                self._write_reports(completed)
                return completed
            completed = self._store.transition(
                status=TrainingStatus.COMPLETED,
                stage=TrainingStage.REPORT,
                action=TrainingAction.IDLE,
            )
            self._write_reports(completed)
            return completed

        generation_index = state.current_generation
        if state.action in {TrainingAction.VALIDATE_INPUT, TrainingAction.PREVIEW}:
            self._driver.preview(state.campaign_id, generation_index)
            self._store.append_event({"event": "generation_previewed", "generation_index": generation_index})
            return self._store.transition(
                status=TrainingStatus.RUNNING,
                stage=TrainingStage.EVOLUTION,
                action=TrainingAction.EXECUTE,
            )
        if state.action is TrainingAction.EXECUTE:
            self._driver.execute(state.campaign_id, generation_index)
            self._store.append_event({"event": "generation_executed", "generation_index": generation_index})
            return self._store.transition(action=TrainingAction.SUMMARIZE)
        if state.action is TrainingAction.SUMMARIZE:
            inspected = self._driver.inspect_generation(state.campaign_id, generation_index)
            if self._worker_failed(inspected):
                return self._mark_worker_failed(state, generation_index, inspected)
            if inspected.get("status") != "completed":
                return self._store.transition(action=TrainingAction.WAIT_WORKER)
            completed = tuple(sorted((*state.completed_generations, generation_index)))
            self._store.append_event({"event": "generation_completed", "generation_index": generation_index})
            return self._store.transition(
                completed_generations=completed,
                current_generation=generation_index + 1,
                action=TrainingAction.PREVIEW,
            )
        if state.action is TrainingAction.WAIT_WORKER:
            inspected = self._driver.inspect_generation(state.campaign_id, generation_index)
            if self._worker_failed(inspected):
                return self._mark_worker_failed(state, generation_index, inspected)
            if inspected.get("status") == "completed":
                return self._store.transition(action=TrainingAction.SUMMARIZE)
            return state
        return state

    def _write_reports(self, state: TrainingState) -> None:
        TrainingReportWriter(self._store).write(state)

    @staticmethod
    def _phase8_finished(result: dict[str, object]) -> bool:
        return result.get("status") in {"completed", "NO_PROMOTABLE_EXPERIENCE", "pending_review"}

    @staticmethod
    def _worker_failed(inspected: dict[str, object]) -> bool:
        return str(inspected.get("status", "")).lower() in {
            "failed",
            "cancelled_incomplete",
        }

    def _mark_worker_failed(
        self,
        state: TrainingState,
        generation_index: int,
        inspected: dict[str, object],
    ) -> TrainingState:
        self._store.append_event({
            "event": "generation_worker_failed",
            "generation_index": generation_index,
            "worker_status": inspected.get("status"),
        })
        return self._store.transition(
            status=TrainingStatus.FAILED,
            action=TrainingAction.IDLE,
        )

    def reconcile(self) -> TrainingState:
        state = self._store.load_state()
        if state.campaign_id is not None:
            self._driver.reconcile(state.campaign_id)
            self._store.append_event({"event": "campaign_reconciled", "campaign_id": state.campaign_id})
        return self._store.load_state()

    def pause(self) -> TrainingState:
        state = self._store.load_state()
        if state.campaign_id is not None and state.status is not TrainingStatus.PAUSED:
            self._driver.pause(state.campaign_id)
            self._store.append_event({"event": "workflow_paused", "campaign_id": state.campaign_id})
        return self._store.transition(status=TrainingStatus.PAUSED)

    def resume(self) -> TrainingState:
        state = self._store.load_state()
        if state.status is not TrainingStatus.PAUSED:
            return state
        if state.campaign_id is not None:
            self._driver.reconcile(state.campaign_id)
            self._driver.resume(state.campaign_id)
            self._store.append_event({"event": "workflow_resumed", "campaign_id": state.campaign_id})
        return self._store.transition(status=TrainingStatus.RUNNING)

    def stop(self) -> TrainingState:
        state = self._store.load_state()
        if state.status is TrainingStatus.STOPPED:
            return state
        if state.campaign_id is not None:
            self._driver.stop(state.campaign_id)
            self._store.append_event({"event": "workflow_stopped", "campaign_id": state.campaign_id})
        return self._store.transition(status=TrainingStatus.STOPPED, action=TrainingAction.IDLE)
