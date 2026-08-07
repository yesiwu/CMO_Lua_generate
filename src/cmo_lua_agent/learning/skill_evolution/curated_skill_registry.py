"""Read-only discovery and loading for simplified curated Markdown Skills."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CuratedSkillRegistryError(ValueError):
    """Raised when a curated Skill cannot be resolved from its current pointer."""


class CuratedSkillRegistry:
    """Scan current curated Skill versions without loading every Markdown body."""

    def __init__(self, skills_root: Path) -> None:
        self._root = Path(skills_root).resolve()
        self._curated = self._root / "curated"

    def list_summaries(self, *, mission_type: str | None = None) -> tuple[dict[str, str], ...]:
        summaries: list[dict[str, str]] = []
        if not self._curated.is_dir():
            return ()
        for base in sorted(path for path in self._curated.iterdir() if path.is_dir()):
            current_path = base / "current.json"
            if not current_path.is_file():
                continue
            current = _object(current_path)
            skill_id = _required_text(current, "skill_id", current_path)
            relative = _required_text(current, "relative_path", current_path)
            version = _required_text(current, "version", current_path)
            description = _required_text(current, "description", current_path)
            version_path = (base / relative).resolve()
            if base.resolve() not in version_path.parents:
                raise CuratedSkillRegistryError("curated_skill_path_escape")
            metadata = _object(version_path / "metadata.json")
            if _required_text(metadata, "skill_id", version_path / "metadata.json") != skill_id:
                raise CuratedSkillRegistryError("curated_skill_id_mismatch")
            item_mission_type = _required_text(metadata, "mission_type", version_path / "metadata.json")
            if mission_type is not None and item_mission_type != mission_type:
                continue
            summaries.append({
                "skill_id": skill_id,
                "version": version,
                "mission_type": item_mission_type,
                "description": description,
            })
        return tuple(summaries)

    def view(self, skill_id: str) -> dict[str, str]:
        if not isinstance(skill_id, str) or not skill_id.strip():
            raise CuratedSkillRegistryError("curated_skill_id_invalid")
        target = skill_id.strip()
        for summary in self.list_summaries():
            if summary["skill_id"] == target:
                base = self._curated / target
                current = _object(base / "current.json")
                skill_path = (base / _required_text(current, "relative_path", base / "current.json") / "SKILL.md").resolve()
                if base.resolve() not in skill_path.parents or not skill_path.is_file():
                    raise CuratedSkillRegistryError("curated_skill_content_missing")
                return {**summary, "content": skill_path.read_text(encoding="utf-8")}
        raise CuratedSkillRegistryError("curated_skill_not_found")


def _object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise CuratedSkillRegistryError("curated_skill_metadata_missing")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CuratedSkillRegistryError("curated_skill_metadata_invalid") from exc
    if not isinstance(value, dict):
        raise CuratedSkillRegistryError("curated_skill_metadata_invalid")
    return value


def _required_text(value: dict[str, Any], field: str, path: Path) -> str:
    item = value.get(field)
    if not isinstance(item, str) or not item.strip():
        raise CuratedSkillRegistryError(f"curated_skill_{field}_invalid:{path.name}")
    return item.strip()
