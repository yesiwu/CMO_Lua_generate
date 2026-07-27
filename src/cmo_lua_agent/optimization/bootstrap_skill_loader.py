"""Read and freeze the one human-authored Phase 6 bootstrap skill."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any

from cmo_lua_agent.optimization.phase6_models import BootstrapSkillSnapshot

_MAX_CONTENT_CHARS = 48_000


class BootstrapSkillLoader:
    def __init__(self, project_root: Path) -> None:
        self._root = Path(project_root).resolve()

    def load(self, relative_path: str) -> BootstrapSkillSnapshot:
        source = Path(relative_path)
        if source.is_absolute() or ".." in source.parts:
            raise ValueError("bootstrap skill path must be project-relative")
        resolved = (self._root / source).resolve()
        if self._root not in resolved.parents or not resolved.is_file():
            raise ValueError("bootstrap skill path is outside the project or missing")
        content = resolved.read_text(encoding="utf-8")
        if not content.strip() or len(content) > _MAX_CONTENT_CHARS:
            raise ValueError("bootstrap skill content is empty or too large")
        metadata = _parse_frontmatter(content)
        required = ("skill_id", "version", "status", "source", "evidence_level", "consumer")
        if any(not metadata.get(key) for key in required):
            raise ValueError("bootstrap skill has incomplete frontmatter")
        if metadata["status"] != "bootstrap" or metadata["source"] != "human-authored":
            raise ValueError("bootstrap skill must be human-authored bootstrap content")
        consumers = tuple(metadata["consumer"] if isinstance(metadata["consumer"], list) else [metadata["consumer"]])
        if "StrategyProposalAgent" not in consumers:
            raise ValueError("bootstrap skill is not for StrategyProposalAgent")
        return BootstrapSkillSnapshot(
            skill_id=str(metadata["skill_id"]), version=str(metadata["version"]), status="bootstrap",
            source="human-authored", evidence_level=str(metadata["evidence_level"]), consumer=consumers,
            source_path=resolved.relative_to(self._root).as_posix(), content=content,
            checksum=sha256(content.encode("utf-8")).hexdigest(),
        )


def _parse_frontmatter(content: str) -> dict[str, Any]:
    if not content.startswith("---\n"):
        raise ValueError("bootstrap skill must start with YAML frontmatter")
    end = content.find("\n---", 4)
    if end < 0:
        raise ValueError("bootstrap skill frontmatter is incomplete")
    lines = content[4:end].splitlines()
    parsed: dict[str, Any] = {}
    active_list: str | None = None
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - "):
            if active_list is None:
                raise ValueError("invalid frontmatter list")
            parsed.setdefault(active_list, []).append(line[4:].strip())
            continue
        if ":" not in line:
            raise ValueError("invalid frontmatter entry")
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        if not key:
            raise ValueError("invalid frontmatter key")
        active_list = key
        parsed[key] = value if value else []
    return parsed
