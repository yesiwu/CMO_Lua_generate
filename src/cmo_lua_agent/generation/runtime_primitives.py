"""Plan primitive registry for the Phase 2 naval-air anti-surface runtime.
Phase2 海空反舰运行时的操作原语注册表，统一管理所有支持的CMO原子操作、配套参数校验器

以后有什么语法，就到这里注册
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Mapping

# 参数校验器类型：接收参数字典，非法返回错误文本，合法返回None
ParameterValidator = Callable[[Mapping[str, Any]], str | None]


@dataclass(frozen=True, slots=True)
class RuntimePrimitive:
    """单条运行时原子操作原语定义"""
    primitive_type: str        # 原语唯一标识字符串
    runtime_id: str            # 归属运行时ID
    runtime_version: str       # 归属运行时版本
    validate_parameters: ParameterValidator  # 该原语专属参数校验函数


class RuntimePrimitiveRegistry:
    """原语注册表：全局存储所有可用原语，提供查询、存在性判断能力"""
    def __init__(self, primitives: tuple[RuntimePrimitive, ...]) -> None:
        # 以primitive_type建立索引，快速查找
        self._primitives = {p.primitive_type: p for p in primitives}
        # 校验：禁止重复同名原语
        if len(self._primitives) != len(primitives):
            raise ValueError("duplicate runtime primitive")

    def get(self, primitive_type: str) -> RuntimePrimitive | None:
        # 根据原语名称查询完整原语定义，不存在返回None
        return self._primitives.get(primitive_type)

    def contains(self, primitive_type: str) -> bool:
        # 判断该原语是否在当前运行时支持列表中
        return primitive_type in self._primitives


# 当前整套海空反舰运行时唯一标识与版本
RUNTIME_ID = "cmo_naval_air_anti_surface"
RUNTIME_VERSION = "1.0.0"


def runtime_primitive_registry_for(
    runtime_id: str = RUNTIME_ID,
    runtime_version: str = RUNTIME_VERSION,
) -> RuntimePrimitiveRegistry:
    """构建默认完整原语注册表，包含全部海空反舰支持原子操作"""
    # 当前Runtime支持的所有原语清单，对应Phase2文档里supported_primitives
    primitive_names = (
        "ensure_sides",                # 创建/确认双方阵营
        "configure_side_state",        # 配置阵营态势、交战规则
        "ensure_ship",                 # 生成舰艇单位
        "ensure_aircraft",             # 生成舰载机单位
        "configure_aircraft",          # 配置飞机基础属性
        "configure_ship_inventory",    # 舰艇装填弹药
        "prepare_target_contact",      # 确保目标可被红方探测识别
        "schedule_ship_attack",       # 调度舰艇延时反舰打击
        "request_aircraft_launch",     # 指令舰载机起飞
        "wait_aircraft_airborne",     # 轮询等待飞机升空完成
        "set_aircraft_route",          # 设置飞机飞行航路
        "wait_aircraft_attack_range", # 等待进入武器射程
        "aircraft_attack",             # 舰载机发起反舰攻击
        "return_aircraft_to_base",    # 调度飞机延时返航
    )
    # 批量注册原语，无专属校验器则使用默认通用校验 _requires_id
    return RuntimePrimitiveRegistry(
        tuple(
            RuntimePrimitive(
                primitive_type=name,
                runtime_id=runtime_id,
                runtime_version=runtime_version,
                validate_parameters=_VALIDATORS.get(name, _requires_id),
            )
            for name in primitive_names
        )
    )


def default_runtime_primitive_registry() -> RuntimePrimitiveRegistry:
    """Return the preserved Phase 2 registry."""
    return runtime_primitive_registry_for()


# -------------------------- 通用校验工具函数 --------------------------
def _text(value: object) -> bool:
    # 判断是否为非空有效字符串
    return isinstance(value, str) and bool(value.strip())

def _positive_int(value: object) -> bool:
    # 判断是否为正整数（排除布尔值）
    return isinstance(value, int) and not isinstance(value, bool) and value > 0

def _non_empty_list(value: object) -> bool:
    # 判断是否为非空数组/元组
    return isinstance(value, (list, tuple)) and len(value) > 0

def _requires_id(parameters: Mapping[str, Any]) -> str | None:
    """通用兜底校验：参数里至少包含一个合法 *_id 字段"""
    if not any(_text(v) for k, v in parameters.items() if k.endswith("_id")):
        return "parameters must include at least one non-empty *_id"
    return None


# -------------------------- 各原语专属参数校验逻辑 --------------------------
def _validate_ensure_sides(parameters: Mapping[str, Any]) -> str | None:
    # 校验创建阵营参数：side_ids非空字符串数组
    side_ids = parameters.get("side_ids")
    if not _non_empty_list(side_ids) or not all(_text(i) for i in side_ids):
        return "side_ids must be a non-empty list of strings"
    return None

def _validate_ensure_ship(parameters: Mapping[str, Any]) -> str | None:
    # 校验舰艇创建参数：unit_id/side_id/name非空，dbid正整数
    for k in ("unit_id", "side_id", "name"):
        if not _text(parameters.get(k)):
            return f"{k} must be a non-empty string"
    if not _positive_int(parameters.get("dbid")):
        return "dbid must be a positive integer"
    return None

def _validate_side_state(parameters: Mapping[str, Any]) -> str | None:
    # 校验阵营交战配置：阵营列表、交战姿态、感知、武器控制状态
    side_ids = parameters.get("side_ids")
    if not _non_empty_list(side_ids) or not all(_text(i) for i in side_ids):
        return "side_ids must be a non-empty list of strings"
    for k in ("posture", "awareness", "weapon_control_status"):
        if not _text(parameters.get(k)):
            return f"{k} must be a non-empty string"
    return None

def _validate_ship_inventory(parameters: Mapping[str, Any]) -> str | None:
    # 校验舰艇弹药装填参数：unit_id合法，弹药列表内dbid均为正整数
    if not _text(parameters.get("unit_id")):
        return "unit_id must be a non-empty string"
    inventory = parameters.get("weapon_inventory")
    if not isinstance(inventory, (list, tuple)):
        return "weapon_inventory must be a list"
    for item in inventory:
        if not isinstance(item, Mapping):
            return "weapon_inventory entries must be objects"
        if not _positive_int(item.get("weapon_dbid")):
            return "weapon_inventory.weapon_dbid must be a positive integer"
    return None

def _validate_ship_attack(parameters: Mapping[str, Any]) -> str | None:
    # 校验舰艇打击调度参数：攻击ID、射手ID、目标列表、武器DBID、发射数量合法
    for k in ("attack_id", "shooter_id"):
        if not _text(parameters.get(k)):
            return f"{k} must be a non-empty string"
    if not _non_empty_list(parameters.get("target_ids")):
        return "target_ids must be non-empty"
    selection = parameters.get("weapon_selection", "explicit")
    if selection not in {"auto", "explicit"}:
        return "weapon_selection must be auto or explicit"
    if selection == "auto":
        if parameters.get("weapon_dbid") is not None:
            return "auto weapon_selection requires weapon_dbid to be null"
    elif not _positive_int(parameters.get("weapon_dbid")):
        return "explicit weapon_selection requires weapon_dbid to be a positive integer"
    if not _positive_int(parameters.get("fire_quantity")):
        return "fire_quantity must be a positive integer"
    return None


# 映射：原语名 → 专属参数校验函数，未收录原语使用通用校验器_requires_id
_VALIDATORS: dict[str, ParameterValidator] = {
    "ensure_sides": _validate_ensure_sides,
    "configure_side_state": _validate_side_state,
    "ensure_ship": _validate_ensure_ship,
    "configure_ship_inventory": _validate_ship_inventory,
    "schedule_ship_attack": _validate_ship_attack,
}
