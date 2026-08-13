"""Deterministic comparison of Phase 5 candidate outcomes.
Phase6 候选结果确定性对比、分类与排行榜排名工具
接收多条Phase5候选评估结果，统一划分结果类别、按得分规则排序，生成标准化排行榜条目；
区分执行失败、语义违规、无法打分、有效成功四类候选，仅合格候选参与排名，全程规则固定、结果可复现。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# Phase5 单候选最终输出结果模型
from cmo_lua_agent.optimization.candidate_models import CandidateOutcome
# Phase6 榜单标识、排行榜条目数据模型
from cmo_lua_agent.optimization.phase6_models import EvaluationIdentity, LeaderboardEntry


class CandidateComparator:
    """按正式评分与有效性规则比较候选，提供稳定排序而不预测 CMO 得分。"""
    def compare(self, *, outcomes: Iterable[tuple[CandidateOutcome, EvaluationIdentity, bool]]) -> tuple[LeaderboardEntry, ...]:
        """
        批量处理一批候选结果，完成分类、打分排序、生成排行榜条目
        :param outcomes: 迭代器，每条内容 (候选结果,评估标识,是否基线策略)
        :return: 全部候选组成的排行榜条目元组（携带名次）
        """
        entries: list[LeaderboardEntry] = []
        expected: EvaluationIdentity | None = None

        for outcome, identity, is_baseline in outcomes:
            # 校验：所有候选必须属于同一轮评估标识，防止跨批次数据混排
            consistent = expected is None or identity == expected
            if expected is None:
                expected = identity

            # 根据候选运行结果划分类别
            category = _category(outcome, consistent)
            # 提取原始总分，无得分则为None
            raw_score = outcome.native_score

            # 构造榜单基础条目（暂时不填充名次rank）
            entries.append(LeaderboardEntry(
                outcome.candidate_id,
                is_baseline,
                category,
                None,                # 名次先留空
                raw_score,
                outcome.success,
                outcome.semantic_valid,
                outcome.scoreable,
                outcome.repair_invocations,
                outcome.execution_attempts,
                outcome.failure_reason.value,
                str(Path(outcome.candidate_dir) / "candidate_outcome.json"),
                consistent,
            ))

        # 筛选只有【有效成功】的候选参与排名
        # 排序规则：优先分数从高到低；分数相同则修复调用次数更少优先；再相同仿真尝试次数更少；最后候选ID字典序
        ranked = sorted(
            (entry for entry in entries if entry.category == "ranked_success"),
            key=lambda entry: (-int(entry.raw_score), entry.repair_invocations, entry.execution_attempts, entry.candidate_id)
        )
        # 建立候选ID -> 名次映射（从1开始）
        ranks = {entry.candidate_id: index + 1 for index, entry in enumerate(ranked)}

        # 给所有条目填充名次，无排名的候选rank为None，返回最终榜单
        return tuple(_with_rank(entry, ranks.get(entry.candidate_id)) for entry in entries)


def _category(outcome: CandidateOutcome, contract_consistent: bool) -> str:
    """
    对候选结果进行四分类判定（Phase6分类标准）
    注意：Phase5会把语义校验/打分失败统一标记success=False，但Phase6需要更精细区分类别
    """
    # 跨批次数据不一致 / Lua无法正常运行执行 → 执行失败
    if (
        outcome.artifact_provenance != "formal_renderer"
        or not outcome.executable
        or not contract_consistent
        or (isinstance(outcome.scenario_reset, dict) and not outcome.scenario_reset.get("scenario_reset_verified", False))
    ):
        return "execution_failed"
    # 仿真能跑完，但作战行为偏离策略意图 → 语义无效
    if not outcome.semantic_valid:
        return "semantic_invalid"
    # 能执行、语义合规，但缺少数据，无法计算有效得分
    if not outcome.scoreable or outcome.native_score is None:
        return "unscorable"
    # 全部校验通过，可以参与排名的有效候选
    return "ranked_success"


def _with_rank(entry: LeaderboardEntry, rank: int | None) -> LeaderboardEntry:
    """复制原有榜单条目，补充名次rank字段，生成新条目（数据模型不可变）"""
    return LeaderboardEntry(
        entry.candidate_id, entry.is_baseline, entry.category, rank, entry.raw_score,
        entry.execution_success, entry.semantic_valid, entry.scoreable,
        entry.repair_invocations, entry.execution_attempts, entry.failure_reason,
        entry.outcome_path, entry.contract_consistent
    )
