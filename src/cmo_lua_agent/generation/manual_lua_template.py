"""Controlled rendering for operator-authored Lua baseline templates.

The template owns the executable CMO state machine.  Python may substitute only
explicitly declared scalar tokens; it never parses or rewrites Lua statements.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Mapping

from cmo_lua_agent.generation.runtime_models import canonical_sha256


_TOKEN_PATTERN = re.compile(r"\{\{([A-Za-z][A-Za-z0-9_]*)\}\}")


class ManualLuaTemplateError(ValueError):
    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(code if message is None else f"{code}: {message}")


@dataclass(frozen=True, slots=True)
class ManualTemplateSlot:
    name: str
    token: str
    value_type: str
    allowed_values: tuple[object, ...] = ()
    minimum: int | float | None = None
    maximum: int | float | None = None
    semantic_dimension: str = "manual_template"
    strategy_path: str | None = None

    def validate(self, value: object) -> None:
        if self.value_type == "lua_string":
            if not isinstance(value, str) or not value:
                raise ManualLuaTemplateError("manual_template_slot_value_invalid")
        elif self.value_type == "number":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ManualLuaTemplateError("manual_template_slot_value_invalid")
        else:
            raise ManualLuaTemplateError("manual_template_slot_type_unsupported")
        if self.allowed_values and value not in self.allowed_values:
            raise ManualLuaTemplateError("manual_template_slot_value_invalid")
        if self.minimum is not None and value < self.minimum:  # type: ignore[operator]
            raise ManualLuaTemplateError("manual_template_slot_value_invalid")
        if self.maximum is not None and value > self.maximum:  # type: ignore[operator]
            raise ManualLuaTemplateError("manual_template_slot_value_invalid")

    def render_literal(self, value: object) -> str:
        self.validate(value)
        if self.value_type == "lua_string":
            return str(value).replace("\\", "\\\\").replace("'", "\\'")
        return str(value)


@dataclass(frozen=True, slots=True)
class ManualTemplateStrategy:
    candidate_id: str
    parameters: Mapping[str, object]
    slots: Mapping[str, ManualTemplateSlot]

    def with_parameters(
        self,
        *,
        candidate_id: str,
        updates: Mapping[str, object],
    ) -> "ManualTemplateStrategy":
        if not isinstance(candidate_id, str) or not candidate_id:
            raise ManualLuaTemplateError("manual_template_candidate_id_invalid")
        values = dict(self.parameters)
        candidate_slot = self.slots.get("candidate_id")
        if candidate_slot is not None:
            candidate_slot.validate(candidate_id)
            values["candidate_id"] = candidate_id
        for name, value in updates.items():
            slot = self.slots.get(name)
            if slot is None:
                raise ManualLuaTemplateError("manual_template_unknown_slot")
            slot.validate(value)
            values[name] = value
        return ManualTemplateStrategy(candidate_id=candidate_id, parameters=values, slots=self.slots)

    @property
    def checksum(self) -> str:
        return canonical_sha256({"candidate_id": self.candidate_id, "parameters": dict(self.parameters)})

    def to_dict(self) -> dict[str, object]:
        return {"candidate_id": self.candidate_id, "parameters": dict(self.parameters)}


@dataclass(frozen=True, slots=True)
class ManualTemplateRenderResult:
    content: str
    lua_checksum: str
    fixed_logic_checksum: str
    changed_slots: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ManualLuaTemplatePackage:
    root: Path
    template_id: str
    template_content: str
    slots: Mapping[str, ManualTemplateSlot]
    baseline_parameters: Mapping[str, object]
    fixed_logic_checksum: str

    @classmethod
    def load(cls, root: Path) -> "ManualLuaTemplatePackage":
        root = Path(root).resolve()
        config_path = root / "manual_baseline_template.json"
        if not config_path.is_file():
            raise ManualLuaTemplateError("manual_template_config_missing")
        config = _load_object(config_path)
        template_id = _required_text(config.get("template_id", "manual_baseline_template"), "manual_template_id_invalid")
        template_name = _required_text(config.get("template_lua"), "manual_template_lua_missing")
        template_path = root / template_name
        if not template_path.is_file():
            raise ManualLuaTemplateError("manual_template_lua_missing")
        template_content = template_path.read_text(encoding="utf-8")
        slots = _parse_slots(config.get("slots"))
        declared_tokens = {slot.token for slot in slots.values()}
        actual_tokens = {match.group(0) for match in _TOKEN_PATTERN.finditer(template_content)}
        if actual_tokens != declared_tokens:
            raise ManualLuaTemplateError("manual_template_token_contract_mismatch")
        baseline_parameters = _load_baseline_parameters(root, config, slots)
        for name, slot in slots.items():
            if name not in baseline_parameters:
                raise ManualLuaTemplateError("manual_template_baseline_parameter_missing")
            slot.validate(baseline_parameters[name])
        return cls(
            root=root,
            template_id=template_id,
            template_content=template_content,
            slots=slots,
            baseline_parameters=baseline_parameters,
            fixed_logic_checksum=canonical_sha256({"template": template_content, "slots": sorted(declared_tokens)}),
        )

    def baseline_strategy(self) -> ManualTemplateStrategy:
        return ManualTemplateStrategy("baseline", dict(self.baseline_parameters), self.slots)

    def strategy_overlay(
        self,
        *,
        candidate_id: str,
        baseline_strategy: Mapping[str, object],
        candidate_strategy: Mapping[str, object],
        changed_paths: tuple[str, ...],
    ) -> ManualTemplateStrategy:
        """Project approved formal StrategySpec changes into template parameters.

        Every changed formal path must map to exactly one declared template slot;
        otherwise the candidate is rejected rather than silently rendering the
        unchanged Lua skeleton.
        """
        slots_by_path = {slot.strategy_path: slot for slot in self.slots.values() if slot.strategy_path}
        updates: dict[str, object] = {}
        for path in changed_paths:
            slot = slots_by_path.get(path)
            if slot is None:
                raise ManualLuaTemplateError("manual_template_strategy_change_unmapped")
            before = _json_pointer_value(baseline_strategy, path)
            after = _json_pointer_value(candidate_strategy, path)
            if before == after:
                raise ManualLuaTemplateError("manual_template_strategy_change_noop")
            updates[slot.name] = after
        return self.baseline_strategy().with_parameters(candidate_id=candidate_id, updates=updates)

    def render(self, strategy: ManualTemplateStrategy) -> ManualTemplateRenderResult:
        if set(strategy.parameters) != set(self.slots):
            raise ManualLuaTemplateError("manual_template_parameter_set_mismatch")
        content = self.template_content
        for name in sorted(self.slots):
            slot = self.slots[name]
            value = strategy.parameters[name]
            content = content.replace(slot.token, slot.render_literal(value))
        if _TOKEN_PATTERN.search(content):
            raise ManualLuaTemplateError("manual_template_unrendered_token")
        changed = tuple(sorted(name for name, value in strategy.parameters.items() if value != self.baseline_parameters[name]))
        return ManualTemplateRenderResult(
            content=content,
            lua_checksum=canonical_sha256(content),
            fixed_logic_checksum=self.fixed_logic_checksum,
            changed_slots=changed,
        )


def _parse_slots(value: object) -> dict[str, ManualTemplateSlot]:
    if not isinstance(value, list) or not value:
        raise ManualLuaTemplateError("manual_template_slots_invalid")
    slots: dict[str, ManualTemplateSlot] = {}
    for row in value:
        if not isinstance(row, Mapping):
            raise ManualLuaTemplateError("manual_template_slots_invalid")
        name = _required_text(row.get("name"), "manual_template_slot_invalid")
        token = _required_text(row.get("token"), "manual_template_slot_invalid")
        if token != "{{" + name + "}}" or name in slots:
            raise ManualLuaTemplateError("manual_template_slot_invalid")
        slots[name] = ManualTemplateSlot(
            name=name,
            token=token,
            value_type=_required_text(row.get("type"), "manual_template_slot_invalid"),
            allowed_values=tuple(row.get("allowed_values", ())),
            minimum=row.get("minimum"),
            maximum=row.get("maximum"),
            semantic_dimension=str(row.get("semantic_dimension", "manual_template")),
            strategy_path=(str(row["strategy_path"]) if row.get("strategy_path") is not None else None),
        )
    return slots


def _load_baseline_parameters(
    root: Path,
    config: Mapping[str, object],
    slots: Mapping[str, ManualTemplateSlot],
) -> dict[str, object]:
    name = config.get("baseline_parameters")
    if isinstance(name, str) and (root / name).is_file():
        payload = _load_object(root / name)
        values = payload.get("parameters")
        if isinstance(values, Mapping):
            return dict(values)
    values = {name: config_slot_baseline for name, config_slot_baseline in _baseline_values(config, slots).items()}
    return values


def _baseline_values(config: Mapping[str, object], slots: Mapping[str, ManualTemplateSlot]) -> dict[str, object]:
    rows = config.get("slots")
    assert isinstance(rows, list)
    values: dict[str, object] = {}
    for row in rows:
        assert isinstance(row, Mapping)
        name = str(row["name"])
        if "baseline_value" not in row:
            raise ManualLuaTemplateError("manual_template_baseline_parameter_missing")
        values[name] = row["baseline_value"]
    return values


def _load_object(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManualLuaTemplateError("manual_template_json_invalid") from exc
    if not isinstance(value, dict):
        raise ManualLuaTemplateError("manual_template_json_invalid")
    return value


def _required_text(value: object, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManualLuaTemplateError(code)
    return value.strip()


def _json_pointer_value(value: Mapping[str, object], pointer: str) -> object:
    current: object = value
    for raw_part in pointer.lstrip("/").split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, Mapping):
            if part not in current:
                raise ManualLuaTemplateError("manual_template_strategy_path_missing")
            current = current[part]
        elif isinstance(current, (list, tuple)):
            try:
                current = current[int(part)]
            except (ValueError, IndexError) as exc:
                raise ManualLuaTemplateError("manual_template_strategy_path_missing") from exc
        else:
            raise ManualLuaTemplateError("manual_template_strategy_path_missing")
    return current
