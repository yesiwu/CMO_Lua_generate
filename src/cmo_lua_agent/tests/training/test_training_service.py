from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from cmo_lua_agent.training.service import TrainingService


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
