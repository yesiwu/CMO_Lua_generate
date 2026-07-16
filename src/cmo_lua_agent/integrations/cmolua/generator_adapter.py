"""
CMOLua-main 确定性 JSON 转 Lua 生成器的轻量适配层。

本模块刻意不包含场景校验、数据库解析、产物持久化、Lua 预校验或 CMO 执行逻辑。
它仅负责：加载配置指定的外部 Python 模块、调用配置的入口函数、
将外部抛出的异常与警告文本统一转换为程序内部稳定的异常类型。

按绝对路径加载 json_to_lua.py
→ 获取 generate_cmo_lua
→ 传入 Manifest 文件路径
→ 接收 Lua 字符串
→ 捕获 stderr 中的 [warn]
→ 返回 GeneratorRawResult
"""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from contextlib import redirect_stderr
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from types import ModuleType
from typing import Any

from cmo_lua_agent.integrations.cmolua.config import CmoLuaIntegrationConfig


# 外部生成器模块内部标识名
_EXTERNAL_MODULE_NAME = "_cmo_lua_external_generator"


class CmoLuaGeneratorImportError(RuntimeError):
    """配置的外部生成器模块或入口函数加载失败时抛出"""


class CmoLuaGenerationError(RuntimeError):
    """外部生成器无法产出非空 Lua 代码文本时抛出"""


@dataclass(frozen=True, slots=True)
class GeneratorRawResult:
    """外部生成器返回的未经校验的原始结果"""
    lua_text: str          # 生成的 Lua 完整文本
    warnings: tuple[str, ...]  # 执行过程收集到的警告信息元组


# 生成器入口函数类型别名：接收字符串入参，返回任意类型结果
GeneratorCallable = Callable[[str], Any]


class CmoLuaGeneratorAdapter:
    """统一封装调用 CMOLua-main/tools/json_to_lua.py 的适配接口。

    外部模块会在首次调用 generate() 时延迟加载，并缓存在当前适配器实例中。
    通过绝对文件路径加载模块，使该集成逻辑不受程序工作目录影响，
    同时无需手动修改 sys.path 环境变量。
    """

    def __init__(self, config: CmoLuaIntegrationConfig) -> None:
        self._config = config
        self._generator: GeneratorCallable | None = None  # 缓存外部生成器函数
        self._import_warnings: tuple[str, ...] = ()       # 模块导入阶段产生的警告

    def generate(self, manifest_path: Path) -> GeneratorRawResult:
        """基于已解析的清单 JSON 文件生成 Lua 代码

        参数：
            manifest_path：外部 generate_cmo_lua 函数可读取的、已存在的清单 JSON 文件路径

        抛出异常：
            CmoLuaGeneratorImportError：模块或配置入口函数加载失败
            CmoLuaGenerationError：清单文件缺失、外部函数执行报错、返回空/非字符串结果
        """
        # 解析为绝对路径，消除相对路径、用户家目录符号影响
        resolved_manifest = Path(manifest_path).expanduser().resolve()
        if not resolved_manifest.is_file():
            raise CmoLuaGenerationError(
        f"Manifest 文件不存在或不是常规文件：{resolved_manifest}"
            )

        generator = self._load_generator()
        stderr_buffer = StringIO()  # 捕获标准错误输出，提取警告日志

        try:
            # 重定向标准错误流，拦截外部脚本打印的警告信息
            with redirect_stderr(stderr_buffer):
                raw_result = generator(str(resolved_manifest))
        except Exception as exc:
            raise CmoLuaGenerationError(
                f"CMOLua 外部生成器执行失败："
                f"{self._config.generator_path}::"
                f"{self._config.generator_function}，异常详情：{exc}"
            ) from exc

        # 校验返回结果必须为非空字符串
        if not isinstance(raw_result, str) or not raw_result.strip():
            raise CmoLuaGenerationError(
                "CMOLua 外部生成器必须返回非空字符串，"
                f"实际返回数据类型：{type(raw_result).__name__}"
            )

        # 合并导入阶段警告 + 本次执行产生的警告
        warnings = self._import_warnings + _extract_warning_lines(
            stderr_buffer.getvalue()
        )
        return GeneratorRawResult(
            lua_text=raw_result,
            warnings=warnings,
        )

    def _load_generator(self) -> GeneratorCallable:
        """延迟加载外部生成器模块与入口函数，加载后缓存复用"""
        if self._generator is not None:
            return self._generator

        generator_path = self._config.generator_path
        function_name = self._config.generator_function.strip()
        stderr_buffer = StringIO()

        try:
            # 根据文件路径创建模块加载规范
            spec = importlib.util.spec_from_file_location(
                _EXTERNAL_MODULE_NAME,
                generator_path,
            )
            if spec is None or spec.loader is None:
                raise ImportError("无法创建模块加载配置对象")

            # 实例化模块对象并执行模块代码
            module = importlib.util.module_from_spec(spec)
            with redirect_stderr(stderr_buffer):
                spec.loader.exec_module(module)
        except Exception as exc:
            raise CmoLuaGeneratorImportError(
        f"无法导入 CMOLua 外部生成器 {generator_path}：{exc}"
            ) from exc

        # 解析模块内的目标入口函数
        generator = _resolve_entry_point(
            module=module,
            function_name=function_name,
            generator_path=generator_path,
        )
        self._generator = generator
        self._import_warnings = _extract_warning_lines(
            stderr_buffer.getvalue()
        )
        return generator


def _resolve_entry_point(
    *,
    module: ModuleType,
    function_name: str,
    generator_path: Path,
) -> GeneratorCallable:
    """从加载完成的模块中读取并校验入口函数"""
    entry_point = getattr(module, function_name, None)
    if not callable(entry_point):
        raise CmoLuaGeneratorImportError(
            f"CMOLua 外部生成器缺少可调用入口函数："
            f"{generator_path}::{function_name}"
        )
    return entry_point


def _extract_warning_lines(stderr_text: str) -> tuple[str, ...]:
    """从捕获的标准错误文本中提取以 [warn] 开头的警告行，返回清洗后的警告元组"""
    warnings: list[str] = []
    warn_prefix = "[warn]"

    for line in stderr_text.splitlines():
        stripped_line = line.strip()
        # 仅保留以 [warn] 开头的日志行
        if not stripped_line.lower().startswith(warn_prefix):
            continue

        # 剔除前缀与多余分隔符，提取纯警告文本
        warn_msg = stripped_line[len(warn_prefix) :].lstrip(" :-\t")
        warnings.append(warn_msg or stripped_line)

    return tuple(warnings)
