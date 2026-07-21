"""校验中间表示对象 ScenarioIR 的内部自洽性

IRValidator 只校验 IRBuilder 重构后的索引、结构自洽，不重复校验业务逻辑。
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from math import isfinite
from typing import Any

from cmo_lua_agent.contract.models import (
    ScenarioIR,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)

# 当前IR标准版本号
_IR_VERSION = "scenario-ir-v1"
# IR顶层强制必填字段
_REQUIRED_ROOT_FIELDS = (
    "irVersion",
    "scenario",
    "sides",
    "unitById",
    "strikePlan",
)
# 固定两大阵营标识
_SIDE_KEYS = ("red", "blue")
# 固定坐标四字段
_POSITION_FIELDS = ("latitude", "longitude", "heading", "speed")


class IRValidator:
    """校验IR结构完整、索引一致、格式标准化无冲突"""

    def validate(self, ir: ScenarioIR) -> ValidationResult:
        """入口主方法：执行全套IR自洽校验，一次性收集全部结构错误"""
        if not isinstance(ir, ScenarioIR):
            raise TypeError("入参ir必须是ScenarioIR实例")

        data = ir.data
        issues: list[ValidationIssue] = []

        # 检查顶层必填字段是否缺失
        missing = [field for field in _REQUIRED_ROOT_FIELDS if field not in data]
        for field in missing:
            self._add_issue(
                issues,
                code="ir.missing_field",
                message=f"IR 缺少必填字段：{field}",
                path=f"$.{field}",
            )

        # 存在顶层关键字段缺失，直接返回错误，无需继续深层校验
        if missing:
            return ValidationResult(issues=tuple(issues))

        # 校验IR版本匹配
        self._validate_version(data["irVersion"], issues)
        # 校验顶层scenario场景基础信息
        self._validate_scenario(data["scenario"], issues)

        sides = data["sides"]
        unit_by_id = data["unitById"]
        # 校验阵营unitIds与全局单位索引的映射关系，输出单位所属阵营映射表
        side_membership = self._validate_side_indexes(
            sides=sides,
            unit_by_id=unit_by_id,
            issues=issues,
        )
        # 校验全局unitById里所有单位自身数据、阵营归属标记一致性
        self._validate_units(
            unit_by_id=unit_by_id,
            side_membership=side_membership,
            issues=issues,
        )
        # 校验攻击计划shooters/targets引用合法性
        self._validate_strikes(
            strikes=data["strikePlan"],
            unit_by_id=unit_by_id,
            issues=issues,
        )

        return ValidationResult(issues=tuple(issues))

    def _validate_version(
        self,
        value: Any,
        issues: list[ValidationIssue],
    ) -> None:
        """校验IR版本号，版本不匹配直接报错"""
        if value != _IR_VERSION:
            self._add_issue(
                issues,
                code="ir.unsupported_version",
                message=f"不支持的 IR 版本：{value!r}",
                path="$.irVersion",
            )

    def _validate_scenario(
        self,
        value: Any,
        issues: list[ValidationIssue],
    ) -> None:
        """校验顶层scenario对象基础字段"""
        if not isinstance(value, Mapping):
            self._add_issue(
                issues,
                code="ir.invalid_scenario",
                message="scenario 必须是对象",
                path="$.scenario",
            )
            return

        # id、name必须存在且为非空字符串
        for field in ("id", "name"):
            if not _is_non_blank_string(value.get(field)):
                self._add_issue(
                    issues,
                    code="ir.invalid_scenario_field",
                    message=f"scenario.{field} 必须是非空字符串",
                    path=f"$.scenario.{field}",
                )

    def _validate_side_indexes(
        self,
        *,
        sides: Any,
        unit_by_id: Any,
        issues: list[ValidationIssue],
    ) -> dict[str, list[str]]:
        """校验sides阵营结构、unitIds单位ID列表，核对与全局unitById索引一致性
        返回：{单位ID: [所属阵营]} 映射表，用于后续单位归属校验
        """
        membership: dict[str, list[str]] = defaultdict(list)

        # sides顶层必须是对象
        if not isinstance(sides, Mapping):
            self._add_issue(
                issues,
                code="ir.invalid_sides",
                message="sides 必须是对象",
                path="$.sides",
            )
            return membership

        # 全局单位索引必须是对象
        if not isinstance(unit_by_id, Mapping):
            self._add_issue(
                issues,
                code="ir.invalid_unit_index",
                message="unitById 必须是对象",
                path="$.unitById",
            )
            return membership

        # 遍历红蓝阵营
        for side_key in _SIDE_KEYS:
            side_path = f"$.sides.{side_key}"
            side = sides.get(side_key)
            # 阵营不存在或不是对象
            if not isinstance(side, Mapping):
                self._add_issue(
                    issues,
                    code="ir.invalid_side",
                    message=f"缺少或无效的阵营：{side_key}",
                    path=side_path,
                )
                continue

            # 阵营内置key必须和外层red/blue标识一致
            if side.get("key") != side_key:
                self._add_issue(
                    issues,
                    code="ir.side_key_mismatch",
                    message=f"阵营 key 必须为 {side_key}",
                    path=f"{side_path}.key",
                )

            unit_ids = side.get("unitIds")
            # unitIds必须是字符串数组
            if not _is_string_sequence(unit_ids):
                self._add_issue(
                    issues,
                    code="ir.invalid_unit_ids",
                    message="unitIds 必须是字符串数组",
                    path=f"{side_path}.unitIds",
                )
                continue

            # unitCount数值必须等于unitIds数组长度
            if side.get("unitCount") != len(unit_ids):
                self._add_issue(
                    issues,
                    code="ir.unit_count_mismatch",
                    message="unitCount 与 unitIds 数量不一致",
                    path=f"{side_path}.unitCount",
                )

            seen_in_side: set[str] = set()
            for index, unit_id in enumerate(unit_ids):
                membership[unit_id].append(side_key)
                # 同一阵营unitIds内重复单位ID
                if unit_id in seen_in_side:
                    self._add_issue(
                        issues,
                        code="ir.duplicate_unit_membership",
                        message=f"单位 {unit_id} 在同一阵营重复出现",
                        path=f"{side_path}.unitIds[{index}]",
                    )
                seen_in_side.add(unit_id)

                # unitIds引用的单位ID在全局unitById不存在
                if unit_id not in unit_by_id:
                    self._add_issue(
                        issues,
                        code="ir.unknown_unit_id",
                        message=f"unitIds 引用了不存在的单位：{unit_id}",
                        path=f"{side_path}.unitIds[{index}]",
                    )

        return membership

    def _validate_units(
        self,
        *,
        unit_by_id: Any,
        side_membership: Mapping[str, list[str]],
        issues: list[ValidationIssue],
    ) -> None:
        """校验全局unitById内所有单位的自洽约束
        1. 索引key与单位内部id一致
        2. 单位只能归属单一阵营，不能无阵营/多阵营
        3. 单位sideKey标记与所属阵营匹配
        4. 坐标模式结构合规（inherit_base无坐标、固定坐标全数字）
        """
        if not isinstance(unit_by_id, Mapping):
            return

        for index_key, unit in unit_by_id.items():
            unit_path = f"$.unitById.{index_key}"
            # unitById的键必须是非空字符串
            if not isinstance(index_key, str) or not index_key:
                self._add_issue(
                    issues,
                    code="ir.invalid_unit_index_key",
                    message="unitById 的键必须是非空字符串",
                    path="$.unitById",
                )
                continue
            # 单位本体必须是对象
            if not isinstance(unit, Mapping):
                self._add_issue(
                    issues,
                    code="ir.invalid_unit",
                    message=f"单位 {index_key} 必须是对象",
                    path=unit_path,
                )
                continue

            # 索引key和单位内部id字段必须完全相同
            if unit.get("id") != index_key:
                self._add_issue(
                    issues,
                    code="ir.unit_id_mismatch",
                    message="unitById 键与单位 id 不一致",
                    path=f"{unit_path}.id",
                )

            memberships = side_membership.get(index_key, [])
            # 单位未分配到任何阵营
            if not memberships:
                self._add_issue(
                    issues,
                    code="ir.unassigned_unit",
                    message=f"单位 {index_key} 未分配到阵营",
                    path=unit_path,
                )
            # 单位同时属于红蓝多个阵营
            elif len(set(memberships)) > 1:
                self._add_issue(
                    issues,
                    code="ir.multiple_side_membership",
                    message=f"单位 {index_key} 同时属于多个阵营",
                    path=unit_path,
                )
            # 单位内置sideKey与所属阵营不匹配
            elif unit.get("sideKey") != memberships[0]:
                self._add_issue(
                    issues,
                    code="ir.unit_side_mismatch",
                    message="单位 sideKey 与 sides.unitIds 不一致",
                    path=f"{unit_path}.sideKey",
                )

            # 校验单位坐标模式合法性
            self._validate_position(unit, unit_path, issues)

    def _validate_position(
        self,
        unit: Mapping[str, Any],
        unit_path: str,
        issues: list[ValidationIssue],
    ) -> None:
        """校验单位两种坐标模式的IR规范：
        模式1：inherit_base 继承母舰坐标：必须有base，不能存在lat/lon/heading/speed
        模式2：固定部署坐标：四字段全部存在且为有限数字
        """
        if unit.get("positionMode") == "inherit_base":
            # 继承坐标模式必须携带合法base母舰ID
            if not _is_non_blank_string(unit.get("base")):
                self._add_issue(
                    issues,
                    code="ir.inherited_position_missing_base",
                    message="inherit_base 单位必须包含 base",
                    path=f"{unit_path}.base",
                )
            # 继承模式不允许残留四个坐标字段
            for field in _POSITION_FIELDS:
                if field in unit:
                    self._add_issue(
                        issues,
                        code="ir.inherited_position_has_coordinates",
                        message="inherit_base 单位不能保留固定位置字段",
                        path=f"{unit_path}.{field}",
                    )
            return

        # 固定部署模式：四个坐标字段必须齐全且为合法数字
        for field in _POSITION_FIELDS:
            if field not in unit:
                self._add_issue(
                    issues,
                    code="ir.missing_fixed_position",
                    message=f"固定部署单位缺少 {field}",
                    path=f"{unit_path}.{field}",
                )
            elif not _is_finite_number(unit[field]):
                self._add_issue(
                    issues,
                    code="ir.invalid_fixed_position",
                    message=f"固定部署单位 {field} 必须是有限数字",
                    path=f"{unit_path}.{field}",
                )

    def _validate_strikes(
        self,
        *,
        strikes: Any,
        unit_by_id: Any,
        issues: list[ValidationIssue],
    ) -> None:
        """校验strikePlan攻击计划IR规范：
        1. 禁止单数shooter，只能用shooters数组
        2. shooters、targets必须是非空字符串数组
        3. 射手、目标ID必须在全局unitById中存在
        """
        if not isinstance(strikes, list):
            self._add_issue(
                issues,
                code="ir.invalid_strike_plan",
                message="strikePlan 必须是数组",
                path="$.strikePlan",
            )
            return

        known_units = unit_by_id if isinstance(unit_by_id, Mapping) else {}
        for strike_index, strike in enumerate(strikes):
            strike_path = f"$.strikePlan[{strike_index}]"
            if not isinstance(strike, Mapping):
                self._add_issue(
                    issues,
                    code="ir.invalid_strike",
                    message="打击条目必须是对象",
                    path=strike_path,
                )
                continue

            # IR标准化后不允许残留旧格式shooter单字段
            if "shooter" in strike:
                self._add_issue(
                    issues,
                    code="ir.singular_shooter_forbidden",
                    message="IR 中禁止使用单数 shooter",
                    path=f"{strike_path}.shooter",
                )

            shooters = strike.get("shooters")
            # shooters必须是非空字符串数组
            if not _is_string_sequence(shooters) or not shooters:
                self._add_issue(
                    issues,
                    code="ir.missing_shooters",
                    message="IR 打击条目必须包含非空 shooters 数组",
                    path=f"{strike_path}.shooters",
                )
            else:
                # 校验每个射手ID存在于全局单位索引
                for index, shooter_id in enumerate(shooters):
                    if shooter_id not in known_units:
                        self._add_issue(
                            issues,
                            code="ir.unknown_shooter",
                            message=f"射手单位不存在：{shooter_id}",
                            path=f"{strike_path}.shooters[{index}]",
                        )

            targets = strike.get("targets")
            # targets必须是非空字符串数组
            if not _is_string_sequence(targets) or not targets:
                self._add_issue(
                    issues,
                    code="ir.invalid_targets",
                    message="IR 打击条目必须包含非空 targets 数组",
                    path=f"{strike_path}.targets",
                )
            else:
                # 校验每个目标ID存在于全局单位索引
                for index, target_id in enumerate(targets):
                    if target_id not in known_units:
                        self._add_issue(
                            issues,
                            code="ir.unknown_target",
                            message=f"目标单位不存在：{target_id}",
                            path=f"{strike_path}.targets[{index}]",
                        )

    @staticmethod
    def _add_issue(
        issues: list[ValidationIssue],
        *,
        code: str,
        message: str,
        path: str,
    ) -> None:
        """统一新增IR结构错误，全部为ERROR等级"""
        issues.append(
            ValidationIssue(
                code=code,
                message=message,
                path=path,
                severity=ValidationSeverity.ERROR,
            )
        )


# -------------------------- 底层类型判断工具函数 --------------------------
def _is_non_blank_string(value: Any) -> bool:
    """判断是否为去除首尾空格后非空的字符串"""
    return isinstance(value, str) and bool(value.strip())


def _is_string_sequence(value: Any) -> bool:
    """判断是否为纯非空字符串数组，排除字符串、字节串本身"""
    return (
        isinstance(value, Sequence)
        and not isinstance(value, (str, bytes, bytearray))
        and all(_is_non_blank_string(item) for item in value)
    )


def _is_finite_number(value: Any) -> bool:
    """判断是否为合法有限数字：int/float，排除布尔、NaN、无穷大"""
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and isfinite(value)
    )