# """用于确定性Lua脚本生成与生成前预检报告的数据模型定义"""

# from __future__ import annotations

# from dataclasses import dataclass
# from pathlib import Path
# from typing import Any

# # 导入上游输出清单、通用校验结果模型
# from cmo_lua_agent.contract import (
#     ResolvedScenarioManifest,
#     ValidationIssue,
#     ValidationResult,
# )


# @dataclass(frozen=True, slots=True)
# class LuaGenerationRequest:
#     """单次Lua生成任务请求体，绑定场景清单与文件输出路径"""
#     # 经过完整解析校验的标准场景清单（ManifestBuilder输出）
#     manifest: ResolvedScenarioManifest
#     # 清单JSON文件本地路径
#     manifest_path: Path
#     # Lua脚本最终输出保存路径
#     output_path: Path

#     def __post_init__(self) -> None:
#         """实例化后置校验+路径标准化处理"""
#         # 强制校验清单类型，防止传入非法数据
#         if not isinstance(
#             self.manifest,
#             ResolvedScenarioManifest,
#         ):
#             raise TypeError(
#                 "manifest 必须是 ResolvedScenarioManifest 类型实例"
#             )

#         # 统一规范化路径：展开用户家目录、转为绝对路径，覆盖原始属性
#         object.__setattr__(
#             self,
#             "manifest_path",
#             _normalize_path(self.manifest_path),
#         )
#         object.__setattr__(
#             self,
#             "output_path",
#             _normalize_path(self.output_path),
#         )

#     def to_dict(self) -> dict[str, Any]:
#         """序列化为可JSON导出的字典，用于日志、持久化存储"""
#         return {
#             "manifest": self.manifest.to_dict(),
#             "manifest_path": str(self.manifest_path),
#             "output_path": str(self.output_path),
#         }


# @dataclass(frozen=True, slots=True)
# class LuaPreflightReport:
#     """Lua生成前置预检完整报告，由LuaPreflightValidator产出"""
#     # 预检全量校验错误/警告集合
#     validation: ValidationResult

#     def __post_init__(self) -> None:
#         """后置校验：校验结果类型合法"""
#         if not isinstance(self.validation, ValidationResult):
#             raise TypeError(
#                 "validation 必须是 ValidationResult 类型实例"
#             )

#     @property
#     def valid(self) -> bool:
#         """只读属性：预检是否全部通过（无ERROR级错误）"""
#         return self.validation.valid

#     @property
#     def issues(self) -> tuple[ValidationIssue, ...]:
#         """只读属性：获取所有校验问题（错误+警告）"""
#         return self.validation.issues

#     @property
#     def errors(self) -> tuple[ValidationIssue, ...]:
#         """只读属性：仅获取阻断生成的ERROR严重错误"""
#         return self.validation.errors

#     @property
#     def warnings(self) -> tuple[ValidationIssue, ...]:
#         """只读属性：仅获取不阻断生成的WARNING提示"""
#         return self.validation.warnings

#     def to_dict(self) -> dict[str, Any]:
#         """将预检报告转为可序列化字典"""
#         return self.validation.to_dict()


# @dataclass(frozen=True, slots=True)
# class LuaGenerationResult:
#     """Lua脚本生成完整结果载体
#     包含：生成成功标记、预检报告、生成脚本文本、输出路径、生成器自身警告

#     success = True 代表：预检全部通过 + Lua文本已写入output_path
#     生成失败时仍会保留lua_text用于调试排查，但不会落地写入文件，output_path为None
#     """
#     # 整体生成是否成功
#     success: bool
#     # 完整Lua脚本字符串；失败时仍有内容，成功不可为空
#     lua_text: str | None
#     # 脚本落地文件路径；成功必填，失败为None
#     output_path: Path | None
#     # 生成器运行过程中产生的业务警告字符串元组
#     generator_warnings: tuple[str, ...]
#     # 生成前置预检报告
#     preflight: LuaPreflightReport

#     def __post_init__(self) -> None:
#         """实例后置强约束校验，保证数据自洽无矛盾"""
#         # success 必须是布尔值
#         if not isinstance(self.success, bool):
#             raise TypeError("success 必须为布尔类型")

#         lua_text = self.lua_text
#         if lua_text is not None:
#             # 有文本时必须是字符串，且不能全空白
#             if not isinstance(lua_text, str):
#                 raise TypeError("lua_text 只能为字符串或 None")
#             if not lua_text.strip():
#                 raise ValueError("lua_text 不允许全空白空文本")

#         output_path = self.output_path
#         if output_path is not None:
#             # 路径标准化并覆盖属性
#             output_path = _normalize_path(output_path)
#             object.__setattr__(self, "output_path", output_path)

#         # 标准化警告文本：去首尾空格、校验格式
#         warnings = _normalize_warnings(self.generator_warnings)
#         object.__setattr__(self, "generator_warnings", warnings)

#         # 预检报告类型校验
#         if not isinstance(self.preflight, LuaPreflightReport):
#             raise TypeError(
#                 "preflight 必须是 LuaPreflightReport 实例"
#             )

#         # 成功场景强约束：三者缺一不可
#         if self.success:
#             if lua_text is None:
#                 raise ValueError(
#                     "生成成功时必须提供lua_text脚本内容"
#                 )
#             if output_path is None:
#                 raise ValueError(
#                     "生成成功时必须提供output_path输出路径"
#                 )
#             if not self.preflight.valid:
#                 raise ValueError(
#                     "preflight 必须在生成成功前通过且不包含错误"
#                 )

#     def to_dict(self) -> dict[str, Any]:
#         """序列化生成结果，用于接口返回、日志持久化"""
#         return {
#             "success": self.success,
#             "lua_text": self.lua_text,
#             "output_path": (
#                 str(self.output_path)
#                 if self.output_path is not None
#                 else None
#             ),
#             "generator_warnings": list(
#                 self.generator_warnings
#             ),
#             "preflight": self.preflight.to_dict(),
#         }


# def _normalize_path(value: Path) -> Path:
#     """路径标准化工具函数
#     功能：展开~家目录、转为绝对真实路径，不校验文件是否存在
#     """
#     try:
#         return Path(value).expanduser().resolve(strict=False)
#     except TypeError as exc:
#         raise TypeError("路径参数必须是合法路径类型") from exc


# def _normalize_warnings(
#     values: tuple[str, ...],
# ) -> tuple[str, ...]:
#     """生成器警告标准化处理工具
#     1. 校验全部元素为字符串
#     2. 去除每条警告首尾空白
#     3. 禁止空字符串警告
#     返回清洗后的元组
#     """
#     try:
#         normalized_values = tuple(values)
#     except TypeError as exc:
#         raise TypeError(
#             "generator_warnings 必须是字符串可迭代集合"
#         ) from exc

#     normalized: list[str] = []
#     for value in normalized_values:
#         if not isinstance(value, str):
#             raise TypeError(
#                 "generator_warnings 内仅允许字符串元素"
#             )
#         warning = value.strip()
#         if not warning:
#             raise ValueError(
#                 "generator_warnings 不允许空白字符串警告"
#             )
#         normalized.append(warning)

#     return tuple(normalized)
"""Data models for deterministic Lua generation and preflight reporting."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cmo_lua_agent.contract import (
    ResolvedScenarioManifest,
    ValidationIssue,
    ValidationResult,
)


@dataclass(frozen=True, slots=True)
class LuaGenerationRequest:
    """One generator invocation with explicit manifest and output paths."""

    manifest: ResolvedScenarioManifest
    manifest_path: Path
    output_path: Path

    def __post_init__(self) -> None:
        if not isinstance(
            self.manifest,
            ResolvedScenarioManifest,
        ):
            raise TypeError(
                "manifest must be a ResolvedScenarioManifest"
            )

        object.__setattr__(
            self,
            "manifest_path",
            _normalize_path(self.manifest_path),
        )
        object.__setattr__(
            self,
            "output_path",
            _normalize_path(self.output_path),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a detached JSON-serializable representation."""

        return {
            "manifest": self.manifest.to_dict(),
            "manifest_path": str(self.manifest_path),
            "output_path": str(self.output_path),
        }


@dataclass(frozen=True, slots=True)
class LuaPreflightReport:
    """Structured findings produced by LuaPreflightValidator."""

    validation: ValidationResult

    def __post_init__(self) -> None:
        if not isinstance(self.validation, ValidationResult):
            raise TypeError(
                "validation must be a ValidationResult"
            )

    @property
    def valid(self) -> bool:
        return self.validation.valid

    @property
    def issues(self) -> tuple[ValidationIssue, ...]:
        return self.validation.issues

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        return self.validation.errors

    @property
    def warnings(self) -> tuple[ValidationIssue, ...]:
        return self.validation.warnings

    def to_dict(self) -> dict[str, Any]:
        return self.validation.to_dict()


@dataclass(frozen=True, slots=True)
class LuaGenerationResult:
    """Outcome of Lua generation and preflight validation.

    ``success`` means the candidate passed preflight and is ready for the
    orchestration layer to persist at ``output_path``. The generation service
    itself performs no filesystem writes. A failed result may retain
    ``lua_text`` so orchestration can persist a rejected candidate separately.
    """

    success: bool
    lua_text: str | None
    output_path: Path | None
    generator_warnings: tuple[str, ...]
    preflight: LuaPreflightReport

    def __post_init__(self) -> None:
        if not isinstance(self.success, bool):
            raise TypeError("success must be a bool")

        lua_text = self.lua_text
        if lua_text is not None:
            if not isinstance(lua_text, str):
                raise TypeError("lua_text must be a string or None")
            if not lua_text.strip():
                raise ValueError("lua_text must not be blank")

        output_path = self.output_path
        if output_path is not None:
            output_path = _normalize_path(output_path)
            object.__setattr__(self, "output_path", output_path)

        warnings = _normalize_warnings(self.generator_warnings)
        object.__setattr__(self, "generator_warnings", warnings)

        if not isinstance(self.preflight, LuaPreflightReport):
            raise TypeError(
                "preflight must be a LuaPreflightReport"
            )

        if self.success:
            if lua_text is None:
                raise ValueError(
                    "successful result requires lua_text"
                )
            if output_path is None:
                raise ValueError(
                    "successful result requires output_path"
                )
            if not self.preflight.valid:
                raise ValueError(
                    "successful result requires valid preflight"
                )

    def to_dict(self) -> dict[str, Any]:
        """Return a stable JSON-serializable generation result."""

        return {
            "success": self.success,
            "lua_text": self.lua_text,
            "output_path": (
                str(self.output_path)
                if self.output_path is not None
                else None
            ),
            "generator_warnings": list(
                self.generator_warnings
            ),
            "preflight": self.preflight.to_dict(),
        }


def _normalize_path(value: Path) -> Path:
    try:
        return Path(value).expanduser().resolve(strict=False)
    except TypeError as exc:
        raise TypeError("path values must be path-like") from exc


def _normalize_warnings(
    values: tuple[str, ...],
) -> tuple[str, ...]:
    try:
        normalized_values = tuple(values)
    except TypeError as exc:
        raise TypeError(
            "generator_warnings must be an iterable of strings"
        ) from exc

    normalized: list[str] = []
    for value in normalized_values:
        if not isinstance(value, str):
            raise TypeError(
                "generator_warnings must contain only strings"
            )
        warning = value.strip()
        if not warning:
            raise ValueError(
                "generator_warnings must not contain blank strings"
            )
        normalized.append(warning)

    return tuple(normalized)