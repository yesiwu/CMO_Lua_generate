from __future__ import annotations

from cmo_lua_agent.training.models import TrainingRequest
from cmo_lua_agent.training.runner import TrainingRunner
from cmo_lua_agent.training.service import TrainingService
from cmo_lua_agent.training.store import TrainingStore


class _ThreeGenerationDriver:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def prepare(self, request: TrainingRequest) -> str:
        self.calls.append("prepare")
        return f"{request.workflow_id}-campaign"

    def preview(self, _campaign_id: str, generation_index: int) -> None:
        self.calls.append(f"preview:{generation_index}")

    def execute(self, _campaign_id: str, generation_index: int) -> None:
        self.calls.append(f"execute:{generation_index}")

    def inspect_generation(self, _campaign_id: str, generation_index: int) -> dict[str, str]:
        self.calls.append(f"inspect:{generation_index}")
        return {"status": "completed"}

    def reconcile(self, _campaign_id: str) -> dict[str, str]:
        self.calls.append("reconcile")
        return {"status": "ok"}

    def pause(self, _campaign_id: str) -> None: pass
    def resume(self, _campaign_id: str) -> None: pass
    def stop(self, _campaign_id: str) -> None: pass

    def run_phase8(self, _campaign_id: str, completed: tuple[int, ...]) -> dict[str, str]:
        self.calls.append(f"phase8:{','.join(map(str, completed))}")
        return {"status": "completed", "job_id": "phase8-final"}


def test_three_generation_training_is_queryable_restartable_and_aggregates_phase8_once(tmp_path) -> None:
    launches: list[str] = []
    service = TrainingService(
        project_root=tmp_path,
        input_resolver=type("Resolver", (), {"resolve": lambda _self, _path: type("Input", (), {"reference": "scenario.json"})()})(),
        process_manager=type("Process", (), {"start": lambda _self, workflow_id: launches.append(workflow_id) or 1})(),
        workflow_id_factory=lambda: "training-acceptance",
        baseline_builder=lambda _workflow_id: "abc123",
    )
    service.start(input_path="scenario.json", objective="improve", generation_count=3)
    store = TrainingStore(tmp_path, "training-acceptance")
    driver = _ThreeGenerationDriver()

    first = TrainingRunner(store, driver)
    first.run_once()
    progress = service.inspect("training-acceptance")
    assert progress["status"] == "RUNNING"
    assert progress["current_generation"] == 0

    state = TrainingRunner(store, driver).run()

    assert state.completed_generations == (0, 1, 2)
    assert driver.calls == [
        "prepare",
        "preview:0", "execute:0", "inspect:0",
        "preview:1", "execute:1", "inspect:1",
        "preview:2", "execute:2", "inspect:2",
        "phase8:0,1,2",
    ]
    assert launches == ["training-acceptance"]
    assert (store.root / "summary.json").is_file()
    assert (store.root / "TODO.md").is_file()
    assert (store.root / "journal.jsonl").is_file()
