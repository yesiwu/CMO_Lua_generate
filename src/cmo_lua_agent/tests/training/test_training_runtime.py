from __future__ import annotations

from types import SimpleNamespace

from cmo_lua_agent.training.models import TrainingStatus
import cmo_lua_agent.training.runtime as runtime


def test_runtime_retries_running_workflow_after_a_wait(monkeypatch, tmp_path) -> None:
    calls: list[str] = []

    class Runner:
        def __init__(self, *_args, **_kwargs) -> None:
            self.count = 0

        def reconcile(self) -> None:
            calls.append("reconcile")

        def run(self):
            self.count += 1
            return SimpleNamespace(
                status=(TrainingStatus.RUNNING if self.count == 1 else TrainingStatus.COMPLETED)
            )

    monkeypatch.setattr(runtime, "load_config", lambda: SimpleNamespace(llm=object()))
    monkeypatch.setattr(runtime, "ClaudeClient", lambda _config: object())
    monkeypatch.setattr(runtime, "create_production_evolution_campaign_service", lambda **_kwargs: object())
    monkeypatch.setattr(runtime, "TrainingRunner", Runner)
    monkeypatch.setattr(runtime, "sleep", lambda seconds: calls.append(f"sleep:{seconds}"))

    assert runtime.run_workflow(project_root=tmp_path, workflow_id="training-001") is TrainingStatus.COMPLETED
    assert calls == ["reconcile", "sleep:1"]
