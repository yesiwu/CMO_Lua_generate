from __future__ import annotations

from pathlib import Path

from cmo_lua_agent.training.models import (
    TrainingAction,
    TrainingRequest,
    TrainingStage,
    TrainingStatus,
)
from cmo_lua_agent.training.runner import TrainingRunner
from cmo_lua_agent.training.runtime import ProductionCampaignDriver
from cmo_lua_agent.training.store import TrainingStore


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
    assert state.stage is TrainingStage.PHASE8
    assert state.action is TrainingAction.IDLE
    assert driver.calls == ["prepare", "preview:0", "execute:0", "inspect:0"]


def test_runner_drives_requested_generations_without_count_budget(tmp_path: Path) -> None:
    driver = FakeCampaignDriver()

    state = TrainingRunner(_store(tmp_path, generations=3), driver).run()

    assert state.status is TrainingStatus.RUNNING
    assert state.completed_generations == (0, 1, 2)
    assert driver.calls == [
        "prepare",
        "preview:0", "execute:0", "inspect:0",
        "preview:1", "execute:1", "inspect:1",
        "preview:2", "execute:2", "inspect:2",
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
