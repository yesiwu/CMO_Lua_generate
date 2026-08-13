"""面向 Chat/CLI 的 Training Workflow 生命周期门面。

用户入口只通过本类创建、查询、暂停、恢复或停止训练。它负责创建最小持久化请求并
启动后台进程；真正逐代推进在 TrainingRunner，Campaign 内部细节不会暴露给 Chat。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from cmo_lua_agent.training.input_resolver import ScenarioInputResolver
from cmo_lua_agent.training.models import TrainingAction, TrainingRequest, TrainingStatus
from cmo_lua_agent.training.process import TrainingProcessManager
from cmo_lua_agent.training.recovery import establish_training_baseline
from cmo_lua_agent.training.store import TrainingStore


class TrainingService:
    """提供稳定的训练生命周期 API，不暴露 Campaign 预算和内部审批实现。"""

    def __init__(
        self,
        *,
        project_root: Path,
        input_resolver: object | None = None,
        process_manager: object | None = None,
        workflow_id_factory: Callable[[], str] | None = None,
        baseline_builder: Callable[[str], str] | None = None,
    ) -> None:
        self._root = Path(project_root).resolve()
        self._resolver = input_resolver or ScenarioInputResolver(project_root=self._root)
        self._processes = process_manager or TrainingProcessManager(project_root=self._root)
        self._workflow_id_factory = workflow_id_factory or (lambda: f"training-{uuid4().hex[:12]}")
        self._baseline_builder = baseline_builder or (
            lambda workflow_id: establish_training_baseline(
                project_root=self._root,
                workflow_id=workflow_id,
            )
        )

    def start(
        self,
        *,
        input_path: str,
        objective: str,
        generation_count: int,
        session_id: str | None = None,
        execution_mode: str = "PRODUCTION_CMO",
    ) -> dict[str, object]:
        """创建可恢复 Training 请求并启动后台 Runner。

返回 workflow_id 与后台 pid。请求先落盘、后启动进程，保证进程启动失败或重启时
仍能由 inspect/control 找到同一 Workflow，而不是只留在一次 Chat 调用内。
        """
        resolved = self._resolver.resolve(input_path)
        workflow_id = self._workflow_id_factory()
        request = TrainingRequest.create(
            workflow_id=workflow_id,
            input_path=str(resolved.reference),
            objective=objective,
            generation_count=generation_count,
            session_id=session_id,
            execution_mode=execution_mode,
        )
        try:
            last_good_commit = self._baseline_builder(workflow_id)
        except Exception as exc:
            raise RuntimeError(
                f"训练 Git 基线建立或推送失败：{type(exc).__name__}: {exc}"
            ) from exc
        TrainingStore(self._root, workflow_id).create(
            request,
            last_good_commit=last_good_commit,
        )
        pid = self._processes.start(workflow_id)
        return {"workflow_id": workflow_id, "pid": pid}

    def inspect(self, workflow_id: str) -> dict[str, object]:
        """读取当前训练进度；发现 RUNNING 但后台进程消失时尝试重新启动 Runner。"""
        return self._inspect(workflow_id, recover_runner=True)

    def _inspect(self, workflow_id: str, *, recover_runner: bool) -> dict[str, object]:
        """从持久化请求与状态构造查询视图，并按需补起丢失的后台 Runner。

        该方法不直接推进训练动作；进程恢复后仍由 Runtime 读取同一状态继续，避免查询
        接口因用户轮询而改变代次或 Campaign 业务状态。
        """
        store = TrainingStore(self._root, workflow_id)
        request = store.load_request()
        state = store.load_state()
        replacement_pid = None
        if (
            recover_runner
            and state.status in {TrainingStatus.RUNNING, TrainingStatus.REPAIRING}
            and self._process_is_running(workflow_id) is False
        ):
            replacement_pid = self._processes.start(workflow_id)
        status: dict[str, object] = {
            "workflow_id": workflow_id,
            "generation_count": request.generation_count,
            "status": state.status.value,
            "stage": state.stage.value,
            "action": state.action.value,
            "current_generation": state.current_generation,
            "completed_generations": list(state.completed_generations),
            "campaign_id": state.campaign_id,
            "phase8_status": state.phase8.status.value,
            "retry": state.runner.get("retry"),
        }
        if replacement_pid is not None:
            status["runner_pid"] = replacement_pid
        return status

    def control(self, workflow_id: str, action: str) -> dict[str, object]:
        """写入 pause/stop/resume 控制意图并返回最新持久化状态。"""
        store = TrainingStore(self._root, workflow_id)
        if action == "pause":
            store.transition(status=TrainingStatus.PAUSED, action=TrainingAction.IDLE)
        elif action == "stop":
            store.transition(status=TrainingStatus.STOPPED, action=TrainingAction.IDLE)
        elif action == "resume":
            state = store.load_state()
            if state.status is TrainingStatus.PAUSED:
                store.transition(status=TrainingStatus.RUNNING, action=TrainingAction.PREVIEW)
            if not self._process_is_running(workflow_id):
                self._processes.start(workflow_id)
        else:
            raise ValueError("invalid_training_control_action")
        return self._inspect(workflow_id, recover_runner=False)

    def _process_is_running(self, workflow_id: str) -> bool | None:
        """委托可选进程管理器做健康检查；测试替身未提供该能力时返回未知。"""
        checker = getattr(self._processes, "is_running", None)
        return bool(checker(workflow_id)) if callable(checker) else None
