"""基于校验完成的中间表示IR，解析CMO数据库真实ID信息

本解析器核心工作：
1. 校验舰船/飞机平台DBID、机载挂载方案Loadout是否存在于CMO数据库；
2. 解析所有武器条目，自动补全缺失的weaponDbid；
规则约束：仅当武器名称精确匹配且数据库只返回1条记录时，才自动填充DBID；
限制：不会修改原始输入IR实例，不使用硬编码DBID映射表兜底，全部依赖真实数据库查询。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from cmo_lua_agent.contract.models import (
    ScenarioIR,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)
# 数据库底层仓储：提供平台、挂载、武器查询能力
from cmo_lua_agent.integrations.cmolua.database_repository import (
    CmoDatabaseRecord,
    CmoDatabaseRepository,
)


@dataclass(frozen=True, slots=True)
class DatabaseResolutionOutput:
    """数据库解析完成后的输出容器
    包含：补全DBID后的IR、数据库相关校验错误、可序列化的查询统计报告
    """
    resolved_ir: ScenarioIR       # 新增数据库信息、补全武器DBID后的IR对象
    validation: ValidationResult  # 数据库层面校验产生的全部错误
    report: Mapping[str, Any]     # 完整查询日志/统计报表，用于日志、测试报告输出


class DatabaseResolver:
    """执行确定性数据库校验、自动补全武器DBID的解析器"""

    def __init__(self, repository: CmoDatabaseRepository) -> None:
        # 注入CMO数据库查询仓储，所有DB查询都通过该实例执行
        self._repository = repository

    def resolve(
        self,
        ir: ScenarioIR,
        *,
        platform_resolutions: Mapping[str, Any] | None = None,
    ) -> DatabaseResolutionOutput:
        """对外主入口：完整执行全量数据库查询、校验、字段填充"""
        if not isinstance(ir, ScenarioIR):
            raise TypeError("入参ir必须是ScenarioIR中间表示实例")

        # 深拷贝IR数据字典，所有新增字段、补全DBID仅操作副本，不污染原始IR
        data = ir.to_dict()
        issues: list[ValidationIssue] = []
        resolutions = _normalize_platform_resolutions(platform_resolutions)

        # 三类查询明细日志，用于生成最终报表
        platform_report: list[dict[str, Any]] = []    # 平台(舰船/飞机)查询记录
        loadout_report: list[dict[str, Any]] = []     # 机载挂载方案查询记录
        weapon_report: list[dict[str, Any]] = []      # 所有武器条目解析记录

        # 多层缓存：避免重复查询相同DBID，大幅减少数据库IO
        platform_cache: dict[tuple[int, str | None], CmoDatabaseRecord | None] = {}
        loadout_cache: dict[int, CmoDatabaseRecord | None] = {}         # 挂载方案ID缓存
        loadout_owner_cache: dict[tuple[int, int], bool] = {}           # (飞机DBID,挂载ID) → 是否归属本机
        weapon_id_cache: dict[int, CmoDatabaseRecord | None] = {}      # 武器DBID缓存
        exact_weapon_cache: dict[str, tuple[CmoDatabaseRecord, ...]] = {} # 标准化武器名称→精确匹配结果

        # 遍历全局所有单位
        unit_by_id = data["unitById"]
        unknown_resolution_ids = sorted(
            set(resolutions).difference(unit_by_id)
        )
        if unknown_resolution_ids:
            raise ValueError(
                "platform_resolutions 包含场景中不存在的单位："
                + ", ".join(unknown_resolution_ids)
            )
        applied_resolutions: list[dict[str, Any]] = []
        for unit_id, unit in unit_by_id.items():
            unit_path = f"$.unitById.{unit_id}"
            resolution = resolutions.get(unit_id)
            requested_category = unit.get("platformCategory")
            if resolution is not None:
                unit["dbid"] = resolution["dbid"]
                requested_category = resolution["category"]
                unit["platformCategory"] = requested_category
                applied_resolutions.append(
                    {
                        "unitId": unit_id,
                        "category": requested_category,
                        "dbid": resolution["dbid"],
                        "source": "explicit_resolution",
                    }
                )
            platform_dbid = unit["dbid"]
            # 从缓存/数据库查询平台信息
            if requested_category is None:
                candidates = self._find_platform_candidates(
                    platform_dbid,
                    cache=platform_cache,
                )
                if len(candidates) == 1:
                    platform = candidates[0]
                elif len(candidates) > 1:
                    candidate_report = [
                        {
                            "category": item.category,
                            "dbid": item.dbid,
                            "databaseName": item.name,
                        }
                        for item in candidates
                    ]
                    issues.append(
                        _error(
                            code="database.platform_resolution_required",
                            message=(
                                f"单位 {unit_id} 的平台 DBID {platform_dbid} "
                                "在多个平台类别中存在；必须由用户确认类别和 DBID"
                            ),
                            path=f"{unit_path}.dbid",
                        )
                    )
                    platform_report.append(
                        {
                            "unitId": unit_id,
                            "dbid": platform_dbid,
                            "status": "resolution_required",
                            "candidates": candidate_report,
                        }
                    )
                    # 未决歧义不再继续校验该单位的挂载关系，避免产生
                    # 与用户决策无关的次生错误。
                    continue
                else:
                    platform = None
            else:
                platform = self._get_platform(
                    platform_dbid,
                    category=requested_category,
                    cache=platform_cache,
                )

            # 平台DBID在数据库不存在，记录错误与日志
            if platform is None:
                issues.append(
                    _error(
                        code="database.platform_not_found",
                        message=(
                            f"平台 DBID {platform_dbid} 未在 CMO 数据库中找到"
                        ),
                        path=f"{unit_path}.dbid",
                    )
                )
                platform_report.append(
                    {
                        "unitId": unit_id,
                        "dbid": platform_dbid,
                        "status": "not_found",
                    }
                )
            else:
                # 数据库查询成功，写入数据库原名、平台分类到单位数据
                unit["databaseName"] = platform.name
                unit["platformCategory"] = platform.category
                platform_report.append(
                    {
                        "unitId": unit_id,
                        "dbid": platform.dbid,
                        "databaseName": platform.name,
                        "category": platform.category,
                        "status": "resolved",
                    }
                )

            # 单位存在挂载方案loadoutId，执行挂载合法性校验
            if "loadoutId" in unit:
                self._resolve_unit_loadout(
                    unit=unit,
                    unit_id=unit_id,
                    unit_path=unit_path,
                    platform=platform,
                    issues=issues,
                    report=loadout_report,
                    loadout_cache=loadout_cache,
                    owner_cache=loadout_owner_cache,
                )

            # 遍历单位自身武器挂载列表，解析每一件武器
            for index, weapon_entry in enumerate(
                unit.get("weaponLoad", [])
            ):
                self._resolve_weapon_entry(
                    entry=weapon_entry,
                    path=(
                        f"{unit_path}.weaponLoad[{index}]"
                    ),
                    issues=issues,
                    report=weapon_report,
                    weapon_id_cache=weapon_id_cache,
                    exact_weapon_cache=exact_weapon_cache,
                )

        # 遍历全局攻击计划strikePlan，解析每条打击配置里的武器
        for index, strike in enumerate(data["strikePlan"]):
            self._resolve_weapon_entry(
                entry=strike,
                path=f"$.strikePlan[{index}]",
                issues=issues,
                report=weapon_report,
                weapon_id_cache=weapon_id_cache,
                exact_weapon_cache=exact_weapon_cache,
            )

        # 封装所有数据库校验错误
        validation = ValidationResult(issues=tuple(issues))
        # 组装完整查询统计报表
        report: dict[str, Any] = {
            "platforms": platform_report,
            "platformResolutions": applied_resolutions,
            "loadouts": loadout_report,
            "weapons": weapon_report,
            "summary": {
                "platformsChecked": len(platform_report),               # 校验平台总数
                "loadoutsChecked": len(loadout_report),                # 校验挂载方案总数
                "weaponOccurrencesChecked": len(weapon_report),        # 解析武器条目总数
                "weaponNamesResolved": sum(
                    1
                    for matches in exact_weapon_cache.values()
                    if len(matches) == 1
                ),                                                     # 通过名称自动补全DBID的武器数量
                "errors": len(validation.errors),                      # 数据库层面总错误数
            },
        }

        # 封装解析完成的IR与结果返回
        return DatabaseResolutionOutput(
            resolved_ir=ScenarioIR(data=data),
            validation=validation,
            report=report,
        )

    def _resolve_unit_loadout(
        self,
        *,
        unit: dict[str, Any],
        unit_id: str,
        unit_path: str,
        platform: CmoDatabaseRecord | None,
        issues: list[ValidationIssue],
        report: list[dict[str, Any]],
        loadout_cache: dict[int, CmoDatabaseRecord | None],
        owner_cache: dict[tuple[int, int], bool],
    ) -> None:
        """校验单位机载挂载方案loadoutId合法性
        校验规则：
        1. loadoutId必须在数据库存在；
        2. 只有飞机(aircraft)类型平台才能配置挂载；
        3. 该挂载方案必须归属当前这架飞机，不能跨机型混用。
        """
        loadout_id = unit["loadoutId"]
        loadout = self._get_loadout(
            loadout_id,
            cache=loadout_cache,
        )

        # 初始化挂载查询日志条目
        report_entry: dict[str, Any] = {
            "unitId": unit_id,
            "aircraftDbid": unit["dbid"],
            "loadoutId": loadout_id,
        }

        # 挂载ID数据库不存在
        if loadout is None:
            issues.append(
                _error(
                    code="database.loadout_not_found",
                    message=(
                        f"LoadoutID {loadout_id} 未在 CMO 数据库中找到"
                    ),
                    path=f"{unit_path}.loadoutId",
                )
            )
            report_entry["status"] = "not_found"
            report.append(report_entry)
            return

        # 挂载查询成功，写入数据库挂载名称
        report_entry["databaseName"] = loadout.name
        unit["loadoutDatabaseName"] = loadout.name

        # 平台DBID本身查询失败，无法校验归属关系
        if platform is None:
            report_entry["status"] = "platform_unresolved"
            report.append(report_entry)
            return

        # 只有飞机平台允许配置loadout，舰船不能使用挂载方案
        if platform.category != "aircraft":
            issues.append(
                _error(
                    code="database.loadout_requires_aircraft",
                    message=(
                        f"单位 {unit_id} 的平台类别为 "
                        f"{platform.category}，不能配置飞机 Loadout"
                    ),
                    path=f"{unit_path}.loadoutId",
                )
            )
            report_entry["status"] = "non_aircraft_platform"
            report.append(report_entry)
            return

        # 缓存查询：(飞机DBID,挂载ID) 是否为本机可用挂载
        owner_key = (unit["dbid"], loadout_id)
        if owner_key not in owner_cache:
            owner_cache[owner_key] = (
                self._repository.loadout_belongs_to_aircraft(
                    aircraft_dbid=unit["dbid"],
                    loadout_id=loadout_id,
                )
            )

        # 挂载不属于当前飞机，机型不匹配报错
        if not owner_cache[owner_key]:
            issues.append(
                _error(
                    code="database.loadout_mismatch",
                    message=(
                        f"LoadoutID {loadout_id} 不属于飞机 DBID "
                        f"{unit['dbid']}"
                    ),
                    path=f"{unit_path}.loadoutId",
                )
            )
            report_entry["status"] = "mismatch"
            report.append(report_entry)
            return

        # 全部校验通过
        report_entry["status"] = "resolved"
        report.append(report_entry)

    def _resolve_weapon_entry(
        self,
        *,
        entry: dict[str, Any],
        path: str,
        issues: list[ValidationIssue],
        report: list[dict[str, Any]],
        weapon_id_cache: dict[int, CmoDatabaseRecord | None],
        exact_weapon_cache: dict[str, tuple[CmoDatabaseRecord, ...]],
    ) -> None:
        """解析单条武器配置（单位weaponLoad、strikePlan通用）
        两种分支逻辑：
        1. 配置中已有weaponDbid：校验DBID存在、名称与数据库匹配；
        2. 无weaponDbid：按武器名称精确查询，唯一匹配则自动填充weaponDbid。
        """
        weapon_name = entry["weapon"].strip()
        report_entry: dict[str, Any] = {
            "path": path,
            "weapon": weapon_name,
        }

        # 分支1：用户手动填写了weaponDbid
        if "weaponDbid" in entry:
            weapon_dbid = entry["weaponDbid"]
            # 缓存查询武器DBID
            if weapon_dbid not in weapon_id_cache:
                weapon_id_cache[weapon_dbid] = (
                    self._repository.get_weapon(weapon_dbid)
                )
            record = weapon_id_cache[weapon_dbid]

            report_entry["weaponDbid"] = weapon_dbid
            report_entry["resolutionSource"] = "explicit_dbid"

            # DBID在数据库不存在
            if record is None:
                issues.append(
                    _error(
                        code="database.weapon_not_found",
                        message=(
                            f"武器 DBID {weapon_dbid} 未在 CMO 数据库中找到"
                        ),
                        path=f"{path}.weaponDbid",
                    )
                )
                report_entry["status"] = "not_found"
                report.append(report_entry)
                return

            # 写入解析来源、数据库标准武器名
            entry["resolutionSource"] = "explicit_dbid"
            entry["databaseName"] = record.name
            report_entry["databaseName"] = record.name

            # 武器名称与DBID对应的数据库标准名不一致，名称冲突报错
            if _normalize_name(record.name) != _normalize_name(weapon_name):
                issues.append(
                    _error(
                        code="database.weapon_name_mismatch",
                        message=(
                            f"武器名称 {weapon_name!r} 与 DBID {weapon_dbid} "
                            f"对应的数据库名称 {record.name!r} 不一致"
                        ),
                        path=f"{path}.weapon",
                    )
                )
                report_entry["status"] = "name_mismatch"
            else:
                report_entry["status"] = "resolved"

            report.append(report_entry)
            return

        # 分支2：未填写weaponDbid，通过武器名称精确匹配查询
        cache_key = _normalize_name(weapon_name)
        if cache_key not in exact_weapon_cache:
            exact_weapon_cache[cache_key] = tuple(
                self._repository.find_weapon_exact(weapon_name)
            )
        matches = exact_weapon_cache[cache_key]
        report_entry["resolutionSource"] = "database_exact_name"

        # 数据库无匹配武器
        if not matches:
            issues.append(
                _error(
                    code="database.weapon_not_found",
                    message=(
                        f"武器名称 {weapon_name!r} 没有精确数据库匹配"
                    ),
                    path=f"{path}.weapon",
                )
            )
            report_entry["status"] = "not_found"
            report.append(report_entry)
            return

        # 名称匹配到多条武器，无法自动填充DBID，歧义报错
        if len(matches) > 1:
            issues.append(
                _error(
                    code="database.weapon_ambiguous",
                    message=(
                        f"武器名称 {weapon_name!r} 精确命中多个 DBID："
                        + ", ".join(str(item.dbid) for item in matches)
                    ),
                    path=f"{path}.weapon",
                )
            )
            report_entry["candidateDbids"] = [
                item.dbid for item in matches
            ]
            report_entry["status"] = "ambiguous"
            report.append(report_entry)
            return

        # 精确匹配唯一一条武器，自动补全weaponDbid
        record = matches[0]
        entry["weaponDbid"] = record.dbid
        entry["resolutionSource"] = "database_exact_name"
        entry["databaseName"] = record.name
        report_entry.update(
            {
                "weaponDbid": record.dbid,
                "databaseName": record.name,
                "status": "resolved",
            }
        )
        report.append(report_entry)

    def _get_platform(
        self,
        dbid: int,
        *,
        category: str | None,
        cache: dict[tuple[int, str | None], CmoDatabaseRecord | None],
    ) -> CmoDatabaseRecord | None:
        """缓存工具：查询平台DBID，命中缓存直接返回，减少数据库查询"""
        cache_key = (dbid, category)
        if cache_key not in cache:
            cache[cache_key] = self._repository.get_platform(
                dbid,
                category=category,
            )
        return cache[cache_key]

    def _find_platform_candidates(
        self,
        dbid: int,
        *,
        cache: dict[tuple[int, str | None], CmoDatabaseRecord | None],
    ) -> tuple[CmoDatabaseRecord, ...]:
        """Query every supported platform table without relying on DBID uniqueness."""
        candidates: dict[tuple[str, int], CmoDatabaseRecord] = {}
        for category in ("aircraft", "ship", "submarine", "facility"):
            record = self._get_platform(
                dbid,
                category=category,
                cache=cache,
            )
            if record is not None:
                candidates[(record.category, record.dbid)] = record
        return tuple(
            candidates[key]
            for key in sorted(candidates)
        )

    def _get_loadout(
        self,
        loadout_id: int,
        *,
        cache: dict[int, CmoDatabaseRecord | None],
    ) -> CmoDatabaseRecord | None:
        """缓存工具：查询挂载方案DBID，复用缓存"""
        if loadout_id not in cache:
            cache[loadout_id] = self._repository.get_loadout(loadout_id)
        return cache[loadout_id]


def _normalize_name(value: str) -> str:
    """标准化武器/平台名称：去除首尾空格、全部小写，用于模糊匹配对比"""
    return value.strip().casefold()


def _normalize_platform_resolutions(
    raw: Mapping[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """Validate user-approved platform selections before querying the database."""
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise ValueError("platform_resolutions 必须是以单位 ID 为键的对象")

    allowed_categories = {"aircraft", "ship", "submarine", "facility"}
    result: dict[str, dict[str, Any]] = {}
    for unit_id, value in raw.items():
        if not isinstance(unit_id, str) or not unit_id.strip():
            raise ValueError("platform_resolutions 的单位 ID 必须是非空字符串")
        if not isinstance(value, Mapping):
            raise ValueError(f"单位 {unit_id} 的平台决策必须是对象")
        category = value.get("category")
        dbid = value.get("dbid")
        if category not in allowed_categories:
            raise ValueError(f"单位 {unit_id} 的 category 不受支持：{category!r}")
        if isinstance(dbid, bool) or not isinstance(dbid, int) or dbid <= 0:
            raise ValueError(f"单位 {unit_id} 的 dbid 必须是正整数")
        result[unit_id.strip()] = {"category": category, "dbid": dbid}
    return result


def _error(*, code: str, message: str, path: str) -> ValidationIssue:
    """快速构造数据库校验错误实例，统一ERROR等级"""
    return ValidationIssue(
        code=code,
        message=message,
        path=path,
        severity=ValidationSeverity.ERROR,
    )
