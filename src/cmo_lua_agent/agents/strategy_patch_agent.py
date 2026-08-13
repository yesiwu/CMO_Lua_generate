"""候选补丁 Agent：根据已冻结的候选意图生成一个受约束策略补丁。

上游 ``strategy_intent_agent`` 负责确定候选方案意图；本模块仅把该意图映射到
允许修改的策略叶节点，并以结构化响应交给提案协调器校验。解析或契约失败时，
会要求模型返回完整替代响应，而不会直接落盘或执行 CMO。
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Protocol

from cmo_lua_agent.llm.json_client import JsonCompletionError
from cmo_lua_agent.optimization.proposal_models import AcceptedCandidateSummary, CandidateIntent, CandidatePatch, ProposalContractError, StrategyPatchOperation, MAX_EFFECTIVE_PATCH_LEAVES, MIN_EFFECTIVE_PATCH_LEAVES
from cmo_lua_agent.optimization.strategy_patch import (
    PatchableLeaf,
    validate_patch_paths_executable,
)
from cmo_lua_agent.optimization.strategy_dimensions import semantic_dimension


class PatchJsonClient(Protocol):
    def complete_json(self, *, system: str, prompt: str) -> object: ...


class CandidatePatchGenerator:
    """根据已冻结的意图与战术上下文生成标量 Patch，供确定性组装器验证。"""
    def __init__(self, client: PatchJsonClient) -> None:
        self._client = client

    def generate(
        self,
        *,
        intent: CandidateIntent,
        catalog: tuple[PatchableLeaf, ...],
        accepted: tuple[AcceptedCandidateSummary, ...],
        tactical_context: dict[str, object] | None = None,
        error: ProposalContractError | None = None,
    ) -> CandidatePatch:
        grouped_catalog = _catalog_by_dimension(catalog)
        try:
            response = self._client.complete_json(
                system=_SYSTEM,
                prompt=json.dumps({
                "candidate_id": intent.candidate_id,
                "role": intent.role,
                "objective": intent.objective,
                "preferred_dimensions": list(intent.preferred_dimensions),
                "required_dimensions": list(intent.required_dimensions),
                "hard_change_count": {"minimum": MIN_EFFECTIVE_PATCH_LEAVES, "maximum": MAX_EFFECTIVE_PATCH_LEAVES},
                "role_change_preference": {"minimum": intent.min_changes, "maximum": intent.max_changes},
                "operation_count": {"minimum": intent.min_operations, "maximum": intent.max_operations},
                "dimension_count": {"minimum": intent.min_dimensions, "maximum": intent.max_dimensions},
                "require_surface": intent.require_surface,
                "require_sortie": intent.require_sortie,
                "failure_profile_available": intent.failure_profile_mode == "required",
                "failure_operation_ids": list(intent.failure_operation_ids),
                "failure_semantic_dimensions": list(intent.failure_semantic_dimensions),
                "candidate_instruction": (
                    _candidate_instruction(intent)
                ),
                "repair_instruction": _repair_instruction(intent, error),
                "repair_alternatives": _repair_alternatives(catalog, error),
                "patchable_leaves": [leaf.to_prompt_dict() for leaf in catalog],
                "patchable_leaves_by_dimension": grouped_catalog,
                "accepted_candidates": [
                    {"candidate_id": item.candidate_id, "changed_paths": list(item.changed_paths), "strategy_dimensions": list(item.strategy_dimensions)}
                    for item in accepted
                ],
                "proposal_tactical_context": tactical_context,
                "previous_error": _repair_error(error),
                }, ensure_ascii=False, sort_keys=True),
            )
        except JsonCompletionError as error:
            raise ProposalContractError(
                "proposal_json_invalid", diagnostics=error.diagnostics
            ) from error
        if not isinstance(response, Mapping) or set(response) != {"proposal_summary", "changes"}:
            raise ProposalContractError("invalid_patch_response_shape")
        summary, changes = response["proposal_summary"], response["changes"]
        if not isinstance(summary, str) or not isinstance(changes, list):
            raise ProposalContractError("invalid_patch_response_value")
        operations: list[StrategyPatchOperation] = []
        for row in changes:
            if not isinstance(row, Mapping) or set(row) != {"path", "value"}:
                raise ProposalContractError("invalid_patch_change_fields")
            operations.append(StrategyPatchOperation(row["path"], row["value"]))
        patch = CandidatePatch(intent.candidate_id, summary, tuple(operations))
        validate_patch_paths_executable(patch)
        if not MIN_EFFECTIVE_PATCH_LEAVES <= len(patch.changes) <= MAX_EFFECTIVE_PATCH_LEAVES:
            raise ProposalContractError(
                "candidate_change_count_out_of_bounds",
                diagnostics={
                    "actual_change_count": len(patch.changes),
                    "required_min_changes": MIN_EFFECTIVE_PATCH_LEAVES,
                    "required_max_changes": MAX_EFFECTIVE_PATCH_LEAVES,
                    "proposed_paths": [change.path for change in patch.changes],
                },
            )
        known = {leaf.path for leaf in catalog}
        if any(change.path not in known for change in patch.changes):
            raise ProposalContractError("patch_path_not_offered")
        return patch


def _repair_error(error: ProposalContractError | None) -> dict[str, object] | None:
    if error is None:
        return None
    violations = getattr(error, "violations", ())
    payload: dict[str, object] = {
        "code": error.code,
        "diagnostics": dict(error.diagnostics),
        "changed_paths": list(getattr(error, "changed_paths", ())),
        "violations": [
            {
                "code": item.get("code"),
                "path": item.get("path"),
                "actual_value": item.get("actual_value"),
                "constraint_summary": item.get("constraint_summary"),
            }
            for item in violations
            if isinstance(item, Mapping)
        ],
    }
    for key in (
        "previous_patch",
        "actual_change_count",
        "actual_dimensions",
        "minimum_dimension_count",
        "required_change_range",
        "required_operation_range",
        "required_dimension_range",
        "changed_paths",
        "actual_operation_count",
    ):
        if key in error.diagnostics:
            payload[key] = error.diagnostics[key]
    return payload


def _repair_instruction(
    intent: CandidateIntent,
    error: ProposalContractError | None,
) -> str | None:
    if error is None:
        return None
    return (
        "返回一份完整替换用的 Patch。尽可能保留合法的初始变更，修复全部硬校验错误，"
        "并将角色质量告警作为偏好处理。changes 必须包含全部修正后的变更，不能只返回增量。"
        "每个替换值都必须不同于 patchable_leaves 中对应路径的 current_value；"
        "删除或替换任何无效果变更。若出现无效果变更，请从 repair_alternatives 选择值。"
    )


def _repair_alternatives(
    catalog: tuple[PatchableLeaf, ...], error: ProposalContractError | None,
) -> list[dict[str, object]]:
    """为无效果修复提供受限、确定性的备选值；不得由模型凭空编造。"""
    if error is None or error.code != "no_effective_change":
        return []
    noops = error.diagnostics.get("no_effective_changes")
    paths = (
        [item.get("path") for item in noops if isinstance(item, Mapping)]
        if isinstance(noops, list)
        else [error.diagnostics.get("path")]
    )
    alternatives: list[dict[str, object]] = []
    for path in paths:
        leaf = next((item for item in catalog if item.path == path), None)
        if leaf is None:
            continue
        values: list[object] = []
        if leaf.allowed_values:
            values = [value for value in leaf.allowed_values if value != leaf.current_value][:2]
        elif isinstance(leaf.current_value, (int, float)) and not isinstance(leaf.current_value, bool):
            for value in (leaf.current_value - 1, leaf.current_value + 1, leaf.minimum, leaf.maximum):
                if value is None or value == leaf.current_value:
                    continue
                if leaf.minimum is not None and value < leaf.minimum:
                    continue
                if leaf.maximum is not None and value > leaf.maximum:
                    continue
                if value not in values:
                    values.append(value)
                if len(values) == 2:
                    break
        alternatives.append({
            "path": leaf.path,
            "baseline_value": leaf.current_value,
            "allowed_alternatives": values,
        })
    return alternatives


def _candidate_instruction(intent: CandidateIntent) -> str:
    noops = (
        " 从 patchable_leaves 中选择的每条路径都必须设置为不同于 current_value 的值。"
        "不得重复 Baseline 值。"
    )
    if intent.candidate_id == "candidate_02":
        return (
            "优先产生 5 到 8 项不同变更，覆盖至少 3 个操作和 3 个语义维度；合适时同时覆盖"
            " surface 与 sortie 操作。这些是质量目标，不是硬性 schema 要求。"
            + noops
        )
    if intent.candidate_id == "candidate_03":
        return (
            "优先只做一到两项变更，并集中于一个操作和一个语义维度，使结果便于解释。"
            "这是质量偏好，不是硬性 schema 规则。"
            + noops
        )
    return (
        "使用角色偏好让实验具备价值，同时确保每项变更都在提供的可执行叶子范围内。"
        "每项变更都必须将路径设置为不同于 patchable_leaves 中 current_value 的值。"
        "不得重复 Baseline 值。"
    )


_SYSTEM = """你是 CandidatePatchGenerator。只能返回一个包含 proposal_summary 和 changes 的 JSON 对象。
changes 必须是非空 JSON 数组，元素为 {path, value}；只能替换列出的标量叶子节点。
不得输出完整策略、Lua、CMO 命令、计分、ID、Markdown 或额外字段。
必须遵守精确的 candidate ID、变更数量边界、允许叶子约束及此前的结构化错误信息。
修复时必须返回完整替换 Patch，changes 数组要包含全部修正后的变更，不能只返回增量。"""


def _catalog_by_dimension(catalog: tuple[PatchableLeaf, ...]) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for leaf in catalog:
        grouped.setdefault(semantic_dimension(leaf.path), []).append(leaf.to_prompt_dict())
    return {dimension: grouped[dimension] for dimension in sorted(grouped)}
