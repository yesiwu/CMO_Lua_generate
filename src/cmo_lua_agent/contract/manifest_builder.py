"""基于数据库解析完成的ScenarioIR，构建专供Lua生成器使用的场景清单Manifest

JSON 文件 → JsonLoader → Schema 校验 → 语义标准化 → IRBuilder 生成 IR → IRValidator 校验 IR 结构 → DatabaseResolver 对接 CMO 数据库补全 DBID → ManifestBuilder → Lua 脚本生成
ManifestBuilder：不访问数据库，只校验数据库解析是否全部完成，重构数据结构适配 Lua，产出最终交付清单。
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

# 业务模型导入：输出清单、场景契约、中间表示、校验结果
from cmo_lua_agent.contract.models import (
    ResolvedScenarioManifest,
    ScenarioContract,
    ScenarioIR,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)

# 当前清单文件版本标识，用于版本兼容判断
_MANIFEST_VERSION = "resolved-scenario-manifest-v1"
# 固定两大阵营标识
_SIDE_KEYS = ("red", "blue")
# IR内部专用字段，输出清单时剔除，不暴露给Lua生成器
_INTERNAL_TOP_LEVEL_FIELDS = {
    "irVersion",
    "unitById",
    "manifestVersion",
}
# 流水线运行时临时字段，仅工作流内部流转，禁止带入最终场景清单
_RUNTIME_FIELDS = {
    "artifactPaths",
    "cmoOutput",
    "execution",
    "executionResult",
    "logs",
    "outputPath",
    "runId",
    "runRoot",
    "workflowResult",
    "workflowState",
}
# 标准业务顶层字段，正常保留至输出清单
_STANDARD_TOP_LEVEL_FIELDS = {
    "scenario",
    "sides",
    "strikePlan",
    "missileSummary",
    "notes",
}


@dataclass(frozen=True, slots=True)
class ManifestBuildOutput:
    """清单构建完成后完整输出容器
    manifest：供给Lua生成器的标准场景清单
    contract：全局资源契约，汇总所有单位、射手、目标ID集合
    validation：构建阶段产生的完整性校验错误
    """
    manifest: ResolvedScenarioManifest
    contract: ScenarioContract
    validation: ValidationResult


class ManifestBuilder:
    """将数据库解析完毕的IR转换为CMOLua生成器可直接消费的标准JSON清单"""

    def build(
        self,
        resolved_ir: ScenarioIR,
    ) -> ManifestBuildOutput:
        """入口主函数：完整执行清单重构、完整性校验、契约生成"""
        if not isinstance(resolved_ir, ScenarioIR):
            raise TypeError("resolved_ir 必须是经过数据库解析的ScenarioIR实例")

        # 转为字典副本，所有操作不污染原始IR对象
        source = resolved_ir.to_dict()
        issues: list[ValidationIssue] = []

        # 第一步：拦截禁止携带的流水线运行时临时字段
        self._reject_runtime_fields(source, issues)

        # 提取场景基础信息，校验场景ID合法性
        scenario = deepcopy(source.get("scenario", {}))
        scenario_id = scenario.get("id")
        if not _is_non_blank_string(scenario_id):
            issues.append(
                _error(
                    code="manifest.missing_scenario_id",
                    message="Resolved IR 缺少有效的 scenario.id",
                    path="$.scenario.id",
                )
            )
            # ID非法时填充占位符，避免后续逻辑报错
            scenario_id = "__invalid_scenario__"

        # 读取IR全局扁平化单位索引
        unit_by_id = source.get("unitById", {})
        if not isinstance(unit_by_id, Mapping):
            unit_by_id = {}
            issues.append(
                _error(
                    code="manifest.invalid_unit_index",
                    message="Resolved IR 的 unitById 必须是对象",
                    path="$.unitById",
                )
            )

        manifest_sides: dict[str, dict[str, Any]] = {}
        # 用于构建全局契约：收集所有单位ID、单位名称
        contract_unit_ids: list[str] = []
        contract_unit_names: list[str] = []
        # 全局去重集合，防止单位跨阵营重复引用
        seen_side_units: set[str] = set()

        source_sides = source.get("sides", {})
        if not isinstance(source_sides, Mapping):
            source_sides = {}

        # 重构红蓝阵营结构：把扁平化unitById还原为阵营内嵌套units数组
        for side_key in _SIDE_KEYS:
            side_source = source_sides.get(side_key, {})
            if not isinstance(side_source, Mapping):
                side_source = {}

            # 拷贝阵营基础信息，剔除IR专用冗余字段
            side_manifest = {
                key: deepcopy(value)
                for key, value in side_source.items()
                if key not in {
                    "key",
                    "unitIds",
                    "units",
                    "unitCount",
                }
            }
            units: list[dict[str, Any]] = []
            unit_ids = side_source.get("unitIds", [])
            if not isinstance(unit_ids, list):
                unit_ids = []

            # 遍历阵营内全部单位ID，从全局索引取出完整单位数据
            for unit_index, unit_id in enumerate(unit_ids):
                unit_path = (
                    f"$.sides.{side_key}.units[{unit_index}]"
                )
                unit_source = unit_by_id.get(unit_id)

                # 单位ID在全局索引不存在，引用断裂报错
                if not isinstance(unit_source, Mapping):
                    issues.append(
                        _error(
                            code="manifest.unknown_unit_reference",
                            message=(
                                f"阵营 {side_key} 引用了不存在的单位 "
                                f"{unit_id!r}"
                            ),
                            path=unit_path,
                        )
                    )
                    continue

                # 单位重复出现在多个阵营/同一阵营多次
                if unit_id in seen_side_units:
                    issues.append(
                        _error(
                            code="manifest.duplicate_side_unit",
                            message=(
                                f"单位 {unit_id!r} 被多个阵营或重复引用"
                            ),
                            path=f"{unit_path}.id",
                        )
                    )
                seen_side_units.add(unit_id)

                # 校验单位自身标记阵营与所属阵营匹配
                actual_side = unit_source.get("sideKey")
                if actual_side != side_key:
                    issues.append(
                        _error(
                            code="manifest.side_mismatch",
                            message=(
                                f"单位 {unit_id!r} 的 sideKey 为 "
                                f"{actual_side!r}，但被放入 {side_key}"
                            ),
                            path=f"{unit_path}.sideKey",
                        )
                    )

                # 深拷贝单位数据，移除IR内部标记sideKey，输出清单不需要该字段
                unit = deepcopy(dict(unit_source))
                unit.pop("sideKey", None)

                # 校验单位数据库解析完整性（必须存在数据库名称、分类）
                self._validate_resolved_unit(
                    unit,
                    path=unit_path,
                    issues=issues,
                )

                units.append(unit)

                # 收集合法单位ID、名称到契约集合（去重）
                if _is_non_blank_string(unit.get("id")):
                    contract_unit_ids.append(unit["id"].strip())
                if _is_non_blank_string(unit.get("name")):
                    contract_unit_names.append(
                        unit["name"].strip()
                    )

            # 重计算阵营单位总数，挂载完整单位数组
            side_manifest["unitCount"] = len(units)
            side_manifest["units"] = units
            manifest_sides[side_key] = side_manifest

        # 处理攻击计划数组
        strike_plan = deepcopy(source.get("strikePlan", []))
        if not isinstance(strike_plan, list):
            strike_plan = []
            issues.append(
                _error(
                    code="manifest.invalid_strike_plan",
                    message="Resolved IR 的 strikePlan 必须是数组",
                    path="$.strikePlan",
                )
            )

        # 契约全局射手、目标ID集合（自动去重）
        contract_shooters: list[str] = []
        contract_targets: list[str] = []

        for strike_index, strike in enumerate(strike_plan):
            strike_path = f"$.strikePlan[{strike_index}]"
            if not isinstance(strike, dict):
                issues.append(
                    _error(
                        code="manifest.invalid_strike",
                        message="strikePlan 条目必须是对象",
                        path=strike_path,
                    )
                )
                continue

            # 清单规范禁止残留旧格式shooter单字段，只允许shooters数组
            if "shooter" in strike:
                issues.append(
                    _error(
                        code="manifest.singular_shooter_forbidden",
                        message=(
                            "Resolved Manifest 只允许 shooters 数组"
                        ),
                        path=f"{strike_path}.shooter",
                    )
                )

            # 校验打击条目武器完整性：必须存在合法weaponDbid
            self._validate_weapon_entry(
                strike,
                path=strike_path,
                issues=issues,
            )

            # 收集所有射手ID至契约
            shooters = strike.get("shooters", [])
            if isinstance(shooters, list):
                for shooter in shooters:
                    if _is_non_blank_string(shooter):
                        _append_unique(
                            contract_shooters,
                            shooter.strip(),
                        )

            # 收集所有目标ID至契约
            targets = strike.get("targets", [])
            if isinstance(targets, list):
                for target in targets:
                    if _is_non_blank_string(target):
                        _append_unique(
                            contract_targets,
                            target.strip(),
                        )

        # 组装最终清单顶层结构
        manifest_data: dict[str, Any] = {
            "manifestVersion": _MANIFEST_VERSION,
            "scenario": scenario,
            "sides": manifest_sides,
            "strikePlan": strike_plan,
        }

        # 保留可选顶层业务字段
        for field in ("missileSummary", "notes"):
            if field in source:
                manifest_data[field] = deepcopy(source[field])

        # 保留用户自定义扩展顶层字段，剔除内部/运行时保留字段
        reserved = (
            _INTERNAL_TOP_LEVEL_FIELDS
            | _RUNTIME_FIELDS
            | _STANDARD_TOP_LEVEL_FIELDS
        )
        for field in sorted(set(source) - reserved):
            manifest_data[field] = deepcopy(source[field])

        # 生成全局场景契约，汇总全场景资源索引
        contract = ScenarioContract(
            scenario_id=scenario_id,
            unit_ids=tuple(contract_unit_ids),
            unit_names=tuple(contract_unit_names),
            shooter_ids=tuple(contract_shooters),
            target_ids=tuple(contract_targets),
        )

        # 封装清单、契约、校验错误统一返回
        return ManifestBuildOutput(
            manifest=ResolvedScenarioManifest(
                data=manifest_data
            ),
            contract=contract,
            validation=ValidationResult(
                issues=tuple(issues)
            ),
        )

    @staticmethod
    def _reject_runtime_fields(
        source: Mapping[str, Any],
        issues: list[ValidationIssue],
    ) -> None:
        """拦截流水线运行时临时字段，不允许写入最终场景清单"""
        for field in sorted(_RUNTIME_FIELDS):
            if field not in source:
                continue
            issues.append(
                _error(
                    code="manifest.runtime_field_forbidden",
                    message=(
                        f"运行时字段 {field!r} 不得进入 "
                        "ResolvedScenarioManifest"
                    ),
                    path=f"$.{field}",
                )
            )

    def _validate_resolved_unit(
        self,
        unit: dict[str, Any],
        *,
        path: str,
        issues: list[ValidationIssue],
    ) -> None:
        """校验单位数据库解析完整性
        规则：经过DatabaseResolver后必须填充databaseName、platformCategory；
        配置loadoutId的飞机必须填充loadoutDatabaseName
        """
        if not _is_non_blank_string(
            unit.get("databaseName")
        ) or not _is_non_blank_string(
            unit.get("platformCategory")
        ):
            issues.append(
                _error(
                    code="manifest.unresolved_platform",
                    message=(
                        "单位缺少数据库解析后的平台名称或类别"
                    ),
                    path=f"{path}.dbid",
                )
            )

        # 存在挂载ID，但无解析后的挂载名称，说明数据库解析未完成
        if "loadoutId" in unit and not _is_non_blank_string(
            unit.get("loadoutDatabaseName")
        ):
            issues.append(
                _error(
                    code="manifest.unresolved_loadout",
                    message=(
                        "单位配置了 loadoutId，但缺少已解析的 "
                        "Loadout 数据库名称"
                    ),
                    path=f"{path}.loadoutId",
                )
            )

        # 递归校验单位自身挂载武器列表
        weapon_load = unit.get("weaponLoad", [])
        if not isinstance(weapon_load, list):
            return

        for weapon_index, weapon_entry in enumerate(
            weapon_load
        ):
            if not isinstance(weapon_entry, dict):
                continue
            self._validate_weapon_entry(
                weapon_entry,
                path=(
                    f"{path}.weaponLoad[{weapon_index}]"
                ),
                issues=issues,
            )

    @staticmethod
    def _validate_weapon_entry(
        entry: Mapping[str, Any],
        *,
        path: str,
        issues: list[ValidationIssue],
    ) -> None:
        """校验单条武器条目完整性
        核心强制规则：数据库解析完成后，所有武器必须携带合法weaponDbid正整数
        """
        if "weaponDbid" not in entry:
            issues.append(
                _error(
                    code="manifest.missing_weapon_dbid",
                    message=(
                        "数据库解析完成后，每个武器条目都必须 "
                        "显式包含 weaponDbid"
                    ),
                    path=f"{path}.weaponDbid",
                )
            )
            return

        weapon_dbid = entry["weaponDbid"]
        # 禁止布尔、小数、零、负数，仅允许正整数
        if (
            isinstance(weapon_dbid, bool)
            or not isinstance(weapon_dbid, int)
            or weapon_dbid <= 0
        ):
            issues.append(
                _error(
                    code="manifest.invalid_weapon_dbid",
                    message="weaponDbid 必须是正整数",
                    path=f"{path}.weaponDbid",
                )
            )


def _append_unique(values: list[str], value: str) -> None:
    """工具函数：列表仅添加不存在的字符串，自动去重"""
    if value not in values:
        values.append(value)


def _is_non_blank_string(value: Any) -> bool:
    """判断是否为去除首尾空格后非空的字符串"""
    return isinstance(value, str) and bool(value.strip())


def _error(
    *,
    code: str,
    message: str,
    path: str,
) -> ValidationIssue:
    """快速构造清单构建阶段错误实例，统一ERROR等级"""
    return ValidationIssue(
        code=code,
        message=message,
        path=path,
        severity=ValidationSeverity.ERROR,
    )