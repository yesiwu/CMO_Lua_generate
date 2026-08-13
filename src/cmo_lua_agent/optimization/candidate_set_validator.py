"""Deterministic validation of Phase 6 candidate sets before CMO is invoked.
Phase6 批量候选集合校验器
在启动CMO仿真之前，一次性校验同一批次4条候选策略是否满足实验规范；
强制约束：候选数量、ID格式、策略不能重复、不能增删作战条目、只能修改允许字段、保证策略多样性；
输出多样性校验报告，非法批次直接拦截，避免无效仿真资源浪费。
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

# 场景、标准作战策略模型、策略合法性校验器
from cmo_lua_agent.contract.strategy_models import ScenarioDefinition, StrategySpec
from cmo_lua_agent.contract.strategy_validator import StrategyValidator
# Phase6 多样性报告、单条候选、候选批次集合模型
from cmo_lua_agent.optimization.phase6_models import DiversityReport, StrategyCandidate, StrategyCandidateSet
from cmo_lua_agent.optimization.executable_patch_paths import is_executable_patch_path
from cmo_lua_agent.optimization.strategy_dimensions import semantic_dimension


class CandidateSetValidator:
    """校验一批候选是否满足正式执行前的结构与差异约束。"""
    def validate(
        self, *,
        scenario: ScenarioDefinition,
        baseline: StrategySpec,
        candidates: tuple[StrategyCandidate, ...],
        allowed_paths: tuple[str, ...],
        diversity_dimensions: tuple[str, ...]
    ) -> StrategyCandidateSet:
        """
        对一代4条候选做全套前置校验
        :param scenario: 当前固定场景
        :param baseline: 基线基准策略
        :param candidates: 本次待评估的4条候选策略
        :param allowed_paths: 允许修改的策略叶子路径白名单
        :param diversity_dimensions: 系统要求具备的多样性维度
        :return: 封装校验结果与多样性报告的候选集合对象
        """
        violations: list[str] = []

        # 规则1：一代强制固定4条候选
        if len(candidates) != 4:
            violations.append("candidate_count_must_be_four")

        # 规则2：候选ID格式必须严格 candidate_00、candidate_01、candidate_02、candidate_03
        ids = [candidate.candidate_id for candidate in candidates]
        if ids != [f"candidate_{index:02d}" for index in range(4)]:
            violations.append("candidate_ids_invalid")

        # 规则3：不允许出现完全相同的策略（哈希重复）
        checksums = [candidate.strategy_checksum for candidate in candidates]
        duplicate_checksums = tuple(sorted({cs for cs in checksums if checksums.count(cs) > 1}))
        if duplicate_checksums:
            violations.append("duplicate_strategy_checksum")

        validator = StrategyValidator()
        diffs: dict[str, tuple[str, ...]] = {}  # 记录每条候选相对基线的改动路径
        dimensions: set[str] = set()            # 收集本批次用到的改动维度

        for candidate in candidates:
            # 校验策略本身结构、场景约束是否合法
            report = validator.validate(candidate.strategy_spec, scenario)
            if not report.valid:
                violations.append(f"{candidate.candidate_id}:strategy_invalid")
                continue

            # 对比基线，找出本条候选所有改动路径，同时校验只允许修改白名单字段
            changed_paths = _leaf_diff(baseline, candidate.strategy_spec, allowed_paths)
            non_executable_paths = tuple(
                path for path in changed_paths if not is_executable_patch_path(path)
            )
            if non_executable_paths:
                violations.append(
                    f"{candidate.candidate_id}:patch_path_not_executable"
                )
                changed_paths = [
                    path for path in changed_paths if is_executable_patch_path(path)
                ]
            diffs[candidate.candidate_id] = tuple(changed_paths)

            # 规则4：候选必须有改动，不允许和基线完全一致
            if not changed_paths:
                violations.append(f"{candidate.candidate_id}:no_effective_change")

            # 根据改动路径归类多样性维度
            for path in changed_paths:
                dimensions.add(semantic_dimension(path))

        # 规则5：整批候选至少覆盖2个不同改动维度，保证策略多样性
        warnings: list[str] = []
        if len(dimensions) < 2:
            warnings.append("insufficient_diversity_dimensions")

        # 生成多样性&违规汇总报告
        diversity_report = DiversityReport(
            valid=not violations,
            dimensions_covered=tuple(sorted(dimensions)),
            candidate_diffs=diffs,
            duplicates=duplicate_checksums,
            violations=tuple(violations),
            warnings=tuple(warnings),
        )
        # 封装批次信息与报告返回
        return StrategyCandidateSet(baseline, candidates, diversity_report)


def strategy_leaf_diff(baseline: StrategySpec, candidate: StrategySpec, allowed_paths: tuple[str, ...]) -> tuple[str, ...]:
    """对外暴露工具：对比基线与候选策略，返回所有改动的叶子路径"""
    return tuple(_leaf_diff(baseline, candidate, allowed_paths))


def _leaf_diff(baseline: StrategySpec, candidate: StrategySpec, allowed_paths: tuple[str, ...]) -> list[str]:
    """底层差异对比核心逻辑 + 强结构约束"""
    # 策略不能跨场景混用
    if candidate.scenario_id != baseline.scenario_id:
        raise ValueError("candidate scenario_id differs from baseline")

    changed_paths: list[str] = []

    # 遍历两大集合：attacks攻击条目、sorties出击条目
    for collection_name, stable_id_field in (("attacks", "attack_id"), ("sorties", "sortie_id")):
        base_items = getattr(baseline, collection_name)
        cand_items = getattr(candidate, collection_name)

        # 【核心强约束】禁止增、删、调换条目顺序、修改条目attack_id/sortie_id
        if len(base_items) != len(cand_items) or [getattr(i, stable_id_field) for i in base_items] != [getattr(i, stable_id_field) for i in cand_items]:
            raise ValueError(f"{collection_name} may not be added, removed, reordered, or renamed")

        # 逐条对比同序号条目内部字段
        for idx, (old_item, new_item) in enumerate(zip(base_items, cand_items, strict=True)):
            _diff_values(old_item.to_dict(), new_item.to_dict(), f"/{collection_name}/{idx}", changed_paths)

    # 校验：所有改动路径必须在白名单内，禁止修改不受允许的字段
    for path in changed_paths:
        if not any(path == allowed or path.startswith(allowed + "/") for allowed in allowed_paths):
            raise ValueError(f"candidate modifies forbidden path: {path}")

    return sorted(changed_paths)


def _diff_values(old: Any, new: Any, current_path: str, output: list[str]) -> None:
    """递归对比字典/列表/标量，收集发生变化的叶子路径
    强制约束：不能增删字典key、不能增删数组元素，仅允许修改叶子标量值
    """
    # 字典对比：key集合必须完全一致，禁止新增/删除字段
    if isinstance(old, dict) and isinstance(new, dict):
        if set(old) != set(new):
            raise ValueError(f"candidate changes object shape at {current_path}")
        for key in sorted(old):
            _diff_values(old[key], new[key], f"{current_path}/{key}", output)
        return

    # 数组对比：长度必须完全一致，禁止新增/删除元素
    if isinstance(old, list) and isinstance(new, list):
        if len(old) != len(new):
            raise ValueError(f"candidate changes array shape at {current_path}")
        for idx, (left, right) in enumerate(zip(old, new, strict=True)):
            _diff_values(left, right, f"{current_path}/{idx}", output)
        return

    # 叶子标量值不相等 → 记录改动路径
    if old != new:
        output.append(current_path)


def _legacy_dimension(path: str) -> str:
    """根据改动路径，归类属于哪一类战术维度（用于多样性评估）"""
    if path.endswith("/target_ids") or "/target_ids/" in path:
        return "target_assignment"        # 目标分配
    if path.endswith("/fire_quantity"):
        return "fire_quantity"             # 弹药发射数量
    if path.endswith("/delay_seconds") or path.endswith("/fire_delay_seconds"):
        return "attack_timing"            # 攻击时机/延时
    if "/route/" in path:
        return "air_route"                # 飞机航路
    if path.endswith("/reserve_quantity"):
        return "ammunition_reserve"       # 弹药预留量
    if path.endswith("/return_delay_seconds"):
        return "risk_policy"              # 返航策略（风险偏好）
    return "other"                       # 其他维度
