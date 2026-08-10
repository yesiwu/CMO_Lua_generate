from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from cmo_lua_agent.training.service import TrainingService
from cmo_lua_agent.training.models import TrainingStatus
from cmo_lua_agent.training.store import TrainingStore


def test_service_persists_request_before_launching_runner(tmp_path: Path) -> None:
    launches: list[str] = []

    class Resolver:
        def resolve(self, path: str) -> SimpleNamespace:
            assert path == "scenario.json"
            return SimpleNamespace(reference="scenario.json")

    class ProcessManager:
        def start(self, workflow_id: str) -> int:
            launches.append(workflow_id)
            return 4321

    service = TrainingService(
        project_root=tmp_path,
        input_resolver=Resolver(),
        process_manager=ProcessManager(),
        workflow_id_factory=lambda: "training-001",
    )

    result = service.start(
        input_path="scenario.json",
        objective="improve official score",
        generation_count=3,
    )

    assert result == {"workflow_id": "training-001", "pid": 4321}
    assert launches == ["training-001"]
    assert service.inspect("training-001")["generation_count"] == 3


def test_service_control_persists_safe_boundary_commands(tmp_path: Path) -> None:
    class Resolver:
        def resolve(self, _path: str) -> SimpleNamespace:
            return SimpleNamespace(reference="scenario.json")

    service = TrainingService(
        project_root=tmp_path,
        input_resolver=Resolver(),
        process_manager=SimpleNamespace(start=lambda _workflow_id: 1),
        workflow_id_factory=lambda: "training-001",
    )
    service.start(input_path="scenario.json", objective="improve", generation_count=1)

    assert service.control("training-001", "pause")["status"] == "PAUSED"
    assert service.control("training-001", "stop")["status"] == "STOPPED"


def test_service_resume_restarts_a_dead_running_workflow(tmp_path: Path) -> None:
    launches: list[str] = []

    class ProcessManager:
        def start(self, workflow_id: str) -> int:
            launches.append(workflow_id)
            return 1

        def is_running(self, _workflow_id: str) -> bool:
            return False

    service = TrainingService(
        project_root=tmp_path,
        input_resolver=SimpleNamespace(resolve=lambda _path: SimpleNamespace(reference="scenario.json")),
        process_manager=ProcessManager(),
        workflow_id_factory=lambda: "training-001",
    )
    service.start(input_path="scenario.json", objective="improve", generation_count=1)
    TrainingStore(tmp_path, "training-001").transition(status=TrainingStatus.RUNNING)

    assert service.control("training-001", "resume")["status"] == "RUNNING"
    assert launches == ["training-001", "training-001"]


def test_service_inspect_exposes_persisted_transient_retry(tmp_path: Path) -> None:
    service = TrainingService(
        project_root=tmp_path,
        input_resolver=SimpleNamespace(resolve=lambda _path: SimpleNamespace(reference="scenario.json")),
        process_manager=SimpleNamespace(start=lambda _workflow_id: 1),
        workflow_id_factory=lambda: "training-001",
    )
    service.start(input_path="scenario.json", objective="improve", generation_count=1)
    TrainingStore(tmp_path, "training-001").transition(runner={"retry": {"kind": "TRANSIENT"}})

    assert service.inspect("training-001")["retry"] == {"kind": "TRANSIENT"}


def test_service_inspect_relaunches_a_known_dead_running_workflow(tmp_path: Path) -> None:
    launches: list[str] = []

    class ProcessManager:
        def start(self, workflow_id: str) -> int:
            launches.append(workflow_id)
            return len(launches)

        def is_running(self, _workflow_id: str) -> bool:
            return False

    service = TrainingService(
        project_root=tmp_path,
        input_resolver=SimpleNamespace(resolve=lambda _path: SimpleNamespace(reference="scenario.json")),
        process_manager=ProcessManager(),
        workflow_id_factory=lambda: "training-001",
    )
    service.start(input_path="scenario.json", objective="improve", generation_count=1)
    TrainingStore(tmp_path, "training-001").transition(status=TrainingStatus.RUNNING)

    status = service.inspect("training-001")

    assert launches == ["training-001", "training-001"]
    assert status["runner_pid"] == 2
