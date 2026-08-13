from __future__ import annotations

from types import SimpleNamespace

from cmo_lua_agent.training.models import TrainingStatus
import cmo_lua_agent.training.runtime as runtime


def test_runtime_retries_running_workflow_after_a_wait(monkeypatch, tmp_path) -> None:
    calls: list[str] = []
    wiring: dict[str, object] = {}

    class Runner:
        def __init__(self, *_args, **kwargs) -> None:
            self.count = 0
            wiring["coordinator"] = kwargs["repair_coordinator"]

        def reconcile(self) -> None:
            calls.append("reconcile")

        def run(self):
            self.count += 1
            return SimpleNamespace(
                status=(TrainingStatus.RUNNING if self.count == 1 else TrainingStatus.COMPLETED)
            )

    monkeypatch.setattr(runtime, "load_config", lambda: SimpleNamespace(llm=object()))
    llm_client = object()
    monkeypatch.setattr(runtime, "ClaudeClient", lambda _config: llm_client)
    monkeypatch.setattr(runtime, "create_production_evolution_campaign_service", lambda **_kwargs: object())
    monkeypatch.setattr(
        runtime,
        "CodeRepairAgent",
        lambda **kwargs: wiring.update(agent_kwargs=kwargs) or "repair-agent",
    )
    monkeypatch.setattr(
        runtime,
        "CodeRepairCoordinator",
        lambda **kwargs: wiring.update(coordinator_kwargs=kwargs) or "coordinator",
    )
    monkeypatch.setattr(runtime, "TrainingRunner", Runner)
    monkeypatch.setattr(runtime, "sleep", lambda seconds: calls.append(f"sleep:{seconds}"))
    monkeypatch.setattr(runtime, "retry_sleep_seconds", lambda _state: 5)

    assert runtime.run_workflow(project_root=tmp_path, workflow_id="training-001") is TrainingStatus.COMPLETED
    assert calls == ["reconcile", "sleep:5"]
    assert wiring["agent_kwargs"]["llm_client"] is llm_client
    assert wiring["coordinator_kwargs"]["system_repair_agent"] == "repair-agent"
    assert wiring["coordinator"] == "coordinator"
