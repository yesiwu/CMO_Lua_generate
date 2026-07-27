"""
检查skill证据是否可信，是否足以形成规则，

待审核技能包的静态校验、溯源完整性校验与提案回归测试服务。
技能进入人工审批前必须执行本轮校验；只有三项校验全部通过，技能包才允许被审批归档为正式可用技能。
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

from .assets import SkillPackage


@dataclass(frozen=True, slots=True)
class SkillRegressionReport:
    """
    技能回归校验报告实体
    汇总三类校验结果与失败原因，持久化为 regression-report.json，作为审批准入依据
    """
    static_validation_passed: bool        # 静态语法与内容规范校验是否通过
    traceability_validation_passed: bool  # 经验溯源链路完整性校验是否通过
    proposal_regression_passed: bool      # 策略提案回归测试是否通过
    cmo_effectiveness_validation: str     # CMO仿真有效性校验状态（当前暂未执行）
    failures: tuple[str, ...]             # 失败项标识列表
    package_checksum: str = "<skill-package-checksum>"

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典用于落地JSON报告文件"""
        return asdict(self)


class SkillRegressionService:
    """
    技能回归校验服务
    在人工审批（approve）之前自动执行三层校验：静态规范校验、溯源链路校验、提案回归校验。
    在校验不通过时，SkillAssetStore 将拒绝执行审批归档操作。
    """
    # 静态内容黑名单正则：禁止出现TODO、原始Lua代码、ScenEdit接口、Windows绝对路径、Unix系统路径
    _forbidden = re.compile(
        r"\b(?:TODO|TBD)\b|```lua|\bScenEdit_[A-Za-z0-9_]+\b|"
        r"[A-Za-z]:\\|(?:^|\s)/(?:home|tmp|var)/",
        re.IGNORECASE | re.MULTILINE,
    )

    def __init__(
        self, *, proposal_validator: Callable[[SkillPackage], bool]
    ) -> None:
        """
        :param proposal_validator: 外部注入的策略提案回归校验回调函数
        接收技能包对象，返回布尔值代表回归测试是否通过
        """
        self._proposal_validator = proposal_validator

    def validate(
        self,
        package: SkillPackage,
        *,
        evidence_records: dict[str, dict[str, Any]],
    ) -> SkillRegressionReport:
        """
        执行全套回归校验流程
        :param package: 待审核技能包快照
        :param evidence_records: 经验原始证据记录字典，用于溯源核对
        :return: 标准化回归校验报告
        """
        failures: list[str] = []
        skill_text = (package.path / "SKILL.md").read_text(encoding="utf-8")
        metadata = json.loads(
            (package.path / "metadata.json").read_text(encoding="utf-8")
        )

        # ========== 1. 静态规范校验 ==========
        static_ok = (
            # 元数据标识与技能包信息一致
            metadata.get("skill_id") == package.skill_id
            and metadata.get("version") == package.version
            and metadata.get("package_checksum") == package.checksum
            # 不存在黑名单违禁内容
            and not self._forbidden.search(skill_text)
            # 文档必须包含全部强制章节，保证结构统一
            and all(
                marker in skill_text
                for marker in (
                    "## Strategy Patterns",
                    "## Conditions",
                    "## Counterexamples",
                    "## Verification Rules",
                )
            )
        )
        if not static_ok:
            failures.append("static_validation_failed")

        # ========== 2. 溯源完整性校验 ==========
        manifest = json.loads(
            (package.path / "evidence-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        source_slots = manifest.get("source_slots", {})
        traceability_ok = bool(source_slots)

        for slot, row in source_slots.items():
            ids = row.get("experience_ids", ())
            # 校验规则：
            # 1. 插槽必须存在于技能包定义的插槽映射
            # 2. 绑定经验ID列表与内存快照完全一致
            # 3. 不能存在空经验ID列表
            # 4. 所有引用的经验ID必须存在原始证据记录
            if (
                slot not in package.source_slot_map
                or tuple(ids) != package.source_slot_map[slot]
                or not ids
                or any(experience_id not in evidence_records for experience_id in ids)
            ):
                traceability_ok = False

            # 校验清单内证据文件路径与原始经验记录自动汇总结果保持一致
            expected_refs = sorted({
                str(ref)
                for experience_id in ids
                for ref in evidence_records.get(experience_id, {}).get(
                    "evidence_refs", ()
                )
            })
            if row.get("evidence_refs") != expected_refs:
                traceability_ok = False

        if not traceability_ok:
            failures.append("traceability_validation_failed")

        # ========== 3. 策略提案回归校验（外部注入逻辑） ==========
        proposal_ok = bool(self._proposal_validator(package))
        if not proposal_ok:
            failures.append("proposal_regression_failed")

        return SkillRegressionReport(
            static_validation_passed=static_ok,
            traceability_validation_passed=traceability_ok,
            proposal_regression_passed=proposal_ok,
            cmo_effectiveness_validation="not_run",
            failures=tuple(failures),
        )
