"""
受控的Phase8技能编写智能体。
该智能体负责生成结构化的StrategySpec规划规则。
**职责边界**：仅产出技能规则草稿；不参与晋升判定、版本管理、证据标识、文件路径、人工审批、运行时行为决策。
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from cmo_lua_agent.skill_evolution_errors import fail


class SkillAuthorJsonClient(Protocol):
    """
    LLM JSON调用客户端协议
    定义统一接口，用于注入不同大模型实现，方便单元测试Mock
    """
    def complete_json(self, *, system: str, prompt: str) -> object: ...


@dataclass(frozen=True, slots=True)
class SkillRule:
    """
    单条战术规则实体
    rule_key：唯一规则标识
    statement：自然语言战术规则描述
    source_slots：规则依赖的数据源插槽列表（溯源绑定经验证据）
    """
    rule_key: str
    statement: str
    source_slots: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SkillDraftContent:
    """
    完整技能草稿实体（新建技能输出结构）
    划分固定章节，保证所有技能文档结构统一
    """
    title: str                                  # 技能标题
    description: str                            # 技能总体描述
    when_to_use: tuple[SkillRule, ...]          # 适用场景判定规则
    strategy_patterns: tuple[SkillRule, ...]    # 核心战术模式规则
    conditions: tuple[SkillRule, ...]           # 生效前置约束条件
    counterexamples: tuple[SkillRule, ...]      # 反例/不适用场景
    verification_rules: tuple[SkillRule, ...]   # 结果校验规则

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "when_to_use": [item.to_dict() for item in self.when_to_use],
            "strategy_patterns": [
                item.to_dict() for item in self.strategy_patterns
            ],
            "conditions": [item.to_dict() for item in self.conditions],
            "counterexamples": [
                item.to_dict() for item in self.counterexamples
            ],
            "verification_rules": [
                item.to_dict() for item in self.verification_rules
            ],
        }


@dataclass(frozen=True, slots=True)
class SkillRevisionOperation:
    """
    技能修订单条操作
    operation：操作类型；仅支持新增规则、替换描述
    """
    operation: str
    rule: SkillRule | None = None
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {"operation": self.operation}
        if self.rule is not None:
            value["rule"] = self.rule.to_dict()
        if self.description is not None:
            value["description"] = self.description
        return value


@dataclass(frozen=True, slots=True)
class SkillRevisionProposal:
    """
    技能修订提案
    多条修订操作集合，Phase8采用**增量追加模式**：禁止删除、修改已有规则
    """
    operations: tuple[SkillRevisionOperation, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"operations": [item.to_dict() for item in self.operations]}


@dataclass(frozen=True, slots=True)
class SkillAuthorContext:
    """
    技能生成上下文，输入给LLM的全部受控信息
    """
    family: str                                  # 所属技能家族ID
    mission_type: str                            # 任务类型
    canonical_hypotheses: tuple[str, ...]        # 本轮参与构建技能的标准经验假说
    source_slots: dict[str, tuple[str, ...]]     # 可用数据源插槽集合（LLM只能使用这些插槽）
    active_skill_summary: dict[str, Any] | None  # 当前线上生效技能摘要；新建技能为None
    maximum_rules: int = 40                      # 单份技能最大规则条数上限

    def to_prompt_dict(self) -> dict[str, Any]:
        """序列化为送入LLM Prompt的结构化上下文"""
        return {
            "family": self.family,
            "mission_type": self.mission_type,
            "canonical_hypotheses": list(self.canonical_hypotheses),
            "available_source_slots": sorted(self.source_slots),
            "active_skill_summary": self.active_skill_summary,
            "maximum_rules": self.maximum_rules,
            "response_contract": {
                "top_level_fields": [
                    "title",
                    "description",
                    "when_to_use",
                    "strategy_patterns",
                    "conditions",
                    "counterexamples",
                    "verification_rules",
                ],
                "rule_fields": [
                    "rule_key",
                    "statement",
                    "source_slots",
                ],
                "forbidden_fields": [
                    "evidence",
                    "evidence_refs",
                    "confidence",
                    "rationale",
                    "metadata",
                    "version",
                ],
            },
        }


# 技能草稿合法顶层字段集合
_DRAFT_FIELDS = {
    "title",
    "description",
    "when_to_use",
    "strategy_patterns",
    "conditions",
    "counterexamples",
    "verification_rules",
}
# 单条规则合法字段集合
_RULE_FIELDS = {"rule_key", "statement", "source_slots"}
# 规则标识正则：小写开头，支持多级命名空间 a.b.c
_RULE_KEY = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
# 禁止内容正则：拦截代码块、ScenEdit接口、命令行指令，防止LLM输出可执行代码
_FORBIDDEN_CONTENT = re.compile(
    r"```(?:lua|powershell|bash|shell)|\bscenedit_[a-z0-9_]*\b|"
    r"\b(?:python|powershell|cmd|bash|sh)\s+[\w./\\-]+",
    re.IGNORECASE,
)
# 允许的新增类修订操作
_ADD_OPERATIONS = {
    "add_strategy_pattern",
    "add_condition",
    "add_counterexample",
    "add_verification_rule",
}


class SkillAuthorAgent:
    """
    Phase8技能编写智能体核心实现
    两大能力：
    create：从零生成全新技能草稿
    revise：基于现有线上技能生成增量修订提案（只允许追加、更新描述，禁止修改旧规则）
    内置严格JSON结构校验、内容安全校验、插槽合法性校验，约束LLM输出边界
    """
    def __init__(self, client: SkillAuthorJsonClient) -> None:
        self._client = client

    def create(self, context: SkillAuthorContext) -> SkillDraftContent:
        """
        创建全新技能草稿
        :param context: 生成上下文
        :return: 标准化技能草稿实体
        """
        response = self._client.complete_json(
            system=_CREATE_SYSTEM,
            prompt=json.dumps(
                context.to_prompt_dict(),
                ensure_ascii=False,
                sort_keys=True,
            ),
        )
        return self._parse_draft(response, context)

    def revise(self, context: SkillAuthorContext) -> SkillRevisionProposal:
        """
        生成技能增量修订提案
        :param context: 生成上下文（必须携带当前生效技能摘要）
        :return: 修订提案
        """
        if context.active_skill_summary is None:
            raise fail(
                "skill_author_active_skill_required",
                "执行修订操作必须提供当前生效技能摘要",
            )
        response = self._client.complete_json(
            system=_REVISE_SYSTEM,
            prompt=json.dumps(
                context.to_prompt_dict(),
                ensure_ascii=False,
                sort_keys=True,
            ),
        )
        return self._parse_revision(response, context)

    def _parse_draft(
        self, response: object, context: SkillAuthorContext
    ) -> SkillDraftContent:
        """
        解析并校验LLM返回的新建技能JSON结果
        """
        if not isinstance(response, Mapping):
            raise fail("skill_author_schema_invalid", "技能草稿返回结果必须是JSON对象")
        if set(response) != _DRAFT_FIELDS:
            raise fail("skill_author_unsupported_fields", "技能草稿包含非法顶层字段")
        title = self._text(response["title"], "title")
        description = self._text(response["description"], "description")
        self._reject_executable(title)
        self._reject_executable(description)
        groups = {
            name: self._rules(response[name], context)
            for name in (
                "when_to_use",
                "strategy_patterns",
                "conditions",
                "counterexamples",
                "verification_rules",
            )
        }
        total = sum(len(items) for items in groups.values())
        if total == 0 or total > context.maximum_rules:
            raise fail("skill_author_rule_limit", "技能草稿规则总数超出允许范围")
        return SkillDraftContent(
            title=title,
            description=description,
            **groups,
        )

    def _parse_revision(
        self, response: object, context: SkillAuthorContext
    ) -> SkillRevisionProposal:
        """
        解析并校验LLM返回的修订提案JSON结果
        """
        if not isinstance(response, Mapping) or set(response) != {"operations"}:
            raise fail("skill_author_schema_invalid", "技能修订返回结果只能包含 operations 字段")
        rows = response["operations"]
        if not isinstance(rows, list) or not rows:
            raise fail("skill_author_schema_invalid", "技能修订操作列表不能为空")
        if len(rows) > context.maximum_rules:
            raise fail(
                "skill_author_rule_limit",
                "技能修订操作数量超限",
            )
        result: list[SkillRevisionOperation] = []
        for row in rows:
            if not isinstance(row, Mapping):
                raise fail(
                    "skill_author_schema_invalid",
                    "非法的技能修订操作结构",
                )
            operation = str(row.get("operation", ""))
            if operation in _ADD_OPERATIONS:
                if set(row) != {"operation", "rule"}:
                    raise fail(
                        "skill_author_unsupported_fields",
                        "新增规则操作包含非法字段",
                    )
                rule = self._rule(row["rule"], context)
                result.append(SkillRevisionOperation(operation, rule=rule))
            elif operation == "replace_description":
                if set(row) != {"operation", "description"}:
                    raise fail(
                        "skill_author_unsupported_fields",
                        "描述替换操作包含非法字段",
                    )
                description = self._text(
                    row["description"], "revision description"
                )
                self._reject_executable(description)
                result.append(SkillRevisionOperation(
                    operation,
                    description=description,
                ))
            else:
                raise fail(
                    "skill_author_revision_operation_unsupported",
                    f"不支持的修订操作类型：{operation}",
                )
        return SkillRevisionProposal(tuple(result))

    def _rules(
        self, value: object, context: SkillAuthorContext
    ) -> tuple[SkillRule, ...]:
        """批量解析一组规则列表"""
        if not isinstance(value, list):
            raise fail(
                "skill_author_schema_invalid",
                "技能规则分组必须为数组",
            )
        return tuple(self._rule(row, context) for row in value)

    def _rule(
        self, value: object, context: SkillAuthorContext
    ) -> SkillRule:
        """
        解析并校验单条规则
        核心校验：rule_key格式合法、只能使用上下文中存在的source_slot
        """
        if not isinstance(value, Mapping) or set(value) != _RULE_FIELDS:
            raise fail("skill_author_unsupported_fields", "技能规则包含非法字段")
        rule_key = self._text(value["rule_key"], "rule_key")
        if not _RULE_KEY.fullmatch(rule_key):
            raise fail("skill_author_rule_key_invalid", f"非法规则标识 rule_key：{rule_key}")
        statement = self._text(value["statement"], "statement")
        self._reject_executable(statement)
        slots = value["source_slots"]
        if (
            not isinstance(slots, list)
            or not slots
            or not all(isinstance(slot, str) for slot in slots)
        ):
            raise fail("skill_author_source_slots_invalid", "source_slots 必须为非空字符串数组")
        # 去重并保持顺序
        normalized = tuple(dict.fromkeys(slots))
        unknown = set(normalized) - set(context.source_slots)
        if unknown:
            raise fail(
                "skill_author_source_slot_unknown",
                f"引用了未定义的数据源插槽：{sorted(unknown)[0]}",
            )
        return SkillRule(rule_key, statement, normalized)

    @staticmethod
    def _text(value: object, field: str) -> str:
        """校验文本字段非空，去除首尾空白"""
        if not isinstance(value, str) or not value.strip():
            raise fail(
                "skill_author_text_invalid",
                f"{field} 必须为非空字符串",
            )
        return value.strip()

    @staticmethod
    def _reject_executable(value: str) -> None:
        """拦截禁止出现的代码、命令、引擎接口"""
        if _FORBIDDEN_CONTENT.search(value):
            raise fail(
                "skill_author_executable_content_forbidden",
                "技能文本内包含禁止的可执行内容/引擎接口",
            )


# 新建技能系统提示词
_CREATE_SYSTEM = """你是受管控的Phase 8 技能编写智能体。
严格返回唯一一份JSON对象，且顶层字段必须恰好为：
"title"、"description"、"when_to_use"、"strategy_patterns"、"conditions"、"counterexamples"、"verification_rules"。
除 title 和 description 外，每个规则分组必须是数组。每个数组元素必须恰好为：
{"rule_key":"小写.分层键","statement":"StrategySpec层战术规则","source_slots":["提供的插槽名"]}。
不得输出 markdown、schema、metadata、rules、version、notes 或任何其他顶层字段。
仅编写面向CMO作战规划的StrategySpec层级战术规则。每条规则必须使用至少一个提供的数据源插槽名称。
禁止输出证据ID、文件路径、校验和、版本、状态、审批信息、Lua代码、CMO引擎接口、Shell命令、工具指令、评分规则，不得携带任何额外字段。"""

# 修订技能系统提示词
_REVISE_SYSTEM = """你是受管控的Phase 8 技能编写智能体。
仅返回包含操作列表的JSON对象。仅允许以下操作类型：add_strategy_pattern、add_condition、add_counterexample、add_verification_rule、replace_description。
不得删除、调整顺序、重写当前已生效技能内原有规则。仅可使用上下文提供的数据源插槽。
禁止输出证据ID、版本、路径、Lua代码、CMO引擎接口、各类命令、评分规则以及额外字段。"""


def skill_draft_from_dict(
    value: object,
    *,
    allowed_source_slots: tuple[str, ...] | None = None,
) -> SkillDraftContent:
    """
    从已校验的字典还原技能草稿实体，用于断点续跑，无需调用LLM
    """
    if not isinstance(value, Mapping) or set(value) != _DRAFT_FIELDS:
        raise fail(
            "skill_author_checkpoint_schema_invalid",
            "已保存的技能草稿结构非法",
        )

    def rules(field: str) -> tuple[SkillRule, ...]:
        rows = value[field]
        if not isinstance(rows, list):
            raise fail(
                "skill_author_checkpoint_schema_invalid",
                "已保存的技能规则分组格式非法",
            )
        result: list[SkillRule] = []
        for row in rows:
            if not isinstance(row, Mapping) or set(row) != _RULE_FIELDS:
                raise fail(
                    "skill_author_checkpoint_schema_invalid",
                    "已保存的单条技能规则格式非法",
                )
            slots = row["source_slots"]
            if not isinstance(slots, list) or not slots:
                raise fail(
                    "skill_author_source_slots_invalid",
                    "已保存的 source_slots 格式非法",
                )
            rule_key = str(row["rule_key"])
            statement = str(row["statement"])
            if not _RULE_KEY.fullmatch(rule_key):
                raise fail(
                    "skill_author_rule_key_invalid",
                    f"非法规则标识 rule_key：{rule_key}",
                )
            SkillAuthorAgent._reject_executable(statement)
            normalized_slots = tuple(map(str, slots))
            if (
                allowed_source_slots is not None
                and set(normalized_slots) - set(allowed_source_slots)
            ):
                raise fail(
                    "skill_author_source_slot_unknown",
                    "保存的技能草稿引用了未知 source slot",
                )
            result.append(SkillRule(
                rule_key,
                statement,
                normalized_slots,
            ))
        return tuple(result)

    title = SkillAuthorAgent._text(value["title"], "title")
    description = SkillAuthorAgent._text(
        value["description"], "description"
    )
    SkillAuthorAgent._reject_executable(title)
    SkillAuthorAgent._reject_executable(description)
    return SkillDraftContent(
        title=title,
        description=description,
        when_to_use=rules("when_to_use"),
        strategy_patterns=rules("strategy_patterns"),
        conditions=rules("conditions"),
        counterexamples=rules("counterexamples"),
        verification_rules=rules("verification_rules"),
    )


def apply_skill_revision(
    active: SkillDraftContent,
    proposal: SkillRevisionProposal,
) -> SkillDraftContent:
    """
    将增量修订提案应用到当前线上技能草稿，生成新版本草稿
    约束：只允许追加规则、替换描述；不允许修改、删除已有规则；不允许重复rule_key
    """
    groups = {
        "strategy_patterns": list(active.strategy_patterns),
        "conditions": list(active.conditions),
        "counterexamples": list(active.counterexamples),
        "verification_rules": list(active.verification_rules),
    }
    description = active.description
    operation_to_group = {
        "add_strategy_pattern": "strategy_patterns",
        "add_condition": "conditions",
        "add_counterexample": "counterexamples",
        "add_verification_rule": "verification_rules",
    }
    # 收集全部已存在规则key，防止重复新增同名规则
    existing_keys = {
        rule.rule_key
        for rules in groups.values()
        for rule in rules
    } | {rule.rule_key for rule in active.when_to_use}
    for operation in proposal.operations:
        if operation.operation == "replace_description":
            assert operation.description is not None
            description = operation.description
            continue
        group = operation_to_group.get(operation.operation)
        if group is None or operation.rule is None:
            raise fail(
                "skill_author_revision_operation_unsupported",
                f"不支持的修订操作类型：{operation.operation}",
            )
        if operation.rule.rule_key in existing_keys:
            raise fail(
                "skill_author_rule_key_conflict",
                f"修订提案内规则标识已存在：{operation.rule.rule_key}",
            )
        existing_keys.add(operation.rule.rule_key)
        groups[group].append(operation.rule)
    return SkillDraftContent(
        title=active.title,
        description=description,
        when_to_use=active.when_to_use,
        strategy_patterns=tuple(groups["strategy_patterns"]),
        conditions=tuple(groups["conditions"]),
        counterexamples=tuple(groups["counterexamples"]),
        verification_rules=tuple(groups["verification_rules"]),
    )
