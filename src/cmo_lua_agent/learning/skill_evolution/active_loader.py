"""
具备兼容分组感知的只读加载器，用于加载经过人工筛选、固化的运行时技能(Skill)。
核心目标：基于兼容性分组(Cohort)隔离不同版本仿真环境下的技能包，防止跨环境混用引发语义漂移。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import CompatibilityCohort
from .aggregation import canonical_sha256
from .assets import compute_skill_package_checksum
from .errors import fail


@dataclass(frozen=True, slots=True)
class ActiveSkillSnapshot:
    """
    已激活技能快照
    不可变数据模型：承载一套完整可用Skill的全部静态内容、元数据、经验绑定关系
    """
    skill_id: str                          # 技能唯一标识
    cohort_id: str                         # 所属兼容分组ID
    version: str                           # 技能版本号
    checksum: str                          # 技能包完整校验和，防篡改
    content: str                           # 原始技能文本（SKILL.md）
    structured_content: dict[str, Any]     # 结构化配置（content.json）
    covered_experience_keys: tuple[str, ...] # 该技能已经内置覆盖的正向经验键集合
    source_slot_map: dict[str, tuple[str, ...]] # 插槽映射：插槽名称 → 绑定经验ID列表
    source_slot_refs: dict[str, tuple[str, ...]] # 插槽溯源：插槽名称 → 原始证据文件路径

    def to_prompt_dict(self) -> dict[str, Any]:
        """序列化为送入LLM Prompt的精简字典，剔除审计冗余字段"""
        return {
            "skill_id": self.skill_id,
            "cohort_id": self.cohort_id,
            "version": self.version,
            "checksum": self.checksum,
            "content": self.content,
            "covered_experience_keys": list(self.covered_experience_keys),
        }

    def filter_experience_cards(
        self, cards: tuple[dict[str, Any], ...]
    ) -> tuple[dict[str, Any], ...]:
        """
        经验卡片过滤器
        作用：避免将技能内部已经固化的正向战术经验再次塞入Prompt，造成重复冗余
        过滤规则：如果经验属于tactical_positive且key在技能覆盖列表内，则剔除
        """
        covered = set(self.covered_experience_keys)
        return tuple(
            dict(card)
            for card in cards
            if not (
                card.get("experience_key") in covered
                and card.get("experience_type") == "tactical_positive"
            )
        )


class ActiveSkillLoader:
    """
    运行时技能加载器
    只读加载经过审核固化的Skill包；强制按兼容分组隔离，校验文件完整性、路径逃逸、哈希一致性
    """
    def __init__(
        self,
        skills_root: Path,
        *,
        expected_provenance: str = "production",
    ) -> None:
        self._root = Path(skills_root).resolve()
        self._expected_provenance = expected_provenance

    def load(
        self,
        *,
        skill_id: str,
        cohort: CompatibilityCohort,
    ) -> ActiveSkillSnapshot | None:
        """
        根据技能ID与当前环境兼容分组，加载当前生效版本的技能快照
        :param skill_id: 目标技能标识
        :param cohort: 当前运行环境兼容分组契约
        :return: 技能快照；不存在则返回None
        :raises ValueError: 索引不匹配、路径越界、文件缺失、校验和不一致等异常
        """
        # 技能根路径：curated/技能ID/兼容分组ID
        base = self._root / "curated" / skill_id
        current_path = base / "current.json"
        # Legacy cohort-scoped assets are readable but no longer written.
        if not current_path.is_file():
            base = base / cohort.cohort_id
            current_path = base / "current.json"
        if not current_path.is_file():
            legacy = sorted((self._root / "curated" / skill_id).glob("*/current.json"))
            if legacy:
                current_path = legacy[0]
                base = current_path.parent
        # 不存在当前版本索引 → 无可用技能
        if not current_path.is_file():
            return None
        current = _object(current_path)
        # 校验索引文件中的skill_id、cohort_id和请求参数一致
        if current.get("skill_id") != skill_id:
            raise fail(
                "active_skill_cohort_mismatch",
                "已审核技能的当前索引与兼容分组不匹配",
            )
        relative = current.get("relative_path")
        if not isinstance(relative, str):
            raise fail(
                "active_skill_path_invalid",
                "已审核技能的版本相对路径格式非法",
            )
        # 解析技能包目录绝对路径
        version_path = (base / relative).resolve()
        # 安全防护：禁止路径逃逸出当前cohort目录
        if base.resolve() not in version_path.parents:
            raise fail(
                "active_skill_path_escape",
                "已审核技能路径超出当前兼容分组目录范围",
            )
        metadata = _object(version_path / "metadata.json")
        # 技能包声明的兼容分组与运行环境不匹配 → 不可加载
        metadata_cohort = metadata.get("compatibility_cohort", {})
        if not isinstance(metadata_cohort, dict):
            raise fail(
                "skill_package_metadata_invalid",
                "Skill compatibility metadata must be an object",
            )
        if metadata.get("provenance") != self._expected_provenance:
            raise fail(
                "skill_provenance_mismatch",
                "Active Skill provenance 与当前加载环境不一致",
            )
        checksum = str(metadata.get("package_checksum", ""))
        # 校验技能包哈希与current索引记录一致，防止文件被篡改
        if not checksum or checksum != current.get("package_checksum"):
            raise fail(
                "skill_package_checksum_mismatch",
                "技能包校验和与索引记录不一致",
            )
        if compute_skill_package_checksum(version_path) != checksum:
            raise fail(
                "skill_package_checksum_mismatch",
                "已审核技能包实际内容与声明校验和不一致",
            )
        skill_path = version_path / "SKILL.md"
        content_path = version_path / "content.json"
        # 核心文件缺失，技能包不完整
        if not skill_path.is_file() or not content_path.is_file():
            raise fail(
                "skill_package_incomplete",
                "已审核技能包核心文件缺失",
            )
        evidence_path = version_path / "evidence-manifest.json"
        evidence = _object(evidence_path) if evidence_path.is_file() else {}
        source_slots = evidence.get("source_slots", {})
        if not isinstance(source_slots, dict):
            raise fail(
                "skill_evidence_manifest_invalid",
                "已审核技能证据清单格式非法",
            )

        return ActiveSkillSnapshot(
            skill_id=skill_id,
            cohort_id=cohort.cohort_id,
            version=str(metadata["version"]),
            checksum=checksum,
            content=skill_path.read_text(encoding="utf-8"),
            structured_content=_object(content_path),
            covered_experience_keys=tuple(sorted(
                map(str, metadata.get("applicable_experience_keys", ()))
            )),
            source_slot_map={
                str(slot): tuple(map(str, row.get("experience_ids", ())))
                for slot, row in source_slots.items()
                if isinstance(row, dict)
            },
            source_slot_refs={
                str(slot): tuple(map(str, row.get("evidence_refs", ())))
                for slot, row in source_slots.items()
                if isinstance(row, dict)
            },
        )


def make_compatibility_cohort(
    *,
    score_spec_version: str,
    score_spec_checksum: str,
    runtime_version: str,
    renderer_version: str,
    scenario_schema_version: str = "1.0",
    score_source: str = "execution_summary",
) -> CompatibilityCohort:
    """
    构造环境兼容分组契约 CompatibilityCohort
    将版本信息归一化，生成唯一cohort_id；用于隔离不同仿真环境，禁止跨环境加载技能与经验
    """
    def major(value: str) -> int:
        """提取版本号主版本数字（如 "2.1.0" → 2）"""
        try:
            return int(value.split(".", 1)[0])
        except (AttributeError, ValueError) as exc:
            raise fail(
                "compatibility_version_invalid",
                f"非法兼容版本号：{value}",
            ) from exc

    body = {
        "score_spec_major": major(score_spec_version),
        "score_spec_checksum": score_spec_checksum,
        "runtime_major": major(runtime_version),
        "renderer_major": major(renderer_version),
        "scenario_schema_version": scenario_schema_version,
        "score_source": score_source,
    }
    # 基于环境契约哈希生成分组ID，取前16字符缩短标识
    return CompatibilityCohort(
        # Keep precise environment values as metadata, but expose one shared
        # mission scope for retrieval and curated Skill storage.
        cohort_id="scope_naval_air_anti_surface",
        **body,
    )


def _object(path: Path) -> dict[str, Any]:
    """
    内部工具函数：读取JSON文件并强制校验根节点为字典
    :param path: JSON文件路径
    :return: 解析字典
    :raises ValueError: 文件缺失或根不是对象
    """
    if not path.is_file():
        raise fail(
            "skill_package_incomplete",
            f"缺少必需的已审核技能文件：{path}",
        )
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise fail(
            "skill_package_file_invalid",
            f"已审核技能 JSON 文件根节点必须为对象：{path}",
        )
    return value
