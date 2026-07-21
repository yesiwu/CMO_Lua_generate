"""
CMOLua-main Skill 资源的只读、边界受限访问仓库。

本仓库仅对外暴露 Chat 工具所需的可读文档资源；
不开放数据库、生成产物、归档文件，也不提供一次性加载完整 Skill 目录树到内存的接口。
"""

# __future__ 导入必须放在文件最顶部，规避语法报错
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Literal

# 导入CMOLua集成配置类
from cmo_lua_agent.integrations.cmolua.config import CmoLuaIntegrationConfig

# Skill允许访问的目录区域字面量类型
SkillArea = Literal[
    "skill",
    "templates",
    "references",
    "errors",
    "examples",
]

# 全部合法访问区域列表
_ALLOWED_AREAS: tuple[SkillArea, ...] = (
    "skill",
    "templates",
    "references",
    "errors",
    "examples",
)
# 允许访问的子目录集合（除根目录SKILL.md外）
_ALLOWED_DIRECTORIES = frozenset(
    {"templates", "references", "errors", "examples"}
)
# 允许读取的文件后缀白名单
_ALLOWED_SUFFIXES = frozenset(
    {".md", ".txt", ".json", ".lua", ".yaml", ".yml"}
)
# 单次搜索最大返回结果条数
_MAX_SEARCH_RESULTS = 100
# 单次读取文件最大行数限制
_MAX_READ_LINES = 500
# 搜索结果单行摘要最大字符长度
_MAX_SNIPPET_CHARS = 240


class CmoSkillRepositoryError(RuntimeError):
    """CMOLua Skill 资源访问异常基类"""


class CmoSkillAccessError(CmoSkillRepositoryError, ValueError):
    """请求的搜索条件、文件路径或读取行数超出访问边界限制时抛出"""


class CmoSkillInfrastructureError(CmoSkillRepositoryError):
    """Skill 资源目录缺失、文件损坏或无法读取时抛出底层资源异常"""


@dataclass(frozen=True, slots=True)
class SkillSearchHit:
    """单次文件搜索匹配结果单条记录"""
    relative_path: str  # 文件相对于Skill根目录的路径
    area: str            # 所属访问区域
    line_number: int     # 匹配文本所在行号
    snippet: str         # 匹配行的精简摘要


@dataclass(frozen=True, slots=True)
class SkillReadResult:
    """限定行范围读取文档的返回结果封装"""
    relative_path: str  # 文件相对路径
    start_line: int     # 读取起始行号
    end_line: int       # 读取结束行号
    text: str           # 读取到的文本内容
    truncated: bool     # 是否因为行数限制被截断（True=未读完文件）


class CmoSkillRepository:
    """用于检索、读取CMOLua-main目录下受权限管控的文档资源"""

    def __init__(self, config: CmoLuaIntegrationConfig) -> None:
        self._skill_root = config.skill_root.resolve()

        # 校验Skill根目录存在
        if not self._skill_root.is_dir():
            raise CmoSkillInfrastructureError(
                f"CMOLua Skill 根目录不存在或不是目录：{self._skill_root}"
            )

        # 校验核心说明文件SKILL.md存在
        manifest = self._skill_root / "SKILL.md"
        if not manifest.is_file():
            raise CmoSkillInfrastructureError(
                f"CMOLua Skill 根目录缺少 SKILL.md：{manifest}"
            )

    def search(
        self,
        query: str,
        *,
        area: SkillArea | None = None,
        limit: int = 10,
    ) -> tuple[SkillSearchHit, ...]:
        """逐行检索允许访问的文本资源。

        匹配规则：Unicode大小写不敏感；
        结果固定有序：优先SKILL.md，再依次遍历templates、references、errors、examples；
        文件与匹配行均按字典升序排列，结果顺序稳定可复现。
        """
        normalized_query = self._validate_search_args(query, area, limit)
        # 确定本次检索需要遍历的区域
        selected_areas: tuple[SkillArea, ...] = (
            (area,) if area is not None else _ALLOWED_AREAS
        )

        hits: list[SkillSearchHit] = []
        for selected_area in selected_areas:
            # 遍历当前区域内所有合法文件
            for file_path in self._iter_area_files(selected_area):
                try:
                    # 读取文件并按行分割，兼容utf-8带BOM编码
                    lines = file_path.read_text(
                        encoding="utf-8-sig"
                    ).splitlines()
                except (OSError, UnicodeError):
                    # 搜索采用尽力而为策略，单个文件读取失败直接跳过；
                    # 完整读取接口read()会单独抛出精准的资源异常
                    continue

                # 转为POSIX格式相对路径，统一跨平台展示
                relative_path = file_path.relative_to(
                    self._skill_root
                ).as_posix()
                # 遍历每行文本，行号从1开始计数
                for line_number, line in enumerate(lines, start=1):
                    if normalized_query not in line.casefold():
                        continue

                    hits.append(
                        SkillSearchHit(
                            relative_path=relative_path,
                            area=selected_area,
                            line_number=line_number,
                            snippet=self._make_snippet(line),
                        )
                    )
                    # 达到返回条数上限，提前终止检索
                    if len(hits) >= limit:
                        return tuple(hits)

        return tuple(hits)

    def read(
        self,
        relative_path: str,
        *,
        start_line: int = 1,
        limit: int = 200,
    ) -> SkillReadResult:
        """读取单个合法Skill文档的指定行数，最多读取limit行"""
        # 起始行号最小为1
        if start_line < 1:
            raise CmoSkillAccessError("start_line 必须大于或等于 1")
        # 单次读取行数限制校验
        if limit < 1 or limit > _MAX_READ_LINES:
            raise CmoSkillAccessError(
                f"limit 必须位于 1..{_MAX_READ_LINES}"
            )

        # 校验路径合法性并获取绝对文件路径
        file_path, normalized_relative = self._resolve_allowed_file(
            relative_path
        )
        try:
            lines = file_path.read_text(
                encoding="utf-8-sig"
            ).splitlines()
        except (OSError, UnicodeError) as exc:
            raise CmoSkillInfrastructureError(
                f"无法读取 CMOLua Skill 文档：{normalized_relative}"
            ) from exc

        # 转换为列表下标切片读取
        start_index = start_line - 1
        selected_lines = lines[start_index : start_index + limit]
        end_line = start_line + len(selected_lines) - 1
        # 判断是否还有剩余未读取行（内容被截断）
        truncated = start_index + len(selected_lines) < len(lines)

        return SkillReadResult(
            relative_path=normalized_relative,
            start_line=start_line,
            end_line=end_line,
            text="\n".join(selected_lines),
            truncated=truncated,
        )

    def _validate_search_args(
        self,
        query: str,
        area: SkillArea | None,
        limit: int,
    ) -> str:
        """内部工具：校验search接口入参合法性，返回小写标准化检索关键词"""
        if not isinstance(query, str) or not query.strip():
            raise CmoSkillAccessError("搜索关键词不能为空")
        if area is not None and area not in _ALLOWED_AREAS:
            raise CmoSkillAccessError(f"不支持的 Skill 区域：{area}")
        if limit < 1 or limit > _MAX_SEARCH_RESULTS:
            raise CmoSkillAccessError(
                f"limit 必须位于 1..{_MAX_SEARCH_RESULTS}"
            )
        # 返回去除首尾空格、全小写的检索文本
        return query.strip().casefold()

    def _iter_area_files(self, area: SkillArea) -> tuple[Path, ...]:
        """内部工具：遍历指定区域下所有符合后缀白名单的文件，返回排序后的路径元组"""
        # skill区域仅包含根目录SKILL.md
        if area == "skill":
            return (self._skill_root / "SKILL.md",)

        area_root = self._skill_root / area
        # 目标区域目录不存在，直接返回空列表
        if not area_root.is_dir():
            return ()

        candidates: list[Path] = []
        # 递归遍历区域内所有子文件
        for candidate in area_root.rglob("*"):
            # 过滤不在后缀白名单内的文件
            if candidate.suffix.casefold() not in _ALLOWED_SUFFIXES:
                continue
            try:
                resolved = candidate.resolve(strict=True)
            except OSError:
                # 文件访问异常直接跳过
                continue
            if not resolved.is_file():
                continue
            # 防止路径跳出Skill根目录
            if not resolved.is_relative_to(self._skill_root):
                continue
            candidates.append(resolved)

        # 去重并按相对路径字典序排序后返回
        return tuple(
            sorted(
                set(candidates),
                key=lambda item: item.relative_to(
                    self._skill_root
                ).as_posix(),
            )
        )

    def _resolve_allowed_file(
        self,
        relative_path: str,
    ) -> tuple[Path, str]:
        """内部工具：校验传入相对路径是否合法，返回文件绝对路径+标准化POSIX相对路径"""
        if not isinstance(relative_path, str) or not relative_path.strip():
            raise CmoSkillAccessError("relative_path 不能为空")

        raw_path = relative_path.strip()
        windows_path = PureWindowsPath(raw_path)
        # 禁止传入绝对路径（Windows带盘符、/开头路径均拦截）
        if Path(raw_path).is_absolute() or windows_path.is_absolute() or (
            windows_path.drive
        ):
            raise CmoSkillAccessError("只允许读取 Skill 根目录内的相对路径")

        # 统一将Windows反斜杠转为标准斜杠
        normalized_text = raw_path.replace("\\", "/")
        # 拆分路径片段，过滤空片段、当前目录标记.
        parts = tuple(
            part
            for part in normalized_text.split("/")
            if part not in {"", "."}
        )
        # 禁止空路径、父目录跳转..（路径穿越防护）
        if not parts or ".." in parts:
            raise CmoSkillAccessError("文档路径包含非法目录跳转")

        normalized_relative = Path(*parts)
        # 校验路径是否处于允许访问的目录范围内
        if not self._is_allowed_relative_path(normalized_relative):
            raise CmoSkillAccessError(
                f"文档不在允许的 Skill 范围内：{normalized_text}"
            )

        candidate = self._skill_root / normalized_relative
        try:
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError as exc:
            raise CmoSkillAccessError(
                f"Skill 文档不存在：{normalized_relative.as_posix()}"
            ) from exc
        except OSError as exc:
            raise CmoSkillInfrastructureError(
                f"无法解析 Skill 文档路径：{normalized_relative.as_posix()}"
            ) from exc

        # 二次校验文件未跳出Skill根目录
        if not resolved.is_relative_to(self._skill_root):
            raise CmoSkillAccessError("Skill 文档路径越过根目录")
        if not resolved.is_file():
            raise CmoSkillAccessError("Skill 路径不是普通文件")

        return resolved, normalized_relative.as_posix()

    @staticmethod
    def _is_allowed_relative_path(relative_path: Path) -> bool:
        """静态工具：判断相对路径是否在允许访问的白名单范围内"""
        # 根目录SKILL.md永久放行
        if relative_path.as_posix() == "SKILL.md":
            return True
        if not relative_path.parts:
            return False
        # 一级目录在允许列表 + 文件后缀在白名单则放行
        return (
            relative_path.parts[0] in _ALLOWED_DIRECTORIES
            and relative_path.suffix.casefold() in _ALLOWED_SUFFIXES
        )

    @staticmethod
    def _make_snippet(line: str) -> str:
        """静态工具：生成单行文本精简摘要，超长末尾补充省略号"""
        # 合并连续空白字符压缩文本
        compact = " ".join(line.strip().split())
        if len(compact) <= _MAX_SNIPPET_CHARS:
            return compact
        # 截断并添加省略号占位
        return compact[: _MAX_SNIPPET_CHARS - 1] + "…"