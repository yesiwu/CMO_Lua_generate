"""
构造受约束的Phase 9世代规划上下文；本模块不负责生成StrategySpec策略规约。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json

from cmo_lua_agent.evolution.knowledge_snapshot import KnowledgeSnapshot


@dataclass(frozen=True, slots=True)
class GenerationPlan:
    """
    单世代演化规划方案
    承载生成候选策略所需全部上下文、参考策略引用、知识快照与完整性校验哈希
    """
    campaign_id: str                     # 推演任务ID
    generation_index: int                # 当前世代编号
    optimization_id: str                 # 本次优化唯一标识
    anchor_strategy_ref: str             # 锚点策略引用地址
    rolling_strategy_ref: str            # 滚动基线策略引用（当前全局最优）
    parent_strategy_ref: str             # 父代策略引用，继承演化起点
    knowledge_snapshot_ref: str          # 知识库快照引用
    context: dict[str, object]           # 完整规划上下文载荷（传给LLM用于生成候选策略）
    checksum: str                        # 规划内容哈希，用于完整性校验


class GenerationPlanner:
    """
    世代规划生成器
    为每一代构造标准化规划上下文，固定4条候选策略分工角色，封装演化约束与知识库素材。
    """
    # 4条候选策略固定分工角色
    _ROLES = {
        "candidate_00": "exploit",              # 利用型：深耕当前最优策略，小幅优化
        "candidate_01": "repair",               # 修复型：修补现有策略缺陷、规避失败模式
        "candidate_02": "explore",              # 探索型：大范围尝试新颖战术方案
        "candidate_03": "conservative_control", # 保守控制型：降低风险、减少资源消耗
    }

    def plan(self, *, campaign_id: str, generation_index: int, anchor_strategy_ref: str,
             rolling_strategy_ref: str, knowledge_snapshot_ref: str, snapshot: KnowledgeSnapshot,
             objective: str, allowed_strategy_paths: tuple[str, ...], history_fingerprints: tuple[str, ...],
             previous_generation_failures: tuple[str, ...]) -> GenerationPlan:
        """
        组装生成一份世代规划方案
        :param campaign_id: 推演任务ID
        :param generation_index: 当前世代编号
        :param anchor_strategy_ref: 锚点策略引用
        :param rolling_strategy_ref: 滚动最优基线策略引用
        :param knowledge_snapshot_ref: 知识快照引用标识
        :param snapshot: 加载完成的知识库快照
        :param objective: 当前演化优化目标文字描述
        :param allowed_strategy_paths: 允许加载的历史策略路径集合
        :param history_fingerprints: 历史已评估策略指纹集合，避免重复探索
        :param previous_generation_failures: 上一代失败策略/失败模式指纹
        :return: 不可变 GenerationPlan 规划对象
        """
        # 组装完整上下文载荷，提供给LLM策略生成环节
        body = {
            "generation_index": generation_index,
            "candidate_roles": self._ROLES,                         # 4条候选分工定义
            "objective": objective,                                 # 优化目标
            "allowed_strategy_paths": list(allowed_strategy_paths),# 可复用历史策略
            "history_fingerprints": list(history_fingerprints),     # 历史策略指纹，防止重复生成
            "previous_generation_failures": list(previous_generation_failures), # 上代失败经验
            "retrieved_experience_cards": [dict(item) for item in snapshot.experience_cards], # 经验案例卡片
            "active_curated_skills": [dict(item) for item in snapshot.active_skills], # 可用战术技能库
            "knowledge_snapshot_checksum": snapshot.checksum,      # 绑定知识库快照哈希
            "conservative_max_changed_leaves": 1,                  # 保守策略最大允许改动节点数量约束
        }
        # 计算规划上下文哈希，保证规划未被篡改、可复现
        checksum = sha256(json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        return GenerationPlan(
            campaign_id=campaign_id,
            generation_index=generation_index,
            optimization_id=f"{campaign_id}_generation_{generation_index:03d}",
            anchor_strategy_ref=anchor_strategy_ref,
            rolling_strategy_ref=rolling_strategy_ref,
            parent_strategy_ref=rolling_strategy_ref, # 默认以上一代最优基线作为演化父本
            knowledge_snapshot_ref=knowledge_snapshot_ref,
            context=body,
            checksum=checksum,
        )