from __future__ import annotations

import pytest
from cmo_lua_agent.skill_evolution_errors import SkillEvolutionError

from cmo_lua_agent.agents import SkillAuthorAgent
from cmo_lua_agent.agents.skill_author_agent import (
    SkillAuthorContext,
    SkillDraftContent,
    SkillRevisionProposal,
)


class _Client:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls = 0
        self.prompts: list[str] = []

    def complete_json(self, *, system: str, prompt: str) -> object:
        self.calls += 1
        self.prompts.append(prompt)
        return self.response


def _rule(
    key: str = "target_deconfliction.avoid_duplicate_target",
    slots: list[str] | None = None,
) -> dict:
    return {
        "rule_key": key,
        "statement": "避免多个攻击单元无意重复选择同一首要目标",
        "source_slots": slots or ["support_01"],
    }


def _draft_response() -> dict:
    return {
        "title": "海空协同反舰策略模式",
        "description": "面向 StrategySpec 的受控战术规划规则。",
        "when_to_use": [_rule("target_deconfliction.when_multi_platform")],
        "strategy_patterns": [_rule()],
        "conditions": [_rule("target_deconfliction.require_multiple_targets")],
        "counterexamples": [
            _rule(
                "target_deconfliction.single_priority_exception",
                ["qualify_01"],
            )
        ],
        "verification_rules": [
            _rule("target_deconfliction.verify_assignments")
        ],
    }


def _context(*, active: bool = False) -> SkillAuthorContext:
    return SkillAuthorContext(
        family="cmo_naval_air_strategy_patterns",
        mission_type="naval_air_anti_surface",
        canonical_hypotheses=(
            "避免舰艇与舰载机无意重复分配同一首要目标",
        ),
        source_slots={
            "support_01": ("exp-1",),
            "qualify_01": ("exp-2",),
        },
        active_skill_summary={"version": "0.1.0"} if active else None,
        maximum_rules=20,
    )


def test_create_returns_strict_structured_draft_once() -> None:
    client = _Client(_draft_response())
    result = SkillAuthorAgent(client).create(_context())

    assert isinstance(result, SkillDraftContent)
    assert result.strategy_patterns[0].source_slots == ("support_01",)
    assert client.calls == 1
    assert "exp-1" not in client.prompts[0]


def test_create_rejects_extra_fields() -> None:
    response = _draft_response()
    response["version"] = "9.0.0"
    with pytest.raises(SkillEvolutionError) as captured:
        SkillAuthorAgent(_Client(response)).create(_context())
    assert captured.value.error_code == "skill_author_unsupported_fields"


def test_create_rejects_unknown_source_slot() -> None:
    response = _draft_response()
    response["strategy_patterns"] = [_rule(slots=["evidence-real-id"])]
    with pytest.raises(SkillEvolutionError) as captured:
        SkillAuthorAgent(_Client(response)).create(_context())
    assert captured.value.error_code == "skill_author_source_slot_unknown"


@pytest.mark.parametrize(
    "statement",
    (
        "```lua\nScenEdit_AttackContact()\n```",
        "运行 python tool.py",
        "调用 ScenEdit_SetAction",
    ),
)
def test_create_rejects_lua_api_and_runtime_commands(statement: str) -> None:
    response = _draft_response()
    response["strategy_patterns"][0]["statement"] = statement
    with pytest.raises(SkillEvolutionError) as captured:
        SkillAuthorAgent(_Client(response)).create(_context())
    assert captured.value.error_code == (
        "skill_author_executable_content_forbidden"
    )


def test_revision_allows_only_controlled_section_operations() -> None:
    client = _Client({
        "operations": [
            {
                "operation": "add_counterexample",
                "rule": _rule(
                    "target_deconfliction.new_exception",
                    ["qualify_01"],
                ),
            },
            {
                "operation": "replace_description",
                "description": "更新后的受控说明。",
            },
        ]
    })
    result = SkillAuthorAgent(client).revise(_context(active=True))

    assert isinstance(result, SkillRevisionProposal)
    assert [item.operation for item in result.operations] == [
        "add_counterexample",
        "replace_description",
    ]


def test_revision_rejects_delete_or_full_rewrite() -> None:
    response = {
        "operations": [
            {
                "operation": "delete_strategy_pattern",
                "rule_key": "target_deconfliction.old",
            }
        ]
    }
    with pytest.raises(SkillEvolutionError) as captured:
        SkillAuthorAgent(_Client(response)).revise(_context(active=True))
    assert captured.value.error_code == (
        "skill_author_revision_operation_unsupported"
    )
