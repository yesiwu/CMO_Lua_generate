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


_SYSTEM = """只用 Markdown 编写一份简洁的 CMO 规划 SKILL.md。
开头必须是仅包含 name 和 description 的 YAML frontmatter。description 必须以 "Use when" 开头，
并说明何种规划情境应加载此技能。
必须且只能使用以下标题：# title、## Quick Reference、## When To Use、## Strategy Patterns、## Counterexamples。
Strategy Patterns 下使用简短的 ### 小节，并按能力分组；Quick Reference 必须是紧凑摘要。
只能提供 StrategySpec 层级的战术指导。不得包含 Lua、ScenEdit API、shell 命令、绝对路径、
run ID、精确实验分数、虚构的数值战术、metadata JSON 或已证实因果关系的声明。"""
