"""单次 JSON → Lua 工作流的状态模型。

这个文件负责定义：
1. 当前任务处于哪个阶段；
2. 哪些状态可以互相转换；
3. 失败、暂停、完成如何记录。

它类似一个“小型状态机”。

真正执行流程的代码在其他模块，
这里只负责约束流程不能乱走。
"""


from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any

from cmo_lua_agent.artifacts import RunArtifactPaths


class WorkflowTransitionError(ValueError):
    """工作流状态非法转换时抛出的异常。"""


class WorkflowStatus(str, Enum):
    """任务整体状态。"""

    # 刚创建，还没有开始执行
    CREATED = "created"

    # 正在处理中
    RUNNING = "running"

    # 正常完成
    COMPLETED = "completed"

    # 需要用户决策，暂停等待
    NEEDS_USER_INPUT = "needs_user_input"

    # 执行失败
    FAILED = "failed"


class WorkflowStage(str, Enum):
    """JSON → Lua 的具体执行阶段。"""

    CREATED = "created"

    # 读取输入 JSON
    INPUT = "input"

    # 检查 JSON 格式
    SCHEMA = "schema"

    # 检查业务逻辑是否合理
    SEMANTIC = "semantic"

    # 构建内部统一表示
    IR = "ir"

    # 查询数据库信息
    DATABASE = "database"

    # 生成 Lua 前的任务描述
    MANIFEST = "manifest"

    # 调用 Lua 生成器
    GENERATION = "generation"

    # 完成
    COMPLETED = "completed"


# 定义每个阶段允许去往哪里。
# 相当于状态机的路线图。
_ALLOWED_TRANSITIONS = {
    WorkflowStage.CREATED:
        {WorkflowStage.INPUT, WorkflowStage.MANIFEST},

    WorkflowStage.INPUT:
        {WorkflowStage.SCHEMA},

    WorkflowStage.SCHEMA:
        {WorkflowStage.SEMANTIC},

    WorkflowStage.SEMANTIC:
        {WorkflowStage.IR},

    WorkflowStage.IR:
        {WorkflowStage.DATABASE},

    WorkflowStage.DATABASE:
        {WorkflowStage.MANIFEST},

    WorkflowStage.MANIFEST:
        {WorkflowStage.GENERATION},
}


# 这些状态表示任务已经结束，
# 后续不能继续推进。
_TERMINAL_STATUSES = {
    WorkflowStatus.COMPLETED,
    WorkflowStatus.NEEDS_USER_INPUT,
    WorkflowStatus.FAILED,
}


# 正常执行中的阶段
_RUNNING_STAGES = {
    WorkflowStage.INPUT,
    WorkflowStage.SCHEMA,
    WorkflowStage.SEMANTIC,
    WorkflowStage.IR,
    WorkflowStage.DATABASE,
    WorkflowStage.MANIFEST,
    WorkflowStage.GENERATION,
}


@dataclass(frozen=True, slots=True)
class WorkflowState:
    """保存一次运行任务的完整状态。

    它会被保存到 Artifact 中，
    用于恢复、查询和测试。

    frozen=True:
    状态创建后不可修改。

    状态变化时：
        旧状态
          ↓
        创建新的状态对象

    这种方式更安全。
    """

    run_id: str

    # 当前整体状态
    status: WorkflowStatus

    # 当前具体阶段
    stage: WorkflowStage

    # 生成文件路径等产物信息
    artifact_paths: Mapping[str, str]

    # 失败信息
    error_code: str | None = None
    error_message: str | None = None


    def __post_init__(self):

        # 检查基础字段是否合法
        run_id = _require_non_blank(
            self.run_id,
            field_name="run_id",
        )

        if not isinstance(self.status, WorkflowStatus):
            raise TypeError(
                "status 必须是 WorkflowStatus"
            )

        if not isinstance(self.stage, WorkflowStage):
            raise TypeError(
                "stage 必须是 WorkflowStage"
            )


        # artifact 路径必须是字典结构
        if not isinstance(self.artifact_paths, Mapping):
            raise TypeError(
                "artifact_paths 必须是 mapping"
            )


        # 清理路径数据
        normalized_paths = {}

        for key, value in self.artifact_paths.items():
            normalized_paths[
                _require_non_blank(
                    key,
                    field_name="artifact key",
                )
            ] = _require_non_blank(
                value,
                field_name="artifact path",
            )


        error_code = _normalize_optional_string(
            self.error_code,
            field_name="error_code",
        )

        error_message = _normalize_optional_string(
            self.error_message,
            field_name="error_message",
        )


        # 失败状态必须携带错误信息
        if self.status in {
            WorkflowStatus.FAILED,
            WorkflowStatus.NEEDS_USER_INPUT,
        }:
            if error_code is None:
                raise ValueError(
                    "失败状态必须有 error_code"
                )

            if error_message is None:
                raise ValueError(
                    "失败状态必须有 error_message"
                )


        # 正常运行状态不能带错误信息
        elif error_code or error_message:
            raise ValueError(
                "非失败状态不能包含错误信息"
            )


        # 状态和阶段必须匹配

        if self.status is WorkflowStatus.CREATED:

            if self.stage is not WorkflowStage.CREATED:
                raise ValueError(
                    "created 状态必须对应 created 阶段"
                )


        elif self.status is WorkflowStatus.RUNNING:

            if self.stage not in _RUNNING_STAGES:
                raise ValueError(
                    "running 状态必须处于执行阶段"
                )


        elif self.status is WorkflowStatus.COMPLETED:

            if self.stage is not WorkflowStage.COMPLETED:
                raise ValueError(
                    "completed 必须对应 completed 阶段"
                )


        object.__setattr__(
            self,
            "run_id",
            run_id,
        )

        # 防止外部修改 artifact 路径
        object.__setattr__(
            self,
            "artifact_paths",
            MappingProxyType(normalized_paths),
        )


    @classmethod
    def initial(
        cls,
        paths: RunArtifactPaths,
    ):
        """创建任务初始状态。"""

        return cls(
            run_id=paths.run_id,
            status=WorkflowStatus.CREATED,
            stage=WorkflowStage.CREATED,
            artifact_paths=paths.to_dict(),
        )


    def advance(
        self,
        stage: WorkflowStage,
    ):
        """进入下一个阶段。

        不修改当前对象，
        而是返回新的状态。
        """

        self._require_non_terminal()

        allowed = _ALLOWED_TRANSITIONS.get(
            self.stage,
            set(),
        )

        # 不允许非法跳转
        if stage not in allowed:
            raise WorkflowTransitionError(
                f"非法阶段转换: "
                f"{self.stage.value} -> {stage.value}"
            )


        return WorkflowState(
            run_id=self.run_id,
            status=WorkflowStatus.RUNNING,
            stage=stage,
            artifact_paths=self.artifact_paths,
        )


    def complete(self):
        """任务成功完成。

        只有 Lua 生成阶段完成后，
        才允许进入 completed。
        """

        self._require_non_terminal()

        if self.stage is not WorkflowStage.GENERATION:
            raise WorkflowTransitionError(
                "必须完成 Lua 生成后才能结束"
            )

        return WorkflowState(
            run_id=self.run_id,
            status=WorkflowStatus.COMPLETED,
            stage=WorkflowStage.COMPLETED,
            artifact_paths=self.artifact_paths,
        )


    def fail(
        self,
        code: str,
        message: str,
    ):
        """记录失败状态。"""

        self._require_non_terminal()

        return WorkflowState(
            run_id=self.run_id,
            status=WorkflowStatus.FAILED,
            stage=self.stage,
            artifact_paths=self.artifact_paths,
            error_code=code,
            error_message=message,
        )


    def needs_user_input(
        self,
        code: str,
        message: str,
    ):
        """暂停等待用户决策。"""

        self._require_non_terminal()

        return WorkflowState(
            run_id=self.run_id,
            status=WorkflowStatus.NEEDS_USER_INPUT,
            stage=self.stage,
            artifact_paths=self.artifact_paths,
            error_code=code,
            error_message=message,
        )


    def to_dict(self):
        """转换成可以保存的 JSON 数据。"""

        return {
            "run_id": self.run_id,
            "status": self.status.value,
            "stage": self.stage.value,
            "artifact_paths": dict(self.artifact_paths),
            "error_code": self.error_code,
            "error_message": self.error_message,
        }


    def _require_non_terminal(self):
        """禁止已经结束的任务继续变化。"""

        if self.status in _TERMINAL_STATUSES:
            raise WorkflowTransitionError(
                "任务已经结束，不能继续转换"
            )


def _require_non_blank(
    value: str,
    *,
    field_name: str,
):
    """检查字符串不能为空。"""

    if not isinstance(value, str):
        raise TypeError(
            f"{field_name} 必须是字符串"
        )

    value = value.strip()

    if not value:
        raise ValueError(
            f"{field_name} 不能为空"
        )

    return value


def _normalize_optional_string(
    value: str | None,
    *,
    field_name: str,
):
    """处理可选字符串字段。"""

    if value is None:
        return None

    return _require_non_blank(
        value,
        field_name=field_name,
    )