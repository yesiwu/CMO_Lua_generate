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
from cmo_lua_agent.training.recovery import ErrorEnvelope, RecoveryDecision, RecoveryRouter
from cmo_lua_agent.training.repair import RepairSnapshot
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


def test_runner_writes_final_reports_for_a_completed_workflow(tmp_path: Path) -> None:
    store = _store(tmp_path, generations=1)

    TrainingRunner(store, FakeCampaignDriver()).run()

    assert (store.root / "training-report.md").read_text(encoding="utf-8")
    assert (store.root / "skill-generation-report.md").read_text(encoding="utf-8")
    assert not (store.root / "code-repair-report.md").exists()


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

    assert state.status is TrainingStatus.RUNNING
    assert state.action is TrainingAction.VALIDATE_INPUT
    assert state.runner["recovery"]["attempts"] == 1


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
    assert state.runner["recovery"]["action"] == "RETRY"
    assert state.runner["recovery"]["attempts"] == 1
    assert any('"kind": "TRANSIENT"' in line for line in (store.root / "journal.jsonl").read_text(encoding="utf-8").splitlines())
    assert any('"event": "recovery_incident"' in line for line in (store.root / "journal.jsonl").read_text(encoding="utf-8").splitlines())


def test_runner_resumes_completed_worker_after_a_temporary_worker_file_lock(tmp_path: Path) -> None:
    class TemporarilyLockedWorkerDriver(FakeCampaignDriver):
        def __init__(self) -> None:
            super().__init__()
            self._locked = True

        def inspect_generation(self, campaign_id: str, generation_index: int) -> dict[str, str]:
            self.calls.append(f"inspect:{generation_index}")
            if self._locked:
                self._locked = False
                raise PermissionError(
                    13,
                    "Permission denied",
                    r"D:\\project\\runs\\evolution\\campaign\\workers\\g000_phase6.json",
                )
            return {"status": "completed"}

    driver = TemporarilyLockedWorkerDriver()
    runner = TrainingRunner(_store(tmp_path, generations=1), driver)
    runner.run_once()  # prepare
    runner.run_once()  # preview
    runner.run_once()  # execute

    retrying = runner.run_once()
    resumed = runner.run_once()

    assert retrying.runner["retry"]["error_type"] == "PermissionError"
    assert resumed.completed_generations == (0,)
    assert driver.calls == ["prepare", "preview:0", "execute:0", "inspect:0", "inspect:0"]


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
    assert state.runner["recovery"]["action"] == "DOMAIN_REPAIR"


def test_runner_stops_same_action_after_three_failed_recoveries(tmp_path: Path) -> None:
    class UnavailableDriver(FakeCampaignDriver):
        def prepare(self, request: TrainingRequest) -> str:
            raise ConnectionError("Connection reset")

    store = _store(tmp_path, generations=1)
    runner = TrainingRunner(store, UnavailableDriver())

    runner.run_once()
    runner.run_once()
    state = runner.run_once()

    assert state.status is TrainingStatus.STOPPED
    assert state.action is TrainingAction.IDLE
    assert state.runner["recovery"]["attempts"] == 3
    assert (store.root / "recovery-report.md").is_file()


def test_runner_passes_error_context_and_original_action_replay_to_code_repair(
    tmp_path: Path,
) -> None:
    class BrokenOnceDriver(FakeCampaignDriver):
        def __init__(self) -> None:
            super().__init__()
            self.broken = True

        def prepare(self, request: TrainingRequest) -> str:
            if self.broken:
                self.broken = False
                raise AttributeError("missing adapter")
            return super().prepare(request)

    captured: dict[str, object] = {}

    class Repairs:
        def repair(self, **kwargs):
            captured.update(kwargs)
            kwargs["replay_task"]()
            return SimpleNamespace(succeeded=True, commit_id="abc123")

    store = _store(tmp_path, generations=1)
    state = TrainingRunner(
        store,
        BrokenOnceDriver(),
        repair_coordinator=Repairs(),
    ).run_once()

    assert captured["envelope"].error_type == "AttributeError"
    assert "missing adapter" in captured["repair_context"]
    assert state.status is TrainingStatus.RUNNING
    assert state.campaign_id == "training-001-campaign"
    assert state.action is TrainingAction.PREVIEW
    assert state.last_good_commit == "abc123"
    assert state.runner["recovery"] == {"status": "IDLE"}


def test_runner_puts_unknown_diagnosis_files_into_repair_context(tmp_path: Path) -> None:
    class StrangeDriver(FakeCampaignDriver):
        def prepare(self, request: TrainingRequest) -> str:
            raise RuntimeError("strange adapter incident")

    source = tmp_path / "src" / "cmo_lua_agent" / "training" / "runtime.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("KNOWN_SOURCE_MARKER = True\n", encoding="utf-8")
    captured: dict[str, object] = {}

    class Repairs:
        def repair(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(succeeded=False)

    router = RecoveryRouter(
        unknown_diagnoser=lambda _envelope: RecoveryDecision(
            "CODE",
            "CODE_REPAIR",
            "未知适配器故障",
            ["src/cmo_lua_agent/training/runtime.py"],
        )
    )
    TrainingRunner(
        _store(tmp_path, generations=1),
        StrangeDriver(),
        repair_coordinator=Repairs(),
        recovery_router=router,
    ).run_once()

    assert "KNOWN_SOURCE_MARKER" in captured["repair_context"]


def test_reconcile_restores_interrupted_repair_and_restarts_same_incident(
    tmp_path: Path,
) -> None:
    source = tmp_path / "src" / "cmo_lua_agent" / "worker.py"
    source.parent.mkdir(parents=True)
    source.write_text("VALUE = 'before'\n", encoding="utf-8")
    store = _store(tmp_path, generations=1)
    snapshot = RepairSnapshot(
        project_root=tmp_path,
        archive_path=store.root / "repair-snapshot.zip",
    )
    snapshot.create()
    source.write_text("VALUE = 'interrupted'\n", encoding="utf-8")
    envelope = ErrorEnvelope(
        workflow_id="training-001",
        stage="PREPARE",
        generation=0,
        task="VALIDATE_INPUT",
        subtask=None,
        error_type="AttributeError",
        message="missing adapter",
        traceback="AttributeError: missing adapter",
        stdout_path=None,
        stderr_path=None,
        related_files=[],
    )
    store.transition(
        status=TrainingStatus.REPAIRING,
        runner={
            "recovery": {
                "status": "REPAIRING",
                "attempts": 1,
                "category": "CODE",
                "action": "CODE_REPAIR",
                "stage": "PREPARE",
                "task": "VALIDATE_INPUT",
                "generation": 0,
                "envelope": envelope.to_dict(),
                "snapshot_path": snapshot.path.relative_to(tmp_path).as_posix(),
            }
        },
    )
    captured: dict[str, object] = {}

    class Repairs:
        def repair(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(succeeded=False, summary="still broken")

    runner = TrainingRunner(store, FakeCampaignDriver(), repair_coordinator=Repairs())

    reconciled = runner.reconcile()
    assert source.read_text(encoding="utf-8") == "VALUE = 'before'\n"
    assert reconciled.status is TrainingStatus.RUNNING
    assert reconciled.runner["recovery"]["status"] == "FAILED"
    assert reconciled.runner["recovery"]["attempts"] == 2

    runner.run_once()

    assert captured["attempt"] == 2
    assert captured["envelope"].message == "missing adapter"


def test_code_repair_reconciles_existing_preview_without_generating_it_again(
    tmp_path: Path,
) -> None:
    class PreviewPersistedDriver(FakeCampaignDriver):
        def preview(self, campaign_id: str, generation_index: int) -> None:
            self.calls.append(f"preview:{generation_index}")
            raise AttributeError("preview adapter bug")

        def inspect_generation(self, campaign_id: str, generation_index: int):
            self.calls.append(f"inspect:{generation_index}")
            return {"preview": {"checksum": "persisted"}, "status": "ready"}

    class Repairs:
        def repair(self, **kwargs):
            kwargs["replay_task"]()
            return SimpleNamespace(succeeded=True, commit_id="abc123", summary="fixed")

    store = _store(tmp_path, generations=1)
    driver = PreviewPersistedDriver()
    runner = TrainingRunner(store, driver, repair_coordinator=Repairs())
    runner.run_once()  # prepare

    state = runner.run_once()

    assert state.action is TrainingAction.EXECUTE
    assert driver.calls == ["prepare", "preview:0", "reconcile", "inspect:0"]


def test_reconcile_finishes_pending_push_for_committed_repair(tmp_path: Path) -> None:
    store = _store(tmp_path, generations=1)
    store.transition(
        status=TrainingStatus.REPAIRING,
        runner={
            "recovery": {
                "status": "COMMITTED",
                "action": "CODE_REPAIR",
                "attempts": 1,
                "commit_id": "abc123",
                "push_completed": False,
            }
        },
    )
    calls: list[str] = []

    class Repairs:
        def resume_committed(self, *, workflow_id: str, commit_id: str):
            calls.append(f"{workflow_id}:{commit_id}")
            return SimpleNamespace(succeeded=True, commit_id=commit_id, summary="push completed")

    state = TrainingRunner(
        store,
        FakeCampaignDriver(),
        repair_coordinator=Repairs(),
    ).reconcile()

    assert calls == ["training-001:abc123"]
    assert state.status is TrainingStatus.RUNNING
    assert state.last_good_commit == "abc123"
    assert state.runner["recovery"] == {"status": "IDLE"}


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
