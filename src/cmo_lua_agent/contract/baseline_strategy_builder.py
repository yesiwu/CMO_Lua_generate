"""Derive the formal Phase 9C baseline only from the reviewed ScenarioIR schema."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any, Mapping

from cmo_lua_agent.contract.strategy_models import (
    AirTactics,
    AttackDirective,
    RouteWaypoint,
    ScenarioDefinition,
    ScenarioUnit,
    SortieDirective,
    StrategySpec,
    WeaponInventory,
)


BUILDER_VERSION = "1.1.0"


class BaselineDerivationError(ValueError):
    """Stable failure code for malformed or non-representable ScenarioIR input."""


def _checksum(value: object) -> str:
    serialized = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class BaselineDerivationManifest:
    schema_version: str
    builder_version: str
    scenario_ir_checksum: str
    scenario_definition_checksum: str
    baseline_strategy_checksum: str
    mapping_checksum: str
    defaulted_fields: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DerivedBaseline:
    scenario: ScenarioDefinition
    strategy: StrategySpec
    manifest: BaselineDerivationManifest


class BaselineStrategyBuilder:
    """Small, deterministic adapter for the reviewed 6v4 ScenarioIR v1 schema.

    The builder does not infer weapons or reserve quantities from inventory. A
    missing ``reserveQuantity`` receives the documented schema default of zero.
    """

    def build(self, scenario_ir: Mapping[str, Any]) -> DerivedBaseline:
        if not isinstance(scenario_ir, Mapping):
            raise BaselineDerivationError("baseline_derivation_ir_invalid")
        source = dict(scenario_ir)
        scenario = source.get("scenario")
        units_payload = source.get("units")
        missions = source.get("missions")
        if not isinstance(scenario, Mapping) or not isinstance(scenario.get("id"), str):
            raise BaselineDerivationError("baseline_derivation_scenario_id_missing")
        if not isinstance(units_payload, list) or not isinstance(missions, list):
            raise BaselineDerivationError("baseline_derivation_collections_invalid")
        if len({item.get("id") for item in missions if isinstance(item, Mapping)}) != len(missions):
            raise BaselineDerivationError("baseline_derivation_duplicate_mission_id")
        inventory = self._inventory(source.get("weapons"))
        units = self._units(units_payload, inventory)
        scenario_definition = ScenarioDefinition(scenario_id=scenario["id"], units=units)
        attacks, sorties, defaulted = self._missions(missions, scenario_definition)
        strategy = StrategySpec(scenario_id=scenario["id"], attacks=attacks, sorties=sorties)
        scenario_ir_checksum = _checksum(source)
        manifest = BaselineDerivationManifest(
            schema_version="1.0",
            builder_version=BUILDER_VERSION,
            scenario_ir_checksum=scenario_ir_checksum,
            scenario_definition_checksum=_checksum(scenario_definition.to_dict()),
            baseline_strategy_checksum=_checksum(strategy.to_dict()),
            mapping_checksum=_checksum({"schema": "6v4-scenario-ir-v1", "builder": BUILDER_VERSION}),
            defaulted_fields=tuple(sorted(defaulted)),
        )
        return DerivedBaseline(scenario_definition, strategy, manifest)

    @staticmethod
    def _inventory(value: object) -> dict[str, tuple[WeaponInventory, ...]]:
        if value is None:
            return {}
        if not isinstance(value, list):
            raise BaselineDerivationError("baseline_derivation_weapons_invalid")
        grouped: dict[str, list[WeaponInventory]] = {}
        for entry in value:
            if not isinstance(entry, Mapping):
                raise BaselineDerivationError("baseline_derivation_weapon_invalid")
            try:
                item = WeaponInventory(
                    weapon_dbid=entry["weaponDbid"],
                    weapon_name=entry["weaponName"],
                    max_quantity=entry["quantity"],
                )
                unit_id = entry["unitId"]
            except (KeyError, TypeError, ValueError) as error:
                raise BaselineDerivationError("baseline_derivation_weapon_invalid") from error
            if not isinstance(unit_id, str) or not unit_id:
                raise BaselineDerivationError("baseline_derivation_weapon_invalid")
            grouped.setdefault(unit_id, []).append(item)
        return {unit_id: tuple(items) for unit_id, items in grouped.items()}

    @staticmethod
    def _units(
        values: list[object], inventory: Mapping[str, tuple[WeaponInventory, ...]],
    ) -> tuple[ScenarioUnit, ...]:
        result: list[ScenarioUnit] = []
        for value in values:
            if not isinstance(value, Mapping):
                raise BaselineDerivationError("baseline_derivation_unit_invalid")
            try:
                result.append(ScenarioUnit(
                    unit_id=value["id"], side_id=value["sideId"], name=value["name"],
                    platform_type=value["type"], dbid=value["dbid"],
                    loadout_id=value.get("loadoutId"), base_unit_id=value.get("baseUnitId"),
                    latitude=value.get("latitude"), longitude=value.get("longitude"),
                    heading=value.get("heading"), speed=value.get("speed"),
                    weapon_inventory=inventory.get(value["id"], ()),
                ))
            except (KeyError, TypeError, ValueError) as error:
                raise BaselineDerivationError("baseline_derivation_unit_invalid") from error
        if len({unit.unit_id for unit in result}) != len(result):
            raise BaselineDerivationError("baseline_derivation_duplicate_unit_id")
        return tuple(result)

    @staticmethod
    def _missions(
        values: list[object], scenario: ScenarioDefinition,
    ) -> tuple[tuple[AttackDirective, ...], tuple[SortieDirective, ...], list[str]]:
        attacks: list[AttackDirective] = []
        sorties: list[SortieDirective] = []
        defaulted: list[str] = []
        known_units = scenario.unit_by_id()
        for mission in values:
            if not isinstance(mission, Mapping):
                raise BaselineDerivationError("baseline_derivation_mission_invalid")
            mission_id = mission.get("id")
            mission_type = mission.get("type")
            if not isinstance(mission_id, str) or not mission_id or mission_type not in {"ship_attack", "aircraft_attack"}:
                raise BaselineDerivationError("baseline_derivation_mission_invalid")
            shooter_id = mission.get("unitId")
            target_id = mission.get("targetId")
            if shooter_id not in known_units or target_id not in known_units:
                raise BaselineDerivationError("baseline_derivation_mission_unit_unknown")
            selection = mission.get("weaponSelection", "explicit")
            dbid = mission.get("weaponDbid")
            if selection == "auto":
                dbid = None
            elif selection == "manual":
                selection = "explicit"
            elif selection != "explicit":
                raise BaselineDerivationError("baseline_derivation_weapon_selection_invalid")
            reserve = mission.get("reserveQuantity")
            if reserve is None:
                reserve = 0
                defaulted.append(f"missions/{mission_id}/reserveQuantity")
            try:
                attacks.append(AttackDirective(
                    attack_id=mission_id, shooter_id=shooter_id, target_ids=(target_id,),
                    weapon_dbid=dbid, weapon_selection=selection,
                    fire_quantity=mission["fireQuantity"], delay_seconds=mission.get("delaySeconds", 0),
                    reserve_quantity=reserve,
                ))
            except (KeyError, TypeError, ValueError) as error:
                raise BaselineDerivationError("baseline_derivation_attack_invalid") from error
            if mission_type == "aircraft_attack":
                try:
                    route_source = mission.get(
                        "route",
                        mission.get("resolvedBaselineRoute"),
                    )
                    route = tuple(
                        RouteWaypoint(
                            latitude=point["latitude"],
                            longitude=point["longitude"],
                        )
                        for point in route_source
                    )
                    air_tactics = AirTactics(
                        launch_delay_seconds=mission.get(
                            "launchStartDelaySeconds",
                            mission.get("delaySeconds", 5),
                        ),
                        ingress_altitude_m=mission.get("ingressAltitudeM", 200),
                        popup_altitude_m=mission.get("popupAltitudeM", 9500),
                        popup_range_nm=mission.get("popupRangeNm", 95),
                        attack_range_nm=mission.get("attackRangeNm", 80),
                    )
                    sorties.append(SortieDirective(
                        sortie_id=mission_id, aircraft_id=shooter_id, target_id=target_id,
                        base_unit_id=mission["baseUnitId"], route=route,
                        altitude_meters=mission.get(
                            "altitude",
                            mission.get("popupAltitudeM", 8000),
                        ),
                        throttle=mission["throttle"],
                        fire_delay_seconds=mission["attackStartAfterAirborneSeconds"],
                        return_delay_seconds=mission["returnAfterAttackSeconds"],
                        air_tactics=air_tactics,
                    ))
                except (KeyError, TypeError, ValueError) as error:
                    raise BaselineDerivationError("baseline_derivation_sortie_invalid") from error
        return tuple(attacks), tuple(sorties), defaulted
