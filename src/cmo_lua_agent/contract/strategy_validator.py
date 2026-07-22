"""
StrategyValidator 就是校验 Planning Agent 生成的每个 StrategySpec 是否满足场景约束、能否进入后续 Lua 生成和 CMO 执行
"""

from __future__ import annotations

from cmo_lua_agent.contract.models import (
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)
from cmo_lua_agent.contract.strategy_models import (
    ScenarioDefinition,
    StrategySpec,
)


class StrategyValidator:
    """长期接口只依赖 StrategySpec 与 ScenarioDefinition。"""

    def validate(
        self,
        strategy: StrategySpec,
        scenario_definition: ScenarioDefinition,
    ) -> ValidationResult:
        if not isinstance(strategy, StrategySpec):
            raise TypeError("strategy 必须是 StrategySpec")
        if not isinstance(scenario_definition, ScenarioDefinition):
            raise TypeError("scenario_definition 必须是 ScenarioDefinition")

        issues: list[ValidationIssue] = []
        if strategy.scenario_id != scenario_definition.scenario_id:
            issues.append(self._error(
                "strategy.scenario_mismatch",
                "$.scenario_id",
                "策略与场景的 scenario_id 不一致",
            ))
            return ValidationResult(issues=tuple(issues))

        units = scenario_definition.unit_by_id()
        requested_fire: dict[tuple[str, int], int] = {}
        requested_reserve: dict[tuple[str, int], int] = {}
        for index, attack in enumerate(strategy.attacks):
            path = f"$.attacks[{index}]"
            shooter = units.get(attack.shooter_id)
            if shooter is None:
                issues.append(self._error(
                    "strategy.unknown_shooter", f"{path}.shooter_id", "射手不存在"
                ))
                continue
            inventory = next(
                (
                    item
                    for item in shooter.weapon_inventory
                    if item.weapon_dbid == attack.weapon_dbid
                ),
                None,
            )
            if inventory is None:
                issues.append(self._error(
                    "strategy.weapon_not_available", f"{path}.weapon_dbid", "射手没有该武器"
                ))
            elif attack.fire_quantity + attack.reserve_quantity > inventory.max_quantity:
                issues.append(self._error(
                    "strategy.ammo_exceeded", f"{path}.fire_quantity", "发射量与保留量超过场景库存"
                ))
            else:
                inventory_key = (attack.shooter_id, attack.weapon_dbid)
                requested_fire[inventory_key] = (
                    requested_fire.get(inventory_key, 0)
                    + attack.fire_quantity
                )
                requested_reserve[inventory_key] = max(
                    requested_reserve.get(inventory_key, 0),
                    attack.reserve_quantity,
                )
            for target_index, target_id in enumerate(attack.target_ids):
                target = units.get(target_id)
                if target is None:
                    issues.append(self._error(
                        "strategy.unknown_target", f"{path}.target_ids[{target_index}]", "目标不存在"
                    ))
                elif target.side_id == shooter.side_id:
                    issues.append(self._error(
                        "strategy.friendly_target", f"{path}.target_ids[{target_index}]", "策略不能攻击友方单位"
                    ))
        for (shooter_id, weapon_dbid), fire_quantity in requested_fire.items():
            shooter = units[shooter_id]
            inventory = next(
                item
                for item in shooter.weapon_inventory
                if item.weapon_dbid == weapon_dbid
            )
            if fire_quantity + requested_reserve[(shooter_id, weapon_dbid)] > inventory.max_quantity:
                issues.append(self._error(
                    "strategy.total_ammo_exceeded",
                    "$.attacks",
                    "同一射手的累计发射量与保留量超过场景库存",
                ))
        for index, sortie in enumerate(strategy.sorties):
            path = f"$.sorties[{index}]"
            aircraft = units.get(sortie.aircraft_id)
            target = units.get(sortie.target_id)
            if aircraft is None:
                issues.append(self._error(
                    "strategy.unknown_aircraft", f"{path}.aircraft_id", "飞机不存在"
                ))
                continue
            if aircraft.base_unit_id != sortie.base_unit_id:
                issues.append(self._error(
                    "strategy.base_mismatch", f"{path}.base_unit_id", "出动基地与场景事实不一致"
                ))
            if target is None:
                issues.append(self._error(
                    "strategy.unknown_target", f"{path}.target_id", "目标不存在"
                ))
            elif target.side_id == aircraft.side_id:
                issues.append(self._error(
                    "strategy.friendly_target", f"{path}.target_id", "策略不能攻击友方单位"
                ))
            for waypoint_index, waypoint in enumerate(sortie.route):
                if not (-90 <= waypoint.latitude <= 90 and -180 <= waypoint.longitude <= 180):
                    issues.append(self._error(
                        "strategy.route_coordinate_invalid",
                        f"{path}.route[{waypoint_index}]",
                        "航路坐标超出经纬度范围",
                    ))
        return ValidationResult(issues=tuple(issues))

    @staticmethod
    def _error(code: str, path: str, message: str) -> ValidationIssue:
        return ValidationIssue(
            code=code,
            message=message,
            path=path,
            severity=ValidationSeverity.ERROR,
        )
