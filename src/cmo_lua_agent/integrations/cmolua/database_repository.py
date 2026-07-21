"""
CMOLua-main/mcp/query.py 的只读封装适配层。

该仓库对外暴露面向领域的精简API，刻意不支持任意SQL语句，
也不包含场景校验、业务流程逻辑；所有内置SQL均为带参数的固定SELECT查询。

参数化武器名称查询
零命中与多命中
JSON 包装查询结果解析
武器 DBID 查询
平台 DBID 查询
Loadout 查询
飞机与 Loadout 归属校验
缺少 query.py
缺少 read_query
外部查询异常包装
禁止通用写数据库接口
"""

# __future__导入必须放在文件最顶部，规避语法报错
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import threading
from collections.abc import Mapping, Sequence
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from types import ModuleType
from typing import Any, Iterator

# 导入CMOLua集成配置类
from cmo_lua_agent.integrations.cmolua.config import CmoLuaIntegrationConfig


# 外部查询模块读取数据库路径所用的环境变量名
_SQLITE_DB_PATH_ENV = "SQLITE_DB_PATH"
# 导入外部查询脚本时使用的线程互斥锁，防止并发导入冲突
_IMPORT_LOCK = threading.RLock()

# 平台类别 -> CMO数据库真实数据表名 映射表
_PLATFORM_TABLES: dict[str, str] = {
    "aircraft": "DataAircraft",
    "ship": "DataShip",
    "submarine": "DataSubmarine",
    "facility": "DataFacility",
}

# 平台类别别名归一化映射：各类简称统一转为标准分类
_PLATFORM_CATEGORY_ALIASES: dict[str, str] = {
    "aircraft": "aircraft",
    "air": "aircraft",
    "plane": "aircraft",
    "ship": "ship",
    "carrier": "ship",
    "surface": "ship",
    "submarine": "submarine",
    "sub": "submarine",
    "facility": "facility",
    "land": "facility",
}


class CmoDatabaseInfrastructureError(RuntimeError):
    """CMOLua数据库查询能力缺失或执行异常时抛出"""


@dataclass(frozen=True, slots=True)
class CmoDatabaseRecord:
    """CMO数据库单行记录的标准化统一封装对象"""
    dbid: int               # 数据库唯一ID
    name: str               # 装备/平台/载荷名称
    category: str           # 资源分类（weapon/aircraft/ship等）
    raw: Mapping[str, Any]  # 原始数据库行字典数据


class CmoDatabaseRepository:
    """轻量化只读封装，包装CMOLua固化的数据库查询模块"""

    def __init__(self, config: CmoLuaIntegrationConfig) -> None:
        self._config = config
        # 拼接外部查询脚本绝对路径：CMOLua-main/mcp/query.py
        self._query_module_path = (
            config.skill_root / "mcp" / "query.py"
        ).resolve(strict=False)
        # 缓存加载完成的query.py模块实例，延迟加载
        self._query_module: ModuleType | None = None

    @property
    def query_module_path(self) -> Path:
        """返回当前仓库绑定的外部 query.py 文件路径"""
        return self._query_module_path

    @property
    def database_path(self) -> Path:
        """返回配置文件中定义的只读CMO数据库文件路径"""
        return self._config.database_path

    def find_weapon_exact(self, name: str) -> tuple[CmoDatabaseRecord, ...]:
        """根据武器名称精确匹配查询，返回全部匹配记录元组。

        匹配规则：大小写不敏感，不使用模糊LIKE搜索；
        保留0/1/多条匹配结果，交由上层DatabaseResolver执行业务过滤逻辑。
        """
        normalized_name = str(name).strip()
        if not normalized_name:
            return ()

        rows = self._read_query(
            """
            SELECT *
            FROM DataWeapon
            WHERE Name = ? COLLATE NOCASE
            ORDER BY ID
            """,
            (normalized_name,),
            row_limit=100,
        )
        # 将原始行数据转为标准化记录对象
        return tuple(
            self._record_from_row(row, category="weapon")
            for row in rows
        )

    def find_weapons_by_name(
        self,
        name: str,
        *,
        limit: int = 20,
    ) -> tuple[CmoDatabaseRecord, ...]:
        """Return a bounded, case-insensitive name search for user review."""
        normalized_name = str(name).strip()
        if not normalized_name:
            return ()
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValueError("weapon search limit must be a positive integer")

        rows = self._read_query(
            """
            SELECT *
            FROM DataWeapon
            WHERE Name LIKE ? COLLATE NOCASE
            ORDER BY ID
            """,
            (f"%{normalized_name}%",),
            row_limit=min(limit, 100),
        )
        return tuple(
            self._record_from_row(row, category="weapon")
            for row in rows
        )

    def get_weapon(self, dbid: int) -> CmoDatabaseRecord | None:
        """根据武器DBID查询单条武器记录，无匹配返回None"""
        rows = self._read_query(
            """
            SELECT *
            FROM DataWeapon
            WHERE ID = ?
            """,
            (_positive_int(dbid, field_name="weapon dbid"),),
            row_limit=2,
        )
        return self._single_or_none(
            rows,
            category="weapon",
            description=f"武器 DBID {dbid}",
        )

    def get_platform(
        self,
        dbid: int,
        *,
        category: str | None = None,
    ) -> CmoDatabaseRecord | None:
        """根据DBID查询平台（飞机/舰船/潜艇/设施）记录。

        未指定category时，会遍历四张平台数据表；
        若同一个DBID在多张表同时存在，视为数据库结构歧义，直接抛出异常。
        """
        platform_dbid = _positive_int(dbid, field_name="platform dbid")

        # 指定分类：仅查询对应单张数据表
        if category is not None:
            canonical_category = _normalize_platform_category(category)
            table_name = _PLATFORM_TABLES[canonical_category]
            rows = self._select_platform_rows(
                table_name=table_name,
                dbid=platform_dbid,
            )
            return self._single_or_none(
                rows,
                category=canonical_category,
                description=(
                    f"平台 DBID {platform_dbid} ({canonical_category})"
                ),
            )

        # 未指定分类：遍历全部平台表收集匹配结果
        matches: list[CmoDatabaseRecord] = []
        for canonical_category, table_name in _PLATFORM_TABLES.items():
            rows = self._select_platform_rows(
                table_name=table_name,
                dbid=platform_dbid,
            )
            matches.extend(
                self._record_from_row(
                    row,
                    category=canonical_category,
                )
                for row in rows
            )

        # 同一个ID匹配多张表，数据冲突报错
        if len(matches) > 1:
            matched_categories = ", ".join(
                record.category for record in matches
            )
            raise CmoDatabaseInfrastructureError(
                f"平台 DBID {platform_dbid} 同时命中多个平台表："
                f"{matched_categories}"
            )

        return matches[0] if matches else None

    def find_platforms_by_id(
        self,
        dbid: int,
        *,
        category: str | None = None,
    ) -> tuple[CmoDatabaseRecord, ...]:
        """Return all category candidates for a DBID without treating overlap as an error."""
        platform_dbid = _positive_int(dbid, field_name="platform dbid")
        categories = (
            (_normalize_platform_category(category),)
            if category is not None
            else tuple(_PLATFORM_TABLES)
        )
        matches: list[CmoDatabaseRecord] = []
        for canonical_category in categories:
            rows = self._select_platform_rows(
                table_name=_PLATFORM_TABLES[canonical_category],
                dbid=platform_dbid,
            )
            matches.extend(
                self._record_from_row(row, category=canonical_category)
                for row in rows
            )
        return tuple(matches)

    def get_loadout(self, loadout_id: int) -> CmoDatabaseRecord | None:
        """根据LoadoutID查询飞机挂载方案记录"""
        normalized_id = _positive_int(
            loadout_id,
            field_name="loadout id",
        )
        rows = self._read_query(
            """
            SELECT *
            FROM DataAircraftLoadouts
            WHERE ComponentID = ?
            """,
            (normalized_id,),
            row_limit=2,
        )
        # 一个 LoadoutID 可被多种飞机共用；这里仅确认该 Loadout 存在。
        # 是否属于某架飞机必须由 loadout_belongs_to_aircraft 单独校验。
        if not rows:
            return None
        return self._record_from_row(rows[0], category="loadout")

    def find_loadouts_for_aircraft(
        self,
        aircraft_dbid: int,
        *,
        limit: int = 100,
    ) -> tuple[CmoDatabaseRecord, ...]:
        """List the Loadout IDs explicitly linked to one aircraft DBID."""
        normalized_aircraft = _positive_int(
            aircraft_dbid,
            field_name="aircraft dbid",
        )
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValueError("loadout search limit must be a positive integer")
        rows = self._read_query(
            """
            SELECT *
            FROM DataAircraftLoadouts
            WHERE ID = ?
            ORDER BY ComponentID
            """,
            (normalized_aircraft,),
            row_limit=min(limit, 200),
        )
        return tuple(
            self._record_from_row(row, category="loadout")
            for row in rows
        )

    def find_loadout_weapons(
        self,
        loadout_id: int,
        *,
        limit: int = 100,
    ) -> tuple[dict[str, Any], ...]:
        """List the weapon composition of one loadout using a fixed SELECT."""
        normalized_loadout = _positive_int(
            loadout_id,
            field_name="loadout id",
        )
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValueError("loadout weapon search limit must be a positive integer")
        rows = self._read_query(
            """
            SELECT w.ID AS ID, w.Name AS Name,
                   wr.DefaultLoad AS DefaultLoad,
                   wr.MaxLoad AS MaxLoad,
                   lw.ComponentNumber AS Station
            FROM DataLoadoutWeapons AS lw
            JOIN DataWeaponRecord AS wr ON wr.ID = lw.ComponentID
            JOIN DataWeapon AS w ON w.ID = wr.ComponentID
            WHERE lw.ID = ?
            ORDER BY lw.ComponentID
            """,
            (normalized_loadout,),
            row_limit=min(limit, 200),
        )
        result: list[dict[str, Any]] = []
        for row in rows:
            record = self._record_from_row(row, category="weapon")
            result.append(
                {
                    "dbid": record.dbid,
                    "name": record.name,
                    "default_load": _case_insensitive_get(row, "DefaultLoad"),
                    "max_load": _case_insensitive_get(row, "MaxLoad"),
                    "station": _case_insensitive_get(row, "Station"),
                }
            )
        return tuple(result)

    def loadout_belongs_to_aircraft(
        self,
        *,
        aircraft_dbid: int,
        loadout_id: int,
    ) -> bool:
        """校验指定挂载方案是否归属于目标飞机，匹配返回True"""
        normalized_aircraft = _positive_int(
            aircraft_dbid,
            field_name="aircraft dbid",
        )
        normalized_loadout = _positive_int(
            loadout_id,
            field_name="loadout id",
        )
        rows = self._read_query(
            """
            SELECT ID
            FROM DataAircraftLoadouts
            WHERE ID = ?
              AND ComponentID = ?
            """,
            (normalized_aircraft, normalized_loadout),
            row_limit=1,
        )
        return bool(rows)

    def _select_platform_rows(
        self,
        *,
        table_name: str,
        dbid: int,
    ) -> list[dict[str, Any]]:
        """内部工具：查询指定平台数据表中对应DBID的原始行数据
        table_name 仅从内置白名单读取，无SQL注入风险
        """
        return self._read_query(
            f"""
            SELECT *
            FROM {table_name}
            WHERE ID = ?
            """,
            (dbid,),
            row_limit=2,
        )

    def _single_or_none(
        self,
        rows: Sequence[Mapping[str, Any]],
        *,
        category: str,
        description: str,
    ) -> CmoDatabaseRecord | None:
        """内部工具：校验查询结果只能有0或1条记录
        多条记录视为数据库异常，抛出基础设施错误
        """
        if not rows:
            return None
        if len(rows) > 1:
            raise CmoDatabaseInfrastructureError(
                f"{description} 查询返回多条记录，数据库结构或数据异常"
            )
        return self._record_from_row(rows[0], category=category)

    def _record_from_row(
        self,
        row: Mapping[str, Any],
        *,
        category: str,
    ) -> CmoDatabaseRecord:
        """内部工具：将数据库原始行字典转为标准化CmoDatabaseRecord对象"""
        raw = dict(row)
        # 大小写兼容读取ID/DBID字段
        dbid_value = (
            _case_insensitive_get(raw, "ComponentID")
            if category == "loadout"
            else _case_insensitive_get(raw, "ID", "DBID")
        )
        # 兼容Name/LongName/ShortName多名称字段
        name_value = _case_insensitive_get(
            raw,
            "Name",
            "LongName",
            "ShortName",
        )

        # 校验DBID为合法整数
        try:
            dbid = int(dbid_value)
        except (TypeError, ValueError) as exc:
            raise CmoDatabaseInfrastructureError(
                f"{category} 查询结果缺少合法 ID/DBID：{raw!r}"
            ) from exc

        # 名称字段处理：挂载方案无名称时自动生成默认名，其余分类必须存在名称
        if not isinstance(name_value, str) or not name_value.strip():
            if category == "loadout":
                name = f"Loadout {dbid}"
            else:
                raise CmoDatabaseInfrastructureError(
                    f"{category} 查询结果缺少合法 Name：{raw!r}"
                )
        else:
            name = name_value.strip()

        return CmoDatabaseRecord(
            dbid=dbid,
            name=name,
            category=category,
            raw=raw,
        )

    def _read_query(
        self,
        sql: str,
        params: Sequence[Any],
        *,
        row_limit: int,
    ) -> list[dict[str, Any]]:
        """内部统一查询入口：加载外部query模块并执行SQL查询，标准化返回行字典列表"""
        module = self._load_query_module()
        read_query = getattr(module, "read_query", None)
        if not callable(read_query):
            raise CmoDatabaseInfrastructureError(
                f"外部查询模块未提供可调用的 read_query："
                f"{self._query_module_path}"
            )

        try:
            # 临时切换环境与sys.path适配外部query.py，同时捕获标准输出/错误
            with _external_query_context(
                query_directory=self._query_module_path.parent,
                database_path=self._config.database_path,
            ):
                with redirect_stdout(io.StringIO()), redirect_stderr(
                    io.StringIO()
                ):
                    raw_result = read_query(
                        sql,
                        params=list(params),
                        row_limit=row_limit,
                    )
        except CmoDatabaseInfrastructureError:
            raise
        except Exception as exc:
            raise CmoDatabaseInfrastructureError(
                "CMOLua 数据库只读查询失败："
                f"{type(exc).__name__}: {exc}"
            ) from exc

        # 统一格式化外部脚本返回的结果为标准行字典列表
        return _normalize_query_rows(raw_result)

    def _load_query_module(self) -> ModuleType:
        """延迟加载外部 mcp/query.py 模块，加载完成后缓存复用"""
        if self._query_module is not None:
            return self._query_module

        # 校验查询脚本文件存在
        if not self._query_module_path.is_file():
            raise CmoDatabaseInfrastructureError(
                f"CMOLua mcp/query.py 不存在：{self._query_module_path}"
            )

        # 根据文件路径哈希生成唯一模块名，避免多版本query.py模块名冲突
        module_suffix = sha1(
            str(self._query_module_path).encode("utf-8")
        ).hexdigest()[:12]
        module_name = f"_cmo_lua_external_query_{module_suffix}"

        # 加锁防止多线程并发导入模块
        with _IMPORT_LOCK:
            try:
                specification = importlib.util.spec_from_file_location(
                    module_name,
                    self._query_module_path,
                )
                if specification is None or specification.loader is None:
                    raise CmoDatabaseInfrastructureError(
                        "无法为外部 query.py 创建导入规范："
                        f"{self._query_module_path}"
                    )

                module = importlib.util.module_from_spec(specification)
                # 导入时临时适配query.py所需环境变量与搜索路径
                with _external_query_context(
                    query_directory=self._query_module_path.parent,
                    database_path=self._config.database_path,
                ):
                    with redirect_stdout(io.StringIO()), redirect_stderr(
                        io.StringIO()
                    ):
                        specification.loader.exec_module(module)
            except CmoDatabaseInfrastructureError:
                raise
            except Exception as exc:
                raise CmoDatabaseInfrastructureError(
                    "无法导入 CMOLua 数据库查询模块："
                    f"{type(exc).__name__}: {exc}"
                ) from exc

        # 校验模块内必须存在read_query入口函数
        read_query = getattr(module, "read_query", None)
        if not callable(read_query):
            raise CmoDatabaseInfrastructureError(
                f"外部查询模块未提供可调用的 read_query："
                f"{self._query_module_path}"
            )

        self._query_module = module
        return module


@contextmanager
def _external_query_context(
    *,
    query_directory: Path,
    database_path: Path,
) -> Iterator[None]:
    """上下文管理器：临时配置query.py运行所需环境，执行结束自动恢复现场
    1. 写入SQLITE_DB_PATH环境变量
    2. 将mcp目录插入sys.path，适配query.py内部导入逻辑
    3. 退出时还原原始环境变量与sys.path
    """
    with _IMPORT_LOCK:
        previous_database_path = os.environ.get(_SQLITE_DB_PATH_ENV)
        original_sys_path = list(sys.path)
        os.environ[_SQLITE_DB_PATH_ENV] = str(database_path)
        sys.path.insert(0, str(query_directory))
        try:
            yield
        finally:
            # 执行完成恢复环境
            sys.path[:] = original_sys_path
            if previous_database_path is None:
                os.environ.pop(_SQLITE_DB_PATH_ENV, None)
            else:
                os.environ[_SQLITE_DB_PATH_ENV] = previous_database_path


def _normalize_query_rows(raw_result: Any) -> list[dict[str, Any]]:
    """标准化外部read_query返回的异构结果，统一转为行字典列表
    兼容：JSON字符串、带columns/rows的字典、纯列表、嵌套data字段等多种返回格式
    """
    if raw_result is None:
        return []

    # 处理返回JSON字符串的场景
    if isinstance(raw_result, str):
        text = raw_result.strip()
        if not text:
            return []
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError as exc:
            raise CmoDatabaseInfrastructureError(
                "read_query 返回了无法解析的字符串结果"
            ) from exc
        return _normalize_query_rows(decoded)

    # 处理字典类型返回值
    if isinstance(raw_result, Mapping):
        # 识别脚本返回的error错误字段
        error_value = _case_insensitive_get(raw_result, "error")
        if error_value not in (None, "", False):
            raise CmoDatabaseInfrastructureError(
                f"read_query 返回错误：{error_value}"
            )

        # 标准格式：columns字段+rows字段
        columns = _case_insensitive_get(raw_result, "columns")
        rows = _case_insensitive_get(raw_result, "rows")
        if isinstance(columns, Sequence) and not isinstance(
            columns,
            (str, bytes, bytearray),
        ) and isinstance(rows, Sequence) and not isinstance(
            rows,
            (str, bytes, bytearray),
        ):
            column_names = [str(column) for column in columns]
            normalized: list[dict[str, Any]] = []
            for row in rows:
                if isinstance(row, Mapping):
                    normalized.append(dict(row))
                elif isinstance(row, Sequence) and not isinstance(
                    row,
                    (str, bytes, bytearray),
                ):
                    # 按列名绑定索引元组为字典
                    normalized.append(dict(zip(column_names, row)))
                else:
                    raise CmoDatabaseInfrastructureError(
                        "read_query rows 中包含不支持的记录类型"
                    )
            return normalized

        # 兼容嵌套字段：data/results/items
        for key in ("rows", "data", "results", "items"):
            nested = _case_insensitive_get(raw_result, key)
            if nested is not None:
                return _normalize_query_rows(nested)

        # 单条记录字典，包装为列表返回
        return [dict(raw_result)]

    # 处理纯列表行数据
    if isinstance(raw_result, Sequence) and not isinstance(
        raw_result,
        (str, bytes, bytearray),
    ):
        normalized_rows: list[dict[str, Any]] = []
        for row in raw_result:
            if not isinstance(row, Mapping):
                raise CmoDatabaseInfrastructureError(
                    "read_query 返回的列表包含非对象记录"
                )
            normalized_rows.append(dict(row))
        return normalized_rows

    # 不支持的返回数据类型
    raise CmoDatabaseInfrastructureError(
        "read_query 返回了不支持的结果类型："
        f"{type(raw_result).__name__}"
    )


def _case_insensitive_get(
    mapping: Mapping[str, Any],
    *candidate_keys: str,
) -> Any:
    """大小写不敏感的字典取值工具，按候选键顺序匹配返回首个有效值"""
    lowered = {
        str(key).casefold(): value
        for key, value in mapping.items()
    }
    for candidate in candidate_keys:
        if candidate.casefold() in lowered:
            return lowered[candidate.casefold()]
    return None


def _positive_int(value: int, *, field_name: str) -> int:
    """校验入参为合法正整数，布尔值、负数、非数字全部抛出校验异常"""
    if isinstance(value, bool):
        raise ValueError(f"{field_name} 必须是正整数")
    try:
        converted = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} 必须是正整数") from exc
    if converted <= 0:
        raise ValueError(f"{field_name} 必须是正整数")
    return converted


def _normalize_platform_category(category: str) -> str:
    """平台类别名称归一化，简称/别名统一转为标准分类名，非法分类抛出异常"""
    normalized = str(category).strip().casefold()
    canonical = _PLATFORM_CATEGORY_ALIASES.get(normalized)
    if canonical is None:
        supported = ", ".join(sorted(_PLATFORM_TABLES))
        raise ValueError(
            f"不支持的平台类别：{category!r}；支持：{supported}"
        )
    return canonical
