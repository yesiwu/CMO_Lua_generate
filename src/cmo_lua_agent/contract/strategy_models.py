"""
是给整个 CMO 策略优化系统建立一层稳定的“中间表示”，把原始场景、Agent 决策、Lua 实现和仿真结果解耦开。
每个阶段会产生很多种json，或者其他文件，这个文件的作用就是读取文件，并充当这些文件的
中间过渡，然后可以输入给下一个阶段（Planning Agent、Validator、Lua 生成、CMO 评测、候选比较）
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any


def _require_text(value: str, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} 必须是非空字符串")
    return value.strip()


def _require_non_negative(value: int, *, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field_name} 必须是非负整数")
    return value


@dataclass(frozen=True, slots=True)
class WeaponInventory:
    """单位当前可用的武器种类与最大库存，属于场景事实。"""

    weapon_dbid: int
    weapon_name: str
    max_quantity: int

    def __post_init__(self) -> None:
        if not isinstance(self.weapon_dbid, int) or self.weapon_dbid <= 0:
            raise ValueError("weapon_dbid 必须是正整数")
        object.__setattr__(
            self,
            "weapon_name",
            _require_text(self.weapon_name, field_name="weapon_name"),
        )
        _require_non_negative(self.max_quantity, field_name="max_quantity")

    def to_dict(self) -> dict[str, Any]:
        return {
            "weapon_dbid": self.weapon_dbid,
            "weapon_name": self.weapon_name,
            "max_quantity": self.max_quantity,
        }


@dataclass(frozen=True, slots=True)
class ScenarioUnit:
    """不会随候选策略变化的单位事实。"""

    unit_id: str
    side_id: str
    name: str
    platform_type: str
    dbid: int
    loadout_id: int | None = None
    base_unit_id: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    heading: float | None = None
    speed: float | None = None
    weapon_inventory: tuple[WeaponInventory, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("unit_id", "side_id", "name", "platform_type"):
            object.__setattr__(
                self,
                field_name,
                _require_text(getattr(self, field_name), field_name=field_name),
            )
        if not isinstance(self.dbid, int) or self.dbid <= 0:
            raise ValueError("dbid 必须是正整数")
        if self.loadout_id is not None and self.loadout_id <= 0:
            raise ValueError("loadout_id 必须是正整数或 None")
        if self.base_unit_id is not None:
            object.__setattr__(
                self,
                "base_unit_id",
                _require_text(self.base_unit_id, field_name="base_unit_id"),
            )
        inventory = tuple(self.weapon_inventory)
        if not all(isinstance(item, WeaponInventory) for item in inventory):
            raise TypeError("weapon_inventory 仅允许 WeaponInventory")
        if len({item.weapon_dbid for item in inventory}) != len(inventory):
            raise ValueError("同一单位的 weapon_inventory 不允许重复 weapon_dbid")
        object.__setattr__(self, "weapon_inventory", inventory)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "unit_id": self.unit_id,
            "side_id": self.side_id,
            "name": self.name,
            "platform_type": self.platform_type,
            "dbid": self.dbid,
            "weapon_inventory": [
                item.to_dict() for item in self.weapon_inventory
            ],
        }
        for key in (
            "loadout_id",
            "base_unit_id",
            "latitude",
            "longitude",
            "heading",
            "speed",
        ):
            value = getattr(self, key)
            if value is not None:
                payload[key] = value
        return payload


@dataclass(frozen=True, slots=True)
class ScenarioDefinition:
    """固定场景事实；策略对象不能修改或覆盖其中的任意字段。"""

    scenario_id: str
    units: tuple[ScenarioUnit, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "scenario_id",
            _require_text(self.scenario_id, field_name="scenario_id"),
        )
        units = tuple(self.units)
        if not units or not all(isinstance(item, ScenarioUnit) for item in units):
            raise ValueError("units 必须包含至少一个 ScenarioUnit")
        if len({unit.unit_id for unit in units}) != len(units):
            raise ValueError("units 不允许重复 unit_id")
        object.__setattr__(self, "units", units)

    def unit_by_id(self) -> dict[str, ScenarioUnit]:
        return {unit.unit_id: unit for unit in self.units}

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "units": [unit.to_dict() for unit in self.units],
        }


@dataclass(frozen=True, slots=True)
class AttackDirective:
    """一次攻击的策略参数，不含场景库存或平台事实。"""

    attack_id: str
    shooter_id: str
    target_ids: tuple[str, ...]
    weapon_dbid: int
    fire_quantity: int
    delay_seconds: int
    reserve_quantity: int = 0

    def __post_init__(self) -> None:
        for field_name in ("attack_id", "shooter_id"):
            object.__setattr__(
                self,
                field_name,
                _require_text(getattr(self, field_name), field_name=field_name),
            )
        targets = tuple(
            _require_text(target, field_name="target_ids")
            for target in self.target_ids
        )
        if not targets:
            raise ValueError("target_ids 至少需要一个目标")
        object.__setattr__(self, "target_ids", targets)
        if not isinstance(self.weapon_dbid, int) or self.weapon_dbid <= 0:
            raise ValueError("weapon_dbid 必须是正整数")
        for field_name in (
            "fire_quantity",
            "delay_seconds",
            "reserve_quantity",
        ):
            _require_non_negative(getattr(self, field_name), field_name=field_name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "attack_id": self.attack_id,
            "shooter_id": self.shooter_id,
            "target_ids": list(self.target_ids),
            "weapon_dbid": self.weapon_dbid,
            "fire_quantity": self.fire_quantity,
            "delay_seconds": self.delay_seconds,
            "reserve_quantity": self.reserve_quantity,
        }


@dataclass(frozen=True, slots=True)
class RouteWaypoint:
    latitude: float
    longitude: float

    def to_dict(self) -> dict[str, float]:
        return {"latitude": self.latitude, "longitude": self.longitude}


@dataclass(frozen=True, slots=True)
class SortieDirective:
    sortie_id: str
    aircraft_id: str
    target_id: str
    base_unit_id: str
    route: tuple[RouteWaypoint, ...]
    altitude_meters: int
    throttle: str
    fire_delay_seconds: int
    return_delay_seconds: int

    def __post_init__(self) -> None:
        for field_name in (
            "sortie_id",
            "aircraft_id",
            "target_id",
            "base_unit_id",
            "throttle",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_text(getattr(self, field_name), field_name=field_name),
            )
        route = tuple(self.route)
        if not route or not all(isinstance(point, RouteWaypoint) for point in route):
            raise ValueError("route 至少需要一个 RouteWaypoint")
        object.__setattr__(self, "route", route)
        for field_name in (
            "altitude_meters",
            "fire_delay_seconds",
            "return_delay_seconds",
        ):
            _require_non_negative(getattr(self, field_name), field_name=field_name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sortie_id": self.sortie_id,
            "aircraft_id": self.aircraft_id,
            "target_id": self.target_id,
            "base_unit_id": self.base_unit_id,
            "route": [point.to_dict() for point in self.route],
            "altitude_meters": self.altitude_meters,
            "throttle": self.throttle,
            "fire_delay_seconds": self.fire_delay_seconds,
            "return_delay_seconds": self.return_delay_seconds,
        }


@dataclass(frozen=True, slots=True)
class StrategySpec:
    """Phase 1 唯一正式策略模型，后续阶段只消费此表达。"""

    scenario_id: str
    attacks: tuple[AttackDirective, ...] = ()
    sorties: tuple[SortieDirective, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "scenario_id",
            _require_text(self.scenario_id, field_name="scenario_id"),
        )
        attacks = tuple(self.attacks)
        sorties = tuple(self.sorties)
        if not all(isinstance(item, AttackDirective) for item in attacks):
            raise TypeError("attacks 仅允许 AttackDirective")
        if not all(isinstance(item, SortieDirective) for item in sorties):
            raise TypeError("sorties 仅允许 SortieDirective")
        if len({item.attack_id for item in attacks}) != len(attacks):
            raise ValueError("attacks 不允许重复 attack_id")
        if len({item.sortie_id for item in sorties}) != len(sorties):
            raise ValueError("sorties 不允许重复 sortie_id")
        object.__setattr__(self, "attacks", attacks)
        object.__setattr__(self, "sorties", sorties)

    def with_attack_quantity(
        self,
        *,
        attack_id: str,
        fire_quantity: int,
    ) -> "StrategySpec":
        updated = tuple(
            replace(attack, fire_quantity=fire_quantity)
            if attack.attack_id == attack_id
            else attack
            for attack in self.attacks
        )
        if updated == self.attacks:
            raise ValueError(f"未知 attack_id：{attack_id}")
        return replace(self, attacks=updated)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "attacks": [attack.to_dict() for attack in self.attacks],
            "sorties": [sortie.to_dict() for sortie in self.sorties],
        }


@dataclass(frozen=True, slots=True)
class InitialStrategyHint:
    """旧 JSON 中提取的初始计划，不具备已验证基线地位。"""

    strategy: StrategySpec
    source: str = "legacy_json"

    def __post_init__(self) -> None:
        if not isinstance(self.strategy, StrategySpec):
            raise TypeError("strategy 必须是 StrategySpec")
        object.__setattr__(self, "source", _require_text(self.source, field_name="source"))

    def to_dict(self) -> dict[str, Any]:
        return {"source": self.source, "strategy": self.strategy.to_dict()}


@dataclass(frozen=True, slots=True)
class BaselineStrategy:
    """仅包装同一 StrategySpec 与可审计的已验证来源元数据。"""

    strategy: StrategySpec
    source_lua: str
    verified: bool

    def __post_init__(self) -> None:
        if not isinstance(self.strategy, StrategySpec):
            raise TypeError("strategy 必须是 StrategySpec")
        object.__setattr__(
            self,
            "source_lua",
            _require_text(self.source_lua, field_name="source_lua"),
        )
        if self.verified is not True:
            raise ValueError("BaselineStrategy 必须显式标记 verified=true")

    @property
    def scenario_id(self) -> str:
        return self.strategy.scenario_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "source_lua": self.source_lua,
            "verified": self.verified,
            "strategy": self.strategy.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class StrategyDifferenceReport:
    scenario_id: str
    differences: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "differences": [dict(item) for item in self.differences],
        }


def strategy_spec_from_dict(value: dict[str, Any]) -> StrategySpec:
    attacks = tuple(
        AttackDirective(
            attack_id=item["attack_id"],
            shooter_id=item["shooter_id"],
            target_ids=tuple(item["target_ids"]),
            weapon_dbid=item["weapon_dbid"],
            fire_quantity=item["fire_quantity"],
            delay_seconds=item["delay_seconds"],
            reserve_quantity=item.get("reserve_quantity", 0),
        )
        for item in value.get("attacks", [])
    )
    sorties = tuple(
        SortieDirective(
            sortie_id=item["sortie_id"],
            aircraft_id=item["aircraft_id"],
            target_id=item["target_id"],
            base_unit_id=item["base_unit_id"],
            route=tuple(RouteWaypoint(**point) for point in item["route"]),
            altitude_meters=item["altitude_meters"],
            throttle=item["throttle"],
            fire_delay_seconds=item["fire_delay_seconds"],
            return_delay_seconds=item["return_delay_seconds"],
        )
        for item in value.get("sorties", [])
    )
    return StrategySpec(
        scenario_id=value["scenario_id"],
        attacks=attacks,
        sorties=sorties,
    )


def load_baseline_strategy(path: Path) -> BaselineStrategy:
    """读取人工维护的单个已验证 Baseline，不做 Lua 反向解析。"""

    import json

    source = Path(path).expanduser().resolve(strict=True)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Baseline 文件根节点必须是对象")
    return BaselineStrategy(
        strategy=strategy_spec_from_dict(payload["strategy"]),
        source_lua=payload["source_lua"],
        verified=payload["verified"],
    )


def diff_initial_hint_against_baseline(
    *,
    initial_hint: StrategySpec,
    baseline: BaselineStrategy,
) -> StrategyDifferenceReport:
    if initial_hint.scenario_id != baseline.scenario_id:
        raise ValueError("initial_hint 与 baseline 的 scenario_id 必须一致")

    differences: list[dict[str, Any]] = []
    baseline_attacks = {
        attack.attack_id: attack.to_dict() for attack in baseline.strategy.attacks
    }
    hint_attacks = {
        attack.attack_id: attack.to_dict() for attack in initial_hint.attacks
    }
    for attack_id in sorted(set(baseline_attacks) | set(hint_attacks)):
        baseline_attack = baseline_attacks.get(attack_id)
        hint_attack = hint_attacks.get(attack_id)
        if baseline_attack is None or hint_attack is None:
            differences.append(
                {
                    "path": f"strategy.attacks[{attack_id}]",
                    "initial_hint_value": hint_attack,
                    "baseline_value": baseline_attack,
                }
            )
            continue
        for field_name in sorted(set(baseline_attack) | set(hint_attack)):
            if hint_attack.get(field_name) != baseline_attack.get(field_name):
                differences.append(
                    {
                        "path": f"strategy.attacks[{attack_id}].{field_name}",
                        "initial_hint_value": hint_attack.get(field_name),
                        "baseline_value": baseline_attack.get(field_name),
                    }
                )
    return StrategyDifferenceReport(
        scenario_id=baseline.scenario_id,
        differences=tuple(differences),
    )
