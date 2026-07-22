from __future__ import annotations

from cmo_lua_agent.contract import (
    AttackDirective,
    RouteWaypoint,
    ScenarioDefinition,
    ScenarioUnit,
    SortieDirective,
    StrategySpec,
    StrategyValidator,
    WeaponInventory,
)


def _definition() -> ScenarioDefinition:
    return ScenarioDefinition(
        scenario_id="stable-scenario",
        units=(
            ScenarioUnit(
                unit_id="red-ship",
                side_id="red",
                name="Red ship",
                platform_type="ship",
                dbid=100,
                weapon_inventory=(
                    WeaponInventory(
                        weapon_dbid=500,
                        weapon_name="Weapon-500",
                        max_quantity=4,
                    ),
                ),
            ),
            ScenarioUnit(
                unit_id="blue-ship",
                side_id="blue",
                name="Blue ship",
                platform_type="ship",
                dbid=200,
            ),
        ),
    )


def _strategy(*, target_id: str = "blue-ship", quantity: int = 4) -> StrategySpec:
    return StrategySpec(
        scenario_id="stable-scenario",
        attacks=(
            AttackDirective(
                attack_id="ship-attack",
                shooter_id="red-ship",
                target_ids=(target_id,),
                weapon_dbid=500,
                fire_quantity=quantity,
                delay_seconds=30,
            ),
        ),
    )


def test_validator_accepts_strategy_using_existing_enemy_and_inventory() -> None:
    result = StrategyValidator().validate(_strategy(), _definition())

    assert result.valid is True


def test_validator_rejects_strategy_that_exceeds_inventory() -> None:
    result = StrategyValidator().validate(_strategy(quantity=5), _definition())

    assert [issue.code for issue in result.errors] == [
        "strategy.ammo_exceeded",
    ]


def test_validator_rejects_friendly_target_without_contract_dependency() -> None:
    result = StrategyValidator().validate(
        _strategy(target_id="red-ship"),
        _definition(),
    )

    assert [issue.code for issue in result.errors] == [
        "strategy.friendly_target",
    ]


def test_validator_rejects_total_fire_quantity_that_exceeds_one_inventory() -> None:
    strategy = StrategySpec(
        scenario_id="stable-scenario",
        attacks=(
            _strategy(quantity=3).attacks[0],
            AttackDirective(
                attack_id="ship-attack-second",
                shooter_id="red-ship",
                target_ids=("blue-ship",),
                weapon_dbid=500,
                fire_quantity=3,
                delay_seconds=31,
            ),
        ),
    )

    result = StrategyValidator().validate(strategy, _definition())

    assert [issue.code for issue in result.errors] == [
        "strategy.total_ammo_exceeded",
    ]


def test_validator_rejects_sortie_with_wrong_base_and_invalid_route() -> None:
    strategy = StrategySpec(
        scenario_id="stable-scenario",
        sorties=(
            SortieDirective(
                sortie_id="sortie-1",
                aircraft_id="red-ship",
                target_id="blue-ship",
                base_unit_id="blue-ship",
                route=(
                    RouteWaypoint(latitude=91.0, longitude=181.0),
                ),
                altitude_meters=8000,
                throttle="Cruise",
                fire_delay_seconds=30,
                return_delay_seconds=600,
            ),
        ),
    )

    result = StrategyValidator().validate(strategy, _definition())

    assert [issue.code for issue in result.errors] == [
        "strategy.base_mismatch",
        "strategy.route_coordinate_invalid",
    ]
