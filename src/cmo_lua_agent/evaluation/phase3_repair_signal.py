"""把 Phase3 已经解析好的仿真结果，转换成确定性的修复信号。

这层不重新读取原始日志，也不调用 LLM。

它只负责：

    Phase3EvaluationResult
        ↓
    从标准化攻击结果里找错误
        ↓
    判断错误属于哪一类
        ↓
    定位对应的 operation
        ↓
    输出 RepairSignal

后续真正怎么修，由 LuaRepairAgent / RepairWorkflow 处理。
"""

from __future__ import annotations

from dataclasses import dataclass

from cmo_lua_agent.evaluation.phase3_evaluation import (
    Phase3EvaluationResult,
)
from cmo_lua_agent.generation.runtime_models import (
    ExecutionPlan,
)


@dataclass(frozen=True, slots=True)
class RepairSignal:
    """一条标准化修复信号。

    它表示：

        出了什么问题；
        问题对应哪个执行操作；
        原始错误信息是什么；
        当前错误是否允许进入自动修复流程。
    """

    # 标准化错误类型，例如：
    # missing_contact
    # launch_timeout
    # attack_command_failed
    kind: str

    # 这个错误对应 ExecutionPlan 中的 operation_id。
    # 下游修复时可以直接定位问题操作。
    operation_id: str

    # Phase3 中已经整理出来的原始错误信息。
    message: str

    # 是否允许进入自动修复。
    #
    # True：
    #   当前错误的修复方向比较明确。
    #
    # False：
    #   可以识别错误，但暂时没有安全、确定的自动修复方式。
    repairable: bool


class Phase3RepairSignalMapper:
    """把 Phase3 标准化评估结果映射成修复信号。

    注意：

    这里不是修复 Agent。

    它只负责回答：

        “哪里出了问题？”
        “应该修哪个 operation？”
        “这个问题目前能不能自动修？”

    不负责真正修改 Strategy、Runtime 或 Lua。
    """

    def map(
        self,
        *,
        result: Phase3EvaluationResult,
        plan: ExecutionPlan,
    ) -> RepairSignal | None:
        """从 Phase3 评估结果中提取第一条支持的修复信号。"""

        # -------------------------------------------------
        # 第一步：先确认 Phase3 的证据本身可信
        # -------------------------------------------------
        #
        # 如果：
        #   - 多份证据无法对齐；
        #   - 语义校验失败；
        #   - 当前结果不可评分；
        #
        # 就不能继续根据这些结果判断“Lua哪里需要修”。
        #
        # 否则可能是仿真结果本身有问题，
        # 却被误判成策略或 Runtime 的问题。
        if (
            result.reconciliation.status != "valid"
            or not result.semantic_validation.semantic_valid
            or not result.semantic_validation.scoreable
        ):
            return None

        # -------------------------------------------------
        # 第二步：检查每一条标准化攻击链
        # -------------------------------------------------
        #
        # AttackEpisode 已经是 Phase3 从：
        #   execution-summary
        #   SQLite / CSV
        #   Lua telemetry
        #
        # 中整理出来的结构化结果。
        #
        # 所以这里不再重新读日志。
        for episode in result.attack_episodes:

            # 一个攻击过程可能对应多条重要错误
            for error in episode.important_errors:
                lowered = error.lower()

                # -----------------------------------------
                # 情况1：没有获得目标 Contact
                # -----------------------------------------
                #
                # 例如：
                #   missing_contact
                #   contact unavailable
                #
                # 这种错误虽然发生在攻击过程中，
                # 但真正应该检查的通常是前面的：
                #
                #   prepare_target_contact
                #
                # 所以这里根据 target_id，
                # 找到对应的 Contact 准备操作。
                if (
                    "missing_contact" in lowered
                    or "contact unavailable" in lowered
                ):
                    operation_id = (
                        self._contact_operation(
                            plan,
                            episode.target_id,
                        )
                    )

                    # 只有能够明确定位到具体 operation，
                    # 才允许生成自动修复信号。
                    if operation_id:
                        return RepairSignal(
                            kind="missing_contact",
                            operation_id=operation_id,
                            message=error,
                            repairable=True,
                        )

                # -----------------------------------------
                # 情况2：飞机起飞超时
                # -----------------------------------------
                #
                # 当前只能确定：
                #   “起飞阶段失败”
                #
                # 但具体原因可能涉及：
                #   机场状态
                #   飞机状态
                #   调度时机
                #   Runtime逻辑
                #
                # 所以只产生诊断信号，
                # 暂时不允许自动修复。
                if "launch timeout" in lowered:
                    return RepairSignal(
                        kind="launch_timeout",
                        operation_id=(
                            episode.operation_id or ""
                        ),
                        message=error,
                        repairable=False,
                    )

                # -----------------------------------------
                # 情况3：攻击命令调用失败
                # -----------------------------------------
                #
                # 这类错误可能来自：
                #   Contact不存在
                #   平台状态异常
                #   武器不可用
                #   CMO API参数错误
                #   Runtime实现问题
                #
                # 当前无法确定唯一安全修复方式，
                # 因此只标记问题，不自动修。
                if "attack command" in lowered:
                    return RepairSignal(
                        kind="attack_command_failed",
                        operation_id=(
                            episode.operation_id or ""
                        ),
                        message=error,
                        repairable=False,
                    )

                # -----------------------------------------
                # 情况4：进入攻击距离超时
                # -----------------------------------------
                #
                # 可以确定失败阶段是攻击距离等待，
                # 但到底应该改：
                #   航路
                #   攻击距离
                #   等待时间
                #   Runtime
                #
                # 目前还不能确定，所以不自动修。
                if "range timeout" in lowered:
                    return RepairSignal(
                        kind="attack_range_timeout",
                        operation_id=(
                            episode.operation_id or ""
                        ),
                        message=error,
                        repairable=False,
                    )

        # 没有发现当前支持的修复信号
        return None

    @staticmethod
    def _contact_operation(
        plan: ExecutionPlan,
        target_id: str,
    ) -> str | None:
        """找到某个目标对应的 Contact 准备操作。

        例如执行计划中：

            op_01:
                prepare_target_contact
                target_id = blue_01

            op_02:
                aircraft_attack
                target_id = blue_01

        如果 op_02 最终报：

            missing_contact

        真正需要检查的通常不是攻击操作 op_02，
        而是前面的 Contact 准备操作 op_01。

        所以这里根据 target_id，
        反查对应的 prepare_target_contact operation_id。
        """

        for operation in plan.operations:

            if (
                operation.primitive_type
                == "prepare_target_contact"
                and str(
                    operation.parameters.get(
                        "target_id"
                    )
                )
                == target_id
            ):
                return operation.operation_id

        return None