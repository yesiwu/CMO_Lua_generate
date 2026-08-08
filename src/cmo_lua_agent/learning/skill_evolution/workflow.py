"""
Phase8 离线技能演化主工作流。
完整串联经验聚合、资格校验、晋升决策、技能草稿生成、待审核技能包组装、回归校验全链路；
读取Phase7持久化经验记录，自动产出pending待审核技能包，输出全套审计产物，等待人工审批介入。
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

from cmo_lua_agent.agents.skill_author_agent import (
    SkillAuthorContext,
    SkillDraftContent,
    SkillRevisionProposal,
    apply_skill_revision,
    skill_draft_from_dict,
)
from cmo_lua_agent.learning.store import ExperienceStore

from .active_loader import ActiveSkillLoader
from .aggregation import ExperienceAggregator, canonical_sha256
from .assets import SkillAssetStore, SkillPackageAssembler
from .catalog import ExperienceKeyCatalog, SkillFamilyCatalog
from .errors import fail
from .models import (
    ExperienceAggregationResult,
    PromotionAction,
    PromotionDecision,
    ValidatedExperience,
)
from .promotion import PromotionProfile, SkillPromotionPolicy
from .regression import SkillRegressionReport, SkillRegressionService
from .validation import ExperienceValidationService


class SkillAuthor(Protocol):
    """
    技能编写智能体协议定义
    定义创建新技能、修订已有技能两套接口，便于注入不同实现或单元测试Mock对象
    """
    def create(self, context: SkillAuthorContext) -> SkillDraftContent: ...

    def revise(
        self, context: SkillAuthorContext
    ) -> SkillRevisionProposal: ...


@dataclass(frozen=True, slots=True)
class SkillEvolutionResult:
    """
    Phase8技能演化工作流最终输出结果实体
    汇总运行状态、统计指标、产物路径，用于上层调度判断后续流程（人工审核通知、日志归档）
    """
    phase8_run_id: str                     # 本次Phase8运行唯一标识
    status: str                            # 运行结束状态码
    aggregate_count: int                   # 参与处理的经验聚合结果总数
    eligible_experience_count: int         # 具备晋升资格的经验数量
    pending_packages: tuple[str, ...]      # 生成的待审核技能包目录路径列表
    author_invocations: int                # 调用技能编写智能体次数
    artifact_paths: dict[str, str]         # 所有审计产物文件路径映射

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典用于落地结果文件"""
        return asdict(self)


class SkillEvolutionWorkflow:
    """
    Phase8 离线技能演化顶层工作流
    完整流水线：
    读取Phase7经验记录 → 经验聚合 → 经验资格校验 → 晋升决策 →
    技能草稿生成(新建/修订) → 组装pending技能包 → 回归校验 → 写入持久存储与审计文件
    """
    def __init__(
        self,
        *,
        author_agent: SkillAuthor,
        asset_store: SkillAssetStore,
        regression_service: SkillRegressionService,
        key_catalog: ExperienceKeyCatalog | None = None,
        family_catalog: SkillFamilyCatalog | None = None,
        promotion_profile: PromotionProfile | None = None,
    ) -> None:
        # 技能编写智能体（LLM实现，生成SKILL.md、规则结构）
        self._author = author_agent
        # 技能资源持久存储管理器
        self._assets = asset_store
        # 经验键目录（命名归一化、别名管理）
        self._keys = key_catalog or ExperienceKeyCatalog.default()
        # 技能家族目录
        self._families = family_catalog or SkillFamilyCatalog.default()
        # 经验晋升阈值配置
        self._profile = promotion_profile or PromotionProfile.default()
        # 经验聚合器
        self._aggregator = ExperienceAggregator(self._keys)
        # 经验资格校验服务
        self._validator = ExperienceValidationService(self._profile)
        # 晋升决策策略器
        self._policy = SkillPromotionPolicy(self._profile)
        # 技能回归校验服务
        self._regression = regression_service
        # 运行时技能加载器，用于读取当前线上生效版本
        self._active = ActiveSkillLoader(
            self._assets.root,
            expected_provenance=self._assets.provenance,
        )
        # 待审核技能包组装器
        self._assembler = SkillPackageAssembler(self._assets)

    def run(
        self,
        *,
        phase8_run_id: str,
        runs_root: Path,
        experience_store: ExperienceStore,
        experience_ids: tuple[str, ...] | None = None,
    ) -> SkillEvolutionResult:
        """
        执行整套Phase8技能演化流程
        :param phase8_run_id: 本次运行唯一ID，用于隔离不同批次产物
        :param runs_root: 批次产物根目录
        :param experience_store: Phase7经验记录存储，读取原始经验记录
        :return: 标准化运行结果实体
        """
        # 校验运行ID命名规范
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", phase8_run_id):
            raise fail("invalid_phase8_run_id", "phase8_run_id 标识符非法")
        output = (
            Path(runs_root).resolve()
            / phase8_run_id
            / "skill-evolution"
        )
        output.mkdir(parents=True, exist_ok=True)

        # 读取全部Phase7原始经验记录
        records = self._read_records(experience_store, experience_ids=experience_ids)
        manifest_value = {
            "schema_version": "2",
            "profile_id": self._profile.profile_id,
            "store_provenance": self._assets.provenance,
            "record_count": len(records),
            "record_checksums": [
                canonical_sha256(record) for record in records
            ],
        }
        manifest_path = output / "aggregation-manifest.json"
        # 防止重复运行输入数据不一致，出现输入冲突
        if (
            manifest_path.is_file()
            and _object(manifest_path) != manifest_value
        ):
            raise fail(
                "phase8_input_conflict",
                "当前phase8_run_id已存在，输入经验数据发生冲突，无法重复执行"
            )

        # 1. 经验聚合：多条同源经验汇总为ExperienceAggregate
        aggregation = self._aggregator.aggregate(records)
        aggregates = aggregation.aggregates
        # 2. 资格校验：生成ValidatedExperience，判定是否具备晋升条件
        validated = tuple(self._validator.validate(item) for item in aggregates)

        # 按【技能家族+兼容分组】缓存当前线上生效技能
        active_by_group: dict[tuple[str, str], object | None] = {}
        grouped_validated: dict[
            tuple[str, str], list[ValidatedExperience]
        ] = defaultdict(list)
        for item in validated:
            group = (item.family, item.compatibility_cohort.cohort_id)
            grouped_validated[group].append(item)
            if group not in active_by_group:
                active_by_group[group] = self._active.load(
                    skill_id=item.family,
                    cohort=item.compatibility_cohort,
                )
        decisions_by_group: dict[
            tuple[str, str], PromotionDecision
        ] = {}
        for group, items in sorted(grouped_validated.items()):
            active = active_by_group[group]
            decisions_by_group[group] = self._policy.decide(
                tuple(items),
                active_version=getattr(active, "version", None),
                provenance=self._assets.provenance,
            )
        decisions = tuple(decisions_by_group.values())

        # 写入前置审计产物：聚合结果、校验结果、决策单据
        artifact_paths = self._write_initial_artifacts(
            output=output,
            records=records,
            aggregation=aggregation,
            validated=validated,
            decisions=decisions,
        )

        author_invocations = 0
        pending_paths: list[str] = []
        checkpoint_input_checksum = canonical_sha256(manifest_value)
        author_payload: dict[str, Any] = {
            "schema_version": "2",
            "input_checksum": checkpoint_input_checksum,
            "groups": {},
        }
        reports: list[dict[str, Any]] = []
        saved_author_path = output / "skill-author-response.json"
        # 支持断点续跑：如果已存在技能草稿输出，直接复用，避免重复调用LLM
        saved_author = (
            _object(saved_author_path)
            if saved_author_path.is_file()
            else None
        )
        if saved_author is not None:
            if (
                saved_author.get("schema_version") != "2"
                or saved_author.get("input_checksum")
                != checkpoint_input_checksum
                or not isinstance(saved_author.get("groups"), Mapping)
            ):
                raise fail(
                    "skill_author_checkpoint_conflict",
                    "SkillAuthor checkpoint 与当前输入不一致",
                )
            author_payload = dict(saved_author)

        # 筛选出需要生成/修订技能的经验分组
        authorable: dict[
            tuple[str, str],
            tuple[tuple[ValidatedExperience, ...], PromotionDecision],
        ] = {}
        for group, decision in decisions_by_group.items():
            if decision.action in {
                PromotionAction.CREATE_PENDING_SKILL,
                PromotionAction.REVISE_EXISTING_SKILL,
            }:
                authorable[group] = (
                    tuple(grouped_validated[group]),
                    decision,
                )

        # 逐个分组生成技能草稿、组装技能包
        for group, group_data in sorted(authorable.items()):
            family, cohort_id = group
            group_key = f"{family}:{cohort_id}"
            group_validated, decision = group_data
            active = active_by_group[group]

            # 构造技能编写上下文（传入经验假说、数据源插槽、当前线上技能）
            context = SkillAuthorContext(
                family=family,
                mission_type=group_validated[0].mission_type,
                canonical_hypotheses=tuple(
                    item.canonical_hypothesis for item in group_validated
                ),
                source_slots={
                    slot: ids
                    for item in group_validated
                    for slot, ids in item.evidence_slot_map.items()
                },
                active_skill_summary=(
                    {
                        "skill_id": active.skill_id,
                        "version": active.version,
                        "checksum": active.checksum,
                        "structured_content": active.structured_content,
                    }
                    if active is not None
                    else None
                ),
            )

            group_input_checksum = canonical_sha256({
                "family": family,
                "cohort_id": cohort_id,
                "mode": "revise" if active is not None else "create",
                "validation_checksums": sorted(
                    item.checksum for item in group_validated
                ),
                "active_checksum": getattr(active, "checksum", None),
                "schema_version": "2",
            })
            saved_group = author_payload["groups"].get(group_key)
            if saved_group is not None:
                # 断点续跑：复用已生成的技能草稿，不重调LLM
                if (
                    not isinstance(saved_group, Mapping)
                    or saved_group.get("family") != family
                    or saved_group.get("cohort_id") != cohort_id
                    or saved_group.get("input_checksum")
                    != group_input_checksum
                ):
                    raise fail(
                        "skill_author_checkpoint_conflict",
                        "保存的技能草稿与当前 Family/Cohort 输入不一致",
                    )
                content = skill_draft_from_dict(
                    saved_group["content"],
                    allowed_source_slots=tuple(context.source_slots),
                )
                mode = str(saved_group["mode"])
            elif active is None:
                # 无生效技能：新建技能
                content = self._author.create(context)
                mode = "create"
                author_invocations += 1
            else:
                # 已有线上技能：生成修订提案并合并更新
                proposal = self._author.revise(context)
                content = apply_skill_revision(
                    skill_draft_from_dict(active.structured_content),
                    proposal,
                )
                mode = "revise"
                author_invocations += 1

            author_payload["groups"][group_key] = {
                "family": family,
                "cohort_id": cohort_id,
                "input_checksum": group_input_checksum,
                "mode": mode,
                "content": content.to_dict(),
            }
            # LLM 返回后立即持久化；后续组装失败时重跑不再调用模型。
            _write_json(saved_author_path, author_payload)

            # 合并新旧经验证据记录（继承旧技能绑定的证据）
            current_evidence_records = {
                str(record["experience_id"]): record
                for record in records
            }
            if active is not None:
                for slot, ids in active.source_slot_map.items():
                    for experience_id in ids:
                        current_evidence_records.setdefault(
                            experience_id,
                            {
                                "experience_id": experience_id,
                                "evidence_refs": list(
                                    active.source_slot_refs.get(slot, ())
                                ),
                            },
                        )

            # 4. 组装待审核技能包 pending
            package = self._assembler.assemble_pending(
                decision=decision,
                validated=group_validated,
                content=content,
                evidence_records=current_evidence_records,
                inherited_source_slots=(
                    active.source_slot_map if active is not None else None
                ),
                inherited_source_refs=(
                    active.source_slot_refs if active is not None else None
                ),
                inherited_experience_keys=(
                    active.covered_experience_keys
                    if active is not None
                    else ()
                ),
            )

            # 5. 执行技能回归校验
            report = self._regression.validate(
                package,
                evidence_records=current_evidence_records,
            )
            package = self._assets.save_regression_report(package, report)
            pending_paths.append(str(package.path))
            reports.append({
                **report.to_dict(),
                "skill_id": package.skill_id,
                "cohort_id": package.cohort_id,
                "version": package.version,
                "package_checksum": package.checksum,
            })

        # 持久化技能草稿、待审核清单、回归测试报告
        if not saved_author_path.is_file():
            _write_json(saved_author_path, author_payload)
        _write_json(
            output / "pending-skill-manifest.json",
            {"pending_packages": pending_paths},
        )
        _write_json(output / "skill-regression-report.json", reports)

        # 根据回归结果判定最终状态
        regression_failed = any(
            not (
                report["static_validation_passed"]
                and report["traceability_validation_passed"]
                and report["proposal_regression_passed"]
            )
            for report in reports
        )
        status = (
            "pending_regression_failed"
            if regression_failed
            else (
                "pending_review"
                if pending_paths
                else "NO_PROMOTABLE_EXPERIENCE"
            )
        )

        result = SkillEvolutionResult(
            phase8_run_id=phase8_run_id,
            status=status,
            aggregate_count=len(aggregates),
            eligible_experience_count=sum(item.eligible for item in validated),
            pending_packages=tuple(pending_paths),
            author_invocations=author_invocations,
            artifact_paths=artifact_paths,
        )
        _write_json(output / "phase8-result.json", result.to_dict())
        return result

    @staticmethod
    def _read_records(
        store: ExperienceStore,
        *,
        experience_ids: tuple[str, ...] | None = None,
    ) -> tuple[dict[str, Any], ...]:
        """
        读取Phase7持久化的全部经验记录
        :param store: 经验存储实例
        :return: 经验记录元组
        """
        if not store.records.is_dir():
            return ()
        records: list[dict[str, Any]] = []
        excluded_ids = store.excluded_ids()
        selected_ids = set(experience_ids) if experience_ids is not None else None
        for path in sorted(store.records.glob("*.json")):
            value = _object(path)
            if "experience_id" not in value:
                raise ValueError(f"非法的Phase7经验记录文件：{path}")
            if (
                value["experience_id"] not in excluded_ids
                and (selected_ids is None or value["experience_id"] in selected_ids)
            ):
                records.append(value)
        return tuple(records)

    def _write_initial_artifacts(
        self,
        *,
        output: Path,
        records: tuple[dict[str, Any], ...],
        aggregation: ExperienceAggregationResult,
        validated: tuple[ValidatedExperience, ...],
        decisions: tuple[PromotionDecision, ...],
    ) -> dict[str, str]:
        """
        写入流程前置审计产物：聚合清单、聚合结果、校验经验、晋升决策
        :return: 产物路径映射字典
        """
        paths = {
            "aggregation_manifest": str(
                output / "aggregation-manifest.json"
            ),
            "aggregates": str(output / "experience-aggregates.json"),
            "validated": str(output / "validated-experiences.json"),
            "decisions": str(output / "promotion-decisions.json"),
        }
        _write_json(
            output / "aggregation-manifest.json",
            {
                "profile_id": self._profile.profile_id,
                "schema_version": "2",
                "store_provenance": self._assets.provenance,
                "record_count": len(records),
                "record_checksums": [
                    canonical_sha256(record) for record in records
                ],
            },
        )
        _write_json(
            output / "experience-aggregates.json",
            aggregation.to_dict(),
        )
        _write_json(
            output / "validated-experiences.json",
            [item.to_dict() for item in validated],
        )
        _write_json(
            output / "promotion-decisions.json",
            [item.to_dict() for item in decisions],
        )
        return paths


def _object(path: Path) -> dict[str, Any]:
    """读取JSON文件并强制校验根节点为字典"""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON根节点必须为对象：{path}")
    return value


def _write_json(path: Path, value: object) -> None:
    """
    原子写入JSON文件
    有序序列化、临时文件替换，防止进程中断造成文件损坏
    """
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, indent=2, default=str
    ) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", delete=False, dir=path.parent
    ) as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)
