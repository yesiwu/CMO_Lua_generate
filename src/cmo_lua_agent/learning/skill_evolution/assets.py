"""
运行时技能资源文件，仅允许存放于 ``data/skills`` 目录下。
本模块实现Phase8技能生命周期流水线：草稿组装 → 待审核包生成 → 回归校验 → 人工审批(归档/驳回)、索引维护、变更账本审计。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from cmo_lua_agent.agents.skill_author_agent import (
    SkillDraftContent,
    SkillRule,
)

from .aggregation import canonical_sha256
from .config import SkillStorageConfig, SkillStoreMode
from .errors import SkillEvolutionError, fail
from .models import PromotionAction, PromotionDecision, ValidatedExperience


# 合法标识符正则：仅允许字母数字开头，后续可包含字母、数字、下划线、点、横杠
_SAFE_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")
_CHECKSUM_SENTINEL = "<skill-package-checksum>"
_PACKAGE_FILES = (
    "SKILL.md",
    "content.json",
    "evidence-manifest.json",
    "promotion-decision.json",
    "regression-cases.json",
    "regression-report.json",
    "metadata.json",
    "references/validated-experiences.md",
)
_STABLE_METADATA_FIELDS = (
    "schema_version",
    "skill_id",
    "version",
    "family_id",
    "consumer",
    "mission_type",
    "compatibility_cohort",
    "decision_id",
    "validated_experience_ids",
    "applicable_experience_keys",
    "provenance",
    "draft_checksum",
    "package_checksum",
)
_ALLOWED_METADATA_FIELDS = frozenset((*_STABLE_METADATA_FIELDS, "status"))


def _safe(value: str, name: str) -> str:
    """
    标识符合法性校验
    :param value: 待校验字符串
    :param name: 标识符名称（用于报错）
    :return: 合法标识符
    """
    if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
        raise fail("invalid_identifier", f"非法标识符 {name}：{value}")
    return value


def _json(value: object) -> str:
    """
    生成确定性格式化JSON字符串
    有序键、固定缩进，保证相同对象输出文本唯一，用于校验与打包
    """
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, indent=2, default=str
    ) + "\n"


def _atomic_text(path: Path, text: str) -> None:
    """
    原子写入文本文件
    先写入同目录临时文件，再原子替换目标路径，防止断电/进程崩溃产生损坏文件
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", delete=False, dir=path.parent
    ) as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise fail(
            "skill_package_file_invalid",
            f"技能包文件无法读取：{path.name}",
        ) from exc
    if not isinstance(value, dict):
        raise fail(
            "skill_package_file_invalid",
            f"技能包 JSON 根节点必须为对象：{path.name}",
        )
    return value


def compute_skill_package_checksum(package_dir: Path) -> str:
    """Recompute the complete protected package checksum from disk."""
    root = Path(package_dir).resolve()
    missing = [name for name in _PACKAGE_FILES if not (root / name).is_file()]
    if missing:
        raise fail(
            "skill_package_incomplete",
            f"技能包缺失受保护文件：{missing[0]}",
        )
    metadata = _read_json_object(root / "metadata.json")
    report = _read_json_object(root / "regression-report.json")
    unexpected_metadata = sorted(
        set(metadata).difference(_ALLOWED_METADATA_FIELDS)
    )
    if unexpected_metadata:
        raise fail(
            "skill_package_metadata_fields_invalid",
            "技能包 metadata 包含未受控字段："
            f"{unexpected_metadata[0]}",
        )
    metadata_payload = {
        field: metadata.get(field) for field in _STABLE_METADATA_FIELDS
    }
    metadata_payload["package_checksum"] = _CHECKSUM_SENTINEL
    report_payload = dict(report)
    report_payload["package_checksum"] = _CHECKSUM_SENTINEL
    payload = {
        "SKILL.md": (root / "SKILL.md").read_text(
            encoding="utf-8"
        ).replace("\r\n", "\n").replace("\r", "\n"),
        "content.json": _read_json_object(root / "content.json"),
        "evidence-manifest.json": _read_json_object(
            root / "evidence-manifest.json"
        ),
        "promotion-decision.json": _read_json_object(
            root / "promotion-decision.json"
        ),
        "regression-cases.json": _read_json_object(
            root / "regression-cases.json"
        ),
        "regression-report.json": report_payload,
        "metadata.json": metadata_payload,
        "references/validated-experiences.md": (
            root / "references" / "validated-experiences.md"
        ).read_text(encoding="utf-8").replace(
            "\r\n", "\n"
        ).replace("\r", "\n"),
    }
    return canonical_sha256(payload)


def _promotion_decision_body(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "eligible": value.get("eligible"),
        "validated_experience_ids": value.get("validated_experience_ids"),
        "family_id": value.get("family_id"),
        "cohort_id": value.get("cohort_id"),
        "action": value.get("action"),
        "target_version": value.get("target_version"),
        "reasons": value.get("reasons"),
        "profile_id": value.get("profile_id"),
        "provenance": value.get("provenance"),
    }


def _validate_promotion_decision(
    value: dict[str, Any],
) -> dict[str, Any]:
    body = _promotion_decision_body(value)
    expected_checksum = canonical_sha256(body)
    if value.get("checksum") != expected_checksum:
        raise fail(
            "promotion_decision_checksum_mismatch",
            "PromotionDecision 校验和无效",
        )
    if value.get("decision_id") != f"decision_{expected_checksum[:20]}":
        raise fail(
            "promotion_decision_id_mismatch",
            "PromotionDecision ID 与内容不一致",
        )
    if body["eligible"] is not True:
        raise fail(
            "promotion_decision_not_eligible",
            "PromotionDecision 未通过晋升资格",
        )
    if body["action"] not in {
        PromotionAction.CREATE_PENDING_SKILL.value,
        PromotionAction.REVISE_EXISTING_SKILL.value,
    }:
        raise fail(
            "promotion_decision_action_forbidden",
            "PromotionDecision 动作不允许进入审批",
        )
    ids = body["validated_experience_ids"]
    if (
        not isinstance(ids, list)
        or not ids
        or any(not isinstance(item, str) or not item for item in ids)
    ):
        raise fail(
            "promotion_decision_validation_ids_invalid",
            "PromotionDecision 验证经验 ID 非法",
        )
    return body


@dataclass(frozen=True, slots=True)
class SkillPackage:
    """
    技能包快照实体
    不可变模型，描述一套完整待审核/已归档技能包元信息
    """
    skill_id: str                          # 技能唯一标识
    cohort_id: str                         # 兼容分组ID
    version: str                           # 技能版本号
    path: Path                             # 技能包目录路径
    checksum: str                          # 技能包整体校验和
    decision_id: str                       # 晋升决策ID
    validation_ids: tuple[str, ...]        # 关联的有效经验校验ID列表
    source_slot_map: dict[str, tuple[str, ...]] # 规则插槽 → 绑定经验ID映射

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典，用于日志与索引存储"""
        return {
            **asdict(self),
            "path": str(self.path),
            "source_slot_map": {
                key: list(value)
                for key, value in sorted(self.source_slot_map.items())
            },
        }


class SkillPackageAssembler:
    """
    技能包组装器
    根据晋升决策、已验证经验、技能草稿内容，生成完整待审核(Pending)技能包；
    校验插槽一致性、经验引用完整性，渲染所有文档并打包目录结构。
    """
    def __init__(self, store: "SkillAssetStore") -> None:
        self._store = store

    def assemble_pending(
        self,
        *,
        decision: PromotionDecision,
        validated: tuple[ValidatedExperience, ...],
        content: SkillDraftContent,
        evidence_records: dict[str, dict[str, Any]],
        inherited_source_slots: dict[str, tuple[str, ...]] | None = None,
        inherited_source_refs: dict[str, tuple[str, ...]] | None = None,
        inherited_experience_keys: tuple[str, ...] = (),
    ) -> SkillPackage:
        """
        组装生成待审核状态技能包
        :param decision: 经验晋升为技能的决策单据
        :param validated: 本轮参与构建技能的已验证经验集合
        :param content: LLM生成的技能草稿内容（规则、适用条件、反例等）
        :param evidence_records: 经验原始证据记录字典
        :param inherited_source_slots: 继承自旧版本技能的插槽映射
        :param inherited_source_refs: 继承自旧版本技能的证据溯源路径
        :param inherited_experience_keys: 继承的经验键集合
        :return: 待审核技能包快照
        :raises ValueError: 校验不通过时抛出异常
        """
        # 仅允许新建技能或修订已有技能两种动作
        if not decision.eligible or decision.action not in {
            PromotionAction.CREATE_PENDING_SKILL,
            PromotionAction.REVISE_EXISTING_SKILL,
        }:
            raise fail(
                "promotion_decision_not_eligible",
                "该晋升决策不允许生成技能草稿包",
            )
        if not decision.target_version or not validated:
            raise fail(
                "skill_package_input_invalid",
                "待审核技能必须指定目标版本且提供有效经验",
            )
        # 禁止使用不具备晋升资格的经验构建技能
        if any(not item.eligible for item in validated):
            raise fail(
                "validated_experience_not_eligible",
                "不具备晋升资格的经验无法用于构建技能",
            )
        # 经验必须与决策单据的技能ID、兼容分组保持一致
        if any(
            item.family != decision.family_id
            or item.compatibility_cohort.cohort_id != decision.cohort_id
            for item in validated
        ):
            raise fail(
                "promotion_decision_binding_mismatch",
                "已验证经验与晋升决策信息不匹配",
            )
        validation_ids = tuple(sorted(
            item.validation_id for item in validated
        ))
        if validation_ids != decision.validated_experience_ids:
            raise fail(
                "promotion_decision_binding_mismatch",
                "PromotionDecision 绑定的验证经验 ID 不一致",
            )

        inherited_source_slots = inherited_source_slots or {}
        inherited_source_refs = inherited_source_refs or {}
        slot_map: dict[str, tuple[str, ...]] = dict(inherited_source_slots)

        # 合并所有经验的插槽映射，同一插槽不能绑定两组不同经验ID（冲突检测）
        for item in validated:
            for slot, experience_ids in item.evidence_slot_map.items():
                current = slot_map.get(slot)
                if current is not None and current != experience_ids:
                    raise fail(
                        "skill_source_slot_conflict",
                        f"数据源插槽发生冲突：{slot}",
                    )
                slot_map[slot] = tuple(experience_ids)

        # 提取草稿内所有规则使用的插槽
        used_slots = {
            slot
            for rule in _all_rules(content)
            for slot in rule.source_slots
        }
        # 规则引用未定义插槽，属于配置错误
        if unknown := used_slots - set(slot_map):
            raise fail(
                "skill_author_source_slot_unknown",
                f"存在未定义的数据源插槽：{sorted(unknown)[0]}",
            )

        # 收集所有被规则引用的经验ID
        referenced_ids = {
            experience_id
            for slot in used_slots
            for experience_id in slot_map[slot]
        }
        inherited_ids = {
            experience_id
            for ids in inherited_source_slots.values()
            for experience_id in ids
        }
        # 引用的经验必须存在记录（排除继承部分）
        if missing := referenced_ids - set(evidence_records) - inherited_ids:
            raise fail(
                "skill_evidence_record_missing",
                f"缺失经验证据记录：{sorted(missing)[0]}",
            )

        skill_id = _safe(decision.family_id, "skill_id")
        cohort_id = _safe(decision.cohort_id, "cohort_id")
        version = _safe(decision.target_version, "version")
        # 待审核包存放路径
        path = (
            self._store.root
            / "pending"
            / skill_id
            / version
        )

        # 构建证据清单：插槽绑定经验ID + 汇总证据文件路径
        evidence_manifest = {
            "source_slots": {
                slot: {
                    "experience_ids": list(slot_map[slot]),
                    "evidence_refs": sorted(
                        set(inherited_source_refs.get(slot, ()))
                        | {
                            str(ref)
                            for experience_id in slot_map[slot]
                            for ref in evidence_records.get(
                                experience_id, {}
                            ).get("evidence_refs", ())
                        }
                    ),
                }
                for slot in sorted(used_slots)
            }
        }

        # 渲染经验溯源文档
        references = _render_references(
            tuple(sorted(referenced_ids)),
            evidence_records,
            inherited_source_refs,
        )
        # 渲染主技能文档 SKILL.md
        skill_markdown = _render_skill(
            skill_id=skill_id,
            version=version,
            cohort_id=cohort_id,
            content=content,
        )
        # 回归测试约束配置
        regression_cases = {
            "schema_version": "1",
            "mission_type": validated[0].mission_type,
            "applicable_experience_keys": sorted(
                set(inherited_experience_keys)
                | {item.experience_key for item in validated}
            ),
            "forbidden_behaviors": [
                "modify_scenario_facts",
                "use_unknown_units_targets_or_weapons",
                "exceed_inventory",
                "violate_allowed_strategy_paths",
                "ignore_counterexamples",
            ],
        }

        # 草稿校验和用于在回归完成前识别断点恢复冲突。
        draft_payload = {
            "SKILL.md": skill_markdown,
            "content.json": content.to_dict(),
            "evidence-manifest.json": evidence_manifest,
            "promotion-decision.json": decision.to_dict(),
            "regression-cases.json": regression_cases,
            "references/validated-experiences.md": references,
            "decision_checksum": decision.checksum,
            "validation_checksums": sorted(
                item.checksum for item in validated
            ),
        }
        draft_checksum = canonical_sha256(draft_payload)

        # 技能包元数据 metadata.json
        metadata = {
            "schema_version": "2",
            "skill_id": skill_id,
            "version": version,
            "status": "pending",
            "family_id": skill_id,
            "consumer": "StrategyProposalAgent",
            "mission_type": validated[0].mission_type,
            "compatibility_cohort": validated[
                0
            ].compatibility_cohort.to_dict(),
            "decision_id": decision.decision_id,
            "validated_experience_ids": list(validation_ids),
            "applicable_experience_keys": sorted({
                item.experience_key for item in validated
            }),
            "provenance": decision.provenance,
            "draft_checksum": draft_checksum,
            "package_checksum": _CHECKSUM_SENTINEL,
        }

        # 所有待写入文件清单
        files = {
            "SKILL.md": skill_markdown,
            "content.json": _json(content.to_dict()),
            "metadata.json": _json(metadata),
            "evidence-manifest.json": _json(evidence_manifest),
            "promotion-decision.json": _json(decision.to_dict()),
            "regression-cases.json": _json(regression_cases),
            "references/validated-experiences.md": references,
        }
        # 写入pending目录
        self._store.write_pending(path, files, draft_checksum)
        persisted_metadata = self._store._metadata(path)
        persisted_checksum = str(
            persisted_metadata.get("package_checksum", _CHECKSUM_SENTINEL)
        )

        package = SkillPackage(
            skill_id=skill_id,
            cohort_id=cohort_id,
            version=version,
            path=path,
            checksum=persisted_checksum,
            decision_id=decision.decision_id,
            validation_ids=validation_ids,
            source_slot_map={
                slot: slot_map[slot] for slot in sorted(used_slots)
            },
        )
        return package


class SkillAssetStore:
    """
    技能资源持久化存储管理器
    完整管理技能生命周期：pending(待审核) → curated(已归档可用) / rejected(驳回)
    提供写入、审批、驳回、索引重建、生命周期账本、回归报告保存能力。
    """
    def __init__(self, config: SkillStorageConfig) -> None:
        if not isinstance(config, SkillStorageConfig):
            raise fail(
                "skill_store_mode_required",
                "SkillAssetStore 必须使用显式 SkillStorageConfig",
            )
        config.validate()
        self.config = config
        self.root = config.root.resolve()

    @property
    def provenance(self) -> str:
        return self.config.provenance

    def write_pending(
        self, path: Path, files: dict[str, str], checksum: str
    ) -> None:
        """
        写入待审核技能包目录
        安全校验：禁止路径逃逸；已存在相同包且校验和一致直接复用，不一致则冲突报错
        """
        resolved = path.resolve()
        if self.root not in resolved.parents:
            raise fail(
                "skill_package_path_escape",
                "待审核技能路径超出根目录 data/skills 范围",
            )
        metadata = resolved / "metadata.json"
        if resolved.exists():
            if not metadata.is_file():
                raise fail(
                    "pending_skill_conflict",
                    "待审核技能目录存在冲突",
                )
            current = json.loads(metadata.read_text(encoding="utf-8"))
            if current.get("draft_checksum") != checksum:
                raise fail(
                    "pending_skill_conflict",
                    "待审核技能内容发生冲突，草稿校验和不一致",
                )
            if current.get("provenance") != self.provenance:
                raise fail(
                    "skill_provenance_mismatch",
                    "待审核技能 provenance 与 Store 模式不一致",
                )
            return
        resolved.mkdir(parents=True, exist_ok=False)
        for relative, payload in files.items():
            target = (resolved / relative).resolve()
            if resolved != target and resolved not in target.parents:
                raise fail(
                    "skill_package_path_escape",
                    "技能包内部文件路径逃逸待审核目录",
                )
            _atomic_text(target, payload)

    def save_regression_report(
        self, package: SkillPackage, report: object
    ) -> SkillPackage:
        """Finalize the package after binding its regression report."""
        value = report.to_dict()
        value["package_checksum"] = _CHECKSUM_SENTINEL
        metadata = self._metadata(package.path)
        if metadata.get("provenance") != self.provenance:
            raise fail(
                "skill_provenance_mismatch",
                "待审核技能 provenance 与 Store 模式不一致",
            )
        metadata["package_checksum"] = _CHECKSUM_SENTINEL
        _atomic_text(package.path / "regression-report.json", _json(value))
        _atomic_text(package.path / "metadata.json", _json(metadata))
        checksum = compute_skill_package_checksum(package.path)
        metadata["package_checksum"] = checksum
        value["package_checksum"] = checksum
        _atomic_text(package.path / "metadata.json", _json(metadata))
        _atomic_text(package.path / "regression-report.json", _json(value))
        if compute_skill_package_checksum(package.path) != checksum:
            raise fail(
                "skill_package_checksum_mismatch",
                "技能包最终化后的实际校验和不一致",
            )
        finalized = replace(package, checksum=checksum)
        self.record_lifecycle(
            event_type="regression_completed",
            package=finalized,
            details=value,
        )
        self.record_lifecycle(
            event_type="pending_created",
            package=finalized,
            details={
                "decision_id": finalized.decision_id,
                "validated_experience_ids": list(
                    finalized.validation_ids
                ),
            },
        )
        self.rebuild_indexes()
        return finalized

    def review(
        self, *, skill_id: str, cohort_id: str, version: str
    ) -> dict[str, Any]:
        """读取待审核技能元数据，用于人工审核预览"""
        path = self._pending_path(skill_id, cohort_id, version)
        return self._metadata(path)

    def approve(
        self,
        *,
        skill_id: str,
        cohort_id: str,
        version: str,
        expected_checksum: str,
        actor: str,
        reason: str,
    ) -> dict[str, Any]:
        """
        审批通过：将pending包迁移至curated归档目录，更新current.json生效索引
        :param skill_id: 技能ID
        :param cohort_id: 兼容分组ID
        :param version: 版本号
        :param expected_checksum: 预期包校验和，防篡改
        :param actor: 审批人标识
        :param reason: 审批备注
        :return: 审批记录
        """
        actor = _required(actor, "actor")
        reason = _required(reason, "reason")
        pending = self._pending_path(skill_id, cohort_id, version)
        metadata = self._validate_for_approval(
            pending=pending,
            skill_id=skill_id,
            cohort_id=cohort_id,
            version=version,
            expected_checksum=expected_checksum,
        )

        curated = (
            self.root
            / "curated"
            / _safe(skill_id, "skill_id")
        )
        version_path = curated / "versions" / _safe(version, "version")
        if version_path.exists():
            existing = self._metadata(version_path)
            self._verify_checksum(existing, expected_checksum)
            if compute_skill_package_checksum(version_path) != expected_checksum:
                raise fail(
                    "skill_package_checksum_mismatch",
                    "已归档 Skill 的实际内容校验和不一致",
                )
        else:
            version_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = version_path.parent / f".{version}.tmp"
            if temporary.exists():
                shutil.rmtree(temporary)
            shutil.copytree(pending, temporary)
            copied_metadata = self._metadata(temporary)
            copied_metadata["status"] = "curated"
            _atomic_text(
                temporary / "metadata.json",
                _json(copied_metadata),
            )
            os.replace(temporary, version_path)
        # 生成审批记录
        approval = self._decision_record(
            "approved",
            skill_id,
            cohort_id,
            version,
            expected_checksum,
            actor,
            reason,
        )
        approval_path = (
            self.root
            / "approvals"
            / skill_id
            / version
            / "approval-record.json"
        )
        _atomic_text(approval_path, _json(approval))
        # 更新current.json，将此版本设为当前生效版本
        _atomic_text(
            curated / "current.json",
            _json({
                "skill_id": skill_id,
                "cohort_id": cohort_id,
                "version": version,
                "package_checksum": expected_checksum,
                "relative_path": str(
                    Path("versions") / version
                ).replace("\\", "/"),
            }),
        )
        package = self._package_from_metadata(pending, metadata)
        self.record_lifecycle(
            event_type="approved",
            package=package,
            details=approval,
        )
        self.rebuild_indexes()
        return approval

    def _validate_for_approval(
        self,
        *,
        pending: Path,
        skill_id: str,
        cohort_id: str,
        version: str,
        expected_checksum: str,
    ) -> dict[str, Any]:
        metadata = self._metadata(pending)
        actual = compute_skill_package_checksum(pending)
        report = _read_json_object(pending / "regression-report.json")
        decision = _read_json_object(pending / "promotion-decision.json")
        decision_body = _validate_promotion_decision(decision)
        declared = metadata.get("package_checksum")
        if not expected_checksum or not (
            actual == declared == report.get("package_checksum")
            == expected_checksum
        ):
            raise fail(
                "skill_package_checksum_mismatch",
                "实际包、元数据、回归报告与预期校验和不一致",
            )
        if not all(report.get(field) is True for field in (
            "static_validation_passed",
            "traceability_validation_passed",
            "proposal_regression_passed",
        )):
            raise fail(
                "skill_regression_not_passed",
                "技能回归测试未全部通过，禁止审批归档",
            )
        if (
            metadata.get("skill_id") != skill_id
            or metadata.get("family_id") != skill_id
            or metadata.get("version") != version
            or metadata.get("compatibility_cohort", {}).get("cohort_id")
            != cohort_id
            or metadata.get("decision_id") != decision.get("decision_id")
            or metadata.get("validated_experience_ids")
            != decision_body["validated_experience_ids"]
            or decision_body["family_id"] != skill_id
            or decision_body["cohort_id"] != cohort_id
            or decision_body["target_version"] != version
        ):
            raise fail(
                "promotion_decision_binding_mismatch",
                "PromotionDecision、metadata 与审批身份不一致",
            )
        provenance = metadata.get("provenance")
        if (
            provenance != decision_body["provenance"]
            or provenance != self.provenance
        ):
            raise fail(
                "skill_provenance_mismatch",
                "测试 Fixture 或不同 Store provenance 不得进入当前 Curated Store",
            )
        if (
            self.config.mode is SkillStoreMode.PRODUCTION
            and provenance != "production"
        ):
            raise fail(
                "test_fixture_promotion_forbidden",
                "测试 Fixture 永远不得进入生产 Curated Store",
            )
        return metadata

    def reject(
        self,
        *,
        skill_id: str,
        cohort_id: str,
        version: str,
        expected_checksum: str,
        actor: str,
        reason: str,
    ) -> dict[str, Any]:
        """
        驳回技能：将pending目录移动至rejected归档，写入驳回记录
        """
        actor = _required(actor, "actor")
        reason = _required(reason, "reason")
        pending = self._pending_path(skill_id, cohort_id, version)
        rejected = self.root / "rejected" / skill_id / version
        # 已经迁移至驳回目录的场景，直接校验记录一致性
        if not pending.exists() and rejected.is_dir():
            existing = self._metadata(rejected)
            self._verify_checksum(existing, expected_checksum)
            if compute_skill_package_checksum(rejected) != expected_checksum:
                raise fail(
                    "skill_package_checksum_mismatch",
                    "已驳回 Skill 的实际内容校验和不一致",
                )
            record_path = rejected / "rejection-record.json"
            record = json.loads(record_path.read_text(encoding="utf-8"))
            expected = self._decision_record(
                "rejected",
                skill_id,
                cohort_id,
                version,
                expected_checksum,
                actor,
                reason,
            )
            if record != expected:
                raise fail(
                    "skill_rejection_record_conflict",
                    "驳回记录内容冲突",
                )
            return record
        metadata = self._metadata(pending)
        self._verify_checksum(metadata, expected_checksum)
        if compute_skill_package_checksum(pending) != expected_checksum:
            raise fail(
                "skill_package_checksum_mismatch",
                "待驳回 Skill 的实际内容校验和不一致",
            )
        if rejected.exists():
            existing = self._metadata(rejected)
            self._verify_checksum(existing, expected_checksum)
        else:
            rejected.parent.mkdir(parents=True, exist_ok=True)
            os.replace(pending, rejected)
            rejected_metadata = self._metadata(rejected)
            rejected_metadata["status"] = "rejected"
            _atomic_text(
                rejected / "metadata.json",
                _json(rejected_metadata),
            )
        decision = self._decision_record(
            "rejected",
            skill_id,
            cohort_id,
            version,
            expected_checksum,
            actor,
            reason,
        )
        _atomic_text(rejected / "rejection-record.json", _json(decision))
        package = self._package_from_metadata(rejected, metadata)
        self.record_lifecycle(
            event_type="rejected",
            package=package,
            details=decision,
        )
        self.rebuild_indexes()
        return decision

    def record_lifecycle(
        self,
        *,
        event_type: str,
        package: SkillPackage,
        details: dict[str, Any],
    ) -> None:
        """
        写入技能生命周期账本 promotion-ledger.jsonl
        每条事件具备唯一event_id，防止重复写入与内容冲突
        """
        row = {
            "event_id": canonical_sha256({
                "event_type": event_type,
                "skill_id": package.skill_id,
                "cohort_id": package.cohort_id,
                "version": package.version,
                "package_checksum": package.checksum,
                "details": details,
            }),
            "event_type": event_type,
            "skill_id": package.skill_id,
            "cohort_id": package.cohort_id,
            "version": package.version,
            "package_checksum": package.checksum,
            "decision_id": package.decision_id,
            "validation_ids": list(package.validation_ids),
            "details": details,
        }
        row = json.loads(
            json.dumps(row, ensure_ascii=False, sort_keys=True, default=str)
        )
        rows = {item["event_id"]: item for item in self.ledger_rows()}
        current = rows.get(row["event_id"])
        if current is not None and current != row:
            raise fail(
                "skill_ledger_event_conflict",
                "晋升账本事件内容冲突",
            )
        rows[row["event_id"]] = row
        text = "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n"
            for _, item in sorted(rows.items())
        )
        _atomic_text(self.root / "promotion-ledger.jsonl", text)

    def ledger_rows(self) -> list[dict[str, Any]]:
        """读取全部生命周期账本记录"""
        path = self.root / "promotion-ledger.jsonl"
        if not path.is_file():
            return []
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def rebuild_indexes(self) -> None:
        """重建pending、curated两类技能索引文件，用于快速检索"""
        for status in ("pending", "curated"):
            rows: list[dict[str, Any]] = []
            base = self.root / status
            if base.is_dir():
                for metadata_path in sorted(base.rglob("metadata.json")):
                    # curated目录下只读取versions子目录内的元数据
                    if status == "curated" and "versions" not in metadata_path.parts:
                        continue
                    data = json.loads(metadata_path.read_text(encoding="utf-8"))
                    rows.append({
                        "skill_id": data["skill_id"],
                        "cohort_id": data[
                            "compatibility_cohort"
                        ]["cohort_id"],
                        "version": data["version"],
                        "package_checksum": data["package_checksum"],
                        "relative_path": str(
                            metadata_path.parent.relative_to(self.root)
                        ).replace("\\", "/"),
                    })
            text = "".join(
                json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                for row in rows
            )
            _atomic_text(self.root / "indexes" / f"{status}.jsonl", text)

    def _pending_path(
        self, skill_id: str, cohort_id: str, version: str
    ) -> Path:
        """组装待审核技能目录路径，并校验标识符合法性"""
        return (
            self.root
            / "pending"
            / _safe(skill_id, "skill_id")
            / _safe(version, "version")
        )

    @staticmethod
    def _metadata(path: Path) -> dict[str, Any]:
        """读取目录内metadata.json并校验根节点为字典"""
        metadata = path / "metadata.json"
        if not metadata.is_file():
            raise fail("skill_package_not_found", f"未找到技能包：{path}")
        value = json.loads(metadata.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise fail(
                "skill_package_metadata_invalid",
                "技能元数据文件格式非法",
            )
        return value

    @staticmethod
    def _verify_checksum(
        metadata: dict[str, Any], expected_checksum: str
    ) -> None:
        """校验技能包校验和，防止文件篡改"""
        if (
            not expected_checksum
            or metadata.get("package_checksum") != expected_checksum
        ):
            raise fail(
                "skill_package_checksum_mismatch",
                "技能包校验和不匹配",
            )

    @staticmethod
    def _decision_record(
        status: str,
        skill_id: str,
        cohort_id: str,
        version: str,
        checksum: str,
        actor: str,
        reason: str,
    ) -> dict[str, Any]:
        """构造审批/驳回标准记录结构"""
        return {
            "status": status,
            "skill_id": skill_id,
            "cohort_id": cohort_id,
            "version": version,
            "expected_checksum": checksum,
            "actor": actor,
            "reason": reason,
        }

    @staticmethod
    def _package_from_metadata(
        path: Path, metadata: dict[str, Any]
    ) -> SkillPackage:
        """从元数据字典还原SkillPackage快照（插槽映射暂空，用于日志）"""
        return SkillPackage(
            skill_id=metadata["skill_id"],
            cohort_id=metadata["compatibility_cohort"]["cohort_id"],
            version=metadata["version"],
            path=path,
            checksum=metadata["package_checksum"],
            decision_id=metadata["decision_id"],
            validation_ids=tuple(metadata["validated_experience_ids"]),
            source_slot_map={},
        )


def _all_rules(content: SkillDraftContent) -> tuple[SkillRule, ...]:
    """汇总草稿内全部规则集合"""
    return (
        *content.when_to_use,
        *content.strategy_patterns,
        *content.conditions,
        *content.counterexamples,
        *content.verification_rules,
    )


def _render_skill(
    *,
    skill_id: str,
    version: str,
    cohort_id: str,
    content: SkillDraftContent,
) -> str:
    """渲染主技能文档 SKILL.md Markdown文本"""
    sections = [
        "---",
        f"name: {skill_id}",
        f"version: {version}",
        "status: pending",
        "source: phase8-controlled",
        "consumer:",
        "  - StrategyProposalAgent",
        f"compatibility_cohort: {cohort_id}",
        "---",
        "",
        f"# {content.title}",
        "",
        content.description,
    ]
    groups = (
        ("When To Use", content.when_to_use),
        ("Strategy Patterns", content.strategy_patterns),
        ("Conditions", content.conditions),
        ("Counterexamples", content.counterexamples),
        ("Verification Rules", content.verification_rules),
    )
    for heading, rules in groups:
        sections.extend(("", f"## {heading}", ""))
        sections.extend(
            f"- `{rule.rule_key}`: {rule.statement} "
            f"[sources: {', '.join(rule.source_slots)}]"
            for rule in rules
        )
    return "\n".join(sections).rstrip() + "\n"


def _render_references(
    experience_ids: tuple[str, ...],
    records: dict[str, dict[str, Any]],
    inherited_source_refs: dict[str, tuple[str, ...]],
) -> str:
    """渲染经验溯源文档，列出每条经验对应的证据文件路径"""
    lines = ["# Validated Experience References", ""]
    inherited_refs = {
        ref for refs in inherited_source_refs.values() for ref in refs
    }
    for experience_id in experience_ids:
        refs = ", ".join(sorted(map(
            str, records.get(experience_id, {}).get("evidence_refs", ())
        )))
        if not refs and inherited_refs:
            refs = ", ".join(sorted(inherited_refs))
        lines.append(f"- `{experience_id}`: {refs or '无证据溯源路径'}")
    return "\n".join(lines).rstrip() + "\n"


def _required(value: str, name: str) -> str:
    """必填参数校验，去除首尾空白字符"""
    if not isinstance(value, str) or not value.strip():
        raise fail(
            f"{name}_required",
            f"{name} 为必填项",
        )
    return value.strip()
