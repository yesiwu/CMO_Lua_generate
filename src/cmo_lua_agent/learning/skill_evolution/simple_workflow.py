"""Simplified Phase 8: aggregate experiences, author Markdown, create Pending."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from cmo_lua_agent.learning.store import ExperienceStore

from .aggregation import ExperienceAggregator
from .catalog import ExperienceKeyCatalog
from .markdown_author import MarkdownSkillAuthorAgent, validate_skill_markdown
from .promotion import PromotionProfile
from .validation import ExperienceValidationService


def _write(path: Path, value: object) -> None:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent) as handle:
        handle.write(text)
        tmp = handle.name
    os.replace(tmp, path)


def _with_managed_frontmatter(markdown: str) -> str:
    body = markdown
    if body.startswith("---\n"):
        closing = body.find("\n---\n", 4)
        if closing >= 0:
            body = body[closing + 5:]
    frontmatter = "\n".join((
        "---",
        "name: naval-air-anti-surface-tactical-patterns",
        "description: Use when planning a naval-air anti-surface strike involving aircraft survivability, attack-route selection, ammunition reserve, or surface-and-air target deconfliction.",
        "---",
        "",
    ))
    return frontmatter + body.lstrip()


def run_simple_phase8(*, phase8_run_id: str, runs_root: Path, experience_root: Path, skills_root: Path, author: MarkdownSkillAuthorAgent) -> dict[str, object]:
    store = ExperienceStore(experience_root)
    records = []
    for path in sorted(store.records.glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, dict) and "experience_id" in value:
            records.append(value)
    aggregation = ExperienceAggregator(ExperienceKeyCatalog.default()).aggregate(tuple(records))
    validator = ExperienceValidationService(PromotionProfile.default())
    validated = tuple(validator.validate(item) for item in aggregation.aggregates)
    output = Path(runs_root) / phase8_run_id / "skill-evolution"
    _write(output / "experience-aggregates.json", aggregation.to_dict())
    _write(output / "validated-experiences.json", [item.to_dict() for item in validated])
    eligible = [(aggregate, item) for aggregate, item in zip(aggregation.aggregates, validated, strict=True) if item.eligible]
    result: dict[str, object] = {"phase8_run_id": phase8_run_id, "aggregate_count": len(aggregation.aggregates), "eligible_experience_count": len(eligible), "pending_packages": [], "status": "NO_PROMOTABLE_EXPERIENCE"}
    if not eligible:
        _write(output / "phase8-result.json", result)
        return result
    skill_id = "anti_surface_strike.tactical_patterns"
    current = skills_root / "curated" / skill_id / "current.json"
    version = "0.1.0"
    if current.is_file():
        version = f"0.{int(str(json.loads(current.read_text(encoding='utf-8')).get('version', '0.0.0')).split('.')[1]) + 1}.0"
    source_ids = tuple(sorted({experience_id for aggregate, _ in eligible for evidence in (*aggregate.supporting_evidence, *aggregate.contradicting_evidence, *aggregate.qualifying_evidence) for experience_id in evidence.experience_ids}))
    markdown = author.create(skill_id=skill_id, mission_type="naval_air_anti_surface", hypotheses=tuple(item.canonical_hypothesis for _, item in eligible), source_experience_ids=source_ids)
    markdown = _with_managed_frontmatter(markdown)
    package = skills_root / "pending" / skill_id / version
    valid, errors = validate_skill_markdown(markdown)
    _write(package / "SKILL.md", markdown)
    _write(package / "metadata.json", {"skill_id": skill_id, "version": version, "status": "pending", "mission_type": "naval_air_anti_surface", "source_experience_ids": list(source_ids), "created_by": "SkillAuthorAgent"})
    _write(package / "validation-report.json", {"static_validation_passed": valid, "errors": list(errors), "cmo_effectiveness_validation": "not_run"})
    index = skills_root / "indexes" / "pending.jsonl"
    existing = index.read_text(encoding="utf-8") if index.is_file() else ""
    row = json.dumps({"skill_id": skill_id, "version": version, "mission_type": "naval_air_anti_surface", "path": str(package.relative_to(skills_root)), "status": "pending"}, ensure_ascii=False, sort_keys=True) + "\n"
    if row not in existing:
        _write(index, existing + row)
    result.update({"status": "pending_review", "pending_packages": [str(package)], "author_invocations": 1})
    _write(output / "phase8-result.json", result)
    return result
