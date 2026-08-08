from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from cmo_lua_agent.training.models import TrainingRequest
from cmo_lua_agent.training.process import TrainingProcessManager
from cmo_lua_agent.training.store import TrainingStore


def test_process_manager_starts_hidden_training_runtime(tmp_path: Path) -> None:
    store = TrainingStore(tmp_path, "training-001")
    store.create(TrainingRequest.create(
        workflow_id="training-001",
        input_path="scenario.json",
        objective="improve score",
        generation_count=2,
    ))
    calls: list[tuple[list[str], dict[str, object]]] = []

    def launch(command: list[str], **kwargs: object) -> SimpleNamespace:
        calls.append((command, kwargs))
        return SimpleNamespace(pid=2468)

    manager = TrainingProcessManager(
        project_root=tmp_path,
        launcher=launch,
        python_executable="python-test",
    )

    pid = manager.start("training-001")

    assert pid == 2468
    assert calls[0][0] == [
        "python-test", "-m", "cmo_lua_agent.training.runtime", "run",
        "--project-root", str(tmp_path.resolve()), "--workflow-id", "training-001",
    ]
    assert (store.root / "runner.log").is_file()
    assert manager.process_metadata("training-001")["pid"] == 2468
