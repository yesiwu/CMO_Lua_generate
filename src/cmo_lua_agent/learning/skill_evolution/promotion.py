"""
Phase8 确定性经验晋升阈值与决策策略模块。
依据预设指标阈值，对已校验经验自动判定晋升动作；配套语义化版本管理策略，生成标准化晋升决策单据PromotionDecision。
整套规则完全无随机逻辑，保证相同输入永远产出一致决策。
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .aggregation import canonical_sha256
from .errors import fail
from .models import PromotionAction, PromotionDecision, ValidatedExperience


@dataclass(frozen=True, slots=True)
class PromotionProfile:
    """
    晋升评估配置模板
    定义经验晋升为技能规则所需满足的各项硬性指标阈值；可多套配置并存，方便策略迭代对比。
    """
    profile_id: str                              # 配置模板唯一标识
    minimum_independent_scenarios: int           # 最低独立想定数量
    minimum_independent_optimizations: int       # 最低独立优化轮次数量
    minimum_support: int                         # 最低支持类证据条数
    minimum_mean_evidence_quality: float          # 最低平均证据质量
    minimum_execution_success_rate: float         # 最低执行成功率
    minimum_semantic_valid_rate: float            # 最低策略语义合法率
    minimum_execution_fidelity_rate: float        # 最低仿真证据保真验证率
    maximum_contradiction_ratio: float           # 允许的最高矛盾证据占比
    minimum_deterministic_confidence: float      # 最低综合可信置信度

    @classmethod
    def default(cls) -> "PromotionProfile":
        """加载海上空对面战术经验默认晋升阈值配置"""
        return cls(
            profile_id="naval_air_skill_promotion_v1",
            minimum_independent_scenarios=3,
            minimum_independent_optimizations=5,
            minimum_support=5,
            minimum_mean_evidence_quality=0.75,
            minimum_execution_success_rate=0.90,
            minimum_semantic_valid_rate=0.95,
            minimum_execution_fidelity_rate=0.85,
            maximum_contradiction_ratio=0.20,
            minimum_deterministic_confidence=0.70,
        )


def _next_minor(version: str) -> str:
    """
    自动递增次版本号（minor）
    语义化版本 x.y.z → x.(y+1).0
    :param version: 当前版本字符串
    :return: 自动生成的下一个版本号
    :raises ValueError: 版本格式不符合三段数字语义化版本规范
    """
    parts = version.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError(f"非法语义化版本号：{version}")
    return f"{int(parts[0])}.{int(parts[1]) + 1}.0"


def _semver(version: str) -> tuple[int, int, int]:
    """
    将三段式版本字符串解析为(主版本,次版本,修订号)整数元组，便于大小对比
    :raises ValueError: 版本格式非法时报错
    """
    parts = version.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError(f"非法语义化版本号：{version}")
    return tuple(map(int, parts))


class SkillVersionPolicy:
    """
    技能版本管理策略
    自动版本生成具备确定性；只有人工介入时才允许自定义指定版本跃迁。
    """
    def automatic(self, active_version: str | None) -> str:
        """
        自动生成目标版本
        无生效版本 → 初始版本0.1.0；存在生效版本 → 自动升级minor次版本
        """
        return "0.1.0" if active_version is None else _next_minor(active_version)

    def manual(
        self,
        *,
        current_version: str,
        target_version: str,
        change_kind: str,
    ) -> str:
        """
        人工指定版本跃迁校验
        :param current_version: 当前线上生效版本
        :param target_version: 人工指定目标版本
        :param change_kind: 变更类型 patch / major
        :return: 校验通过后的目标版本
        :raises ValueError: 版本跃迁规则不合法时抛出异常
        """
        current = _semver(current_version)
        target = _semver(target_version)
        if change_kind == "patch":
            # patch修订：主版本、次版本不变，修订号增大
            valid = (
                target[:2] == current[:2]
                and target[2] > current[2]
            )
        elif change_kind == "major":
            # major大版本升级：主版本号增大
            valid = target[0] > current[0]
        else:
            raise ValueError("人工变更类型仅支持 patch 或 major")
        if not valid:
            raise ValueError(
                f"人工指定{change_kind}版本跃迁不合法："
                f"{current_version} → {target_version}"
            )
        return target_version


class SkillPromotionPolicy:
    """
    经验晋升决策核心策略器
    接收ValidatedExperience已校验经验，结合晋升阈值模板自动输出PromotionDecision决策单据
    """
    def __init__(self, profile: PromotionProfile) -> None:
        self._profile = profile
        self._versions = SkillVersionPolicy()

    def decide(
        self,
        validated: ValidatedExperience | Sequence[ValidatedExperience],
        *,
        active_version: str | None,
        provenance: str = "production",
    ) -> PromotionDecision:
        """
        执行晋升决策逻辑
        :param validated: 完成资格校验的经验实体
        :param active_version: 当前该技能家族已生效版本；None代表暂无正式技能
        :return: 标准化晋升决策单据
        """
        items = (
            (validated,)
            if isinstance(validated, ValidatedExperience)
            else tuple(validated)
        )
        if not items:
            raise fail(
                "promotion_decision_validation_required",
                "晋升决策必须绑定至少一条验证经验",
            )
        first = items[0]
        if any(
            item.family != first.family
            or item.compatibility_cohort.cohort_id
            != first.compatibility_cohort.cohort_id
            for item in items
        ):
            raise fail(
                "promotion_decision_binding_mismatch",
                "晋升决策中的验证经验不属于同一 Family/Cohort",
            )
        eligible = all(item.eligible for item in items)
        reasons = sorted({
            reason for item in items for reason in item.validation_reasons
        })
        if eligible:
            # 经验满足全部晋升条件：新建技能 / 修订已有技能
            action = (
                PromotionAction.REVISE_EXISTING_SKILL
                if active_version
                else PromotionAction.CREATE_PENDING_SKILL
            )
            target_version = self._versions.automatic(active_version)
        elif (
            active_version
            and "contradiction_ratio_above_maximum" in reasons
        ):
            # 矛盾证据占比超标，需要人工复核
            action = PromotionAction.REQUIRE_REVIEW
            target_version = None
        elif any(reason.startswith("invalid_") for reason in reasons):
            # 存在根本性缺陷，直接拒绝晋升
            action = PromotionAction.REJECT
            target_version = None
        else:
            # 证据尚不充分，继续收集更多仿真数据
            action = PromotionAction.CONTINUE_ACCUMULATING
            target_version = None

        # 构造决策原始载荷，用于生成确定性校验和
        body = {
            "eligible": eligible,
            "validated_experience_ids": sorted(
                item.validation_id for item in items
            ),
            "family_id": first.family,
            "cohort_id": first.compatibility_cohort.cohort_id,
            "action": action.value,
            "target_version": target_version,
            "reasons": reasons,
            "profile_id": self._profile.profile_id,
            "provenance": provenance,
        }
        checksum = canonical_sha256(body)
        return PromotionDecision(
            decision_id=f"decision_{checksum[:20]}",
            eligible=eligible,
            validated_experience_ids=tuple(
                body["validated_experience_ids"]
            ),
            family_id=first.family,
            cohort_id=first.compatibility_cohort.cohort_id,
            action=action,
            target_version=target_version,
            reasons=tuple(reasons),
            profile_id=self._profile.profile_id,
            provenance=provenance,
            checksum=checksum,
        )
