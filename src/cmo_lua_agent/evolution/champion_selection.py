"""
针对已完成迭代世代的确定性冠军策略筛选逻辑
"""
from __future__ import annotations

from cmo_lua_agent.evolution.models import CandidateScore, ChampionDecision


class ChampionSelectionPolicy:
    """
    世代冠军策略选择策略
    依据多维度打分规则选出本代最优候选策略，并对比滚动基线，判断是否产生有效进化
    """
    def __init__(self, *, minimum_improvement_delta: int) -> None:
        """
        :param minimum_improvement_delta: 判断策略进化所需的最低分数提升阈值
        """
        self._delta = minimum_improvement_delta

    def select(self, *, rolling_baseline: CandidateScore, candidates: tuple[CandidateScore, ...]) -> ChampionDecision:
        """
        执行冠军筛选决策
        :param rolling_baseline: 滚动基线策略（上一轮全局最优策略）
        :param candidates: 当前世代全部候选策略打分结果集合
        :return: 冠军决策对象，包含本代最优、下一代基线、是否实现有效提升、淘汰原因清单
        """
        # 基线策略必须合法可用，否则无法继续迭代
        if not rolling_baseline.eligible:
            raise ValueError("rolling_baseline_ineligible")

        # 收集所有不合法候选，标记淘汰原因为：不具备参选资格
        exclusions = {item.candidate_id: "ineligible" for item in candidates if not item.eligible}
        # 过滤得到具备参选资格的候选列表
        eligible = [item for item in candidates if item.eligible]

        # 场景1：本世代没有任何合法候选，继续沿用旧基线
        if not eligible:
            return ChampionDecision(
                best_candidate_id=None,
                selected_champion_id=rolling_baseline.candidate_id,
                selected_score=rolling_baseline.official_score or 0,
                improved=False,
                exclusion_reasons=exclusions,
            )

        # 多关键字排序，按优先级从高到低选出本代最优候选
        best = sorted(eligible, key=lambda item: (
            -(item.official_score or 0),          # 第一优先级：官方综合得分（降序，越高越好）
            item.own_loss_count,                  # 第二优先级：我方损失数量（升序，损失越少越好）
            -item.high_value_enemy_damage,        # 第三优先级：敌方高价值目标毁伤（降序，越高越好）
            item.unexpected_weapon_activity_count,# 第四优先级：异常武器使用次数（升序，越少越好）
            -int(item.execution_fidelity == "verified"), # 第五优先级：推演执行可信度，已验证优先
            item.weapon_expenditure,              # 第六优先级：武器消耗量（升序，节约弹药优先）
            item.candidate_id,                    # 最后：候选ID，保证排序结果完全确定性
        ))[0]

        baseline_score = rolling_baseline.official_score or 0
        # 判断是否满足进化条件：当前最优得分 ≥ 基线得分 + 最小提升阈值
        improved = (best.official_score or 0) >= baseline_score + self._delta

        return ChampionDecision(
            best_candidate_id=best.candidate_id,
            selected_champion_id=best.candidate_id if improved else rolling_baseline.candidate_id,
            selected_score=(best.official_score or 0) if improved else baseline_score,
            improved=improved,
            exclusion_reasons=exclusions,
        )
