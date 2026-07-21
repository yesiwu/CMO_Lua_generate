"""
（军方给的json可能是错的 ，本来是 int 型，结果是存str，有些地方没有完整{}包裹）
这是一套CMO 仿真场景 JSON 加载工具，
只做文件校验、编码校验、JSON 语法校验、根节点格式校验，不校验场景内部业务字段，
解析完成后封装成统一的 ScenarioInput 对象供上层业务使用；
同时封装了统一结构化异常，方便日志、报告统一打印错误信息。

"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cmo_lua_agent.contract import ScenarioInput


class JsonLoadError(ValueError):
    """读取单个场景JSON文件时抛出的结构化异常"""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        source_path: Path,
        line: int | None = None,
        column: int | None = None,
    ) -> None:
        # 校验错误码非空字符串并赋值
        self.code = _require_non_blank(code, field_name="code")
        # 校验错误描述非空字符串并赋值
        self.message = _require_non_blank(message, field_name="message")
        # 标准化文件路径：展开用户目录、解析绝对路径（文件不存在也不报错）
        self.source_path = (
            Path(source_path).expanduser().resolve(strict=False)
        )
        # 校验行号：只能为None或大于0的整数
        self.line = _validate_position(line, field_name="line")
        # 校验列号：只能为None或大于0的整数
        self.column = _validate_position(column, field_name="column")

        # 拼接完整报错位置信息
        location = str(self.source_path)
        if self.line is not None:
            location += f", line {self.line}"
        if self.column is not None:
            location += f", column {self.column}"

        # 组装最终异常提示文本
        super().__init__(
            f"[{self.code}] {self.message} ({location})"
        )

    def to_dict(self) -> dict[str, Any]:
        """转为可JSON序列化字典，用于运行报告输出"""
        return {
            "code": self.code,
            "message": self.message,
            "source_path": str(self.source_path),
            "line": self.line,
            "column": self.column,
        }


class JsonLoader:
    """读取UTF-8编码场景JSON文件，仅做基础文件与JSON格式校验，不执行业务字段校验"""

    def load(self, path: Path) -> ScenarioInput:
        """读取并解析场景JSON文件

        本阶段仅校验文件合法性与JSON基础结构，场景字段合法性由后续Schema、语义校验器处理
        """
        # 标准化输入路径为绝对路径
        source_path = (
            Path(path).expanduser().resolve(strict=False)
        )

        # 判断文件是否存在
        if not source_path.exists():
            raise JsonLoadError(
                code="json.file_not_found",
                message="JSON 文件不存在",
                source_path=source_path,
            )

        # 判断路径是否为普通文件（排除文件夹、软链接等）
        if not source_path.is_file():
            raise JsonLoadError(
                code="json.not_file",
                message="JSON 路径不是普通文件",
                source_path=source_path,
            )

        # 校验文件后缀必须是.json（忽略大小写）
        if source_path.suffix.lower() != ".json":
            raise JsonLoadError(
                code="json.invalid_extension",
                message="场景输入必须使用 .json 扩展名",
                source_path=source_path,
            )

        try:
            # 以带BOM兼容的UTF-8编码打开文件读取
            with source_path.open(
                "r",
                encoding="utf-8-sig",
            ) as file_handle:
                document = json.load(file_handle)
        except UnicodeDecodeError as exc:
            # 文件编码非UTF-8时抛出异常，保留原始异常栈
            raise JsonLoadError(
                code="json.invalid_encoding",
                message="JSON 文件不是有效的 UTF-8 文本",
                source_path=source_path,
            ) from exc
        except json.JSONDecodeError as exc:
            # JSON语法解析失败，携带出错行、列号，保留原始异常栈
            raise JsonLoadError(
                code="json.invalid_json",
                message=f"JSON 解析失败：{exc.msg}",
                source_path=source_path,
                line=exc.lineno,
                column=exc.colno,
            ) from exc
        except OSError as exc:
            # 文件IO读写异常（权限不足、文件损坏等），保留原始异常栈
            raise JsonLoadError(
                code="json.read_failed",
                message=f"无法读取 JSON 文件：{exc}",
                source_path=source_path,
            ) from exc

        # 校验JSON根节点必须为对象（字典），禁止数组/基础类型
        if not isinstance(document, dict):
            raise JsonLoadError(
                code="json.root_not_object",
                message="JSON 顶层必须是对象",
                source_path=source_path,
                line=1,
                column=1,
            )

        # 封装解析结果并返回场景输入实体
        return ScenarioInput(
            source_path=source_path,
            raw=document,
        )


def _require_non_blank(
    value: str,
    *,
    field_name: str,
) -> str:
    """私有工具函数：校验入参为非空白字符串

    Args:
        value: 待校验字符串值
        field_name: 字段名称，用于报错提示
    Returns:
        去除首尾空格后的原始字符串
    """
    # 类型校验：必须是字符串
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")

    normalized = value.strip()
    # 校验去除空格后不能为空
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")

    return normalized


def _validate_position(
    value: int | None,
    *,
    field_name: str,
) -> int | None:
    """私有工具函数：校验行号/列号合法值

    Args:
        value: 待校验位置数字，允许为空
        field_name: 字段名称（line/column），用于报错提示
    Returns:
        合法数字或None
    """
    # 允许传入None
    if value is None:
        return None

    # 禁止布尔值（bool是int子类，单独拦截）、非整型数字
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer or None")

    # 行/列号必须从1开始，不允许0或负数
    if value < 1:
        raise ValueError(f"{field_name} must be greater than zero")

    return value