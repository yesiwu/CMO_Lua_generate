from __future__ import annotations

import pytest

from cmo_lua_agent.scoring.models import (
    ScoreProfile,
    ScoreRole,
    ScenarioObjective,
    ScenarioObjectives,
    UnitRoleAssignment,
    UnitRoleCatalog,
)


def test_scored_assignment_requires_a_role_kind() -> None:
    with pytest.raises(ValueError, match="role_kind"):
        UnitRoleAssignment(
            unit_id="blue_cvn70",
            role_kind=None,
            scoring_status="scored",
        )


def test_unscored_assignment_is_explicit() -> None:
    assignment = UnitRoleAssignment(
        unit_id="blue_support_ship",
        role_kind=None,
        scoring_status="unscored",
    )

    assert assignment.scoring_status == "unscored"


def test_score_profile_owns_one_scoring_side_and_role_points() -> None:
    profile = ScoreProfile(
        profile_id="naval-air-anti-surface",
        profile_version="1.0.0",
        score_side_id="red",
        roles=(
            ScoreRole(
                role_kind="carrier",
                enemy_destroyed_points=200,
                own_destroyed_points=200,
            ),
        ),
    )

    assert profile.score_side_id == "red"
    assert profile.role_scores()["carrier"].enemy_destroyed_points == 200


def test_objectives_reference_target_unit_ids_not_native_rule_ids() -> None:
    objectives = ScenarioObjectives(
        scenario_id="golden",
        objectives_version="1.0.0",
        objectives=(
            ScenarioObjective(
                objective_id="destroy-carrier",
                objective_kind="destroy",
                target_unit_id="blue_cvn70",
                required=True,
            ),
        ),
    )

    assert objectives.objectives[0].target_unit_id == "blue_cvn70"


def test_role_catalog_rejects_duplicate_unit_assignments() -> None:
    with pytest.raises(ValueError, match="unit_id"):
        UnitRoleCatalog(
            catalog_id="golden-roles",
            catalog_version="1.0.0",
            scenario_id="golden",
            assignments=(
                UnitRoleAssignment("blue_cvn70", "carrier", "scored"),
                UnitRoleAssignment("blue_cvn70", "carrier", "scored"),
            ),
        )
