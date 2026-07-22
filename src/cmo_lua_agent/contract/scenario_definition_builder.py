"""从既有 ScenarioIR 派生 Phase 1 的事实与初始策略。

1. 入口类：ScenarioDefinitionBuilder
约束：只读 ScenarioIR，
遍历所有单位，构造 ScenarioDefinition（场景静态事实库）；

解析 IR 里的打击计划、出击计划，组装 InitialStrategyHint（初始作战策略指令）；

返回打包输出对象 ScenarioDefinitionBuildOutput。

2. 输出两大部分含义
① ScenarioDefinition：静态场景事实（“战场有什么”）
    由 _build_unit 构建一批 ScenarioUnit
    每个单位包含：
    基础属性：unit_id、阵营、名称、平台类型、DBID、坐标航向速度
    舰载机特有：base_unit_id（母舰 ID）、loadout_id
    弹药库存：weapon_inventory 弹药清单（武器 DBID、名称、载弹量）
    作用：给下游模块提供全域战场实体视图，谁在哪、带什么弹。

② InitialStrategyHint：初始作战策略（“一开始打算干什么”）
    内部承载 StrategySpec，包含两类指令：
    AttackDirective 舰艇反舰打击指令（对应之前 json_to_lua 里的 strikePlan）
        从 strikePlan 解析：
        射手 ID、目标 ID 列表、武器 DBID、发射数量、打击延时
        自动计算剩余备弹 reserve_quantity = 载弹 - 发射量
        对应 Lua 里舰艇 scheduleFire 延时打击逻辑
    SortieDirective 舰载机出击指令（对应之前 attack-air）
        从 sortiePlan 解析：
        飞机 ID、母舰 ID、目标 ID
        航路航点 route、高度、油门
        开火延时、返航延时
        对应 Lua 舰载机：起飞→航路→打击→返航整套逻辑

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cmo_lua_agent.contract.models import ScenarioIR
from cmo_lua_agent.contract.strategy_models import (
    AttackDirective,
    InitialStrategyHint,
    RouteWaypoint,
    ScenarioDefinition,
    ScenarioUnit,
    SortieDirective,
    StrategySpec,
    WeaponInventory,
)


@dataclass(frozen=True, slots=True)
class ScenarioDefinitionBuildOutput:
    scenario_definition: ScenarioDefinition
    initial_strategy_hint: InitialStrategyHint


class ScenarioDefinitionBuilder:
    """只读取现有 IR；不修改 IR、旧 Contract 或 Manifest。"""

    def build(self, scenario_ir: ScenarioIR) -> ScenarioDefinitionBuildOutput:
        if not isinstance(scenario_ir, ScenarioIR):
            raise TypeError("scenario_ir 必须是 ScenarioIR")
        source = scenario_ir.to_dict()
        scenario_id = source["scenario"]["id"]
        units = tuple(
            self._build_unit(unit_id, value)
            for unit_id, value in source["unitById"].items()
        )
        definition = ScenarioDefinition(scenario_id=scenario_id, units=units)
        hint = InitialStrategyHint(
            strategy=StrategySpec(
                scenario_id=scenario_id,
                attacks=self._build_attacks(source),
                sorties=self._build_sorties(source),
            )
        )
        return ScenarioDefinitionBuildOutput(
            scenario_definition=definition,
            initial_strategy_hint=hint,
        )

    @staticmethod
    def _build_unit(unit_id: str, value: dict[str, Any]) -> ScenarioUnit:
        inventory = tuple(
            WeaponInventory(
                weapon_dbid=load["weaponDbid"],
                weapon_name=load["weapon"],
                max_quantity=load["loaded"],
            )
            for load in value.get("weaponLoad", [])
        )
        return ScenarioUnit(
            unit_id=unit_id,
            side_id=value["sideKey"],
            name=value["name"],
            platform_type=value["type"],
            dbid=value["dbid"],
            loadout_id=value.get("loadoutId"),
            base_unit_id=value.get("base"),
            latitude=value.get("latitude"),
            longitude=value.get("longitude"),
            heading=value.get("heading"),
            speed=value.get("speed"),
            weapon_inventory=inventory,
        )

    @staticmethod
    def _build_attacks(source: dict[str, Any]) -> tuple[AttackDirective, ...]:
        attacks: list[AttackDirective] = []
        for index, strike in enumerate(source.get("strikePlan", [])):
            shooter_id = strike["shooters"][0]
            attacks.append(
                AttackDirective(
                    attack_id=f"initial-attack-{index}",
                    shooter_id=shooter_id,
                    target_ids=tuple(strike["targets"]),
                    weapon_dbid=strike["weaponDbid"],
                    fire_quantity=strike["fired"],
                    delay_seconds=strike.get("delaySeconds", 0),
                    reserve_quantity=max(
                        0,
                        strike["loaded"] - strike["fired"],
                    ),
                )
            )
        return tuple(attacks)

    @staticmethod
    def _build_sorties(source: dict[str, Any]) -> tuple[SortieDirective, ...]:
        sorties: list[SortieDirective] = []
        for index, sortie in enumerate(source.get("sortiePlan", [])):
            sorties.append(
                SortieDirective(
                    sortie_id=f"initial-sortie-{index}",
                    aircraft_id=sortie["aircraft"],
                    target_id=sortie["target"],
                    base_unit_id=sortie["base"],
                    route=tuple(
                        RouteWaypoint(
                            latitude=point["latitude"],
                            longitude=point["longitude"],
                        )
                        for point in sortie["route"]
                    ),
                    altitude_meters=sortie["altitudeMeters"],
                    throttle=sortie["throttle"],
                    fire_delay_seconds=sortie["fireDelaySeconds"],
                    return_delay_seconds=sortie["returnToBaseDelaySeconds"],
                )
            )
        return tuple(sorties)
