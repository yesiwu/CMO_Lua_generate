"""工作流产出物专用确定性序列化工具

序列化逻辑与文件持久化逻辑完全分离：
本模块只负责把业务模型、普通Python对象转换成稳定文本字符串；
后续文件存储层只负责把文本写入磁盘，不关心序列化规则。
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, TypeAlias

# JSON基础标量类型
JsonScalar: TypeAlias = None | bool | int | float | str
# 完整JSON合法值类型（递归定义）
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


class ArtifactSerializationError(ValueError):
    """对象无法转换为确定性JSON产出物时抛出异常"""


def serialize_json(value: Any) -> str:
    """生成稳定、UTF8友好、格式化JSON字符串，末尾固定带一个换行

    业务领域模型优先调用自身to_dict()方法序列化；
    自动递归转换路径、枚举、元组、字典、列表、普通数据类；
    不支持/无法保证确定性的类型会携带数据路径精准报错，
    不会使用默认兜底str()粗暴序列化，避免产出不可控脏数据。
    """
    # 先把任意对象转为纯JSON兼容树
    compatible = to_json_compatible(value)
    try:
        # 固定格式化规则：不转义中文、2空格缩进、key强制排序、禁止NaN/无穷浮点数
        return json.dumps(
            compatible,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ) + "\n"
    except (TypeError, ValueError) as exc:
        # 兜底捕获底层json编码异常，包装为业务序列化错误
        raise ArtifactSerializationError(
            f"$ 根节点无法编码为JSON: {exc}"
        ) from exc


def serialize_text(text: str) -> str:
    """标准化纯文本：统一换行符为LF(\n)，其余内容原样保留"""
    if not isinstance(text, str):
        raise TypeError("text 必须是字符串类型")
    # Windows换行 \r\n、Mac旧换行 \r 全部统一替换为标准LF换行
    return text.replace("\r\n", "\n").replace("\r", "\n")


def to_json_compatible(value: Any) -> JsonValue:
    """入口转换函数：将任意输入转为仅含dict/list/JSON标量的纯净树结构

    直接拒绝循环引用、集合Set、非字符串字典键、无穷浮点数、未知自定义对象；
    以上类型会破坏产出物确定性，导致多次运行文件内容不一致。
    """
    # active 存放当前递归栈内对象id，用于检测循环引用；path 记录当前节点路径用于报错
    return _convert(value, path="$", active=set())


def _convert(
    value: Any,
    *,
    path: str,
    active: set[int],
) -> JsonValue:
    """递归核心转换分发器，按类型分支处理"""
    # 枚举：取枚举底层value值序列化
    if isinstance(value, Enum):
        return _convert(value.value, path=path, active=active)

    # JSON原生标量：None/布尔/字符串/整数，直接返回无需处理
    if value is None or isinstance(value, (bool, str, int)):
        return value

    # 浮点数：禁止NaN、Inf、-Inf等非有限值
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ArtifactSerializationError(
                f"{path}: float values must be finite；不支持 NaN/无穷大"
            )
        return value

    # Path路径对象：转为绝对路径字符串
    if isinstance(value, Path):
        return str(value)

    # 集合set/frozenset：无序，多次序列化输出顺序不一致，直接禁止
    if isinstance(value, (set, frozenset)):
        raise ArtifactSerializationError(
            f"{path}: set values are not supported；元素无序会导致输出非确定性"
        )

    # 对象存在to_dict()方法（业务标准模型契约），走专用对象转换逻辑
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _convert_object_contract(
            value,
            to_dict=to_dict,
            path=path,
            active=active,
        )

    # 原生dataclass数据类，自动遍历字段转换
    if is_dataclass(value) and not isinstance(value, type):
        return _convert_dataclass(value, path=path, active=active)

    # 字典/映射类型，要求所有key必须是字符串
    if isinstance(value, Mapping):
        return _convert_mapping(value, path=path, active=active)

    # 列表/元组序列，转为标准list（元组有序可序列化）
    if isinstance(value, (list, tuple)):
        return _convert_sequence(value, path=path, active=active)

    # 所有未匹配类型均为不支持
    raise ArtifactSerializationError(
        f"{path}: 不支持的序列化类型 {type(value).__name__}"
    )


def _convert_object_contract(
    value: Any,
    *,
    to_dict: Any,
    path: str,
    active: set[int],
) -> JsonValue:
    """处理实现to_dict()契约的业务模型，防止循环引用"""
    # 标记对象入递归栈，检测循环依赖
    object_id = _enter(value, path=path, active=active)
    try:
        # 调用模型自身序列化方法
        try:
            detached = to_dict()
        except Exception as exc:
            raise ArtifactSerializationError(
                f"{path}: 调用to_dict()序列化失败: {exc}"
            ) from exc
        # 递归转换to_dict产出的字典树
        return _convert(detached, path=path, active=active)
    finally:
        # 递归出栈，移除对象标记
        active.remove(object_id)


def _convert_dataclass(
    value: Any,
    *,
    path: str,
    active: set[int],
) -> dict[str, JsonValue]:
    """自动序列化标准dataclass，遍历所有字段递归转换"""
    object_id = _enter(value, path=path, active=active)
    try:
        return {
            field.name: _convert(
                getattr(value, field.name),
                path=_child_path(path, field.name),
                active=active,
            )
            for field in fields(value)
        }
    finally:
        active.remove(object_id)


def _convert_mapping(
    value: Mapping[Any, Any],
    *,
    path: str,
    active: set[int],
) -> dict[str, JsonValue]:
    """转换字典/映射，强制key为字符串，递归转换每一项value"""
    object_id = _enter(value, path=path, active=active)
    try:
        converted: dict[str, JsonValue] = {}
        for key, item in value.items():
            # JSON仅支持字符串键，数字/枚举键全部禁止
            if not isinstance(key, str):
                raise ArtifactSerializationError(
                    f"{path}: mapping keys must be strings；当前类型 {type(key).__name__}"
                )
            converted[key] = _convert(
                item,
                path=_child_path(path, key),
                active=active,
            )
        return converted
    finally:
        active.remove(object_id)


def _convert_sequence(
    value: list[Any] | tuple[Any, ...],
    *,
    path: str,
    active: set[int],
) -> list[JsonValue]:
    """转换列表/元组，统一输出为标准list，下标作为报错路径"""
    object_id = _enter(value, path=path, active=active)
    try:
        return [
            _convert(
                item,
                path=f"{path}[{index}]",
                active=active,
            )
            for index, item in enumerate(value)
        ]
    finally:
        active.remove(object_id)


def _enter(
    value: Any,
    *,
    path: str,
    active: set[int],
) -> int:
    """标记当前对象进入递归栈，检测循环引用，返回对象唯一id"""
    object_id = id(value)
    if object_id in active:
        raise ArtifactSerializationError(
            f"{path}: cyclic reference detected；无法确定性序列化"
        )
    active.add(object_id)
    return object_id


def _child_path(parent: str, key: str) -> str:
    """生成子节点报错路径，模拟JSONPath格式，方便定位错误字段
    合法标识符使用 .key 简写；含特殊字符使用 ['key'] 转义格式
    """
    if key.isidentifier():
        return f"{parent}.{key}"
    # 单引号转义处理
    escaped = key.replace("\\", "\\\\").replace("'", "\\'")
    return f"{parent}['{escaped}']"
