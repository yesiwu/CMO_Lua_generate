"""High-level lifecycle facade for persistent training workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from cmo_lua_agent.training.input_resolver import ScenarioInputResolver
from cmo_lua_agent.training.models import TrainingAction, TrainingRequest, TrainingStatus
from cmo_lua_agent.training.process import TrainingProcessManager
from cmo_lua_agent.training.store import TrainingStore


class TrainingService:
    """Create and inspect workflows without exposing Campaign budgets or approvals."""

    def __init__(
        self,
        *,
        project_root: Path,
        input_resolver: object | None = None,
        process_manager: object | None = None,
        workflow_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._root = Path(project_root).resolve()
        self._resolver = input_resolver or ScenarioInputResolver(project_root=self._root)
        self._processes = process_manager or TrainingProcessManager(project_root=self._root)
        self._workflow_id_factory = workflow_id_factory or (lambda: f"training-{uuid4().hex[:12]}")

    def start(
        self,
        *,
        input_path: str,
        objective: str,
        generation_count: int,
        session_id: str | None = None,
    ) -> dict[str, object]:
        resolved = self._resolver.resolve(input_path)
        workflow_id = self._workflow_id_factory()
        request = TrainingRequest.create(
            workflow_id=workflow_id,
            input_path=str(resolved.reference),
            objective=objective,
            generation_count=generation_count,
            session_id=session_id,
        )
        TrainingStore(self._root, workflow_id).create(request)
        pid = self._processes.start(workflow_id)
        return {"workflow_id": workflow_id, "pid": pid}

    def inspect(self, workflow_id: str) -> dict[str, object]:
        store = TrainingStore(self._root, workflow_id)
        request = store.load_request()
        state = store.load_state()
        return {
            "workflow_id": workflow_id,
            "generation_count": request.generation_count,
            "status": state.status.value,
            "stage": state.stage.value,
            "action": state.action.value,
            "current_generation": state.current_generation,
            "completed_generations": list(state.completed_generations),
            "campaign_id": state.campaign_id,
            "phase8_status": state.phase8.status.value,
        }

    def control(self, workflow_id: str, action: str) -> dict[str, object]:
        store = TrainingStore(self._root, workflow_id)
        if action == "pause":
            store.transition(status=TrainingStatus.PAUSED, action=TrainingAction.IDLE)
        elif action == "stop":
            store.transition(status=TrainingStatus.STOPPED, action=TrainingAction.IDLE)
        elif action == "resume":
            store.transition(status=TrainingStatus.RUNNING, action=TrainingAction.PREVIEW)
            self._processes.start(workflow_id)
        else:
            raise ValueError("invalid_training_control_action")
        return self.inspect(workflow_id)
