"""JSON → Lua Workflow 的执行协调器。

负责协调一次任务运行：

状态推进：
WorkflowState

文件保存：
RunArtifactStore

Lua生成：
LuaGenerationService


这里类似一个“项目经理”：
负责安排流程，但不亲自干具体工作。
"""


from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cmo_lua_agent.artifacts import (
    ArtifactPersistenceError,
    RunArtifactStore,
)

from cmo_lua_agent.contract import (
    ResolvedScenarioManifest,
    ScenarioContract,
)

from cmo_lua_agent.generation import (
    LuaGenerationResult,
    LuaGenerationService,
)

from cmo_lua_agent.orchestration.workflow_state import (
    WorkflowStage,
    WorkflowState,
    WorkflowStatus,
    WorkflowTransitionError,
)


@dataclass(slots=True)
class WorkflowContext:
    """一次 Workflow 执行上下文。

    保存：
    1. 当前任务状态；
    2. 产物保存入口。

    后续所有阶段推进都通过这里完成。
    """

    store: RunArtifactStore
    state: WorkflowState


    def __post_init__(self):

        # 保证状态和文件存储属于同一次运行
        if not isinstance(self.store, RunArtifactStore):
            raise TypeError(
                "store 必须是 RunArtifactStore"
            )

        if not isinstance(self.state, WorkflowState):
            raise TypeError(
                "state 必须是 WorkflowState"
            )

        if self.store.run_id != self.state.run_id:
            raise ValueError(
                "store 和 state 必须属于同一个任务"
            )


    @classmethod
    def create(
        cls,
        runs_root: Path,
        *,
        run_id: str | None = None,
    ):
        """创建一次新的 Workflow。

        创建：
        运行目录
        +
        初始状态

        并立即保存状态，方便后续恢复。
        """

        store = RunArtifactStore.create(
            runs_root,
            run_id=run_id,
        )

        context = cls(
            store=store,
            state=WorkflowState.initial(
                store.paths
            ),
        )

        context._persist_state()

        return context


    def advance(
        self,
        stage: WorkflowStage,
    ):
        """推进 Workflow 到下一阶段。"""

        # 状态转换规则由 WorkflowState 控制
        self.state = self.state.advance(stage)

        # 每次变化立即保存
        self._persist_state()

        return self.state


    def save_manifest(
        self,
        manifest: ResolvedScenarioManifest,
    ):
        """保存解析后的场景清单。

        Manifest 是 Lua 生成前的重要中间结果。
        """

        if not isinstance(
            manifest,
            ResolvedScenarioManifest,
        ):
            raise TypeError(
                "manifest 类型错误"
            )


        # 保存 Manifest 前必须进入对应阶段
        self.state = self.state.advance(
            WorkflowStage.MANIFEST
        )

        self._persist_state()

        return self.store.save_manifest(
            manifest
        )


    def generate_lua(
        self,
        service: LuaGenerationService,
        *,
        manifest: ResolvedScenarioManifest,
        contract: ScenarioContract,
    ):
        """调用 Lua 生成服务，并保存生成结果。

        本函数负责：
        1. 推进状态；
        2. 调用生成服务；
        3. 保存生成结果；
        4. 失败时记录错误。


        不负责：
        Lua 如何生成。
        """

        if (
            self.state.status
            is not WorkflowStatus.RUNNING
            or self.state.stage
            is not WorkflowStage.MANIFEST
        ):
            raise WorkflowTransitionError(
                "必须先保存 Manifest 才能生成 Lua"
            )


        try:

            # 进入 Lua 生成阶段
            self.state = self.state.advance(
                WorkflowStage.GENERATION
            )

            self._persist_state()


            # 真正生成 Lua
            result = service.generate(
                manifest=manifest,
                contract=contract,
                manifest_path=self.store.paths.resolved_manifest,
                output_path=self.store.paths.original_lua,
            )


            # 保存生成检查结果
            self.store.save_validation(
                "lua_preflight",
                result.preflight,
            )


            candidate = _require_candidate_text(
                result
            )


            if result.success:

                # 生成成功，保存正式 Lua
                self.store.save_original_lua(
                    candidate
                )

            else:

                # 生成失败，保存候选版本用于分析
                self.store.save_rejected_lua(
                    candidate
                )


            return result


        except Exception as exc:

            # 区分：
            # 文件保存失败
            # 生成失败
            code = (
                "artifact_persistence_failed"
                if isinstance(
                    exc,
                    ArtifactPersistenceError,
                )
                else "generation_failed"
            )


            # 尝试留下失败状态
            self._mark_failed_best_effort(
                code,
                str(exc),
            )

            raise


    def complete(self):
        """完成 Workflow。

        必须满足：
        1. 已存在有效 Lua；
        2. 没有失败候选文件。
        """

        if not self.store.paths.original_lua.is_file():

            raise WorkflowTransitionError(
                "没有生成成功 Lua，不能完成"
            )


        if self.store.paths.rejected_lua.exists():

            raise WorkflowTransitionError(
                "存在失败 Lua 候选，不能完成"
            )


        self.state = self.state.complete()

        self._persist_state()

        return self.state


    def fail(
        self,
        code: str,
        message: str,
    ):

        # 保存失败状态
        self.state = self.state.fail(
            code,
            message,
        )

        self._persist_state()

        return self.state


    def needs_user_input(
        self,
        code: str,
        message: str,
    ):
        """暂停等待用户决策。"""

        self.state = self.state.needs_user_input(
            code,
            message,
        )

        self._persist_state()

        return self.state


    def _persist_state(self):
        """保存当前 Workflow 状态。"""

        return self.store.save_final_result(
            self.state
        )


    def _mark_failed_best_effort(
        self,
        code: str,
        message: str,
    ):
        """尽力保存失败状态。

        即使保存失败，也不能覆盖原始异常。
        """

        try:

            self.state = self.state.fail(
                code,
                message,
            )

        except (
            WorkflowTransitionError,
            TypeError,
            ValueError,
        ):

            return


        try:

            self._persist_state()

        except ArtifactPersistenceError:

            # 不让失败记录失败覆盖真正原因
            pass



def _require_candidate_text(
    result: LuaGenerationResult,
):
    """检查生成结果是否包含有效 Lua 文本。"""

    if (
        result.lua_text is None
        or not result.lua_text.strip()
    ):
        raise ValueError(
            "生成结果中没有有效 Lua 内容"
        )

    return result.lua_text