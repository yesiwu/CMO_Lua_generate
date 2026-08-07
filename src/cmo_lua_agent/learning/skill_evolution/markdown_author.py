"""Direct Markdown authoring for simplified Phase 8 Pending Skills."""
from __future__ import annotations

import json
import re
from typing import Protocol

from .errors import fail


class MarkdownCompletionClient(Protocol):
    def complete_text(self, *, system: str, prompt: str) -> str: ...


_REQUIRED = (
    "# ",
    "## Quick Reference",
    "## When To Use",
    "## Strategy Patterns",
    "## Counterexamples",
)
_FRONTMATTER = re.compile(r"\A---\n(?P<body>.*?)\n---\n", re.DOTALL)
_FORBIDDEN = re.compile(
    r"```(?:lua|powershell|bash|shell)|\bscenedit_[a-z0-9_]*\b|"
    r"\b(?:python|powershell|cmd|bash|sh)\s+[\w./\\-]+|[A-Za-z]:\\",
    re.IGNORECASE,
)


def validate_skill_markdown(markdown: str) -> tuple[bool, tuple[str, ...]]:
    if not isinstance(markdown, str) or not markdown.strip():
        return False, ("markdown_empty",)
    errors = [f"missing_section:{header}" for header in _REQUIRED if header not in markdown]
    frontmatter = _FRONTMATTER.match(markdown)
    if frontmatter is None:
        errors.append("missing_frontmatter")
    else:
        body = frontmatter.group("body")
        for field in ("name:", "description:"):
            if field not in body:
                errors.append(f"missing_frontmatter_field:{field[:-1]}")
    if len(markdown) > 16000:
        errors.append("markdown_too_long")
    if _FORBIDDEN.search(markdown):
        errors.append("executable_or_path_content_forbidden")
    return not errors, tuple(errors)


class MarkdownSkillAuthorAgent:
    def __init__(self, client: MarkdownCompletionClient) -> None:
        self._client = client

    def create(
        self,
        *,
        skill_id: str,
        mission_type: str,
        hypotheses: tuple[str, ...],
        source_experience_ids: tuple[str, ...],
    ) -> str:
        prompt = json.dumps({
            "skill_id": skill_id,
            "mission_type": mission_type,
            "validated_hypotheses": list(hypotheses),
            "source_experience_ids": list(source_experience_ids),
            "required_markdown_sections": [
                "# <title>", "## When To Use", "## Strategy Patterns", "## Counterexamples",
            ],
        }, ensure_ascii=False, sort_keys=True)
        text = self._client.complete_text(system=_SYSTEM, prompt=prompt)
        valid, errors = validate_skill_markdown(text)
        if not valid:
            raise fail("skill_markdown_static_validation_failed", errors[0])
        return text


_SYSTEM = """Write one concise CMO planning SKILL.md in Markdown only.
Start with YAML frontmatter containing only name and description. The description must start with "Use when" and state the planning situation that should trigger loading this skill.
Use exactly these headings: # title, ## Quick Reference, ## When To Use, ## Strategy Patterns, ## Counterexamples.
Use short ### subsections under Strategy Patterns, grouped by capability. The Quick Reference must be a compact summary.
Use only StrategySpec-level tactical guidance. Do not include Lua, ScenEdit APIs, shell commands,
absolute paths, run IDs, exact experimental scores, invented numeric tactics, metadata JSON, or claims of proven causality."""
