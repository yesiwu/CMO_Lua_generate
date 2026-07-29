"""Immutable Phase 2 contracts for deterministic CMO Lua rendering.
Phase2 不可变数据契约模型，保障Lua生成过程完全确定性，提供标准化序列化、哈希校验、强校验数据结构
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping, TypeAlias

# JSON基础类型别名
JsonScalar: TypeAlias = str | int | float | bool | None
# 不可变JSON结构别名：标量/元组(数组)/只读字典
FrozenJson: TypeAlias = JsonScalar | tuple["FrozenJson", ...] | Mapping[str, "FrozenJson"]


def canonical_json(value: Any) -> str:
    """将可JSON化数据序列化为稳定、固定格式字符串，用于保证确定性哈希"""
    return json.dumps(
        _to_json_value(value),
        ensure_ascii=False,
        sort_keys=True,        # 字典按键排序，消除遍历顺序差异
        separators=(",", ":"), # 无多余空格，固定输出格式
        allow_nan=False,       # 禁止非法浮点数
    )


def canonical_sha256(value: Any) -> str:
    """计算标准化JSON的sha256哈希，用于全链路数据指纹比对、复现校验"""
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _freeze_json(value: Any) -> FrozenJson:
    """冻结任意数据为不可变JSON结构，防止外部修改破坏哈希一致性"""
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("parameters must not contain non-finite floats")
        return value
    # 字典转为只读MappingProxyType，键排序
    if isinstance(value, Mapping):
        frozen: dict[str, FrozenJson] = {}
        for key in sorted(value):
            if not isinstance(key, str):
                raise TypeError("parameters must use string keys")
            frozen[key] = _freeze_json(value[key])
        return MappingProxyType(frozen)
    # 列表转为元组（不可变）
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    raise TypeError(f"parameters contain unsupported value: {type(value).__name__}")


def _to_json_value(value: Any) -> Any:
    """通用转换：自定义模型调用to_dict()，统一转为标准dict/list用于序列化"""
    if isinstance(value, Mapping):
        return {str(key): _to_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    # 支持所有带to_dict方法的契约模型
    if hasattr(value, "to_dict"):
        return _to_json_value(value.to_dict())
    raise TypeError(f"value is not JSON-compatible: {type(value).__name__}")


def _required_text(value: str, field_name: str) -> str:
    """通用非空字符串校验工具，字段必填且不能全空白"""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


# -----------------------------------------------------------------------------
# ExecutionPlan 最小执行单元：单步操作原语（上层 StrategySpec 是用户 / LLM 描述想要达成的战术，编译器会把战术拆解成一串有序原语，构成 ExecutionPlan；LuaRenderer 再把每一条原语翻译成固定 CMO Lua 代码）
# 对应phase2文档ExecutionPlan单条operation结构
# -----------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Operation:
    operation_id: str               # 操作唯一ID
    primitive_type: str             # 运行时原语类型（resolve_unit/schedule_surface_attack等）
    parameters: Mapping[str, FrozenJson] # 原语入参（只读冻结结构）
    depends_on: tuple[str, ...]     # 前置依赖operation_id列表
    source_strategy_path: str | None# 溯源：对应StrategySpec的JSON指针路径

    def __post_init__(self) -> None:
        # 基础字符串校验
        object.__setattr__(self, "operation_id", _required_text(self.operation_id, "operation_id"))
        object.__setattr__(self, "primitive_type", _required_text(self.primitive_type, "primitive_type"))
        # 参数强制冻结为只读字典
        if not isinstance(self.parameters, Mapping):
            raise TypeError("parameters must be a mapping")
        frozen = _freeze_json(self.parameters)
        if not isinstance(frozen, Mapping):
            raise TypeError("parameters must freeze to a mapping")
        object.__setattr__(self, "parameters", frozen)
        # 依赖去重+非空校验
        dependencies = tuple(_required_text(item, "depends_on") for item in self.depends_on)
        if len(set(dependencies)) != len(dependencies):
            raise ValueError("depends_on must not contain duplicates")
        object.__setattr__(self, "depends_on", dependencies)
        # 溯源路径必须是标准JSON Pointer（以/开头）
        if self.source_strategy_path is not None:
            source_path = _required_text(self.source_strategy_path, "source_strategy_path")
            if not source_path.startswith("/"):
                raise ValueError("source_strategy_path must be a JSON Pointer")
            object.__setattr__(self, "source_strategy_path", source_path)

    def to_dict(self) -> dict[str, Any]:
        """序列化为标准字典用于落盘/哈希计算"""
        return {
            "operation_id": self.operation_id,
            "primitive_type": self.primitive_type,
            "parameters": _to_json_value(self.parameters),
            "depends_on": list(self.depends_on),
            "source_strategy_path": self.source_strategy_path,
        }


# -----------------------------------------------------------------------------
# 运行时能力配置包：LuaRuntimeProfile
# 对应phase2文档LuaRuntimeProfile，定义整套CMO执行参数与版本
# -----------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class LuaRuntimeProfile:
    runtime_id: str                 # 运行时唯一标识
    runtime_version: str            # 运行时版本号（用于版本隔离、可复现）
    ship_settle_seconds: int = 30  # 舰艇探测沉降延时
    launch_poll_seconds: int = 15   # 飞机起飞轮询间隔
    attack_poll_seconds: int = 60   # 打击距离轮询间隔
    max_launch_attempts: int = 24   # 最大起飞重试次数
    max_attack_attempts: int = 35   # 最大攻击重试次数
    execution_telemetry_enabled: bool = False

    def __post_init__(self) -> None:
        # ID/版本非空校验
        object.__setattr__(self, "runtime_id", _required_text(self.runtime_id, "runtime_id"))
        object.__setattr__(self, "runtime_version", _required_text(self.runtime_version, "runtime_version"))
        # 所有时间/计数字段必须正整数
        for field_name in (
            "ship_settle_seconds",
            "launch_poll_seconds",
            "attack_poll_seconds",
            "max_launch_attempts",
            "max_attack_attempts",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{field_name} must be a positive integer")
        if not isinstance(self.execution_telemetry_enabled, bool):
            raise TypeError("execution_telemetry_enabled must be a bool")

    def event_name(
        self,
        *,
        scenario_id: str,
        operation_id: str,
        phase: str,
        attempt: int,
    ) -> str:
        """生成稳定、无随机的CMO事件名称，保证确定性，避免随机字符串导致Lua差异"""
        identity = "|".join(
            (
                _required_text(scenario_id, "scenario_id"),
                self.runtime_id,
                self.runtime_version,
                _required_text(operation_id, "operation_id"),
            )
        )
        if not isinstance(attempt, int) or attempt < 0:
            raise ValueError("attempt must be a non-negative integer")
        # 哈希截断16位+阶段+重试次数
        return "evt_" + sha256(identity.encode("utf-8")).hexdigest()[:16] + f"_{_required_text(phase, 'phase')}_{attempt:02d}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime_id": self.runtime_id,
            "runtime_version": self.runtime_version,
            "ship_settle_seconds": self.ship_settle_seconds,
            "launch_poll_seconds": self.launch_poll_seconds,
            "attack_poll_seconds": self.attack_poll_seconds,
            "max_launch_attempts": self.max_launch_attempts,
            "max_attack_attempts": self.max_attack_attempts,
            "execution_telemetry_enabled": self.execution_telemetry_enabled,
        }


# -----------------------------------------------------------------------------
# 完整执行计划：ExecutionPlan
# StrategySpec编译后的分镜总方案，对应文档execution_plan.json
# -----------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    plan_schema_version: str        # 执行计划数据结构版本
    compiler_version: str           # 生成该计划的编译器版本
    scenario_id: str                # 绑定场景ID
    runtime_id: str                 # 绑定运行时ID
    runtime_version: str            # 绑定运行时版本
    operations: tuple[Operation, ...] # 全部执行步骤列表

    def __post_init__(self) -> None:
        # 顶层字符串字段校验
        for field_name in (
            "plan_schema_version",
            "compiler_version",
            "scenario_id",
            "runtime_id",
            "runtime_version",
        ):
            object.__setattr__(self, field_name, _required_text(getattr(self, field_name), field_name))
        # 步骤非空、类型校验、operation_id全局唯一
        operations = tuple(self.operations)
        if not operations or not all(isinstance(item, Operation) for item in operations):
            raise ValueError("operations must contain at least one Operation")
        if len({item.operation_id for item in operations}) != len(operations):
            raise ValueError("operations must use unique operation_id values")
        object.__setattr__(self, "operations", operations)

    @property
    def checksum(self) -> str:
        """执行计划全局哈希指纹，用于比对变更、回归测试"""
        return canonical_sha256(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_schema_version": self.plan_schema_version,
            "compiler_version": self.compiler_version,
            "scenario_id": self.scenario_id,
            "runtime_id": self.runtime_id,
            "runtime_version": self.runtime_version,
            "operations": [item.to_dict() for item in self.operations],
        }


# -----------------------------------------------------------------------------
# 能力缺口模型 CapabilityGap
# 对应phase2文档CapabilityGap：当前Runtime不支持该战法动作
# -----------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class CapabilityGap:
    capability: str                 # 缺失的能力名称
    source_strategy_path: str | None# 对应策略字段指针
    reason: str                     # 缺失原因描述
    supported_runtime_version: str  # 支持该能力的运行时版本

    def __post_init__(self) -> None:
        object.__setattr__(self, "capability", _required_text(self.capability, "capability"))
        object.__setattr__(self, "reason", _required_text(self.reason, "reason"))
        object.__setattr__(self, "supported_runtime_version", _required_text(self.supported_runtime_version, "supported_runtime_version"))
        if self.source_strategy_path is not None and not self.source_strategy_path.startswith("/"):
            raise ValueError("source_strategy_path must be a JSON Pointer")

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "source_strategy_path": self.source_strategy_path,
            "reason": self.reason,
            "supported_runtime_version": self.supported_runtime_version,
        }


# -----------------------------------------------------------------------------
# 黄金基线完整溯源清单 GoldenManifest
# 记录整套基线生成全链路信息，用于审计、复现、测试
# -----------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class GoldenManifest:
    scenario_id: str
    scenario_definition_source: str # 场景定义文件路径
    baseline_strategy_source: str   # 基线策略文件路径
    source_lua: str                 # 原始人工验证Lua路径
    cmo_version: str                # 适配CMO软件版本
    database_version: str           # CMO武器数据库版本
    runtime_id: str
    runtime_version: str
    successful_run_id: str          # 成功仿真运行ID
    input_checksums: Mapping[str, str] # 所有输入文件sha256哈希

    def __post_init__(self) -> None:
        # 文本字段非空校验
        for field_name in (
            "scenario_id",
            "scenario_definition_source",
            "baseline_strategy_source",
            "source_lua",
            "cmo_version",
            "database_version",
            "runtime_id",
            "runtime_version",
        ):
            object.__setattr__(self, field_name, _required_text(getattr(self, field_name), field_name))
        # 输入哈希校验：必须包含指定key，且值为64位sha256字符串
        checksums = dict(self.input_checksums)
        required = {"scenario_definition", "baseline_strategy", "source_lua"}
        if required - set(checksums) or any(not isinstance(value, str) or len(value) != 64 for value in checksums.values()):
            raise ValueError("input_checksums must include a SHA-256 checksum for every Golden input")
        object.__setattr__(self, "input_checksums", MappingProxyType(dict(sorted(checksums.items()))))

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "scenario_definition_source": self.scenario_definition_source,
            "baseline_strategy_source": self.baseline_strategy_source,
            "source_lua": self.source_lua,
            "cmo_version": self.cmo_version,
            "database_version": self.database_version,
            "runtime_id": self.runtime_id,
            "runtime_version": self.runtime_version,
            "successful_run_id": self.successful_run_id,
            "input_checksums": dict(self.input_checksums),
        }


# -----------------------------------------------------------------------------
# Lua源码映射区间：记录哪段Lua代码对应哪个Operation
# 用于报错溯源，定位Lua行号对应原始策略字段
# -----------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class LuaSourceSpan:
    start_line: int # 起始行号
    end_line: int   # 结束行号

    def __post_init__(self) -> None:
        if self.start_line <= 0 or self.end_line < self.start_line:
            raise ValueError("source span lines must be positive and ordered")

    def to_dict(self) -> dict[str, int]:
        return {"start_line": self.start_line, "end_line": self.end_line}


# -----------------------------------------------------------------------------
# 渲染完成的Lua产物模型 RenderedLua
# 存储最终生成脚本、元数据、源码映射表
# -----------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class RenderedLua:
    content: str                         # 完整Lua文本
    metadata: Mapping[str, Any]          # 生成元数据（版本、ID等）
    source_map: Mapping[str, LuaSourceSpan] # operation_id -> 代码行区间映射

    def __post_init__(self) -> None:
        object.__setattr__(self, "content", _required_text(self.content, "content"))
        # 元数据冻结只读
        frozen_metadata = _freeze_json(self.metadata)
        if not isinstance(frozen_metadata, Mapping):
            raise TypeError("metadata must freeze to a mapping")
        object.__setattr__(self, "metadata", frozen_metadata)
        # 源码映射校验，转为有序只读字典
        source_map = dict(self.source_map)
        if not all(isinstance(value, LuaSourceSpan) for value in source_map.values()):
            raise TypeError("source_map values must be LuaSourceSpan")
        object.__setattr__(self, "source_map", MappingProxyType(dict(sorted(source_map.items()))))

    @property
    def lua_checksum(self) -> str:
        """Lua脚本哈希指纹"""
        return sha256(self.content.encode("utf-8")).hexdigest()

    def to_manifest_dict(self) -> dict[str, Any]:
        """输出用于生成manifest清单的字典"""
        return {
            **_to_json_value(self.metadata),
            "lua_checksum": self.lua_checksum,
            "source_map": {
                operation_id: span.to_dict()
                for operation_id, span in self.source_map.items()
            },
        }
