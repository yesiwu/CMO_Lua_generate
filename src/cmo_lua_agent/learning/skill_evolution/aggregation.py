"""
对不可变的Phase7经验记录执行确定性聚合运算。
核心目标：将多条同源、同兼容分组的分散经验记录汇总，形成统一经验聚合视图，量化支持/矛盾/限定证据，消除单轮仿真的随机偏差。
"""
from __future__ import annotations

import hashlib
import json
import statistics
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from .catalog import ExperienceKeyCatalog
from .models import (
    AggregateEvidence,
    AggregationExclusion,
    CompatibilityCohort,
    EvidenceStance,
    ExperienceAggregate,
    ExperienceAggregationResult,
)


def canonical_sha256(value: object) -> str:
    """
    生成确定性SHA256哈希
    使用固定分隔符、有序序列化，保证相同语义对象输出完全一致哈希值，用于校验与唯一标识
    """
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _major(value: object) -> int:
    """
    提取版本号主版本数字
    失败时返回-1，用于兼容分组契约构建
    """
    try:
        return int(str(value).split(".", 1)[0])
    except (TypeError, ValueError):
        return -1


def _cohort(environment: Mapping[str, Any]) -> CompatibilityCohort:
    """
    根据环境字典构造兼容分组契约
    保留评分规范、运行时、渲染器版本等证据上下文，并返回共享任务范围标识。
    """
    body = {
        "score_spec_major": _major(environment.get("score_spec_version")),
        "score_spec_checksum": str(
            environment.get("score_spec_checksum", "")
        ),
        "runtime_major": _major(environment.get("runtime_version")),
        "renderer_major": _major(environment.get("renderer_version")),
        "scenario_schema_version": str(
            environment.get("scenario_schema_version", "")
        ),
        "score_source": str(environment.get("score_source", "")),
    }
    return CompatibilityCohort(
        # Runtime and renderer metadata remains attached to every record, but
        # must not split a single tactical hypothesis into isolated pools.
        cohort_id="scope_naval_air_anti_surface",
        **body,
    )


def _stance(record: Mapping[str, Any]) -> EvidenceStance:
    """读取显式证据立场；正式链路禁止从经验类型推断。"""
    return EvidenceStance(str(record["evidence_stance"]))


def _candidate_ids(record: Mapping[str, Any]) -> tuple[str, ...]:
    """
    提取经验记录内支撑候选方案ID集合，去重并排序，返回不可变元组
    格式异常时返回空元组
    """
    effect = record.get("observed_effect", {})
    if not isinstance(effect, Mapping):
        return ()
    values = effect.get("supporting_candidate_ids", ())
    if not isinstance(values, Sequence) or isinstance(values, str):
        return ()
    return tuple(sorted({str(value) for value in values}))


def _score_delta(record: Mapping[str, Any]) -> float | None:
    """Read both current numeric and legacy per-candidate score deltas."""
    effect = record.get("observed_effect")
    if not isinstance(effect, Mapping):
        return None
    value = effect.get("score_delta_vs_baseline")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, Mapping):
        values = [
            float(item)
            for item in value.values()
            if isinstance(item, (int, float)) and not isinstance(item, bool)
        ]
        if values:
            return statistics.mean(values)
    return None


class ExperienceAggregator:
    """
    经验聚合器
    将多条独立生成的原始经验记录，按【经验键-任务类型-兼容分组】分组聚合；
    汇总多轮优化产生的证据，计算置信统计指标，生成标准化ExperienceAggregate聚合视图。
    非战术类经验、未分类经验、跨任务类型经验直接过滤，不参与聚合。
    """
    # 参与聚合的有效战术经验类型
    _tactical = {"tactical_positive", "tactical_negative", "counterexample"}
    # 证据立场优先级：用于同一轮优化内多条冲突经验时选取最终立场
    _precedence = {
        EvidenceStance.SUPPORT: 0,
        EvidenceStance.QUALIFY: 1,
        EvidenceStance.CONTRADICT: 2,
    }

    def __init__(self, catalog: ExperienceKeyCatalog) -> None:
        self._catalog = catalog

    def aggregate(
        self, records: Sequence[Mapping[str, Any]]
    ) -> ExperienceAggregationResult:
        """
        批量聚合原始经验记录
        :param records: 多条原始经验候选记录
        :return: 多条经验聚合结果元组
        """
        # Group by the actual reusable concept: tactical key plus mission.
        # Cohort metadata is evidence context, not an aggregation boundary.
        grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = (
            defaultdict(list)
        )
        exclusions: list[AggregationExclusion] = []
        for record in records:
            # New records may explicitly state that their official score is
            # unavailable. Such evidence cannot support a Skill promotion.
            # Legacy records without this field retain their prior behavior.
            if record.get("scoreable") is False:
                exclusions.append(AggregationExclusion(
                    experience_id=str(record.get("experience_id", "unknown")),
                    error_code="unscoreable_experience",
                ))
                continue
            # 过滤非战术经验
            if record.get("experience_type") not in self._tactical:
                continue
            try:
                _stance(record)
            except (KeyError, ValueError):
                exclusions.append(AggregationExclusion(
                    experience_id=str(record.get("experience_id", "unknown")),
                    error_code="missing_or_invalid_evidence_stance",
                ))
                continue
            # 归一化经验键，未分类经验直接丢弃
            key = self._catalog.normalize(str(record.get("experience_key", "")))
            if key == "unclassified":
                continue
            environment = record.get("environment")
            if not isinstance(environment, Mapping):
                continue
            # 当前仅支持海上空对面任务类型
            mission = str(
                environment.get("mission_type", "naval_air_anti_surface")
            )
            if mission != "naval_air_anti_surface":
                continue
            grouped[(key, mission)].append(record)

        # 按键排序，依次构建聚合实体
        aggregates = tuple(
            self._build(key, mission, rows)
            for (key, mission), rows in sorted(grouped.items())
        )
        return ExperienceAggregationResult(
            aggregates=aggregates,
            exclusions=tuple(sorted(
                exclusions,
                key=lambda item: (item.experience_id, item.error_code),
            )),
        )

    def _build(
        self,
        key: str,
        mission: str,
        records: list[Mapping[str, Any]],
    ) -> ExperienceAggregate:
        """
        根据同一分组下全部经验记录，构建单条经验聚合实体
        :param key: 归一化经验键
        :param mission: 任务类型
        :param records: 同一分组下全部原始经验记录
        :return: 标准化经验聚合视图 ExperienceAggregate
        """
        definition = self._catalog.definition(key)
        # 按优化轮次分组，同一轮内多条经验归为一组
        by_optimization: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for record in records:
            by_optimization[str(record["source_optimization_id"])].append(
                record
            )

        evidence: list[AggregateEvidence] = []
        conflicts: list[str] = []
        for optimization_id, rows in sorted(by_optimization.items()):
            # 提取本轮所有经验的证据立场
            stances = {_stance(row) for row in rows}
            # 根据优先级选择本轮最终立场
            chosen = max(stances, key=self._precedence.__getitem__)
            # 同一轮内同时存在多种立场，标记为本轮存在立场冲突
            if len(stances) > 1:
                conflicts.append(optimization_id)
            # 汇总本轮全部支撑候选ID
            candidates = tuple(sorted({
                candidate
                for row in rows
                for candidate in _candidate_ids(row)
            }))
            # 本轮证据质量列表
            qualities = [float(row.get("evidence_quality", 0)) for row in rows]
            # 本轮相对基线得分差值
            deltas = [
                delta for row in rows
                if (delta := _score_delta(row)) is not None
            ]
            # 汇总全部溯源证据文件路径
            refs = tuple(sorted({
                str(ref)
                for row in rows
                for ref in row.get("evidence_refs", ())
            }))
            evidence.append(AggregateEvidence(
                evidence_key=f"{optimization_id}:{key}",
                stance=chosen,
                source_optimization_id=optimization_id,
                scenario_id=str(rows[0].get("environment", {}).get(
                    "scenario_id", "unknown"
                )),
                experience_ids=tuple(sorted(
                    str(row["experience_id"]) for row in rows
                )),
                supporting_candidates=candidates,
                evidence_quality=round(statistics.mean(qualities), 6),
                score_delta=round(statistics.mean(deltas), 6)
                if deltas else None,
                execution_success=all(
                    bool(row.get("execution_success", False)) for row in rows
                ),
                semantic_valid=all(
                    bool(row.get("semantic_valid", False)) for row in rows
                ),
                fidelity_verified=all(
                    row.get("execution_fidelity") == "verified" for row in rows
                ),
                evidence_refs=refs,
            ))

        # 将本轮汇总证据按立场分类
        supporting = tuple(
            item for item in evidence if item.stance is EvidenceStance.SUPPORT
        )
        contradicting = tuple(
            item
            for item in evidence
            if item.stance is EvidenceStance.CONTRADICT
        )
        qualifying = tuple(
            item for item in evidence if item.stance is EvidenceStance.QUALIFY
        )
        counted = (*supporting, *contradicting, *qualifying)
        deltas = [item.score_delta for item in counted if item.score_delta is not None]
        denominator = len(supporting) + len(contradicting)
        cohort = _cohort(records[0]["environment"])
        body = {
            "experience_key": key,
            "mission_type": mission,
            "family": definition.family,
            "cohort": cohort.to_dict(),
            "evidence": [item.to_dict() for item in counted],
            "stance_conflicts": sorted(conflicts),
        }
        checksum = canonical_sha256(body)
        rate_denominator = max(1, len(counted))
        return ExperienceAggregate(
            aggregate_id=f"agg_{checksum[:20]}",
            experience_key=key,
            mission_type=mission,
            family=definition.family,
            canonical_hypothesis=definition.canonical_hypothesis,
            compatibility_cohort=cohort,
            supporting_evidence=supporting,
            contradicting_evidence=contradicting,
            qualifying_evidence=qualifying,
            excluded_experience_ids=(),
            independent_optimization_count=len(counted),
            independent_scenario_count=len({
                item.scenario_id for item in counted
                if item.scenario_id != "unknown"
            }),
            support_count=len(supporting),
            contradict_count=len(contradicting),
            qualify_count=len(qualifying),
            contradiction_ratio=round(
                len(contradicting) / denominator, 6
            ) if denominator else 0.0,
            mean_evidence_quality=round(
                statistics.mean(item.evidence_quality for item in counted), 6
            ) if counted else 0.0,
            mean_score_delta=round(statistics.mean(deltas), 6)
            if deltas else None,
            median_score_delta=round(statistics.median(deltas), 6)
            if deltas else None,
            execution_success_rate=round(
                sum(item.execution_success for item in counted)
                / rate_denominator,
                6,
            ),
            semantic_valid_rate=round(
                sum(item.semantic_valid for item in counted)
                / rate_denominator,
                6,
            ),
            execution_fidelity_rate=round(
                sum(item.fidelity_verified for item in counted)
                / rate_denominator,
                6,
            ),
            stance_conflicts=tuple(sorted(conflicts)),
            score_sources=tuple(sorted({
                str(row.get("environment", {}).get("score_source", ""))
                for row in records
            })),
            aggregate_status="aggregated",
            checksum=checksum,
        )
