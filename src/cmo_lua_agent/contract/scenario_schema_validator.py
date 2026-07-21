"""
JsonLoader 是文件读取 + JSON 语法层校验；ScenarioSchemaValidator 是业务场景数据结构层校验，是前后两道独立关卡。
只看字段有没有、类型对不对，完全不管各个单位之间的关联逻辑
"""

from __future__ import annotations

"""场景JSON文档结构校验模块

本模块用于校验字段存在性、局部对象结构、基础数据类型。
仅做纯结构层面校验，不做以下操作：
1. 解析/校验对象间引用关系
2. 跨字段数值对比校验
3. 查询CMO数据库
4. 标准化/改写原始字段内容
5. 生成Lua脚本
"""

import math
from collections.abc import Mapping
from typing import Any

from cmo_lua_agent.contract.models import (
    ScenarioInput,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)

# 位置相关固定字段：纬度、经度、航向、速度
_POSITION_FIELDS = ("latitude", "longitude", "heading", "speed")
# 单位对象必填基础字段
_REQUIRED_UNIT_FIELDS = ("id", "name", "dbid", "type")


class ScenarioSchemaValidator:
    """校验V1版本场景JSON结构契约"""

    def validate(self, scenario: ScenarioInput) -> ValidationResult:
        """执行完整结构校验，一次性收集全部独立错误，输出顺序固定"""
        if not isinstance(scenario, ScenarioInput):
            raise TypeError("入参scenario必须为ScenarioInput类型实例")

        issues: list[ValidationIssue] = []
        raw = scenario.raw

        # 校验顶层必填对象字段：scenario
        self._validate_required_mapping(
            raw,
            field="scenario",
            path="$.scenario",
            issues=issues,
            validator=self._validate_scenario,
        )
        # 校验顶层必填对象字段：sides（红蓝阵营）
        self._validate_required_mapping(
            raw,
            field="sides",
            path="$.sides",
            issues=issues,
            validator=self._validate_sides,
        )
        # 校验顶层攻击计划数组 strikePlan
        self._validate_strike_plan_root(raw, issues)
        # 可选字段：导弹汇总信息
        self._validate_optional_missile_summary(raw, issues)
        # 可选字段：备注文本数组
        self._validate_optional_notes(raw, issues)

        return ValidationResult(issues=tuple(issues))

    def _validate_required_mapping(
        self,
        container: Mapping[str, Any],
        *,
        field: str,
        path: str,
        issues: list[ValidationIssue],
        validator: Any,
    ) -> None:
        """通用工具：校验顶层必填对象字段
        1. 判断字段是否缺失
        2. 判断字段值是否为对象(Mapping)
        3. 校验通过则执行对应子校验函数
        """
        if field not in container:
            self._add_issue(
                issues,
                code="schema.missing_field",
                message=f"缺少必填字段 {field}",
                path=path,
            )
            return

        value = container[field]
        if not isinstance(value, Mapping):
            self._add_issue(
                issues,
                code="schema.invalid_type",
                message=f"字段 {field} 必须是对象",
                path=path,
            )
            return

        # 执行子结构校验
        validator(value, path, issues)

    def _validate_scenario(
        self,
        value: Mapping[str, Any],
        path: str,
        issues: list[ValidationIssue],
    ) -> None:
        """校验顶层 scenario 场景基础信息对象"""
        # 必填：场景ID、场景名称（非空字符串）
        self._validate_required_non_blank_string(
            value,
            field="id",
            path=f"{path}.id",
            issues=issues,
        )
        self._validate_required_non_blank_string(
            value,
            field="name",
            path=f"{path}.name",
            issues=issues,
        )

        # 可选字段 time / timeZone：存在则必须为非空字符串
        for field in ("time", "timeZone"):
            if field in value and not _is_non_blank_string(value[field]):
                self._add_issue(
                    issues,
                    code="schema.invalid_type",
                    message=f"字段 {field} 必须是非空字符串",
                    path=f"{path}.{field}",
                )

        # 可选字段 summary：存在则必须是字符串（允许空）
        if "summary" in value and not isinstance(value["summary"], str):
            self._add_issue(
                issues,
                code="schema.invalid_type",
                message="字段 summary 必须是字符串",
                path=f"{path}.summary",
            )

    def _validate_sides(
        self,
        value: Mapping[str, Any],
        path: str,
        issues: list[ValidationIssue],
    ) -> None:
        """校验 sides 阵营根对象，必须同时包含 red、blue"""
        for side_key in ("red", "blue"):
            side_path = f"{path}.{side_key}"
            # 阵营缺失
            if side_key not in value:
                self._add_issue(
                    issues,
                    code="schema.side_missing",
                    message=f"缺少阵营 {side_key}",
                    path=side_path,
                )
                continue

            side = value[side_key]
            # 阵营必须是对象
            if not isinstance(side, Mapping):
                self._add_issue(
                    issues,
                    code="schema.invalid_side",
                    message=f"阵营 {side_key} 必须是对象",
                    path=side_path,
                )
                continue

            # 校验单个阵营内部结构
            self._validate_side(side, side_path, issues)

    def _validate_side(
        self,
        value: Mapping[str, Any],
        path: str,
        issues: list[ValidationIssue],
    ) -> None:
        """校验单个阵营（red/blue）内部结构"""
        # 阵营名称必填、非空字符串
        self._validate_required_non_blank_string(
            value,
            field="name",
            path=f"{path}.name",
            issues=issues,
        )

        # 校验必填 units 单位数组
        if "units" not in value:
            self._add_issue(
                issues,
                code="schema.missing_field",
                message="缺少必填字段 units",
                path=f"{path}.units",
            )
            return

        units = value["units"]
        if not isinstance(units, list):
            self._add_issue(
                issues,
                code="schema.invalid_type",
                message="字段 units 必须是数组",
                path=f"{path}.units",
            )
            return

        # 可选字段 unitCount：校验数值类型，同时校验与实际单位数量匹配
        if "unitCount" in value:
            unit_count = value["unitCount"]
            if not _is_non_negative_integer(unit_count):
                self._add_issue(
                    issues,
                    code="schema.invalid_type",
                    message="字段 unitCount 必须是非负整数",
                    path=f"{path}.unitCount",
                )
            elif unit_count != len(units):
                self._add_issue(
                    issues,
                    code="schema.unit_count_mismatch",
                    message=(
                        "字段 unitCount 与 units 实际数量不一致："
                        f"{unit_count} != {len(units)}"
                    ),
                    path=f"{path}.unitCount",
                )

        # 遍历校验每一个单位
        for index, unit in enumerate(units):
            unit_path = f"{path}.units[{index}]"
            if not isinstance(unit, Mapping):
                self._add_issue(
                    issues,
                    code="schema.invalid_unit",
                    message="单位必须是对象",
                    path=unit_path,
                )
                continue
            self._validate_unit(unit, unit_path, issues)

    def _validate_unit(
        self,
        value: Mapping[str, Any],
        path: str,
        issues: list[ValidationIssue],
    ) -> None:
        """校验单个作战单位完整结构"""
        # 循环校验单位4个必填基础字段
        for field in _REQUIRED_UNIT_FIELDS:
            field_path = f"{path}.{field}"
            if field not in value:
                self._add_issue(
                    issues,
                    code="schema.missing_unit_field",
                    message=f"单位缺少必填字段 {field}",
                    path=field_path,
                )
                continue

            field_value = value[field]
            # dbid特殊规则：必须正整数，禁止布尔、字符串、0/负数
            if field == "dbid":
                if not _is_positive_integer(field_value):
                    self._add_issue(
                        issues,
                        code="schema.invalid_dbid",
                        message="单位 dbid 必须是正整数",
                        path=field_path,
                    )
            # id / name / type 必须是非空字符串
            elif not _is_non_blank_string(field_value):
                self._add_issue(
                    issues,
                    code="schema.invalid_unit_field",
                    message=f"单位字段 {field} 必须是非空字符串",
                    path=field_path,
                )

        # 可选 base：母舰标识，存在则必须非空字符串
        if "base" in value and not _is_non_blank_string(value["base"]):
            self._add_issue(
                issues,
                code="schema.invalid_unit_field",
                message="单位字段 base 必须是非空字符串",
                path=f"{path}.base",
            )

        # 可选 loadoutId：挂载方案ID，存在则必须正整数
        if "loadoutId" in value and not _is_positive_integer(
            value["loadoutId"]
        ):
            self._add_issue(
                issues,
                code="schema.invalid_loadout_id",
                message="单位 loadoutId 必须是正整数",
                path=f"{path}.loadoutId",
            )

        # 可选 aircraftCarried：搭载机型列表，必须字符串数组（允许空数组）
        if "aircraftCarried" in value and not _is_non_empty_string_list(
            value["aircraftCarried"],
            allow_empty=True,
        ):
            self._add_issue(
                issues,
                code="schema.invalid_unit_field",
                message="字段 aircraftCarried 必须是字符串数组",
                path=f"{path}.aircraftCarried",
            )

        # 可选 note：单位备注，存在必须为字符串
        if "note" in value and not isinstance(value["note"], str):
            self._add_issue(
                issues,
                code="schema.invalid_unit_field",
                message="字段 note 必须是字符串",
                path=f"{path}.note",
            )

        # 校验位置坐标规则（核心分支：固定坐标 / 继承母舰）
        self._validate_position(value, path, issues)
        # 校验机载武器挂载列表
        self._validate_weapon_load(value, path, issues)

    def _validate_position(
        self,
        value: Mapping[str, Any],
        path: str,
        issues: list[ValidationIssue],
    ) -> None:
        """校验单位坐标两套互斥模式：
        模式1：无base → 必须全部存在有限数字坐标
        模式2：有base → 四个坐标全部省略 / 全部为描述字符串，禁止数字+字符串混用
        """
        has_valid_base = _is_non_blank_string(value.get("base"))
        # 收集当前对象存在的位置字段
        present = [field for field in _POSITION_FIELDS if field in value]

        # 分支1：无母舰base，固定坐标模式
        if not has_valid_base:
            for field in _POSITION_FIELDS:
                field_path = f"{path}.{field}"
                # 坐标字段缺失
                if field not in value:
                    self._add_issue(
                        issues,
                        code="schema.missing_position",
                        message=f"固定部署单位缺少位置字段 {field}",
                        path=field_path,
                    )
                # 坐标不是合法有限数字
                elif not _is_finite_number(value[field]):
                    self._add_issue(
                        issues,
                        code="schema.invalid_coordinate_type",
                        message=f"位置字段 {field} 必须是有限数字",
                        path=field_path,
                    )
            return

        # 分支2：存在合法base，继承母舰坐标模式
        # 存在部分坐标、部分缺失，结构非法
        if not present:
            return
        if len(present) != len(_POSITION_FIELDS):
            self._add_issue(
                issues,
                code="schema.invalid_inherited_position",
                message=(
                    "带 base 的单位必须同时省略全部位置字段，"
                    "或同时提供四个数字/描述字段"
                ),
                path=path,
            )
            return

        values = [value[field] for field in _POSITION_FIELDS]
        # 全部数字 或 全部描述字符串 均合法
        if all(_is_finite_number(item) for item in values):
            return
        if all(_is_non_blank_string(item) for item in values):
            return

        # 数字与描述字符串混合，模式冲突
        self._add_issue(
            issues,
            code="schema.mixed_position_mode",
            message="带 base 的单位不能混用数字和描述性位置字段",
            path=path,
        )

    def _validate_weapon_load(
        self,
        value: Mapping[str, Any],
        path: str,
        issues: list[ValidationIssue],
    ) -> None:
        """校验单位武器挂载列表 weaponLoad"""
        if "weaponLoad" not in value:
            return

        weapon_load = value["weaponLoad"]
        load_path = f"{path}.weaponLoad"
        # 挂载列表必须是数组
        if not isinstance(weapon_load, list):
            self._add_issue(
                issues,
                code="schema.invalid_weapon_load",
                message="字段 weaponLoad 必须是数组",
                path=load_path,
            )
            return

        # 遍历校验每条武器挂载项
        for index, item in enumerate(weapon_load):
            item_path = f"{load_path}[{index}]"
            if not isinstance(item, Mapping):
                self._add_issue(
                    issues,
                    code="schema.invalid_weapon_load",
                    message="weaponLoad 条目必须是对象",
                    path=item_path,
                )
                continue

            # 校验武器名称、弹药数量
            self._validate_required_weapon(item, item_path, issues)
            self._validate_required_ammo_quantity(
                item,
                field="loaded",
                path=f"{item_path}.loaded",
                issues=issues,
            )
            self._validate_required_ammo_quantity(
                item,
                field="fired",
                path=f"{item_path}.fired",
                issues=issues,
            )

            # 可选武器数据库ID：存在则为正整数
            if "weaponDbid" in item and not _is_positive_integer(
                item["weaponDbid"]
            ):
                self._add_issue(
                    issues,
                    code="schema.invalid_weapon_dbid",
                    message="weaponDbid 必须是正整数",
                    path=f"{item_path}.weaponDbid",
                )

            # 可选目标列表：存在则为非空字符串数组
            if "targets" in item and not _is_non_empty_string_list(
                item["targets"]
            ):
                self._add_issue(
                    issues,
                    code="schema.invalid_targets",
                    message="targets 必须是非空字符串数组",
                    path=f"{item_path}.targets",
                )

    def _validate_strike_plan_root(
        self,
        raw: Mapping[str, Any],
        issues: list[ValidationIssue],
    ) -> None:
        """校验顶层 strikePlan 攻击计划数组根节点"""
        path = "$.strikePlan"
        # 攻击计划数组必填
        if "strikePlan" not in raw:
            self._add_issue(
                issues,
                code="schema.missing_field",
                message="缺少必填字段 strikePlan",
                path=path,
            )
            return

        strike_plan = raw["strikePlan"]
        if not isinstance(strike_plan, list):
            self._add_issue(
                issues,
                code="schema.invalid_type",
                message="字段 strikePlan 必须是数组",
                path=path,
            )
            return

        # 遍历每条攻击计划
        for index, strike in enumerate(strike_plan):
            strike_path = f"{path}[{index}]"
            if not isinstance(strike, Mapping):
                self._add_issue(
                    issues,
                    code="schema.invalid_strike",
                    message="strikePlan 条目必须是对象",
                    path=strike_path,
                )
                continue
            self._validate_strike(strike, strike_path, issues)

    def _validate_strike(
        self,
        value: Mapping[str, Any],
        path: str,
        issues: list[ValidationIssue],
    ) -> None:
        """校验单条攻击计划结构"""
        # 可选id：存在则为非空字符串
        if "id" in value and not _is_non_blank_string(value["id"]):
            self._add_issue(
                issues,
                code="schema.invalid_type",
                message="strikePlan.id 必须是非空字符串",
                path=f"{path}.id",
            )

        # shooter / shooters 互斥规则：只能二选一
        has_shooter = "shooter" in value
        has_shooters = "shooters" in value
        if has_shooter == has_shooters:
            self._add_issue(
                issues,
                code="schema.invalid_shooter_shape",
                message="shooter 和 shooters 必须且只能存在一个",
                path=path,
            )
        elif has_shooter and not _is_non_blank_string(value["shooter"]):
            self._add_issue(
                issues,
                code="schema.invalid_shooter",
                message="shooter 必须是非空字符串",
                path=f"{path}.shooter",
            )
        elif has_shooters and not _is_non_empty_string_list(
            value["shooters"]
        ):
            self._add_issue(
                issues,
                code="schema.invalid_shooters",
                message="shooters 必须是非空字符串数组",
                path=f"{path}.shooters",
            )

        # 校验武器名称、发射/装填弹药数量
        self._validate_required_weapon(value, path, issues)
        self._validate_required_ammo_quantity(
            value,
            field="loaded",
            path=f"{path}.loaded",
            issues=issues,
        )
        self._validate_required_ammo_quantity(
            value,
            field="fired",
            path=f"{path}.fired",
            issues=issues,
        )

        # targets 目标列表必填，非空字符串数组
        if "targets" not in value:
            self._add_issue(
                issues,
                code="schema.missing_field",
                message="缺少必填字段 targets",
                path=f"{path}.targets",
            )
        elif not _is_non_empty_string_list(value["targets"]):
            self._add_issue(
                issues,
                code="schema.invalid_targets",
                message="targets 必须是非空字符串数组",
                path=f"{path}.targets",
            )

        # 可选 weaponDbid、loadoutId：存在必须正整数
        if "weaponDbid" in value and not _is_positive_integer(
            value["weaponDbid"]
        ):
            self._add_issue(
                issues,
                code="schema.invalid_weapon_dbid",
                message="weaponDbid 必须是正整数",
                path=f"{path}.weaponDbid",
            )

        if "loadoutId" in value and not _is_positive_integer(
            value["loadoutId"]
        ):
            self._add_issue(
                issues,
                code="schema.invalid_loadout_id",
                message="loadoutId 必须是正整数",
                path=f"{path}.loadoutId",
            )

    def _validate_required_weapon(
        self,
        value: Mapping[str, Any],
        path: str,
        issues: list[ValidationIssue],
    ) -> None:
        """通用校验：weapon武器名称必填、非空字符串"""
        weapon_path = f"{path}.weapon"
        if "weapon" not in value:
            self._add_issue(
                issues,
                code="schema.missing_field",
                message="缺少必填字段 weapon",
                path=weapon_path,
            )
        elif not _is_non_blank_string(value["weapon"]):
            self._add_issue(
                issues,
                code="schema.invalid_weapon",
                message="weapon 必须是非空字符串",
                path=weapon_path,
            )

    def _validate_required_ammo_quantity(
        self,
        value: Mapping[str, Any],
        *,
        field: str,
        path: str,
        issues: list[ValidationIssue],
    ) -> None:
        """通用校验：弹药数量字段(loaded/fired)必填、非负整数"""
        if field not in value:
            self._add_issue(
                issues,
                code="schema.missing_field",
                message=f"缺少必填字段 {field}",
                path=path,
            )
        elif not _is_non_negative_integer(value[field]):
            self._add_issue(
                issues,
                code="schema.invalid_ammo_quantity",
                message=f"字段 {field} 必须是非负整数",
                path=path,
            )

    def _validate_optional_missile_summary(
        self,
        raw: Mapping[str, Any],
        issues: list[ValidationIssue],
    ) -> None:
        """校验可选顶层导弹汇总对象 missileSummary"""
        if "missileSummary" not in raw:
            return

        summary = raw["missileSummary"]
        path = "$.missileSummary"
        if not isinstance(summary, Mapping):
            self._add_issue(
                issues,
                code="schema.invalid_type",
                message="字段 missileSummary 必须是对象",
                path=path,
            )
            return

        # 分离武器分类条目与total汇总字段
        weapon_names = sorted(
            key
            for key in summary
            if key not in {"totalLoaded", "totalFired"}
        )
        for weapon_name in weapon_names:
            item = summary[weapon_name]
            item_path = f"{path}.{weapon_name}"
            if not isinstance(item, Mapping):
                self._add_issue(
                    issues,
                    code="schema.invalid_type",
                    message="导弹汇总条目必须是对象",
                    path=item_path,
                )
                continue
            # 单类武器装填/消耗数量校验
            self._validate_required_ammo_quantity(
                item,
                field="loaded",
                path=f"{item_path}.loaded",
                issues=issues,
            )
            self._validate_required_ammo_quantity(
                item,
                field="fired",
                path=f"{item_path}.fired",
                issues=issues,
            )

        # 全局总装填、总发射数量校验
        for field in ("totalLoaded", "totalFired"):
            if field in summary and not _is_non_negative_integer(summary[field]):
                self._add_issue(
                    issues,
                    code="schema.invalid_ammo_quantity",
                    message=f"字段 {field} 必须是非负整数",
                    path=f"{path}.{field}",
                )

    def _validate_optional_notes(
        self,
        raw: Mapping[str, Any],
        issues: list[ValidationIssue],
    ) -> None:
        """校验可选顶层备注数组 notes"""
        if "notes" not in raw:
            return

        notes = raw["notes"]
        path = "$.notes"
        if not isinstance(notes, list):
            self._add_issue(
                issues,
                code="schema.invalid_type",
                message="字段 notes 必须是字符串数组",
                path=path,
            )
            return

        # 每条备注必须是字符串
        for index, note in enumerate(notes):
            if not isinstance(note, str):
                self._add_issue(
                    issues,
                    code="schema.invalid_type",
                    message="notes 条目必须是字符串",
                    path=f"{path}[{index}]",
                )

    def _validate_required_non_blank_string(
        self,
        value: Mapping[str, Any],
        *,
        field: str,
        path: str,
        issues: list[ValidationIssue],
    ) -> None:
        """通用工具：校验必填非空字符串字段"""
        if field not in value:
            self._add_issue(
                issues,
                code="schema.missing_field",
                message=f"缺少必填字段 {field}",
                path=path,
            )
        elif not _is_non_blank_string(value[field]):
            self._add_issue(
                issues,
                code="schema.invalid_type",
                message=f"字段 {field} 必须是非空字符串",
                path=path,
            )

    @staticmethod
    def _add_issue(
        issues: list[ValidationIssue],
        *,
        code: str,
        message: str,
        path: str,
    ) -> None:
        """统一新增校验错误记录，所有Schema错误等级均为ERROR"""
        issues.append(
            ValidationIssue(
                code=code,
                message=message,
                path=path,
                severity=ValidationSeverity.ERROR,
            )
        )


# ------------------------------ 底层类型判断工具函数 ------------------------------
def _is_non_blank_string(value: Any) -> bool:
    """判断是否为去除首尾空格后非空的字符串"""
    return isinstance(value, str) and bool(value.strip())


def _is_positive_integer(value: Any) -> bool:
    """判断是否为正整数，显式排除布尔值（bool是int子类）"""
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value > 0
    )


def _is_non_negative_integer(value: Any) -> bool:
    """判断是否为非负整数（0、1、2...），排除布尔值"""
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value >= 0
    )


def _is_finite_number(value: Any) -> bool:
    """判断是否为合法有限数字（int/float，排除bool、NaN、无穷大）"""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _is_non_empty_string_list(
    value: Any,
    *,
    allow_empty: bool = False,
) -> bool:
    """判断是否为字符串数组
    :param allow_empty: True允许空列表；False要求列表至少有一项
    """
    if not isinstance(value, list):
        return False
    if not allow_empty and not value:
        return False
    # 列表内每一项都必须是非空字符串
    return all(_is_non_blank_string(item) for item in value)
