"""发现并安全加载项目内的文档型 Skill。"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml


_EXCLUDED_DIRECTORIES = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "site-packages",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    }
)
_LINKED_DIRECTORIES = ("references", "templates", "scripts", "assets")
_READABLE_SUFFIXES = frozenset(
    {
        ".md",
        ".txt",
        ".json",
        ".yaml",
        ".yml",
        ".lua",
        ".py",
        ".ps1",
        ".sh",
        ".bash",
    }
)
_MAX_CONTENT_CHARS = 24_000
_FRONTMATTER_END = re.compile(r"^---\s*$", re.MULTILINE)


class SkillLoaderError(ValueError):
    """Skill 文档布局、元数据或访问请求不符合约束。"""


def list_skills(
    skills_root: Path,
    *,
    category: str | None = None,
) -> list[dict[str, Any]]:
    """返回项目内所有有效 Skill 的轻量目录信息。"""
    root = _resolve_root(skills_root)
    normalized_category = _normalize_optional_category(category)
    entries: list[tuple[dict[str, Any], Path]] = []

    for manifest_path in _iter_manifests(root):
        skill_dir = _resolve_within_root(manifest_path.parent, root)
        relative_dir = skill_dir.relative_to(root)
        resolved_category = (
            relative_dir.parts[0] if len(relative_dir.parts) > 1 else ""
        )
        if (
            normalized_category is not None
            and resolved_category != normalized_category
        ):
            continue

        metadata = _parse_metadata(manifest_path)
        entries.append(
            (
                {
                    "id": metadata["name"],
                    "name": metadata["name"],
                    "description": metadata["description"],
                    "category": resolved_category,
                    "tags": metadata["tags"],
                    "path": relative_dir.as_posix(),
                },
                skill_dir,
            )
        )

    _raise_on_duplicate_ids(entries)
    return [
        entry
        for entry, _ in sorted(entries, key=lambda item: item[0]["id"])
    ]


def load_skill(
    skills_root: Path,
    skill_id: str,
    *,
    file_path: str | None = None,
) -> dict[str, Any]:
    """读取一个 Skill 的入口文档，或其允许范围内的关联文件。"""
    root = _resolve_root(skills_root)
    normalized_id = _require_non_blank_string(skill_id, "skill_id")
    matches = _find_skill_directories(root, normalized_id)
    if not matches:
        raise SkillLoaderError(f"未找到 Skill：{normalized_id}")
    if len(matches) > 1:
        paths = ", ".join(
            path.relative_to(root).as_posix() for path in matches
        )
        raise SkillLoaderError(f"Skill 名称重复：{normalized_id}（{paths}）")

    skill_dir = matches[0]
    manifest_path = skill_dir / "SKILL.md"
    metadata = _parse_metadata(manifest_path)
    if file_path is None:
        content, truncated = _read_text(manifest_path)
        return {
            "id": metadata["name"],
            "name": metadata["name"],
            "description": metadata["description"],
            "path": skill_dir.relative_to(root).as_posix(),
            "file_path": "SKILL.md",
            "content": content,
            "truncated": truncated,
            "linked_files": _list_linked_files(skill_dir),
        }

    target_path = _resolve_linked_file(skill_dir, file_path)
    content, truncated = _read_text(target_path)
    return {
        "id": metadata["name"],
        "name": metadata["name"],
        "path": skill_dir.relative_to(root).as_posix(),
        "file_path": target_path.relative_to(skill_dir).as_posix(),
        "content": content,
        "truncated": truncated,
    }


def _resolve_root(skills_root: Path) -> Path:
    root = Path(skills_root).expanduser().resolve(strict=False)
    if not root.is_dir():
        raise SkillLoaderError(f"Skill 根目录不存在：{root}")
    return root


def _iter_manifests(skills_root: Path):
    for current_root, directory_names, file_names in os.walk(skills_root):
        directory_names[:] = [
            name
            for name in directory_names
            if name not in _EXCLUDED_DIRECTORIES
        ]
        if "SKILL.md" in file_names:
            yield Path(current_root) / "SKILL.md"


def _parse_metadata(manifest_path: Path) -> dict[str, Any]:
    content, _ = _read_text(manifest_path, limit=None)
    if not content.startswith("---\n"):
        raise SkillLoaderError(f"Skill 缺少 YAML Frontmatter：{manifest_path}")

    match = _FRONTMATTER_END.search(content, pos=4)
    if match is None:
        raise SkillLoaderError(f"Skill Frontmatter 未闭合：{manifest_path}")
    try:
        frontmatter = yaml.safe_load(content[4 : match.start()])
    except yaml.YAMLError as exc:
        raise SkillLoaderError(
            f"Skill Frontmatter 无法解析：{manifest_path}"
        ) from exc
    if not isinstance(frontmatter, dict):
        raise SkillLoaderError(
            f"Skill Frontmatter 必须是映射：{manifest_path}"
        )

    name = _require_non_blank_string(frontmatter.get("name"), "name")
    description = _require_non_blank_string(
        frontmatter.get("description"),
        "description",
    )
    metadata = frontmatter.get("metadata")
    agent_metadata = (
        metadata.get("cmo_lua_agent")
        if isinstance(metadata, dict)
        else {}
    )
    raw_tags = (
        agent_metadata.get("tags", [])
        if isinstance(agent_metadata, dict)
        else []
    )
    if isinstance(raw_tags, str):
        raw_tags = [raw_tags]
    if (
        not isinstance(raw_tags, list)
        or not all(isinstance(tag, str) for tag in raw_tags)
    ):
        raise SkillLoaderError(
            f"Skill tags 必须是字符串列表：{manifest_path}"
        )
    return {
        "name": name,
        "description": description,
        "tags": [tag.strip() for tag in raw_tags if tag.strip()],
    }


def _find_skill_directories(skills_root: Path, skill_id: str) -> list[Path]:
    matches: list[Path] = []
    for manifest_path in _iter_manifests(skills_root):
        skill_dir = _resolve_within_root(manifest_path.parent, skills_root)
        if _parse_metadata(manifest_path)["name"] == skill_id:
            matches.append(skill_dir)
    return matches


def _raise_on_duplicate_ids(entries: list[tuple[dict[str, Any], Path]]) -> None:
    ids: dict[str, list[Path]] = {}
    for entry, path in entries:
        ids.setdefault(entry["id"], []).append(path)
    duplicates = {
        name: paths for name, paths in ids.items() if len(paths) > 1
    }
    if duplicates:
        details = "; ".join(
            f"{name}: {', '.join(path.as_posix() for path in paths)}"
            for name, paths in sorted(duplicates.items())
        )
        raise SkillLoaderError(f"Skill 名称重复：{details}")


def _list_linked_files(skill_dir: Path) -> dict[str, list[str]]:
    linked_files: dict[str, list[str]] = {}
    for directory_name in _LINKED_DIRECTORIES:
        directory = skill_dir / directory_name
        if not directory.is_dir():
            continue
        files = [
            path.relative_to(skill_dir).as_posix()
            for path in directory.rglob("*")
            if path.is_file()
            and path.suffix.casefold() in _READABLE_SUFFIXES
            and _is_within(path, skill_dir)
        ]
        if files:
            linked_files[directory_name] = sorted(files)
    return linked_files


def _resolve_linked_file(skill_dir: Path, file_path: str) -> Path:
    raw_path = _require_non_blank_string(file_path, "file_path")
    candidate = Path(raw_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise SkillLoaderError(
            "file_path 必须是 Skill 目录内的相对路径"
        )
    if (
        not candidate.parts
        or candidate.parts[0] not in _LINKED_DIRECTORIES
    ):
        raise SkillLoaderError(
            "只能读取 references、templates、scripts 或 assets 中的文件"
        )
    target = _resolve_within_root(skill_dir / candidate, skill_dir)
    if not target.is_file():
        raise SkillLoaderError(f"Skill 关联文件不存在：{raw_path}")
    if target.suffix.casefold() not in _READABLE_SUFFIXES:
        raise SkillLoaderError(
            f"Skill 关联文件不是允许的文本类型：{raw_path}"
        )
    return target


def _resolve_within_root(path: Path, root: Path) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise SkillLoaderError(f"Skill 路径无法解析：{path}") from exc
    if not _is_within(resolved, root):
        raise SkillLoaderError(f"Skill 路径越出根目录：{path}")
    return resolved


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (OSError, ValueError):
        return False
    return True


def _read_text(
    path: Path,
    *,
    limit: int | None = _MAX_CONTENT_CHARS,
) -> tuple[str, bool]:
    try:
        content = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise SkillLoaderError(f"无法读取 Skill 文件：{path}") from exc
    if limit is None or len(content) <= limit:
        return content, False
    return content[:limit], True


def _normalize_optional_category(category: str | None) -> str | None:
    if category is None:
        return None
    normalized = _require_non_blank_string(category, "category")
    if (
        "/" in normalized
        or "\\" in normalized
        or normalized in {".", ".."}
    ):
        raise SkillLoaderError("category 必须是单层目录名称")
    return normalized


def _require_non_blank_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SkillLoaderError(f"{field_name} 必须是非空字符串")
    return value.strip()
