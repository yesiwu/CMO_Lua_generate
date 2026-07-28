"""
Phase9 候选策略在启动CMO仿真前执行确定性新颖性校验，针对四类分工候选做规则约束
保证种群多样性，防止策略重复、演化收敛停滞
"""
from __future__ import annotations

from cmo_lua_agent.optimization.candidate_set_validator import strategy_leaf_diff
from cmo_lua_agent.optimization.phase6_models import StrategyCandidate


class CandidateNoveltyValidator:
    """
    候选策略新颖性校验器
    在送入Phase6执行CMO推演之前，对4条候选策略集合做多样性、角色合规性校验；
    校验不通过直接抛出异常，拒绝进入仿真环节。
    """
    def validate(self, *, baseline, candidates: tuple[StrategyCandidate, ...], generation_context: dict[str, object]) -> None:
        """
        :param baseline: 当前滚动基线策略
        :param candidates: 当前世代4条候选策略集合
        :param generation_context: GenerationPlan.context 规划上下文（包含角色定义、约束参数、历史指纹）
        """
        # 允许改动的策略节点路径白名单
        allowed = tuple(generation_context.get("allowed_strategy_paths", ()))
        # 历史已经评估过的策略指纹集合，避免重复仿真
        history = set(generation_context.get("history_fingerprints", ()))
        # candidate_id → 角色映射 {candidate_00: exploit ...}
        roles = dict(generation_context.get("candidate_roles", {}))

        fingerprints: set[str] = set()   # 记录本世代内部候选指纹，防止本代重复
        dimensions: set[str] = set()    # 收集所有策略改动的维度，用于校验探索型策略

        for candidate in candidates:
            # 规则1：同一世代内部不能出现完全相同的策略
            if candidate.strategy_checksum in fingerprints:
                raise ValueError("novelty_duplicate_candidate")
            fingerprints.add(candidate.strategy_checksum)

            # 规则2：不能生成历史上已经评估过的策略，避免浪费算力重复推演
            if candidate.strategy_checksum in history:
                raise ValueError("novelty_repeated_history")

            # 计算候选相对基线改动的叶子节点路径（只统计允许修改的路径）
            changed = strategy_leaf_diff(baseline, candidate.strategy_spec, allowed)

            # 规则3：候选不能和基线完全一致，必须存在改动
            if not changed:
                raise ValueError("novelty_matches_rolling_baseline")

            # 提取改动所属维度，用于后续探索型策略校验
            dimensions.update(path.split("/")[1] for path in changed if path.count("/") >= 2)

            role = roles.get(candidate.candidate_id)
            # 规则4：保守型策略，改动叶子数量不能超过上限（默认最多改动1处）
            if role == "conservative_control" and len(changed) > int(generation_context.get("conservative_max_changed_leaves", 1)):
                raise ValueError("novelty_conservative_scope_exceeded")

            # 规则5：修复型策略，必须存在上一代失败案例作为修复依据
            if role == "repair" and not generation_context.get("previous_generation_failures"):
                raise ValueError("novelty_repair_has_no_prior_failure")

        # 规则6：探索型策略要求至少在2个不同维度产生改动，保证足够探索广度
        """
        维度 = JSON Pointer 第二层名称（顶层业务域）
            举一套你们兵棋策略典型顶层划分：
            weapon_usage 武器使用规则
            sensor 传感器探测策略
            maneuver 机动规避方案
            force_employment 兵力编组
            engagement_timing 接战时机
            defense_countermeasure 防御对抗手段
        规则 6 完整含义
            探索型候选 explore，整套世代所有改动加起来，至少覆盖 2 个不同顶层业务域。
        """
        explore_id = next((candidate_id for candidate_id, role in roles.items() if role == "explore"), None)
        if explore_id and len(dimensions) < 2:
            raise ValueError("novelty_explore_dimension_missing")