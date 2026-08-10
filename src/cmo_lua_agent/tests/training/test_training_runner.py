from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from cmo_lua_agent.training.models import (
    TrainingAction,
    Phase8Progress,
    Phase8Status,
    TrainingRequest,
    TrainingStage,
    TrainingStatus,
)
from cmo_lua_agent.training.runner import TrainingRunner
from cmo_lua_agent.training.runtime import ProductionCampaignDriver
from cmo_lua_agent.training.store import TrainingStore
from cmo_lua_agent.evolution.production_service import ProductionEvolutionCampaignService
from cmo_lua_agent.optimization.proposal_models import CandidateProposalError, ProposalContractError


class FakeCampaignDriver:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def prepare(self, request: TrainingRequest) -> str:
        self.calls.append("prepare")
        return f"{request.workflow_id}-campaign"

    def preview(self, campaign_id: str, generation_index: int) -> None:
        self.calls.append(f"preview:{generation_index}")

    def execute(self, campaign_id: str, generation_index: int) -> None:
        self.calls.append(f"execute:{generation_index}")

    def inspect_generation(self, campaign_id: str, generation_index: int) -> dict[str, str]:
        self.calls.append(f"inspect:{generation_index}")
        return {"status": "completed"}

    def pause(self, campaign_id: str) -> None:
        self.calls.append("pause")

    def resume(self, campaign_id: str) -> None:
        self.calls.append("resume")

    def stop(self, campaign_id: str) -> None:
        self.calls.append("stop")

    def reconcile(self, campaign_id: str) -> dict[str, str]:
        self.calls.append("reconcile")
        return {"status": "ok"}

    def run_phase8(self, campaign_id: str, completed_generations: tuple[int, ...]) -> dict[str, str]:
        self.calls.append(f"phase8:{','.join(map(str, completed_generations))}")
        return {"status": "completed", "job_id": f"{campaign_id}-phase8"}


def _store(tmp_path: Path, *, generations: int) -> TrainingStore:
    store = TrainingStore(tmp_path, "training-001")
    store.create(TrainingRequest.create(
        workflow_id="training-001",
        input_path="baseline/6v4/manual-template/6v4ScenarioIR_baseline_v3.json",
        objective="improve official red score",
        generation_count=generations,
    ))
    return store


def test_runner_completes_one_generation_without_user_approval(tmp_path: Path) -> None:
    driver = FakeCampaignDriver()

    state = TrainingRunner(_store(tmp_path, generations=1), driver).run()

    assert state.completed_generations == (0,)
    assert state.stage is TrainingStage.REPORT
    assert state.action is TrainingAction.IDLE
    assert state.status is TrainingStatus.COMPLETED
    assert state.phase8 == Phase8Progress(Phase8Status.COMPLETED, "training-001-campaign-phase8")
    assert driver.calls == ["prepare", "preview:0", "execute:0", "inspect:0", "phase8:0"]


def test_runner_completes_phase8_when_no_experience_is_promotable(tmp_path: Path) -> None:
    class NoPromotableExperienceDriver(FakeCampaignDriver):
        def run_phase8(self, campaign_id: str, completed_generations: tuple[int, ...]) -> dict[str, str]:
            self.calls.append(f"phase8:{','.join(map(str, completed_generations))}")
            return {"status": "NO_PROMOTABLE_EXPERIENCE", "phase8_run_id": "training-001_phase8"}

    state = TrainingRunner(_store(tmp_path, generations=1), NoPromotableExperienceDriver()).run()

    assert state.status is TrainingStatus.COMPLETED
    assert state.phase8 == Phase8Progress(Phase8Status.COMPLETED, "training-001_phase8")


def test_runner_keeps_workflow_failed_when_phase8_returns_a_failure(tmp_path: Path) -> None:
    class FailedPhase8Driver(FakeCampaignDriver):
        def run_phase8(self, campaign_id: str, completed_generations: tuple[int, ...]) -> dict[str, str]:
            self.calls.append(f"phase8:{','.join(map(str, completed_generations))}")
            return {"status": "failed"}

    state = TrainingRunner(_store(tmp_path, generations=1), FailedPhase8Driver()).run()

    assert state.status is TrainingStatus.FAILED
    assert state.stage is TrainingStage.PHASE8
    assert state.phase8 == Phase8Progress(Phase8Status.FAILED, "")


def test_runner_drives_requested_generations_without_count_budget(tmp_path: Path) -> None:
    driver = FakeCampaignDriver()

    state = TrainingRunner(_store(tmp_path, generations=3), driver).run()

    assert state.status is TrainingStatus.COMPLETED
    assert state.completed_generations == (0, 1, 2)
    assert driver.calls == [
        "prepare",
        "preview:0", "execute:0", "inspect:0",
        "preview:1", "execute:1", "inspect:1",
        "preview:2", "execute:2", "inspect:2",
        "phase8:0,1,2",
    ]


def test_production_driver_prepares_unbounded_deferred_phase8_campaign() -> None:
    calls: list[dict[str, object]] = []

    class Service:
        def prepare_training_campaign(self, **kwargs):
            calls.append(kwargs)
            return {"campaign_id": kwargs["campaign_id"]}

    request = TrainingRequest.create(
        workflow_id="training-001",
        input_path="baseline/6v4/manual-template/6v4ScenarioIR_baseline_v3.json",
        objective="improve official red score",
        generation_count=7,
    )

    campaign_id = ProductionCampaignDriver(Service()).prepare(request)

    assert campaign_id == "training-001-campaign"
    assert calls == [{
        "campaign_id": "training-001-campaign",
        "input_package_id": request.input_path,
        "generation_objective": request.objective,
        "generation_count": 7,
    }]


def test_production_service_defers_phase8_for_training_campaigns() -> None:
    calls: list[dict[str, object]] = []

    class Service(ProductionEvolutionCampaignService):
        def prepare_campaign_request(self, **kwargs):
            calls.append(kwargs)
            return {"campaign_id": kwargs["campaign_id"]}

    service = object.__new__(Service)
    service.prepare_training_campaign(
        campaign_id="training-001-campaign",
        input_package_id="scenario.json",
        generation_objective="improve",
        generation_count=3,
    )

    assert calls[0]["phase8_mode"] == "after_all_generations"


def test_production_driver_regenerates_a_failed_preview_after_restart() -> None:
    calls: list[dict[str, object]] = []

    class Service:
        def preview_generation(self, **kwargs):
            calls.append(kwargs)
            if not kwargs.get("regenerate_preview"):
                raise ValueError("preview_regeneration_required")

    ProductionCampaignDriver(Service()).preview("training-001-campaign", 0)

    assert calls == [
        {"campaign_id": "training-001-campaign", "generation_index": 0},
        {"campaign_id": "training-001-campaign", "generation_index": 0, "regenerate_preview": True},
    ]


def test_runner_pause_resume_and_stop_at_safe_boundaries(tmp_path: Path) -> None:
    driver = FakeCampaignDriver()
    runner = TrainingRunner(_store(tmp_path, generations=2), driver)
    runner.run_once()

    paused = runner.pause()
    assert paused.status is TrainingStatus.PAUSED
    assert driver.calls == ["prepare", "pause"]

    resumed = runner.resume()
    assert resumed.status is TrainingStatus.RUNNING
    assert resumed.action is TrainingAction.PREVIEW
    assert driver.calls == ["prepare", "pause", "reconcile", "resume"]

    stopped = runner.stop()
    assert stopped.status is TrainingStatus.STOPPED
    runner.stop()
    assert driver.calls == ["prepare", "pause", "reconcile", "resume", "stop"]


def test_restarted_runner_does_not_repeat_a_persisted_execute(tmp_path: Path) -> None:
    driver = FakeCampaignDriver()
    store = _store(tmp_path, generations=1)
    first = TrainingRunner(store, driver)
    first.run_once()
    first.run_once()
    first.run_once()

    recovered = TrainingRunner(store, driver)
    recovered.reconcile()
    state = recovered.run()

    assert state.completed_generations == (0,)
    assert driver.calls == [
        "prepare", "preview:0", "execute:0", "reconcile", "inspect:0", "phase8:0",
    ]


def test_runner_marks_code_failure_for_repair_without_repeating_action(tmp_path: Path) -> None:
    class BrokenDriver(FakeCampaignDriver):
        def prepare(self, request: TrainingRequest) -> str:
            raise ImportError("cannot import Worker")

    class Repairs:
        def repair(self, **kwargs):
            return SimpleNamespace(succeeded=False)

    runner = TrainingRunner(
        _store(tmp_path, generations=1),
        BrokenDriver(),
        repair_coordinator=Repairs(),
    )

    state = runner.run_once()

    assert state.status is TrainingStatus.FAILED


def test_runner_records_verified_repair_commit_before_retrying(tmp_path: Path) -> None:
    class BrokenDriver(FakeCampaignDriver):
        def prepare(self, request: TrainingRequest) -> str:
            raise ImportError("cannot import Worker")

    class Repairs:
        def repair(self, **kwargs):
            return SimpleNamespace(succeeded=True, commit_id="abc123")

    state = TrainingRunner(
        _store(tmp_path, generations=1),
        BrokenDriver(),
        repair_coordinator=Repairs(),
    ).run_once()

    assert state.status is TrainingStatus.RUNNING
    assert state.last_good_commit == "abc123"
    assert state.action is TrainingAction.VALIDATE_INPUT


def test_runner_leaves_transient_failure_runnable_for_the_background_runtime(tmp_path: Path) -> None:
    class UnavailableDriver(FakeCampaignDriver):
        def prepare(self, request: TrainingRequest) -> str:
            raise ConnectionError("Connection error.")

    store = _store(tmp_path, generations=1)
    state = TrainingRunner(store, UnavailableDriver()).run_once()

    assert state.status is TrainingStatus.CREATED
    assert state.action is TrainingAction.VALIDATE_INPUT
    retry = state.runner["retry"]
    assert retry["kind"] == "TRANSIENT"
    assert retry["consecutive_failures"] == 1
    assert retry["next_retry_at"]
    assert any('"kind": "TRANSIENT"' in line for line in (store.root / "journal.jsonl").read_text(encoding="utf-8").splitlines())


def test_runner_retries_a_failed_candidate_preview_by_regenerating_it(tmp_path: Path) -> None:
    class InvalidCandidateDriver(FakeCampaignDriver):
        def preview(self, campaign_id: str, generation_index: int) -> None:
            raise CandidateProposalError(
                candidate_id="candidate_02",
                stage="patch_repair",
                cause=ProposalContractError("strategy_rebuild_failed"),
            )

    store = _store(tmp_path, generations=1)
    runner = TrainingRunner(store, InvalidCandidateDriver())
    runner.run_once()  # prepare the campaign

    state = runner.run_once()

    assert state.status is TrainingStatus.RUNNING
    assert state.action is TrainingAction.PREVIEW
    retry = state.runner["retry"]
    assert retry["kind"] == "BUSINESS"
    assert retry["error_type"] == "CandidateProposalError"
    assert retry["consecutive_failures"] == 1


def test_runner_marks_a_failed_generation_worker_as_failed_instead_of_waiting_forever(tmp_path: Path) -> None:
    class FailedWorkerDriver(FakeCampaignDriver):
        def inspect_generation(self, _campaign_id: str, _generation_index: int) -> dict[str, str]:
            return {"status": "failed"}

    runner = TrainingRunner(_store(tmp_path, generations=1), FailedWorkerDriver())
    for _ in range(4):
        runner.run_once()

    state = runner.run_once()

    assert state.status is TrainingStatus.FAILED
    assert state.action is TrainingAction.IDLE
