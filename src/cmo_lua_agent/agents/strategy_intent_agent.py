"""候选意图 Agent：把本代目标转化为四个受约束的候选方案意图。

该模块接收 Phase 6 的策略上下文，调用结构化 LLM 客户端生成候选意图；下游
``strategy_patch_agent`` 再据此生成可验证补丁。它只负责意图，不直接修改策略或执行 CMO。
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Protocol

from cmo_lua_agent.optimization.phase6_models import StrategyProposalContext
from cmo_lua_agent.optimization.proposal_models import (
    CANDIDATE_IDS,
    CandidateIntent,
    CandidateRoleSpec,
    ProposalContractError,
    STRATEGY_DIMENSIONS,
)


class IntentJsonClient(Protocol):
    def complete_json(self, *, system: str, prompt: str) -> object: ...


_LEGACY_ROLE_SPECS = (
    ("exploit", 1, 2),
    ("repair", 1, 2),
    ("explore", 2, 3),
    ("conservative", 1, 1),
)


class CandidateIntentPlanner:
    """调用结构化 LLM 规划候选意图；不生成完整 StrategySpec，也不管理预算。"""
    def __init__(self, client: IntentJsonClient) -> None:
        self._client = client
        self.last_call_count = 0

    def plan(
        self,
        context: StrategyProposalContext,
        *,
        role_specs: tuple[CandidateRoleSpec, ...] | None = None,
    ) -> tuple[CandidateIntent, ...]:
        allowed_dimensions = _supported_dimensions(context)
        if role_specs is not None and len(role_specs) != 4:
            raise ProposalContractError("invalid_candidate_role_specs")
        response = self._client.complete_json(
            system=_SYSTEM,
            prompt=json.dumps({
                "user_objective": context.user_objective,
                "allowed_strategy_dimensions": sorted(allowed_dimensions),
                "bootstrap_skill": {"skill_id": context.bootstrap.skill_id, "content": context.bootstrap.content},
                "active_curated_skill": (
                    None if context.active_curated_skill is None else dict(context.active_curated_skill)
                ),
                "retrieved_experience_cards": [dict(card) for card in context.retrieved_experience_cards],
                "generation_context": dict(context.generation_context or {}),
                "proposal_tactical_context": (
                    None
                    if context.proposal_tactical_context is None
                    else dict(context.proposal_tactical_context)
                ),
                "candidate_role_constraints": [
                    {
                        "candidate_id": spec.candidate_id,
                        "role": spec.role,
                        "min_changed_leaves": spec.min_changed_leaves,
                        "max_changed_leaves": spec.max_changed_leaves,
                        "min_operations": spec.min_operations,
                        "min_dimensions": spec.min_dimensions,
                        "require_surface": spec.require_surface,
                        "require_sortie": spec.require_sortie,
                        "failure_profile_available": spec.failure_profile_mode == "required",
                    }
                    for spec in (role_specs or ())
                ],
            }, ensure_ascii=False, sort_keys=True),
        )
        self.last_call_count = int(getattr(self._client, "last_calls", 1))
        if not isinstance(response, Mapping) or set(response) != {"intents"}:
            raise ProposalContractError("invalid_intent_response_shape")
        rows = response["intents"]
        if not isinstance(rows, list) or len(rows) != 4:
            raise ProposalContractError("intent_count_must_be_four")
        intents: list[CandidateIntent] = []
        for index, row in enumerate(rows):
            if not isinstance(row, Mapping) or set(row) != {"objective", "strategy_dimensions"}:
                raise ProposalContractError("invalid_intent_fields")
            objective, dimensions = row["objective"], row["strategy_dimensions"]
            if not isinstance(objective, str) or not isinstance(dimensions, list) or not all(isinstance(item, str) for item in dimensions):
                raise ProposalContractError("invalid_intent_value")
            if any(dimension not in allowed_dimensions for dimension in dimensions):
                raise ProposalContractError("intent_dimension_not_allowed")
            if role_specs is None:
                role, minimum, maximum = _LEGACY_ROLE_SPECS[index]
                intent = CandidateIntent(
                    CANDIDATE_IDS[index], role, objective, tuple(dimensions), minimum, maximum
                )
            else:
                role_spec = role_specs[index]
                intent = CandidateIntent(
                    role_spec.candidate_id,
                    role_spec.role,
                    objective,
                    tuple(dimensions),
                    role_spec.min_changed_leaves,
                    role_spec.max_changed_leaves,
                    min_operations=role_spec.min_operations,
                    min_dimensions=role_spec.min_dimensions,
                    require_surface=role_spec.require_surface,
                    require_sortie=role_spec.require_sortie,
                    max_operations=role_spec.max_operations,
                    max_dimensions=role_spec.max_dimensions,
                    failure_profile_mode=role_spec.failure_profile_mode,
                    failure_operation_ids=role_spec.failure_operation_ids,
                    failure_semantic_dimensions=role_spec.failure_semantic_dimensions,
                    failure_profile_source_checksum=role_spec.failure_profile_source_checksum,
                )
            intents.append(intent)
        if len({dimension for intent in intents for dimension in intent.strategy_dimensions}) < 2:
            raise ProposalContractError("intent_diversity_dimensions_insufficient")
        return tuple(intents)


def _supported_dimensions(context: StrategyProposalContext) -> set[str]:
    values = {dimension for dimension in context.diversity_dimensions if dimension in STRATEGY_DIMENSIONS}
    if not values:
        raise ProposalContractError("no_supported_strategy_dimension")
    return values


_SYSTEM = """你是 CandidateIntentPlanner。只能返回一个 JSON 对象，其中 intents 数组必须恰好包含四项。
每项只能包含 objective 和 strategy_dimensions。strategy_dimensions 表示偏好的维度，
不是每个 Patch 都必须逐项实现的清单。
不得包含 candidate ID、角色、Patch、完整策略、Lua、CMO 命令、分数或额外字段。
只能从输入提供的维度中选择；候选固定角色由系统分配，所有 Patch 会在后续由系统校验。"""
