"""
推演任务受控执行的终止判定策略
按照优先级顺序判断各类终止条件，一旦命中最高优先级触发条件，输出终止决策
"""
from __future__ import annotations

from cmo_lua_agent.evolution.models import StopDecision, StopReason


class StopPolicy:
    """
    推演终止规则判定器
    有序遍历全部终止触发条件，优先级从上至下；先命中的条件优先生效，生成停止决策。
    """
    def evaluate(self, *, contract_changed: bool = False, manual_stop_requested: bool = False,
                 cmo_lock_unavailable: bool = False, require_human_review: bool = False,
                 max_generations_reached: bool = False, budget_exhausted: bool = False,
                 no_improvement_exhausted: bool = False) -> StopDecision:
        """
        评估当前是否应当终止整个推演任务
        :param contract_changed: 核心推演契约发生变更
        :param manual_stop_requested: 收到人工下发停止指令
        :param cmo_lock_unavailable: 无法获取CMO实例独占锁
        :param require_human_review: 需要人工介入审查
        :param max_generations_reached: 已达到设置的最大世代数量
        :param budget_exhausted: CMO仿真全局算力预算耗尽
        :param no_improvement_exhausted: 连续多代无有效分数提升，耐心阈值耗尽
        :return: StopDecision 终止决策对象（是否停止 + 终止原因）
        """
        # 终止条件列表，顺序 = 优先级由高到低
        checks = (
            (contract_changed, StopReason.CONTRACT_CHANGED),
            (manual_stop_requested, StopReason.MANUAL_STOP_REQUESTED),
            (cmo_lock_unavailable, StopReason.CMO_LOCK_UNAVAILABLE),
            (require_human_review, StopReason.REQUIRE_HUMAN_REVIEW),
            (budget_exhausted, StopReason.MAX_CMO_RUNS_REACHED),
            (no_improvement_exhausted, StopReason.NO_IMPROVEMENT_PATIENCE_EXHAUSTED),
            (max_generations_reached, StopReason.MAX_GENERATIONS_REACHED),
        )
        # 按优先级依次检查，第一个满足的条件作为最终终止原因
        for enabled, reason in checks:
            if enabled:
                return StopDecision(True, reason)
        # 所有终止条件均不满足，继续运行推演
        return StopDecision(False, StopReason.NONE)