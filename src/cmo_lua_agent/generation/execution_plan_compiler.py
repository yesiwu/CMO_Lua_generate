"""Compile Phase 2 strategy contracts into deterministic execution plans."""

from __future__ import annotations

from dataclasses import dataclass

from cmo_lua_agent.contract.strategy_models import (
    ScenarioDefinition,
    ScenarioUnit,
    StrategySpec,
)
from cmo_lua_agent.generation.runtime_models import (
    CapabilityGap,
    ExecutionPlan,
    LuaRuntimeProfile,
    Operation,
)


PLAN_SCHEMA_VERSION = "1.0.0"
COMPILER_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class ExecutionPlanCompileResult:
    plan: ExecutionPlan | None
    capability_gaps: tuple[CapabilityGap, ...] = ()


class ExecutionPlanCompiler:
    """Lower supported naval/air anti-surface strategy semantics to operations."""

    def compile(
        self,
        *,
        scenario: ScenarioDefinition,
        strategy: StrategySpec,
        runtime: LuaRuntimeProfile,
    ) -> ExecutionPlanCompileResult:
        if scenario.scenario_id != strategy.scenario_id:
            raise ValueError("scenario and strategy must share scenario_id")

        units = scenario.unit_by_id()
        gaps = self._find_capability_gaps(strategy=strategy, units=units)
        if gaps:
            return ExecutionPlanCompileResult(plan=None, capability_gaps=gaps)

        operations: list[Operation] = []
        side_ids = sorted({unit.side_id for unit in scenario.units})
        operations.append(
            Operation(
                operation_id="setup.sides",
                primitive_type="ensure_sides",
                parameters={"side_ids": side_ids},
                depends_on=(),
                source_strategy_path="/scenario_definition",
            )
        )
        operations.append(
            Operation(
                operation_id="setup.side_state",
                primitive_type="configure_side_state",
                parameters={
                    "side_ids": side_ids,
                    "posture": "H",
                    "awareness": "OMNI",
                    "weapon_control_status": "0",
                },
                depends_on=("setup.sides",),
                source_strategy_path="/scenario_definition",
            )
        )

        for unit in sorted(scenario.units, key=lambda item: item.unit_id):
            if unit.platform_type == "ship":
                operations.append(self._ensure_ship_operation(unit))
            elif unit.platform_type == "aircraft":
                operations.append(self._ensure_aircraft_operation(unit))

        for target_id in sorted(self._target_ids(strategy)):
            operations.append(
                Operation(
                    operation_id=f"contact.{target_id}",
                    primitive_type="prepare_target_contact",
                    parameters={
                        "target_id": target_id,
                        "target_side_id": units[target_id].side_id,
                    },
                    depends_on=(f"unit.{target_id}", "setup.side_state"),
                    source_strategy_path="/strategy",
                )
            )

        attack_ops = self._compile_ship_attacks(strategy=strategy, units=units)
        configured_inventory = {
            operation.operation_id for operation in operations
            if operation.primitive_type == "configure_ship_inventory"
        }
        for inventory_operation in attack_ops.inventory_operations:
            if inventory_operation.operation_id not in configured_inventory:
                operations.append(inventory_operation)
                configured_inventory.add(inventory_operation.operation_id)
        operations.extend(attack_ops.attack_operations)
        operations.extend(self._compile_air_sorties(strategy=strategy, units=units))

        plan = ExecutionPlan(
            plan_schema_version=PLAN_SCHEMA_VERSION,
            compiler_version=COMPILER_VERSION,
            scenario_id=scenario.scenario_id,
            runtime_id=runtime.runtime_id,
            runtime_version=runtime.runtime_version,
            operations=tuple(operations),
        )
        return ExecutionPlanCompileResult(plan=plan)

    def _find_capability_gaps(
        self,
        *,
        strategy: StrategySpec,
        units: dict[str, ScenarioUnit],
    ) -> tuple[CapabilityGap, ...]:
        gaps: list[CapabilityGap] = []
        for index, attack in enumerate(strategy.attacks):
            shooter = units.get(attack.shooter_id)
            if shooter is None:
                gaps.append(
                    CapabilityGap(
                        capability="unknown_unit",
                        source_strategy_path=f"/strategy/attacks/{index}",
                        reason=f"unknown shooter_id: {attack.shooter_id}",
                        supported_runtime_version="1.0.0",
                    )
                )
                continue
            if shooter.platform_type == "submarine":
                gaps.append(
                    CapabilityGap(
                        capability="submarine_operations",
                        source_strategy_path=f"/strategy/attacks/{index}",
                        reason="submarine operations are outside Phase 2 runtime scope",
                        supported_runtime_version="1.0.0",
                    )
                )
            elif shooter.platform_type not in {"ship", "aircraft"}:
                gaps.append(
                    CapabilityGap(
                        capability=f"{shooter.platform_type}_operations",
                        source_strategy_path=f"/strategy/attacks/{index}",
                        reason=f"unsupported shooter platform: {shooter.platform_type}",
                        supported_runtime_version="1.0.0",
                    )
                )
        return tuple(gaps)

    def _ensure_ship_operation(self, unit: ScenarioUnit) -> Operation:
        return Operation(
            operation_id=f"unit.{unit.unit_id}",
            primitive_type="ensure_ship",
            parameters={
                "unit_id": unit.unit_id,
                "side_id": unit.side_id,
                "name": unit.name,
                "dbid": unit.dbid,
                "latitude": unit.latitude,
                "longitude": unit.longitude,
                "heading": unit.heading,
                "speed": unit.speed,
            },
            depends_on=("setup.sides",),
            source_strategy_path="/scenario_definition/units",
        )

    def _ensure_aircraft_operation(self, unit: ScenarioUnit) -> Operation:
        return Operation(
            operation_id=f"unit.{unit.unit_id}",
            primitive_type="ensure_aircraft",
            parameters={
                "unit_id": unit.unit_id,
                "side_id": unit.side_id,
                "name": unit.name,
                "dbid": unit.dbid,
                "base_unit_id": unit.base_unit_id,
                "loadout_id": unit.loadout_id,
            },
            depends_on=("setup.sides",)
            if unit.base_unit_id is None
            else ("setup.sides", f"unit.{unit.base_unit_id}"),
            source_strategy_path="/scenario_definition/units",
        )

    def _compile_ship_attacks(
        self,
        *,
        strategy: StrategySpec,
        units: dict[str, ScenarioUnit],
    ) -> "_ShipAttackOperations":
        inventory_operations: list[Operation] = []
        attack_operations: list[Operation] = []
        for index, attack in enumerate(strategy.attacks):
            shooter = units[attack.shooter_id]
            if shooter.platform_type != "ship":
                continue
            target_dependencies = tuple(f"contact.{target_id}" for target_id in attack.target_ids)
            inventory_id = f"inventory.{shooter.unit_id}"
            inventory_operations.append(
                Operation(
                    operation_id=inventory_id,
                    primitive_type="configure_ship_inventory",
                    parameters={
                        "unit_id": shooter.unit_id,
                        "weapon_inventory": [
                            item.to_dict() for item in shooter.weapon_inventory
                        ],
                    },
                    depends_on=(f"unit.{shooter.unit_id}",),
                    source_strategy_path="/scenario_definition/units",
                )
            )
            attack_operations.append(
                Operation(
                    operation_id=f"attack.{attack.attack_id}",
                    primitive_type="schedule_ship_attack",
                    parameters=attack.to_dict(),
                    depends_on=(inventory_id, *target_dependencies),
                    source_strategy_path=f"/strategy/attacks/{index}",
                )
            )
        return _ShipAttackOperations(
            inventory_operations=tuple(inventory_operations),
            attack_operations=tuple(attack_operations),
        )

    def _compile_air_sorties(
        self,
        *,
        strategy: StrategySpec,
        units: dict[str, ScenarioUnit],
    ) -> tuple[Operation, ...]:
        air_attacks = {
            attack.shooter_id: (index, attack)
            for index, attack in enumerate(strategy.attacks)
            if units[attack.shooter_id].platform_type == "aircraft"
        }
        operations: list[Operation] = []
        for sortie_index, sortie in enumerate(strategy.sorties):
            aircraft = units[sortie.aircraft_id]
            if aircraft.platform_type != "aircraft":
                continue
            attack_index, attack = air_attacks[sortie.aircraft_id]
            configure_id = f"aircraft.{sortie.sortie_id}.configure"
            launch_id = f"air_launch.{sortie.sortie_id}"
            airborne_id = f"air_airborne.{sortie.sortie_id}"
            route_id = f"air_route.{sortie.sortie_id}"
            range_id = f"air_range.{sortie.sortie_id}"
            attack_id = f"air_attack.{attack.attack_id}"
            operations.extend(
                (
                    Operation(
                        operation_id=configure_id,
                        primitive_type="configure_aircraft",
                        parameters={
                            "aircraft_id": sortie.aircraft_id,
                            "base_unit_id": sortie.base_unit_id,
                            "loadout_id": aircraft.loadout_id,
                            "weapon_inventory": [
                                item.to_dict() for item in aircraft.weapon_inventory
                            ],
                        },
                        depends_on=(f"unit.{sortie.aircraft_id}", f"unit.{sortie.base_unit_id}"),
                        source_strategy_path=f"/strategy/sorties/{sortie_index}",
                    ),
                    Operation(
                        operation_id=launch_id,
                        primitive_type="request_aircraft_launch",
                        parameters={
                            "sortie_id": sortie.sortie_id,
                            "aircraft_id": sortie.aircraft_id,
                            "base_unit_id": sortie.base_unit_id,
                        },
                        depends_on=(configure_id,),
                        source_strategy_path=f"/strategy/sorties/{sortie_index}",
                    ),
                    Operation(
                        operation_id=airborne_id,
                        primitive_type="wait_aircraft_airborne",
                        parameters={
                            "sortie_id": sortie.sortie_id,
                            "aircraft_id": sortie.aircraft_id,
                        },
                        depends_on=(launch_id,),
                        source_strategy_path=f"/strategy/sorties/{sortie_index}",
                    ),
                    Operation(
                        operation_id=route_id,
                        primitive_type="set_aircraft_route",
                        parameters={
                            "sortie_id": sortie.sortie_id,
                            "aircraft_id": sortie.aircraft_id,
                            "route": [point.to_dict() for point in sortie.route],
                            "altitude_meters": sortie.altitude_meters,
                            "throttle": sortie.throttle,
                        },
                        depends_on=(airborne_id,),
                        source_strategy_path=f"/strategy/sorties/{sortie_index}",
                    ),
                    Operation(
                        operation_id=range_id,
                        primitive_type="wait_aircraft_attack_range",
                        parameters={
                            "sortie_id": sortie.sortie_id,
                            "aircraft_id": sortie.aircraft_id,
                            "target_id": sortie.target_id,
                            "weapon_dbid": attack.weapon_dbid,
                        },
                        depends_on=(route_id, f"contact.{sortie.target_id}"),
                        source_strategy_path=f"/strategy/sorties/{sortie_index}",
                    ),
                    Operation(
                        operation_id=attack_id,
                        primitive_type="aircraft_attack",
                        parameters={
                            **attack.to_dict(),
                            "sortie_id": sortie.sortie_id,
                            "return_delay_seconds": sortie.return_delay_seconds,
                        },
                        depends_on=(range_id,),
                        source_strategy_path=f"/strategy/attacks/{attack_index}",
                    ),
                    Operation(
                        operation_id=f"air_return.{sortie.sortie_id}",
                        primitive_type="return_aircraft_to_base",
                        parameters={
                            "sortie_id": sortie.sortie_id,
                            "aircraft_id": sortie.aircraft_id,
                            "base_unit_id": sortie.base_unit_id,
                            "return_delay_seconds": sortie.return_delay_seconds,
                        },
                        depends_on=(attack_id,),
                        source_strategy_path=f"/strategy/sorties/{sortie_index}",
                    ),
                )
            )
        return tuple(operations)

    @staticmethod
    def _target_ids(strategy: StrategySpec) -> tuple[str, ...]:
        targets: set[str] = set()
        for attack in strategy.attacks:
            targets.update(attack.target_ids)
        for sortie in strategy.sorties:
            targets.add(sortie.target_id)
        return tuple(targets)


@dataclass(frozen=True, slots=True)
class _ShipAttackOperations:
    inventory_operations: tuple[Operation, ...]
    attack_operations: tuple[Operation, ...]
