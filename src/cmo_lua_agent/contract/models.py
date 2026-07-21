"""
JSON 转 Lua 工作流共用契约模型定义（这套代码是多阶段流转的数据契约：输入→IR→契约→最终清单，每个阶段只读取、不修改上游数据。）

定义校验体系：
    用ValidationSeverity区分错误 / 警告，ValidationIssue存单条校验问题，ValidationResult汇总一阶段全部校验结果，用来统一收集、传递格式 / 语义报错。
分层承载工作流各阶段数据，数据流顺序：
    ScenarioInput：原始关系；
    ScenarioIR：存储标准化、归一化后的场景中间关系数据  ，ScenarioIR.data所有「射手 ID - 目标 ID」配对关系完整保留在这里；
    ScenarioContract：提取场景内所有单元、射击方、目标 ID / 名称，用于跨环节引用校验；
    ResolvedScenarioManifest：补全数据库、解析完成后的完整交战关系，交给 Lua 生成器进行lua生成。
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class ValidationSeverity(str, Enum):
    """校验问题严重程度枚举"""

    ERROR = "error"    # 错误：阻断流程
    WARNING = "warning"# 警告：仅提示，不阻断


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """单条标准化、机器可读的校验异常记录"""

    code: str               # 错误/警告唯一编码
    message: str            # 可读描述信息
    path: str               # 数据字段路径（定位出错节点）
    severity: ValidationSeverity  # 严重等级

    def __post_init__(self) -> None:
        # 校验并清洗非空字符串字段
        code = _require_non_blank(self.code, field_name="code")
        message = _require_non_blank(self.message, field_name="message")
        path = _require_non_blank(self.path, field_name="path")

        # 严重等级必须是枚举实例
        if not isinstance(self.severity, ValidationSeverity):
            raise TypeError("severity 必须为 ValidationSeverity 枚举值")

        # frozen 数据类不能直接赋值，通过 object 底层属性修改
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "message", message)
        object.__setattr__(self, "path", path)

    def to_dict(self) -> dict[str, str]:
        """序列化为可JSON导出的字典"""
        return {
            "code": self.code,
            "message": self.message,
            "path": self.path,
            "severity": self.severity.value,
        }


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """单次工作流阶段产出的全套校验结果集合"""

    issues: tuple[ValidationIssue, ...] = ()  # 所有校验异常元组

    def __post_init__(self) -> None:
        # 统一转为元组并校验元素类型
        normalized = tuple(self.issues)
        if not all(isinstance(item, ValidationIssue) for item in normalized):
            raise TypeError("issues 内仅允许存放 ValidationIssue 对象")
        object.__setattr__(self, "issues", normalized)

    @property
    def valid(self) -> bool:
        """整体是否合法：不存在 ERROR 级错误则为 True"""
        return not any(
            issue.severity is ValidationSeverity.ERROR
            for issue in self.issues
        )

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        """筛选所有错误级别的校验项"""
        return tuple(
            issue
            for issue in self.issues
            if issue.severity is ValidationSeverity.ERROR
        )

    @property
    def warnings(self) -> tuple[ValidationIssue, ...]:
        """筛选所有警告级别的校验项"""
        return tuple(
            issue
            for issue in self.issues
            if issue.severity is ValidationSeverity.WARNING
        )

    def to_dict(self) -> dict[str, Any]:
        """完整序列化校验结果为字典"""
        return {
            "valid": self.valid,
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass(frozen=True, slots=True)
class ScenarioInput:
    """原始输入场景：源JSON文件路径 + 未处理原始字典数据"""

    source_path: Path       # 原始JSON文件绝对路径
    raw: Mapping[str, Any] # JSON解析后的原始未归一化数据

    def __post_init__(self) -> None:
        # 路径标准化：展开用户目录、解析为绝对路径
        object.__setattr__(
            self,
            "source_path",
            Path(self.source_path).expanduser().resolve(strict=False),
        )
        # 校验raw必须是字典类映射结构
        _require_mapping(self.raw, field_name="raw")

    def to_dict(self) -> dict[str, Any]:
        """转为可序列化字典，映射执行深拷贝隔离原始数据"""
        return {
            "source_path": str(self.source_path),
            "raw": _copy_mapping(self.raw),
        }


@dataclass(frozen=True, slots=True)
class ScenarioIR:
    """场景中间表示IR：确定性归一化后的标准中间数据结构"""

    data: Mapping[str, Any] # 归一化、格式统一后的场景数据

    def __post_init__(self) -> None:
        _require_mapping(self.data, field_name="data")

    def to_dict(self) -> dict[str, Any]:
        return _copy_mapping(self.data)


@dataclass(frozen=True, slots=True)
class ScenarioContract:
    """场景契约：
    只是告诉你场景中有哪些 id，而不会告诉你谁打谁
    """

    scenario_id: str                # 当前场景唯一标识
    unit_ids: tuple[str, ...]      # 场景内所有单元ID集合
    unit_names: tuple[str, ...]     # 场景内所有单元名称集合
    shooter_ids: tuple[str, ...]   # 所有射击方单元ID
    target_ids: tuple[str, ...]    # 所有目标方单元ID

    def __post_init__(self) -> None:
        # 场景ID清洗去空白
        object.__setattr__(
            self,
            "scenario_id",
            _require_non_blank(self.scenario_id, field_name="scenario_id"),
        )
        # 批量校验所有ID/名称元组：元素必须是非空字符串
        for field_name in (
            "unit_ids",
            "unit_names",
            "shooter_ids",
            "target_ids",
        ):
            values = tuple(getattr(self, field_name))
            if not all(isinstance(value, str) and value.strip() for value in values):
                raise ValueError(f"{field_name} 只能包含非空白字符串")
            object.__setattr__(self, field_name, values)

    def to_dict(self) -> dict[str, Any]:
        """元组转列表输出，适配JSON序列化"""
        return {
            "scenario_id": self.scenario_id,
            "unit_ids": list(self.unit_ids),
            "unit_names": list(self.unit_names),
            "shooter_ids": list(self.shooter_ids),
            "target_ids": list(self.target_ids),
        }


@dataclass(frozen=True, slots=True)
class ResolvedScenarioManifest:
    """解析完成场景清单：经过语义校验、CMO数据库数据补全后，交付Lua生成器的最终数据"""

    data: Mapping[str, Any] # 完整解析、补齐依赖后的场景全量数据

    def __post_init__(self) -> None:
        _require_mapping(self.data, field_name="data")

    def to_dict(self) -> dict[str, Any]:
        return _copy_mapping(self.data)


def _require_non_blank(value: str, *, field_name: str) -> str:
    """私有工具：校验入参为非空白字符串，返回清洗后去除首尾空格的值"""
    if not isinstance(value, str):
        raise TypeError(f"{field_name} 必须是字符串类型")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} 不能为空或全空白字符")
    return normalized


def _require_mapping(value: Mapping[str, Any], *, field_name: str) -> None:
    """私有工具：校验输入为映射类（dict/自定义Mapping）"""
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} 必须为字典/映射结构")


def _copy_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    """私有工具：深拷贝映射转为标准dict，生成与原始数据完全隔离的副本，用于JSON序列化"""
    return deepcopy(dict(value))