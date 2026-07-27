"""
受控的Phase8经验键与技能分类目录。
作用：统一管理经验标识别名、标准定义、归属技能家族；实现经验键归一化解析，防止命名混乱，支撑经验聚合与技能组装链路。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExperienceKeyDefinition:
    """
    经验键标准定义实体
    存储一条经验的标准主键、归属家族、标准假说文本、别名列表
    """
    key: str                          # 标准化完整经验键（命名空间.标识）
    family: str                       # 归属技能家族标识
    canonical_hypothesis: str        # 标准规范假说描述
    aliases: tuple[str, ...]          # 兼容别名集合（简写、横杠变体等）


class ExperienceKeyCatalog:
    """
    经验键目录管理器
    提供别名归一化、标准定义查询能力；统一新旧命名、不同写法的经验键映射。
    """
    def __init__(self, definitions: tuple[ExperienceKeyDefinition, ...]) -> None:
        # 标准key → 完整定义对象
        self._definitions = {item.key: item for item in definitions}
        # 小写别名 → 标准完整key（兼容简写、别名）
        self._aliases = {
            alias.strip().lower(): item.key
            for item in definitions
            for alias in (item.key, *item.aliases)
        }

    @classmethod
    def default(cls) -> "ExperienceKeyCatalog":
        """加载默认海上空对面战术经验目录"""
        family = "cmo_naval_air_strategy_patterns"
        rows = (
            ("target_deconfliction", "避免舰艇与舰载机无意重复分配同一首要目标"),
            ("target_concentration", "在适用条件下集中火力攻击高价值目标"),
            ("salvo_timing", "协调攻击波时序以改善多平台协同"),
            ("fire_quantity", "依据目标和资源约束分配适当的发射数量"),
            ("aircraft_route", "使用受控航路降低舰载机暴露并保持攻击可达性"),
            ("aircraft_early_loss", "避免舰载机在形成有效攻击前过早损失"),
            ("ammunition_reserve", "保留必要弹药以避免单轮攻击耗尽资源"),
        )
        return cls(tuple(
            ExperienceKeyDefinition(
                key=f"naval_air_anti_surface.{suffix}",
                family=family,
                canonical_hypothesis=hypothesis,
                aliases=(suffix, suffix.replace("_", "-")),
            )
            for suffix, hypothesis in rows
        ))

    def normalize(self, key: str) -> str:
        """
        将输入经验键归一化为标准完整命名空间key
        无法识别的名称返回 unclassified（未分类）
        :param key: 原始输入经验键（简写/别名/标准名均可）
        """
        if not isinstance(key, str):
            return "unclassified"
        return self._aliases.get(key.strip().lower(), "unclassified")

    def definition(self, key: str) -> ExperienceKeyDefinition:
        """
        根据原始键查询完整标准定义
        :raises ValueError: 无法归一化、属于未分类经验键时报错
        """
        normalized = self.normalize(key)
        if normalized == "unclassified":
            raise ValueError(f"无法识别的经验键：{key}")
        return self._definitions[normalized]


@dataclass(frozen=True, slots=True)
class SkillFamilyDefinition:
    """
    技能家族定义实体
    描述一类战术技能对应的任务类型、消费模块、内置规则章节划分
    """
    family: str                          # 技能家族标识
    skill_id: str                        # 对应技能ID
    mission_type: str                    # 适用任务类型
    consumer: str                        # 使用该技能的目标智能体
    sections: tuple[str, ...]            # 技能文档内部规则章节划分


class SkillFamilyCatalog:
    """
    技能家族目录管理器
    根据家族标识解析对应的技能配置模板
    """
    @classmethod
    def default(cls) -> "SkillFamilyCatalog":
        """加载默认技能家族目录"""
        return cls()

    def resolve(self, family: str) -> SkillFamilyDefinition:
        """
        根据家族名称解析技能家族完整定义
        :param family: 技能家族标识
        :return: 标准化技能家族定义
        :raises ValueError: 不支持的家族标识抛出异常
        """
        if family != "cmo_naval_air_strategy_patterns":
            raise ValueError(f"不支持的技能家族：{family}")
        return SkillFamilyDefinition(
            family=family,
            skill_id=family,
            mission_type="naval_air_anti_surface",
            consumer="StrategyProposalAgent",
            sections=(
                "target_assignment",
                "target_deconfliction",
                "salvo_timing",
                "fire_quantity",
                "aircraft_route",
                "risk_and_survival",
                "ammunition_reserve",
                "counterexamples",
            ),
        )