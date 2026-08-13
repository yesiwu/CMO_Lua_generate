

"""CMOLua 集成配置。

集中解析并只读校验外部 Skill、生成器、数据库及输出目录；不在此导入外部程序、连接
数据库或写 Artifact，确保配置错误在接入边界被清晰报告。
"""

from __future__ import annotations
"""

作用是验证
CMOLua-main/ 是否存在
CMOLua-main/SKILL.md 是否存在
tools/json_to_lua.py 是否存在
DB3K_504.db3 是否存在
outputs/lua 是否存在
生成器函数名是否为空
"""


"""
CMOLua-main 集成配置。

该模块只负责描述并校验当前应用依赖的外部 CMOLua 资源：

1. CMOLua-main Skill 根目录；
2. JSON → Lua 生成器脚本；
3. 与本机 CMO 版本匹配的 SQLite 数据库；
4. 当前项目的 Lua 输出目录；
5. 生成器导出的稳定函数名。

阶段 0 只确认路径和入口是否存在，不导入生成器、
不读取 Skill 内容、不连接数据库，也不创建输出目录。

后续组件在真正需要时，再分别加载这些外部资源。
"""



import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


# 环境变量名称
_ENV_SKILL_ROOT = "CMO_LUA_SKILL_ROOT"
_ENV_GENERATOR_PATH = "CMO_LUA_GENERATOR_PATH"
_ENV_DATABASE_PATH = "CMO_DATABASE_PATH"
_ENV_OUTPUTS_DIR = "CMO_OUTPUTS_DIR"
_ENV_GENERATOR_FUNCTION = "CMO_LUA_GENERATOR_FUNCTION"

# CMOLua-main 当前提供的默认生成函数
_DEFAULT_GENERATOR_FUNCTION = "generate_cmo_lua"


class CmoLuaConfigurationError(ValueError):
    """
    CMOLua 外部依赖配置错误。

    当 Skill、生成器、数据库或输出目录不存在，
    或者生成器函数名不合法时抛出。
    """


@dataclass(frozen=True, slots=True)
class CmoLuaIntegrationConfig:
    """
    CMOLua-main 外部集成配置。

    Attributes:
        skill_root:
            CMOLua-main 根目录，其中应包含 SKILL.md、
            templates、references、tools 和 mcp 等目录。

        generator_path:
            JSON → Lua 确定性生成器脚本路径，
            默认是 CMOLua-main/tools/json_to_lua.py。

        database_path:
            当前 CMO 版本对应的 DB3K SQLite 数据库路径。

        outputs_dir:
            当前 Agent 项目的 Lua 输出目录，
            默认是项目根目录下的 outputs/lua。

        generator_function:
            json_to_lua.py 对外提供的生成函数名，
            默认是 generate_cmo_lua。
    """

    skill_root: Path
    generator_path: Path
    database_path: Path
    outputs_dir: Path
    generator_function: str = _DEFAULT_GENERATOR_FUNCTION

    def __post_init__(self) -> None:
        """
        将所有路径规范化为绝对路径。

        这里只处理路径，不检查文件是否存在。
        文件系统检查统一由 validate() 完成。
        """
        object.__setattr__(
            self,
            "skill_root",
            self._normalize_path(self.skill_root),
        )
        object.__setattr__(
            self,
            "generator_path",
            self._normalize_path(self.generator_path),
        )
        object.__setattr__(
            self,
            "database_path",
            self._normalize_path(self.database_path),
        )
        object.__setattr__(
            self,
            "outputs_dir",
            self._normalize_path(self.outputs_dir),
        )

        if isinstance(self.generator_function, str):
            object.__setattr__(
                self,
                "generator_function",
                self.generator_function.strip(),
            )

    @property
    def skill_manifest_path(self) -> Path:
        """返回 CMOLua-main/SKILL.md 路径。"""
        return self.skill_root / "SKILL.md"

    @property
    def templates_dir(self) -> Path:
        """返回 CMOLua-main/templates 目录。"""
        return self.skill_root / "templates"

    @property
    def references_dir(self) -> Path:
        """返回 CMOLua-main/references 目录。"""
        return self.skill_root / "references"

    @property
    def examples_dir(self) -> Path:
        """返回 CMOLua-main/examples 目录。"""
        return self.skill_root / "examples"

    @property
    def errors_dir(self) -> Path:
        """返回 CMOLua-main/errors 目录。"""
        return self.skill_root / "errors"

    @classmethod
    def from_project_root(
        cls,
        project_root: Path,
        *,
        environ: Mapping[str, str] | None = None,
        validate: bool = True,
    ) -> CmoLuaIntegrationConfig:
        """
        根据项目根目录创建 CMOLua 集成配置。

        默认目录约定：

        <project_root>/CMOLua-main
        <project_root>/CMOLua-main/tools/json_to_lua.py
        <project_root>/CMOLua-main/mcp/db/DB3K_504.db3
        <project_root>/outputs/lua

        环境变量可以覆盖默认值：

        CMO_LUA_SKILL_ROOT
        CMO_LUA_GENERATOR_PATH
        CMO_DATABASE_PATH
        CMO_OUTPUTS_DIR
        CMO_LUA_GENERATOR_FUNCTION

        环境变量中的相对路径统一相对于 project_root，
        不依赖程序当前的工作目录。

        Args:
            project_root:
                CMO_Lua_generate 项目根目录。

            environ:
                环境变量映射。默认使用 os.environ。
                测试时可以传入普通字典。

            validate:
                是否在创建后立即检查外部依赖。
                默认开启。

        Returns:
            规范化后的 CmoLuaIntegrationConfig。
        """
        root = cls._normalize_path(project_root)
        source = os.environ if environ is None else environ

        skill_root = _resolve_config_path(
            configured_value=source.get(_ENV_SKILL_ROOT),
            base_dir=root,
            default=root / "CMOLua-main",
        )

        generator_path = _resolve_config_path(
            configured_value=source.get(_ENV_GENERATOR_PATH),
            base_dir=root,
            default=skill_root / "tools" / "json_to_lua.py",
        )

        database_path = _resolve_config_path(
            configured_value=source.get(_ENV_DATABASE_PATH),
            base_dir=root,
            default=skill_root / "mcp" / "db" / "DB3K_504.db3",
        )

        outputs_dir = _resolve_config_path(
            configured_value=source.get(_ENV_OUTPUTS_DIR),
            base_dir=root,
            default=root / "outputs" / "lua",
        )

        generator_function = source.get(
            _ENV_GENERATOR_FUNCTION,
            _DEFAULT_GENERATOR_FUNCTION,
        )

        config = cls(
            skill_root=skill_root,
            generator_path=generator_path,
            database_path=database_path,
            outputs_dir=outputs_dir,
            generator_function=generator_function,
        )

        if validate:
            config.validate()

        return config

    def validate(self) -> CmoLuaIntegrationConfig:
        """
        校验阶段 0 所需的外部依赖。

        本方法只检查文件系统元数据：

        - 不读取 SKILL.md；
        - 不导入 json_to_lua.py；
        - 不连接 SQLite；
        - 不创建输出目录。

        Returns:
            当前配置对象，方便链式调用。

        Raises:
            CmoLuaConfigurationError:
                一个或多个外部依赖不完整。
        """
        issues: list[str] = []

        self._validate_skill_root(issues)
        self._validate_generator(issues)
        self._validate_database(issues)
        self._validate_outputs_dir(issues)
        self._validate_generator_function(issues)

        if issues:
            formatted_issues = "\n".join(
                f"- {issue}"
                for issue in issues
            )

            raise CmoLuaConfigurationError(
                "CMOLua 集成配置校验失败：\n"
                f"{formatted_issues}"
            )

        return self

    def to_dict(self) -> dict[str, str]:
        """
        将配置转换为可序列化字典。

        后续可以保存到运行产物或版本清单中。
        """
        return {
            "skill_root": str(self.skill_root),
            "skill_manifest_path": str(
                self.skill_manifest_path
            ),
            "generator_path": str(self.generator_path),
            "database_path": str(self.database_path),
            "outputs_dir": str(self.outputs_dir),
            "generator_function": self.generator_function,
        }

    def _validate_skill_root(
        self,
        issues: list[str],
    ) -> None:
        if not self.skill_root.is_dir():
            issues.append(
                "CMOLua Skill 根目录不存在或不是目录："
                f"{self.skill_root}"
            )
            return

        if not self.skill_manifest_path.is_file():
            issues.append(
                "CMOLua Skill 根目录缺少 SKILL.md："
                f"{self.skill_manifest_path}"
            )

    def _validate_generator(
        self,
        issues: list[str],
    ) -> None:
        if not self.generator_path.is_file():
            issues.append(
                "JSON → Lua 生成器不存在或不是文件："
                f"{self.generator_path}"
            )
            return

        if self.generator_path.suffix.lower() != ".py":
            issues.append(
                "JSON → Lua 生成器必须是 Python 文件："
                f"{self.generator_path}"
            )

    def _validate_database(
        self,
        issues: list[str],
    ) -> None:
        if not self.database_path.is_file():
            issues.append(
                "CMO 数据库不存在或不是文件："
                f"{self.database_path}"
            )
            return

        if self.database_path.suffix.lower() not in {
            ".db",
            ".db3",
            ".sqlite",
            ".sqlite3",
        }:
            issues.append(
                "CMO 数据库文件扩展名不受支持："
                f"{self.database_path}"
            )

    def _validate_outputs_dir(
        self,
        issues: list[str],
    ) -> None:
        if not self.outputs_dir.is_dir():
            issues.append(
                "Lua 输出目录不存在或不是目录："
                f"{self.outputs_dir}"
            )

    def _validate_generator_function(
        self,
        issues: list[str],
    ) -> None:
        if not isinstance(
            self.generator_function,
            str,
        ) or not self.generator_function:
            issues.append(
                "CMOLua 生成器函数名不能为空"
            )

    @staticmethod
    def _normalize_path(path: Path | str) -> Path:
        """
        将路径展开并规范化为绝对路径。

        resolve(strict=False) 不要求目标已经存在，
        因此不会提前触发 FileNotFoundError。
        """
        return Path(path).expanduser().resolve(
            strict=False
        )


def _resolve_config_path(
    configured_value: str | None,
    *,
    base_dir: Path,
    default: Path,
) -> Path:
    """
    解析一个可能来自环境变量的路径。

    规则：

    1. 未配置或只包含空白时使用默认路径；
    2. 绝对路径直接使用；
    3. 相对路径相对于项目根目录；
    4. 最终规范化为绝对路径。
    """
    if configured_value is None:
        return default.expanduser().resolve(
            strict=False
        )

    stripped_value = configured_value.strip()

    if not stripped_value:
        return default.expanduser().resolve(
            strict=False
        )

    configured_path = Path(
        stripped_value
    ).expanduser()

    if not configured_path.is_absolute():
        configured_path = (
            base_dir / configured_path
        )

    return configured_path.resolve(
        strict=False
    )
