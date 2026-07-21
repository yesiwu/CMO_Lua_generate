"""场景JSON语义校验与标准化处理模块

前置流水线回顾，分清三层分工
JsonLoader：管文件、JSON 语法，保证文件能正常解析
ScenarioSchemaValidator（结构校验器）：只看字段有没有、类型对不对，完全不管各个单位之间的关联逻辑
本段 ScenarioSemanticValidator（语义校验器）：结构校验过关后才会执行，专门处理「业务逻辑、对象互相引用、跨字段约束」，
同时统一格式化 JSON，给后面生成 Lua 脚本用。

一、数据标准化（改副本，不动原始 JSON）
统一两种写法，简化后续 Lua 生成代码的处理逻辑：
坐标统一
凡是写了base（母舰）、坐标填 “随航母” 的舰载机，自动新增positionMode:"inherit_base"，删掉 latitude/longitude 等四个冗余坐标字段，后面代码只需要判断一个标记，不用区分文字 / 数字坐标。
射手字段统一
攻击计划里如果写的是单个shooter: "red_055"，自动转成数组shooters: ["red_055"]，后续代码只需要处理数组一种格式。
输出一份规整好的normalized标准 JSON，专门给中间层、Lua 生成器使用。
二、语义逻辑校验（Schema 完全不管的业务规则，全在这里查）
一次性找出所有逻辑错误，不会查到第一个就中断，所有报错附带精准 JSON 路径。
1. 全局单位索引，查重
遍历红蓝所有舰船飞机，建立 ID 映射表：
同一个 ID 出现两次 → 报错「单位 ID 重复」
同名单位 → 报错「单位名称重复」
2. 校验所有内部 ID 引用是否合法（最核心功能）
所有通过 ID 互相绑定的地方全部校验：
base母舰：写的母舰 ID 必须真实存在，而且只能是本方阵营，不能引用敌方航母当母舰；
aircraftCarried搭载飞机：搭载的飞机 ID 必须存在，且和母舰同阵营；
武器targets打击目标、攻击计划shooters射手、targets目标：ID 必须存在。
3. 敌我规则校验（兵棋业务硬性逻辑）
不管是舰船自带武器，还是攻击计划：不能打自己人，目标和射手同一阵营直接报错；
同一条攻击计划里的射手，不能一半红方一半蓝方。
4. 弹药数量逻辑校验（跨字段对比，Schema 做不了）
任何武器 / 打击计划：发射数量fired不能大于装载数量loaded，打出去的弹药不可能比库存多；
攻击计划总弹药不能超过所有射手船上同一种武器的库存总和；
5. 导弹汇总表一致性校验
顶层missileSummary是人工统计的弹药总数，自动遍历所有攻击计划累加弹药，对比统计表：
统计表少统计某一种武器 → 报错；
单武器装填 / 发射总数对不上 → 报错；
全局总装填、总发射数值不匹配 → 报错。
明确它不做的事
不去查 CMO 数据库，不会校验 dbid 在游戏里是否真实存在；
不修改用户原始输入的ScenarioInput，所有标准化只操作深拷贝副本；
不生成 Lua 脚本，只输出规整数据给下游；
不校验坐标数值范围、武器匹配装备等更深层外部数据校验。
和前面 Schema 校验器一句话区分
Schema 校验：只看长得对不对（有没有字段、数字不能写成文字）；
Semantic 语义校验：看逻辑通不通、人物关系合不合理（ID 有没有这个人、不能自相残杀、弹药不能越打越多、统计表不能造假）。
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from cmo_lua_agent.contract.models import (
    ScenarioInput,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)

# 单位位置字段固定列表：纬度、经度、航向、航速
_POSITION_FIELDS = ("latitude", "longitude", "heading", "speed")


@dataclass(frozen=True, slots=True)
class SemanticValidationOutput:
    """语义校验输出结果容器：包含标准化数据 + 全部语义错误信息"""
    # 标准化处理后的完整场景字典
    normalized: Mapping[str, Any]
    # 收集到的所有语义校验错误集合
    validation: ValidationResult

    def __post_init__(self) -> None:
        """数据类型后置校验，防止非法实例传入"""
        if not isinstance(self.normalized, Mapping):
            raise TypeError("normalized 必须为字典/映射类型")
        if not isinstance(self.validation, ValidationResult):
            raise TypeError("validation 必须为 ValidationResult 实例")

    def to_dict(self) -> dict[str, Any]:
        """序列化为可导出字典，深拷贝避免外部篡改内部标准化数据"""
        return {
            "normalized": deepcopy(dict(self.normalized)),
            "validation": self.validation.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class _UnitRef:
    """内部私有单位引用包装类，缓存单位本体、所属阵营、JSON路径，方便全局快速查找"""
    unit: Mapping[str, Any]   # 单位原始字典数据
    side: str                 # 所属阵营 red / blue
    path: str                 # 该单位在JSON中的JSONPath路径，用于报错定位


class ScenarioSemanticValidator:
    """场景语义校验器：校验对象引用、跨字段业务逻辑，并对结构合法的输入做标准化统一"""

    def validate_and_normalize(
        self,
        scenario: ScenarioInput,
    ) -> SemanticValidationOutput:
        """入口主方法：执行标准化 + 全套语义校验，一次性返回处理结果与全部错误"""
        if not isinstance(scenario, ScenarioInput):
            raise TypeError("入参scenario必须是ScenarioInput类型实例")

        # 深拷贝原始数据，所有标准化操作仅修改副本，不改动原始输入
        normalized = deepcopy(dict(scenario.raw))
        # 统一标准化坐标模式、统一射手字段格式
        self._normalize_positions_and_shooters(normalized)

        issues: list[ValidationIssue] = []
        # 遍历全量单位，建立ID全局索引，用于快速引用查找
        units, unit_by_id = self._index_units(normalized, issues)
        # 校验所有内部单位引用合法性（母舰、搭载飞机）
        self._validate_unit_references(units, unit_by_id, issues)
        # 校验单位自身挂载武器的弹药、目标规则
        self._validate_unit_weapon_loads(units, unit_by_id, issues)
        # 校验全局攻击计划 strikePlan 的射手、目标、弹药约束
        self._validate_strike_plan(normalized, unit_by_id, issues)
        # 校验导弹汇总统计数据与攻击计划总量是否匹配
        self._validate_missile_summary(normalized, issues)

        # 封装标准化数据与错误列表返回
        return SemanticValidationOutput(
            normalized=normalized,
            validation=ValidationResult(issues=tuple(issues)),
        )

    def _normalize_positions_and_shooters(
        self,
        raw: dict[str, Any],
    ) -> None:
        """标准化逻辑1：统一单位坐标模式、标准化射手字段格式
        1. 带base母舰继承坐标的单位，统一新增positionMode标记，并删除冗余lat/lon/heading/speed字段；
        2. strikePlan 中单数shooter统一转为复数shooters数组，后续逻辑只需要处理数组格式。
        """
        sides = raw.get("sides", {})
        for side_key in ("red", "blue"):
            side = sides.get(side_key, {})
            for unit in side.get("units", []):
                if not isinstance(unit, dict):
                    continue
                base = unit.get("base")
                # 无合法母舰标识，跳过坐标标准化
                if not isinstance(base, str) or not base.strip():
                    continue

                # 提取当前单位存在的位置字段
                present_values = [
                    unit[field]
                    for field in _POSITION_FIELDS
                    if field in unit
                ]
                # 判断当前单位是否采用母舰继承坐标模式
                inherits_base = not present_values or (
                    len(present_values) == len(_POSITION_FIELDS)
                    and all(
                        isinstance(value, str) and value.strip()
                        for value in present_values
                    )
                )
                if not inherits_base:
                    continue

                # 标记坐标模式为继承母舰，并删除四个原始坐标字段
                unit["positionMode"] = "inherit_base"
                for field in _POSITION_FIELDS:
                    unit.pop(field, None)

        # 统一射手字段：shooter 单字符串 → shooters 字符串数组
        strike_plan = raw.get("strikePlan", [])
        for strike in strike_plan:
            if not isinstance(strike, dict):
                continue
            if "shooter" in strike and "shooters" not in strike:
                strike["shooters"] = [strike.pop("shooter")]

    def _index_units(
        self,
        raw: Mapping[str, Any],
        issues: list[ValidationIssue],
    ) -> tuple[list[_UnitRef], dict[str, _UnitRef]]:
        """建立全局单位索引：
        1. 遍历红蓝所有单位，生成单位对象列表；
        2. unit_by_id：单位ID映射单位实例，全局快速查询；
        3. 检测重复unit_id、重复unit_name并记录错误。
        """
        units: list[_UnitRef] = []
        unit_by_id: dict[str, _UnitRef] = {}
        first_name_path: dict[str, str] = {}

        sides = raw["sides"]
        for side_key in ("red", "blue"):
            side_units = sides[side_key]["units"]
            for index, unit in enumerate(side_units):
                path = f"$.sides.{side_key}.units[{index}]"
                ref = _UnitRef(unit=unit, side=side_key, path=path)
                units.append(ref)

                unit_id = unit["id"]
                # 检测单位ID重复
                if unit_id in unit_by_id:
                    self._add_issue(
                        issues,
                        code="semantic.duplicate_unit_id",
                        message=f"单位 ID 重复：{unit_id}",
                        path=f"{path}.id",
                    )
                else:
                    unit_by_id[unit_id] = ref

                unit_name = unit["name"]
                # 检测单位名称重复
                if unit_name in first_name_path:
                    self._add_issue(
                        issues,
                        code="semantic.duplicate_unit_name",
                        message=f"单位名称重复：{unit_name}",
                        path=f"{path}.name",
                    )
                else:
                    first_name_path[unit_name] = f"{path}.name"

        return units, unit_by_id

    def _validate_unit_references(
        self,
        units: list[_UnitRef],
        unit_by_id: Mapping[str, _UnitRef],
        issues: list[ValidationIssue],
    ) -> None:
        """校验单位内部所有跨ID引用：base母舰、aircraftCarried搭载飞机
        校验规则：
        1. 引用的母舰/飞机ID必须真实存在；
        2. 母舰、搭载飞机必须和当前单位属于同一阵营，不能跨红蓝引用。
        """
        for ref in units:
            base_id = ref.unit.get("base")
            if isinstance(base_id, str) and base_id.strip():
                base_ref = unit_by_id.get(base_id)
                # 母舰ID不存在
                if base_ref is None:
                    self._add_issue(
                        issues,
                        code="semantic.unknown_base",
                        message=f"母平台引用不存在：{base_id}",
                        path=f"{ref.path}.base",
                    )
                # 母舰不属于本方阵营
                elif base_ref.side != ref.side:
                    self._add_issue(
                        issues,
                        code="semantic.cross_side_base",
                        message=f"母平台 {base_id} 不属于同一阵营",
                        path=f"{ref.path}.base",
                    )

            # 校验搭载飞机列表
            for index, aircraft_id in enumerate(
                ref.unit.get("aircraftCarried", [])
            ):
                path = f"{ref.path}.aircraftCarried[{index}]"
                aircraft_ref = unit_by_id.get(aircraft_id)
                # 搭载飞机不存在
                if aircraft_ref is None:
                    self._add_issue(
                        issues,
                        code="semantic.unknown_aircraft",
                        message=f"搭载单位引用不存在：{aircraft_id}",
                        path=path,
                    )
                # 搭载飞机跨阵营
                elif aircraft_ref.side != ref.side:
                    self._add_issue(
                        issues,
                        code="semantic.cross_side_aircraft",
                        message=f"搭载单位 {aircraft_id} 不属于同一阵营",
                        path=path,
                    )

    def _validate_unit_weapon_loads(
        self,
        units: list[_UnitRef],
        unit_by_id: Mapping[str, _UnitRef],
        issues: list[ValidationIssue],
    ) -> None:
        """校验单个单位挂载武器列表 weaponLoad 语义规则
        1. 发射弹药不能超过装载弹药；
        2. 武器目标必须存在、不能打击友方单位。
        """
        for ref in units:
            for load_index, load in enumerate(
                ref.unit.get("weaponLoad", [])
            ):
                load_path = f"{ref.path}.weaponLoad[{load_index}]"
                # 发射量大于装载量，弹药逻辑冲突
                if load["fired"] > load["loaded"]:
                    self._add_issue(
                        issues,
                        code="semantic.ammo_exceeded",
                        message=(
                            f"发射量 {load['fired']} 超过装载量 "
                            f"{load['loaded']}"
                        ),
                        path=f"{load_path}.fired",
                    )

                # 遍历该武器所有打击目标，校验目标合法性
                for target_index, target_id in enumerate(
                    load.get("targets", [])
                ):
                    self._validate_target(
                        target_id=target_id,
                        target_path=(
                            f"{load_path}.targets[{target_index}]"
                        ),
                        attacker_side=ref.side,
                        unit_by_id=unit_by_id,
                        issues=issues,
                    )

    def _validate_strike_plan(
        self,
        raw: Mapping[str, Any],
        unit_by_id: Mapping[str, _UnitRef],
        issues: list[ValidationIssue],
    ) -> None:
        """全局攻击计划 strikePlan 完整语义校验
        规则：
        1. 射手ID必须存在；同一条打击计划射手不能同时包含红蓝双方；
        2. 打击目标必须存在，禁止攻击友方单位；
        3. 打击计划发射弹药不能超过装填数量；
        4. 打击总弹药不能超过所有射手本机同武器库存总和。
        """
        for strike_index, strike in enumerate(raw["strikePlan"]):
            path = f"$.strikePlan[{strike_index}]"
            shooters = strike["shooters"]
            valid_shooters: list[_UnitRef] = []

            # 校验每条射手ID是否存在
            for shooter_index, shooter_id in enumerate(shooters):
                shooter_path = f"{path}.shooters[{shooter_index}]"
                shooter_ref = unit_by_id.get(shooter_id)
                if shooter_ref is None:
                    self._add_issue(
                        issues,
                        code="semantic.unknown_shooter",
                        message=f"射手单位不存在：{shooter_id}",
                        path=shooter_path,
                    )
                else:
                    valid_shooters.append(shooter_ref)

            # 同一条打击计划射手跨红蓝阵营
            shooter_sides = {ref.side for ref in valid_shooters}
            if len(shooter_sides) > 1:
                self._add_issue(
                    issues,
                    code="semantic.mixed_shooter_sides",
                    message="同一打击条目的 shooters 不能跨阵营",
                    path=f"{path}.shooters",
                )

            attacker_side = (
                next(iter(shooter_sides))
                if len(shooter_sides) == 1
                else None
            )
            # 校验打击目标
            for target_index, target_id in enumerate(strike["targets"]):
                target_path = f"{path}.targets[{target_index}]"
                target_ref = unit_by_id.get(target_id)
                # 目标不存在
                if target_ref is None:
                    self._add_issue(
                        issues,
                        code="semantic.unknown_target",
                        message=f"目标单位不存在：{target_id}",
                        path=target_path,
                    )
                # 目标是友方单位
                elif (
                    attacker_side is not None
                    and target_ref.side == attacker_side
                ):
                    self._add_issue(
                        issues,
                        code="semantic.friendly_target",
                        message=f"目标 {target_id} 与射手属于同一阵营",
                        path=target_path,
                    )

            # 打击计划发射弹药超过装填量
            if strike["fired"] > strike["loaded"]:
                self._add_issue(
                    issues,
                    code="semantic.ammo_exceeded",
                    message=(
                        f"发射量 {strike['fired']} 超过装载量 "
                        f"{strike['loaded']}"
                    ),
                    path=f"{path}.fired",
                )

            # 校验打击弹药总量不能超过射手本机同武器库存总和
            self._validate_strike_inventory_capacity(
                strike=strike,
                strike_path=path,
                valid_shooters=valid_shooters,
                expected_shooter_count=len(shooters),
                issues=issues,
            )

    def _validate_strike_inventory_capacity(
        self,
        *,
        strike: Mapping[str, Any],
        strike_path: str,
        valid_shooters: list[_UnitRef],
        expected_shooter_count: int,
        issues: list[ValidationIssue],
    ) -> None:
        """校验打击计划弹药总量不超过射手本机对应武器库存
        说明：部分场景会把集团弹药统一记录在strikePlan，不写在单位weaponLoad，此时跳过库存校验，交给后续数据库校验
        """
        # 存在无效射手，不做库存校验
        if len(valid_shooters) != expected_shooter_count:
            return

        matching_inventories: list[Mapping[str, Any]] = []
        for shooter in valid_shooters:
            # 筛选射手本机和打击计划武器名称、dbid匹配的挂载武器
            matches = [
                load
                for load in shooter.unit.get("weaponLoad", [])
                if self._weapon_matches(strike, load)
            ]
            # 射手本机无对应武器挂载，放弃库存校验
            if not matches:
                return
            matching_inventories.extend(matches)

        # 所有射手本机同武器总库存
        available = sum(load["loaded"] for load in matching_inventories)
        # 打击计划装填/发射总量超过本机库存，报错
        for field in ("loaded", "fired"):
            if strike[field] > available:
                self._add_issue(
                    issues,
                    code="semantic.ammo_inventory_exceeded",
                    message=(
                        f"打击计划 {field}={strike[field]} 超过射手同武器"
                        f"显式库存 {available}"
                    ),
                    path=f"{strike_path}.{field}",
                )

    @staticmethod
    def _weapon_matches(
        strike: Mapping[str, Any],
        load: Mapping[str, Any],
    ) -> bool:
        """静态工具：判断打击计划武器和单位挂载武器是否为同一种
        匹配规则：武器名称必须一致；若双方都存在weaponDbid，则dbid也必须相等
        """
        if strike["weapon"] != load["weapon"]:
            return False
        strike_dbid = strike.get("weaponDbid")
        load_dbid = load.get("weaponDbid")
        if strike_dbid is not None and load_dbid is not None:
            return strike_dbid == load_dbid
        return True

    def _validate_target(
        self,
        *,
        target_id: str,
        target_path: str,
        attacker_side: str,
        unit_by_id: Mapping[str, _UnitRef],
        issues: list[ValidationIssue],
    ) -> None:
        """通用目标校验工具：目标ID存在性 + 禁止友方打击"""
        target_ref = unit_by_id.get(target_id)
        # 目标单位不存在
        if target_ref is None:
            self._add_issue(
                issues,
                code="semantic.unknown_target",
                message=f"目标单位不存在：{target_id}",
                path=target_path,
            )
        # 目标与攻击者同阵营
        elif target_ref.side == attacker_side:
            self._add_issue(
                issues,
                code="semantic.friendly_target",
                message=f"目标 {target_id} 与射手属于同一阵营",
                path=target_path,
            )

    def _validate_missile_summary(
        self,
        raw: Mapping[str, Any],
        issues: list[ValidationIssue],
    ) -> None:
        """校验顶层导弹汇总统计 missileSummary
        逻辑：遍历所有strikePlan累加每种武器装填、发射总量，和汇总表逐项对比，不一致则报错
        1. 汇总表不能缺失攻击计划中出现的武器；
        2. 单武器装填/发射数量必须和打击计划累加值一致；
        3. totalLoaded / totalFired 全局总数必须匹配。
        """
        summary = raw.get("missileSummary")
        if summary is None:
            return

        # 按武器累加所有打击计划的装填、发射数量
        strike_totals: dict[str, dict[str, int]] = defaultdict(
            lambda: {"loaded": 0, "fired": 0}
        )
        weapon_order: list[str] = []
        for strike in raw["strikePlan"]:
            weapon = strike["weapon"]
            if weapon not in strike_totals:
                weapon_order.append(weapon)
            strike_totals[weapon]["loaded"] += strike["loaded"]
            strike_totals[weapon]["fired"] += strike["fired"]

        # 分离汇总表内武器条目与全局total字段
        summary_weapons = [
            key
            for key in summary
            if key not in {"totalLoaded", "totalFired"}
        ]
        ordered_weapons = weapon_order + sorted(
            set(summary_weapons) - set(weapon_order)
        )

        # 逐条校验单武器统计数值
        for weapon in ordered_weapons:
            expected = strike_totals.get(
                weapon,
                {"loaded": 0, "fired": 0},
            )
            actual = summary.get(weapon)
            # 汇总表缺少该武器统计项
            if actual is None:
                self._add_issue(
                    issues,
                    code="semantic.missile_summary_mismatch",
                    message=f"missileSummary 缺少武器汇总：{weapon}",
                    path=f"$.missileSummary.{weapon}",
                )
                continue
            # 装填/发射数量与打击计划累加值不匹配
            for field in ("loaded", "fired"):
                if actual[field] != expected[field]:
                    self._add_issue(
                        issues,
                        code="semantic.missile_summary_mismatch",
                        message=(
                            f"{weapon}.{field}={actual[field]} 与 strikePlan "
                            f"汇总 {expected[field]} 不一致"
                        ),
                        path=f"$.missileSummary.{weapon}.{field}",
                    )

        # 校验全局总装填、总发射数值
        expected_total_loaded = sum(
            values["loaded"] for values in strike_totals.values()
        )
        expected_total_fired = sum(
            values["fired"] for values in strike_totals.values()
        )
        for field, expected in (
            ("totalLoaded", expected_total_loaded),
            ("totalFired", expected_total_fired),
        ):
            if field in summary and summary[field] != expected:
                self._add_issue(
                    issues,
                    code="semantic.missile_total_mismatch",
                    message=(
                        f"{field}={summary[field]} 与 strikePlan 总计 "
                        f"{expected} 不一致"
                    ),
                    path=f"$.missileSummary.{field}",
                )

    @staticmethod
    def _add_issue(
        issues: list[ValidationIssue],
        *,
        code: str,
        message: str,
        path: str,
    ) -> None:
        """统一新增语义校验错误记录，所有语义问题等级均为ERROR"""
        issues.append(
            ValidationIssue(
                code=code,
                message=message,
                path=path,
                severity=ValidationSeverity.ERROR,
            )
        )