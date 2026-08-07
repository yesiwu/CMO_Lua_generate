from __future__ import annotations

import json

from cmo_lua_agent.learning.skill_evolution.markdown_author import validate_skill_markdown
from cmo_lua_agent.learning.skill_evolution.simple_workflow import run_simple_phase8


class _Author:
    def create(self, **_kwargs: object) -> str:
        return "---\nname: test-skill\ndescription: Test description\nversion: 0.1.0\nstatus: pending\nmission_type: naval_air_anti_surface\nmetadata:\n  tags: [attacks]\n  capabilities: [attacks.target_assignment]\n---\n# Test Skill\n\n## Quick Reference\n- Use controlled target assignment.\n\n## When To Use\n- Use for valid planning.\n\n## Strategy Patterns\n### Target Assignment\n- Use controlled target assignment.\n\n## Counterexamples\n- Do not use for invalid targets.\n"


def test_simple_phase8_writes_only_minimal_pending_package(tmp_path) -> None:
    records = tmp_path / "data" / "experiences" / "records"
    records.mkdir(parents=True)
    for index in (1, 2):
        (records / f"exp-{index}.json").write_text(json.dumps({
            "experience_id": f"exp-{index}", "experience_key": "naval_air_anti_surface.fire_quantity",
            "experience_type": "tactical_positive", "evidence_stance": "support",
            "source_optimization_id": f"opt-{index}", "evidence_quality": 0.8,
            "model_confidence": 0.8, "execution_success": True, "semantic_valid": True,
            "execution_fidelity": "verified", "observed_effect": {"score_delta_vs_baseline": 20},
            "environment": {"mission_type": "naval_air_anti_surface", "score_source": "execution_summary", "scenario_id": "s"},
            "evidence_refs": ["runs/x/execution-summary.json"],
        }), encoding="utf-8")
    result = run_simple_phase8(phase8_run_id="simple", runs_root=tmp_path / "runs", experience_root=tmp_path / "data" / "experiences", skills_root=tmp_path / "data" / "skills", author=_Author())
    package = tmp_path / "data" / "skills" / "pending" / "anti_surface_strike.tactical_patterns" / "0.1.0"
    assert result["status"] == "pending_review"
    assert {item.name for item in package.iterdir()} == {"SKILL.md", "metadata.json", "validation-report.json"}
    skill = (package / "SKILL.md").read_text(encoding="utf-8")
    assert "name: naval-air-anti-surface-tactical-patterns" in skill
    assert "description: Use when planning a naval-air anti-surface strike involving aircraft survivability" in skill
    assert "version:" not in skill
    assert "status:" not in skill
    assert "mission_type:" not in skill
    assert "metadata:" not in skill


def test_markdown_validator_rejects_lua_and_missing_sections() -> None:
    valid, errors = validate_skill_markdown("# x\n```lua\nend\n```")
    assert not valid
    assert "executable_or_path_content_forbidden" in errors


def test_markdown_validator_accepts_hermes_style_minimal_frontmatter() -> None:
    markdown = """---
name: naval-air-anti-surface-tactical-patterns
description: Use when planning a naval-air anti-surface strike involving aircraft survivability.
---
# Naval Air Anti-Surface Tactical Patterns

## Quick Reference
- Preserve aircraft while deconflicting targets.

## When To Use
- Use for a coordinated naval-air strike.

## Strategy Patterns
- Plan target assignments deliberately.

## Counterexamples
- Do not treat a single result as proof.
"""
    assert validate_skill_markdown(markdown) == (True, ())
