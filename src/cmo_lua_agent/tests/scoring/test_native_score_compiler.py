from __future__ import annotations

import pytest

from cmo_lua_agent.contract.strategy_models import ScenarioDefinition, ScenarioUnit
from cmo_lua_agent.scoring.models import (
    ScoreProfile,
    ScoreRole,
    ScenarioObjective,
    ScenarioObjectives,
    UnitRoleAssignment,
    UnitRoleCatalog,
)
from cmo_lua_agent.scoring.native_score_compiler import CmoNativeScoreCompileError, CmoNativeScoreCompiler


def _scenario() -> ScenarioDefinition:
    return ScenarioDefinition(
        scenario_id="red_blue_6v4_liaoning",
        units=(
            ScenarioUnit("blue_cvn70", "blue", "Blue CVN-70 Carl Vinson", "ship", 3551),
            ScenarioUnit("blue_cg59", "blue", "Blue CG-59 Princeton", "ship", 2862),
            ScenarioUnit("blue_ddg113_1", "blue", "Blue DDG-113-1 John Finn", "ship", 4299),
            ScenarioUnit("blue_ddg113_2", "blue", "Blue DDG-113-2 John Finn", "ship", 4299),
            ScenarioUnit("red_liaoning", "red", "Red Liaoning", "ship", 2007),
            ScenarioUnit("red_055_nanchang", "red", "Red 055 Nanchang", "ship", 3883),
            ScenarioUnit("red_052d_1", "red", "Red 052D Kunming", "ship", 2296),
            ScenarioUnit("red_052d_2", "red", "Red 052D Nanjing", "ship", 3586),
            ScenarioUnit("red_j15_1", "red", "J-15-1", "aircraft", 2496),
            ScenarioUnit("red_j15_2", "red", "J-15-2", "aircraft", 2496),
            ScenarioUnit("blue_supply", "blue", "Blue Supply", "ship", 1),
        ),
    )


def _catalog() -> UnitRoleCatalog:
    return UnitRoleCatalog(
        catalog_id="red_blue_6v4_roles",
        catalog_version="1.0.0",
        scenario_id="red_blue_6v4_liaoning",
        assignments=(
            UnitRoleAssignment("blue_cvn70", "carrier", "scored"),
            UnitRoleAssignment("blue_cg59", "cruiser", "scored"),
            UnitRoleAssignment("blue_ddg113_1", "destroyer", "scored"),
            UnitRoleAssignment("blue_ddg113_2", "destroyer", "scored"),
            UnitRoleAssignment("red_liaoning", "carrier", "scored"),
            UnitRoleAssignment("red_055_nanchang", "cruiser", "scored"),
            UnitRoleAssignment("red_052d_1", "destroyer", "scored"),
            UnitRoleAssignment("red_052d_2", "destroyer", "scored"),
            UnitRoleAssignment("red_j15_1", "carrier_fighter", "scored"),
            UnitRoleAssignment("red_j15_2", "carrier_fighter", "scored"),
            UnitRoleAssignment("blue_supply", None, "unscored"),
        ),
    )


def _profile() -> ScoreProfile:
    return ScoreProfile(
        profile_id="naval_air_anti_surface",
        profile_version="1.0.0",
        score_side_id="red",
        roles=(
            ScoreRole("carrier", 200, 200),
            ScoreRole("cruiser", 100, 100),
            ScoreRole("destroyer", 75, 75),
            ScoreRole("carrier_fighter", 20, 20),
        ),
    )


def _objectives() -> ScenarioObjectives:
    return ScenarioObjectives(
        scenario_id="red_blue_6v4_liaoning",
        objectives_version="1.0.0",
        objectives=tuple(
            ScenarioObjective(
                objective_id=f"score-{assignment.unit_id}",
                objective_kind="destroy" if assignment.unit_id.startswith("blue_") else "preserve",
                target_unit_id=assignment.unit_id,
                required=True,
            )
            for assignment in _catalog().assignments
            if assignment.scoring_status == "scored"
        ),
    )


def test_compiler_expands_6v4_into_ten_native_score_rules() -> None:
    result = CmoNativeScoreCompiler().compile(
        scenario=_scenario(),
        role_catalog=_catalog(),
        score_profile=_profile(),
        objectives=_objectives(),
    )

    points = {rule.target_unit_id: rule.point_change for rule in result.score_spec.rules}
    assert points == {
        "blue_cvn70": 200,
        "blue_cg59": 100,
        "blue_ddg113_1": 75,
        "blue_ddg113_2": 75,
        "red_liaoning": -200,
        "red_055_nanchang": -100,
        "red_052d_1": -75,
        "red_052d_2": -75,
        "red_j15_1": -20,
        "red_j15_2": -20,
    }
    assert {rule.score_side_id for rule in result.score_spec.rules} == {"red"}
    assert "blue_supply" not in points


def test_compiler_is_deterministic_and_records_all_checksums() -> None:
    compiler = CmoNativeScoreCompiler()
    first = compiler.compile(
        scenario=_scenario(), role_catalog=_catalog(), score_profile=_profile(), objectives=_objectives()
    )
    second = compiler.compile(
        scenario=_scenario(), role_catalog=_catalog(), score_profile=_profile(), objectives=_objectives()
    )

    assert first.score_spec.to_dict() == second.score_spec.to_dict()
    assert first.fragment.content == second.fragment.content
    assert first.score_spec.checksum == second.score_spec.checksum
    assert first.fragment.checksum == second.fragment.checksum
    assert first.scenario_checksum
    assert first.role_catalog_checksum
    assert first.score_profile_checksum
    assert first.objectives_checksum
    assert first.score_spec_checksum == first.score_spec.checksum
    assert first.fragment_checksum == first.fragment.checksum
    assert first.compiler_version


def test_fragment_registers_complete_native_trigger_action_event_chain() -> None:
    fragment = CmoNativeScoreCompiler().compile(
        scenario=_scenario(), role_catalog=_catalog(), score_profile=_profile(), objectives=_objectives()
    ).fragment.content

    assert "pcall(ScenEdit_SetEvent, event_name, {mode='remove'})" in fragment
    assert "pcall(ScenEdit_SetTrigger, {mode='remove', type='UnitDestroyed'" in fragment
    assert "pcall(ScenEdit_SetAction, {mode='remove', type='Points'" in fragment
    assert "pcall(ScenEdit_GetUnit, {side=rule.target_side_id, name=rule.target_unit_name})" in fragment
    assert "type='UnitDestroyed'" in fragment
    assert "type='Points'" in fragment
    assert "ScenEdit_SetEventTrigger(rule.event_name" in fragment
    assert "ScenEdit_SetEventAction(rule.event_name" in fragment
    assert "IsActive=true" in fragment
    assert "[CMO-NATIVE-SCORE]" in fragment
    assert "error(" in fragment


def test_compiler_rejects_unrecognized_scored_role_kind() -> None:
    catalog = UnitRoleCatalog(
        catalog_id="bad-roles",
        catalog_version="1.0.0",
        scenario_id="red_blue_6v4_liaoning",
        assignments=(UnitRoleAssignment("blue_cvn70", "submarine", "scored"),),
    )
    objectives = ScenarioObjectives(
        scenario_id="red_blue_6v4_liaoning",
        objectives_version="1.0.0",
        objectives=(ScenarioObjective("score-carrier", "destroy", "blue_cvn70", True),),
    )

    with pytest.raises(CmoNativeScoreCompileError, match="submarine"):
        CmoNativeScoreCompiler().compile(
            scenario=_scenario(), role_catalog=catalog, score_profile=_profile(), objectives=objectives
        )


def test_compiler_rejects_objective_for_explicitly_unscored_unit() -> None:
    objectives = ScenarioObjectives(
        scenario_id="red_blue_6v4_liaoning",
        objectives_version="1.0.0",
        objectives=(ScenarioObjective("score-supply", "destroy", "blue_supply", True),),
    )

    with pytest.raises(CmoNativeScoreCompileError, match="unscored"):
        CmoNativeScoreCompiler().compile(
            scenario=_scenario(), role_catalog=_catalog(), score_profile=_profile(), objectives=objectives
        )


def test_compiler_rejects_catalog_assignment_for_unknown_unit() -> None:
    catalog = UnitRoleCatalog(
        catalog_id="bad-roles",
        catalog_version="1.0.0",
        scenario_id="red_blue_6v4_liaoning",
        assignments=(
            UnitRoleAssignment("blue_cvn70", "carrier", "scored"),
            UnitRoleAssignment("missing_unit", None, "unscored"),
        ),
    )
    objectives = ScenarioObjectives(
        scenario_id="red_blue_6v4_liaoning",
        objectives_version="1.0.0",
        objectives=(ScenarioObjective("score-carrier", "destroy", "blue_cvn70", True),),
    )

    with pytest.raises(CmoNativeScoreCompileError, match="missing_unit"):
        CmoNativeScoreCompiler().compile(
            scenario=_scenario(), role_catalog=catalog, score_profile=_profile(), objectives=objectives
        )
