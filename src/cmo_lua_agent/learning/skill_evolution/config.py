"""Storage configuration for mutable Phase 8 Skill assets."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .errors import fail


class SkillStoreMode(StrEnum):
    PRODUCTION = "production"
    TEST = "test"


@dataclass(frozen=True, slots=True)
class SkillStorageConfig:
    project_root: Path
    root: Path
    mode: SkillStoreMode

    @classmethod
    def production(cls, project_root: Path) -> "SkillStorageConfig":
        project = Path(project_root).resolve()
        return cls(
            project_root=project,
            root=project / "data" / "skills",
            mode=SkillStoreMode.PRODUCTION,
        )

    @classmethod
    def test(cls, root: Path) -> "SkillStorageConfig":
        resolved = Path(root).resolve()
        return cls(
            project_root=resolved.parent,
            root=resolved,
            mode=SkillStoreMode.TEST,
        )

    def validate(self) -> None:
        root = self.root.resolve()
        if self.mode is SkillStoreMode.PRODUCTION:
            project = self.project_root.resolve()
            expected = (project / "data" / "skills").resolve()
            forbidden = tuple(
                (project / name).resolve()
                for name in ("src", "tests", "runs")
            )
            bootstrap = (
                project
                / "src"
                / "cmo_lua_agent"
                / "skills"
                / "bootstrap"
            ).resolve()
            if root != expected:
                raise fail(
                    "production_skill_root_invalid",
                    "生产 Skill Store 必须固定为项目 data/skills",
                )
            if any(path == root or path in root.parents for path in (*forbidden, bootstrap)):
                raise fail(
                    "production_skill_root_forbidden",
                    "生产 Skill Store 不得位于源码、测试、运行或 Bootstrap 目录",
                )
        elif root.name == "skills" and root.parent.name == "data":
            # Test mode is explicit; a real project data/skills directory must not
            # accidentally be opened as a fixture store.
            project_marker = root.parent.parent / "src" / "cmo_lua_agent"
            if project_marker.is_dir():
                raise fail(
                    "test_store_targets_production",
                    "测试 Store 不得指向真实项目 data/skills",
                )

    @property
    def provenance(self) -> str:
        return (
            "production"
            if self.mode is SkillStoreMode.PRODUCTION
            else "test_fixture"
        )
