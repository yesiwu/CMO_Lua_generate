"""Phase 3.1 CMO 原生计分的不可变、可校验契约。"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from cmo_lua_agent.generation.runtime_models import canonical_sha256


def _text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _non_negative(value: int, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


@dataclass(frozen=True, slots=True)
class UnitRoleAssignment:
    """把场景稳定 unit_id 显式分类为计分或不计分角色。"""

    unit_id: str
    role_kind: str | None
    scoring_status: str   #这个直接设计为True 或 false 不久行了吗

    def __post_init__(self) -> None:
        object.__setattr__(self, "unit_id", _text(self.unit_id, "unit_id"))
        if self.role_kind is not None:
            object.__setattr__(self, "role_kind", _text(self.role_kind, "role_kind"))
        if self.scoring_status not in {"scored", "unscored"}:
            raise ValueError("scoring_status must be 'scored' or 'unscored'")
        if self.scoring_status == "scored" and self.role_kind is None:
            raise ValueError("scored assignment requires role_kind")

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "role_kind": self.role_kind,
            "scoring_status": self.scoring_status,
        }


@dataclass(frozen=True, slots=True)
class UnitRoleCatalog:
    catalog_id: str
    catalog_version: str
    scenario_id: str
    assignments: tuple[UnitRoleAssignment, ...]

    def __post_init__(self) -> None:
        for field_name in ("catalog_id", "catalog_version", "scenario_id"):
            object.__setattr__(self, field_name, _text(getattr(self, field_name), field_name))
        assignments = tuple(self.assignments)
        if not assignments or not all(isinstance(item, UnitRoleAssignment) for item in assignments):
            raise ValueError("assignments must contain UnitRoleAssignment values")
        if len({item.unit_id for item in assignments}) != len(assignments):
            raise ValueError("unit_id must occur once in UnitRoleCatalog")
        object.__setattr__(self, "assignments", assignments)

    @property
    def checksum(self) -> str:
        return canonical_sha256(self.to_dict())
    #快速根据单位 ID 查角色
    def assignments_by_unit_id(self) -> dict[str, UnitRoleAssignment]:
        return {assignment.unit_id: assignment for assignment in self.assignments}

    def to_dict(self) -> dict[str, Any]:
        return {
            "catalog_id": self.catalog_id,
            "catalog_version": self.catalog_version,
            "scenario_id": self.scenario_id,
            "assignments": [item.to_dict() for item in self.assignments],
        }


@dataclass(frozen=True, slots=True)
#规定某一类单位击毁后加 / 扣多少分：
class ScoreRole:
    role_kind: str
    enemy_destroyed_points: int
    own_destroyed_points: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "role_kind", _text(self.role_kind, "role_kind"))
        _non_negative(self.enemy_destroyed_points, "enemy_destroyed_points")
        _non_negative(self.own_destroyed_points, "own_destroyed_points")

    def to_dict(self) -> dict[str, Any]:
        return {
            "role_kind": self.role_kind,
            "enemy_destroyed_points": self.enemy_destroyed_points,
            "own_destroyed_points": self.own_destroyed_points,
        }


@dataclass(frozen=True, slots=True)
#计分权重配置
class ScoreProfile:
    profile_id: str
    profile_version: str
    score_side_id: str
    roles: tuple[ScoreRole, ...]

    def __post_init__(self) -> None:
        for field_name in ("profile_id", "profile_version", "score_side_id"):
            object.__setattr__(self, field_name, _text(getattr(self, field_name), field_name))
        roles = tuple(self.roles)
        if not roles or not all(isinstance(item, ScoreRole) for item in roles):
            raise ValueError("roles must contain ScoreRole values")
        if len({item.role_kind for item in roles}) != len(roles):
            raise ValueError("role_kind must occur once in ScoreProfile")
        object.__setattr__(self, "roles", roles)

    @property
    def checksum(self) -> str:
        return canonical_sha256(self.to_dict())

    def role_scores(self) -> dict[str, ScoreRole]:
        return {role.role_kind: role for role in self.roles}

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "score_side_id": self.score_side_id,
            "roles": [item.to_dict() for item in self.roles],
        }


@dataclass(frozen=True, slots=True)
class ScenarioObjective:
    objective_id: str
    objective_kind: str
    target_unit_id: str
    required: bool

    def __post_init__(self) -> None:
        for field_name in ("objective_id", "objective_kind", "target_unit_id"):
            object.__setattr__(self, field_name, _text(getattr(self, field_name), field_name))
        if not isinstance(self.required, bool):
            raise TypeError("required must be bool")

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective_id": self.objective_id,
            "objective_kind": self.objective_kind,
            "target_unit_id": self.target_unit_id,
            "required": self.required,
        }


@dataclass(frozen=True, slots=True)
class ScenarioObjectives:
    scenario_id: str
    objectives_version: str
    objectives: tuple[ScenarioObjective, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "scenario_id", _text(self.scenario_id, "scenario_id"))
        object.__setattr__(self, "objectives_version", _text(self.objectives_version, "objectives_version"))
        objectives = tuple(self.objectives)
        if not objectives or not all(isinstance(item, ScenarioObjective) for item in objectives):
            raise ValueError("objectives must contain ScenarioObjective values")
        if len({item.objective_id for item in objectives}) != len(objectives):
            raise ValueError("objective_id must be unique")
        if len({item.target_unit_id for item in objectives}) != len(objectives):
            raise ValueError("target_unit_id must be unique")
        object.__setattr__(self, "objectives", objectives)

    @property
    def checksum(self) -> str:
        return canonical_sha256(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "objectives_version": self.objectives_version,
            "objectives": [item.to_dict() for item in self.objectives],
        }


@dataclass(frozen=True, slots=True)
class NativeScoreRule:
    rule_id: str
    objective_id: str
    target_unit_id: str
    target_side_id: str
    target_unit_name: str
    trigger_kind: str
    point_change: int
    event_name: str
    trigger_name: str
    action_name: str
    score_side_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "objective_id": self.objective_id,
            "target_unit_id": self.target_unit_id,
            "target_side_id": self.target_side_id,
            "target_unit_name": self.target_unit_name,
            "trigger_kind": self.trigger_kind,
            "point_change": self.point_change,
            "event_name": self.event_name,
            "trigger_name": self.trigger_name,
            "action_name": self.action_name,
            "score_side_id": self.score_side_id,
        }


@dataclass(frozen=True, slots=True)
class ScenarioScoreSpec:
    schema_version: str
    compiler_version: str
    scenario_id: str
    catalog_id: str
    catalog_version: str
    profile_id: str
    profile_version: str
    objectives_version: str
    rules: tuple[NativeScoreRule, ...]

    @property
    def checksum(self) -> str:
        return canonical_sha256(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "compiler_version": self.compiler_version,
            "scenario_id": self.scenario_id,
            "catalog_id": self.catalog_id,
            "catalog_version": self.catalog_version,
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "objectives_version": self.objectives_version,
            "rules": [item.to_dict() for item in self.rules],
        }


@dataclass(frozen=True, slots=True)
class NativeScoreFragment:
    compiler_version: str
    score_spec_checksum: str
    content: str

    @property
    def checksum(self) -> str:
        return sha256(self.content.encode("utf-8")).hexdigest()
