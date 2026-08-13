"""Training Workflow 的原子化磁盘状态存储。

``request.json`` 保存用户启动时的不可变请求，``state.json`` 是恢复调度的机器
真相，``journal.jsonl`` 只追加记录状态事件；summary/TODO 只是给人查看，不能反向
驱动恢复。TrainingRunner 是主要调用者。
"""

from __future__ import annotations

from dataclasses import asdict, replace
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from cmo_lua_agent.training.models import (
    Phase8Progress,
    Phase8Status,
    TrainingAction,
    TrainingRequest,
    TrainingStage,
    TrainingState,
    TrainingStatus,
    _utc_now,
)


class TrainingStore:
    """在 ``runs/training`` 下保存单个 Workflow 的最小可恢复事实。

不保存完整 CMO 输出或 Campaign 业务结果，避免与正式 Artifact 产生两份冲突真相。
    """

    def __init__(self, project_root: Path, workflow_id: str) -> None:
        if not workflow_id or any(token in workflow_id for token in ("/", "\\", "..")):
            raise ValueError("invalid_training_workflow_id")
        self.root = Path(project_root).resolve() / "runs" / "training" / workflow_id
        self._request_path = self.root / "request.json"
        self._state_path = self.root / "state.json"
        self._journal_path = self.root / "journal.jsonl"
        self._summary_path = self.root / "summary.json"
        self._todo_path = self.root / "TODO.md"

    def create(
        self,
        request: TrainingRequest,
        *,
        last_good_commit: str | None = None,
    ) -> TrainingState:
        """创建一套新的请求、初始状态和可读摘要；已存在的 Workflow 禁止覆盖。"""
        if request.workflow_id != self.root.name:
            raise ValueError("training_store_workflow_mismatch")
        if self.root.exists():
            raise ValueError("training_workflow_already_exists")
        self.root.mkdir(parents=True, exist_ok=False)
        state = TrainingState.initial(request)
        if last_good_commit is not None:
            state = replace(state, last_good_commit=last_good_commit)
        self._write_json(self._request_path, asdict(request))
        self._write_state(state)
        self.write_summary(state)
        self.write_todo(state)
        self.append_event(
            {
                "event": "workflow_created",
                "workflow_id": request.workflow_id,
            }
        )
        return state

    def load_request(self) -> TrainingRequest:
        """读取启动请求，并兼容尚未包含 execution_mode 的历史 Artifact。"""
        value = self._read_json(self._request_path)
        # Workflows created before execution-mode selection always ran real CMO.
        # Default in memory so historical request artifacts remain immutable.
        value.setdefault("execution_mode", "PRODUCTION_CMO")
        return TrainingRequest(**value)

    def load_state(self) -> TrainingState:
        """读取当前调度真相并恢复为强类型状态。

        该方法只解释 ``state.json``，不从摘要、TODO 或事件日志反推状态；因此恢复路径
        始终以 Runner 最后一次原子写入的 revision 为准。
        """
        value = self._read_json(self._state_path)
        phase8 = value.get("phase8", {})
        return TrainingState(
            schema_version=str(value["schema_version"]),
            revision=int(value["revision"]),
            workflow_id=str(value["workflow_id"]),
            campaign_id=value.get("campaign_id"),
            status=TrainingStatus(value["status"]),
            stage=TrainingStage(value["stage"]),
            action=TrainingAction(value["action"]),
            current_generation=int(value["current_generation"]),
            completed_generations=tuple(int(item) for item in value.get("completed_generations", ())),
            worker_operation_id=value.get("worker_operation_id"),
            active_failure_id=value.get("active_failure_id"),
            last_good_commit=value.get("last_good_commit"),
            runner=dict(value.get("runner", {})),
            phase8=Phase8Progress(
                status=Phase8Status(phase8.get("status", Phase8Status.NOT_STARTED)),
                job_id=phase8.get("job_id"),
            ),
            updated_at=str(value["updated_at"]),
        )

    def transition(
        self,
        *,
        status: TrainingStatus | None = None,
        stage: TrainingStage | None = None,
        action: TrainingAction | None = None,
        current_generation: int | None = None,
        campaign_id: str | None = None,
        completed_generations: tuple[int, ...] | None = None,
        worker_operation_id: str | None = None,
        phase8: Phase8Progress | None = None,
        last_good_commit: str | None = None,
        runner: dict[str, Any] | None = None,
    ) -> TrainingState:
        """原子写入下一份调度状态，并同步追加可审阅的状态事件。

调用者只提交发生变化的字段；未提供的字段继承当前状态。每次 revision 递增，使
恢复逻辑能区分“尚未执行”与“已经推进到下一步”。
        """
        current = self.load_state()
        next_state = replace(
            current,
            revision=current.revision + 1,
            status=status or current.status,
            stage=stage or current.stage,
            action=action or current.action,
            current_generation=(
                current_generation
                if current_generation is not None
                else current.current_generation
            ),
            campaign_id=campaign_id if campaign_id is not None else current.campaign_id,
            completed_generations=(
                completed_generations
                if completed_generations is not None
                else current.completed_generations
            ),
            worker_operation_id=(
                worker_operation_id
                if worker_operation_id is not None
                else current.worker_operation_id
            ),
            last_good_commit=(
                last_good_commit
                if last_good_commit is not None
                else current.last_good_commit
            ),
            runner=(
                dict(runner)
                if runner is not None
                else {key: value for key, value in current.runner.items() if key != "retry"}
            ),
            phase8=phase8 if phase8 is not None else current.phase8,
            updated_at=_utc_now(),
        )
        self._write_state(next_state)
        self.write_summary(next_state)
        self.write_todo(next_state)
        self.append_event(
            {
                "event": "state_transition",
                "workflow_id": next_state.workflow_id,
                "revision": next_state.revision,
            }
        )
        return next_state

    def lock(self) -> "TrainingWorkflowLock":
        """返回持久化 Runner 使用的排他锁。

        锁的作用域仅为一个 Workflow，允许不同训练任务并行；它不替代 Campaign 内部
        的 CMO 实例锁。
        """
        return TrainingWorkflowLock(
            self.root / "runner.lock",
            workflow_id=self.root.name,
        )

    def append_event(self, value: dict[str, Any]) -> None:
        """追加诊断事件；它是审阅轨迹，不取代 state.json 的当前调度事实。"""
        sequence = 1
        if self._journal_path.is_file():
            sequence = sum(1 for line in self._journal_path.read_text(encoding="utf-8").splitlines() if line.strip()) + 1
        row = {"sequence": sequence, **value}
        with self._journal_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    def write_summary(self, state: TrainingState) -> None:
        """写入供用户快速查看的摘要；该文件不参与恢复决策。"""
        self._write_json(
            self._summary_path,
            {
                "workflow_id": state.workflow_id,
                "campaign_id": state.campaign_id,
                "status": state.status.value,
                "current_generation": state.current_generation,
                "completed_generations": list(state.completed_generations),
                "updated_at": state.updated_at,
            },
        )

    def write_todo(self, state: TrainingState) -> None:
        """写入当前阶段和下一动作的人工可读提示；不作为状态机输入。"""
        self._write_text(
            self._todo_path,
            "\n".join(
                (
                    f"# Training Workflow {state.workflow_id}",
                    "",
                    f"- Status: {state.status.value}",
                    f"- Stage: {state.stage.value}",
                    f"- Next action: {state.action.value}",
                    f"- Current generation: {state.current_generation}",
                    "",
                )
            ),
        )

    def _write_state(self, state: TrainingState) -> None:
        """将强类型状态转换为稳定 JSON 表示后原子落盘。"""
        value = asdict(state)
        value["status"] = state.status.value
        value["stage"] = state.stage.value
        value["action"] = state.action.value
        value["completed_generations"] = list(state.completed_generations)
        value["phase8"]["status"] = state.phase8.status.value
        self._write_json(self._state_path, value)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("training_state_json_object_required")
        return value

    @staticmethod
    def _write_json(path: Path, value: dict[str, Any]) -> None:
        TrainingStore._write_text(
            path,
            json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        )

    @staticmethod
    def _write_text(path: Path, value: str) -> None:
        # 先写同目录临时文件再替换，避免进程中断留下半个 JSON 让恢复流程无法解析。
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(value, encoding="utf-8", newline="\n")
        os.replace(temporary, path)


class TrainingWorkflowLockError(RuntimeError):
    """另一 Runner 已持有同一 Training Workflow 的排他锁时抛出。"""


class TrainingWorkflowLock:
    """带最小持有者元数据的进程级 Workflow 锁。

    锁文件仅阻止同一 Workflow 的重复调度；其中的 PID 与实例 ID 用于诊断竞争，不把
    进程内存状态当作可恢复数据。
    """

    def __init__(self, path: Path, *, workflow_id: str) -> None:
        self._path = Path(path)
        self._workflow_id = workflow_id
        self._instance_id = uuid4().hex
        self._held = False

    def acquire(self) -> None:
        """以原子创建方式获取锁；已存在时保留原持有者文件并报告稳定错误码。"""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(
                self._path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            )
        except FileExistsError as exc:
            raise TrainingWorkflowLockError("training_workflow_locked") from exc
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(
                {
                    "workflow_id": self._workflow_id,
                    "pid": os.getpid(),
                    "instance_id": self._instance_id,
                },
                handle,
                ensure_ascii=False,
                sort_keys=True,
            )
        self._held = True

    def release(self) -> None:
        """仅删除当前实例成功持有的锁，重复释放保持无害。"""
        if self._held:
            try:
                self._path.unlink()
            except FileNotFoundError:
                pass
        self._held = False

    def __enter__(self) -> "TrainingWorkflowLock":
        self.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.release()
