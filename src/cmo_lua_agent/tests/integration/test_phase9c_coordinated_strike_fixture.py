from __future__ import annotations

import json
from pathlib import Path

import pytest

from cmo_lua_agent.optimization.proposal_models import (
    CandidatePatch,
    ProposalContractError,
    StrategyPatchOperation,
)
from cmo_lua_agent.generation.coordinated_strike_fixture import (
    build_coordinated_strike_fixture,
    load_coordinated_strike_patch,
)


PROJECT_ROOT = Path(__file__).resolve().parents[4]
REGRESSION_ROOT = PROJECT_ROOT / "baseline" / "6v4" / "regressions"


def test_coordinated_strike_fixture_uses_the_formal_chain_deterministically() -> None:
    first = build_coordinated_strike_fixture(PROJECT_ROOT)
    second = build_coordinated_strike_fixture(PROJECT_ROOT)

    assert first.validation.valid
    assert first.changed_paths == (
        "/attacks/0/delay_seconds",
        "/attacks/0/fire_quantity",
        "/attacks/1/delay_seconds",
        "/attacks/1/target_ids/0",
        "/attacks/2/delay_seconds",
        "/sorties/0/route/0/latitude",
        "/sorties/1/route/0/longitude",
    )
    assert first.semantic_dimensions == (
        "air_route",
        "attack_timing",
        "fire_quantity",
        "target_assignment",
    )
    assert len(first.changed_operation_ids) == 5
    assert first.surface_operation_count == 3
    assert first.sortie_operation_count == 2
    assert first.manifest["strategy_checksum"] == second.manifest["strategy_checksum"]
    assert first.plan.checksum == second.plan.checksum
    assert first.rendered.lua_checksum == second.rendered.lua_checksum

    attacks = {attack.shooter_id: attack for attack in first.strategy.attacks}
    assert attacks["red_055_nanchang"].target_ids == ("blue_ddg113_1",)
    assert attacks["red_055_nanchang"].delay_seconds == 15
    assert attacks["red_055_nanchang"].fire_quantity == 7
    assert attacks["red_052d_1"].target_ids == ("blue_cvn70",)
    assert attacks["red_052d_1"].delay_seconds == 45
    assert attacks["red_052d_2"].target_ids == ("blue_cg59",)
    assert attacks["red_052d_2"].delay_seconds == 75
    assert {sortie.aircraft_id: sortie.target_id for sortie in first.strategy.sorties} == {
        "red_j15_1": "blue_cvn70",
        "red_j15_2": "blue_ddg113_2",
    }
    assert {
        sortie.aircraft_id: (sortie.route[0].latitude, sortie.route[0].longitude)
        for sortie in first.strategy.sorties
    } == {
        "red_j15_1": (23.55, 129.98),
        "red_j15_2": (23.65, 130.05),
    }
    assert all(attack.weapon_selection == "auto" for attack in first.strategy.attacks)
    assert all(attack.weapon_dbid is None for attack in first.strategy.attacks)

    ship_operations = {
        operation.parameters["shooter_id"]: operation
        for operation in first.plan.operations
        if operation.primitive_type == "schedule_ship_attack"
    }
    assert ship_operations["red_055_nanchang"].parameters["target_ids"] == (
        "blue_ddg113_1",
    )
    assert ship_operations["red_052d_1"].parameters["delay_seconds"] == 45
    assert ship_operations["red_052d_2"].parameters["delay_seconds"] == 75
    sortie_operations = {
        operation.parameters["aircraft_id"]: operation
        for operation in first.plan.operations
        if operation.primitive_type == "set_aircraft_route"
    }
    assert dict(sortie_operations["red_j15_1"].parameters["route"][0]) == {
        "latitude": 23.55,
        "longitude": 129.98,
    }
    assert dict(sortie_operations["red_j15_2"].parameters["route"][0]) == {
        "latitude": 23.65,
        "longitude": 130.05,
    }
    assert "nil,7)" in first.rendered.content
    assert ",2868,7)" not in first.rendered.content
    assert "23.55,129.98" in first.rendered.content
    assert "23.65,130.05" in first.rendered.content
    for operation_id, delay in (
        ("attack.red_055_attack_ddg113_1", 15),
        ("attack.red_052d_1_attack_cg59", 45),
        ("attack.red_052d_2_attack_cg59", 75),
    ):
        assert operation_id in first.rendered.content
        assert f", {delay})" in first.rendered.content

    manifest = first.manifest
    assert manifest["formal_comparison_eligible"] is False
    assert manifest["fixture_purpose"] == "formal_chain_expression_regression"
    assert manifest["runtime_version"] == "2.0.0"
    assert manifest["score_spec_checksum"] == (
        "9a7f68a20cea722df7ae77c28a93199b1042258bd153973e25021b5e498762df"
    )
    assert manifest["native_score_fragment_checksum"] == (
        "96f2f2e8694520581922d57bc6650e434688e3bcfa90e6f2c99ec27ae3400b4b"
    )
    assert manifest["source_scenario_ir_checksum"] == (
        "b04a65ed8d06d49e20671e446624c2de886f35247e09b28e25d31b995b6a558d"
    )


def test_checked_in_coordinated_strike_artifacts_match_fresh_formal_render() -> None:
    result = build_coordinated_strike_fixture(PROJECT_ROOT)

    assert json.loads((REGRESSION_ROOT / "coordinated-strike-strategy.json").read_text(encoding="utf-8")) == result.strategy.to_dict()
    assert json.loads((REGRESSION_ROOT / "coordinated-strike-execution-plan.json").read_text(encoding="utf-8")) == result.plan.to_dict()
    assert (REGRESSION_ROOT / "coordinated-strike.lua").read_text(encoding="utf-8") == result.rendered.content
    assert json.loads((REGRESSION_ROOT / "coordinated-strike-manifest.json").read_text(encoding="utf-8")) == result.manifest


@pytest.mark.parametrize(
    ("path", "value", "code"),
    (
        ("/scenario_id", "other", "path_not_catalogued"),
        ("/attacks/0/attack_id", "other", "path_not_catalogued"),
        ("/attacks/0/weapon_dbid", 1, "path_not_catalogued"),
        ("/attacks/5/fire_quantity", 1, "path_not_catalogued"),
        ("/sorties/0/route/1/latitude", 20.0, "path_not_catalogued"),
        ("/attacks/0/delay_seconds", -1, "value_below_minimum"),
        ("/attacks/0/fire_quantity", 99, "value_above_maximum"),
    ),
)
def test_coordinated_strike_rejects_unsafe_or_out_of_range_patches(
    path: str, value: object, code: str
) -> None:
    result = build_coordinated_strike_fixture(PROJECT_ROOT)
    patch = CandidatePatch(
        candidate_id="candidate_02",
        proposal_summary="invalid fixture patch",
        changes=(StrategyPatchOperation(path=path, value=value),),
    )

    with pytest.raises(ProposalContractError) as error:
        result.assembler.assemble(patch)
    assert error.value.code == code


def test_coordinated_strike_constraints_reject_duplicate_target_or_delay() -> None:
    patch = load_coordinated_strike_patch(PROJECT_ROOT)
    duplicate = CandidatePatch(
        candidate_id=patch.candidate_id,
        proposal_summary=patch.proposal_summary,
        changes=tuple(
            StrategyPatchOperation(
                path=change.path,
                value=("blue_ddg113_1" if change.path == "/attacks/1/target_ids/0" else change.value),
            )
            for change in patch.changes
        ),
    )

    with pytest.raises(ProposalContractError, match="coordinated_strike_target_deconfliction_failed"):
        build_coordinated_strike_fixture(PROJECT_ROOT, patch=duplicate)

    duplicate_delay = CandidatePatch(
        candidate_id=patch.candidate_id,
        proposal_summary=patch.proposal_summary,
        changes=tuple(
            StrategyPatchOperation(
                path=change.path,
                value=(15 if change.path == "/attacks/1/delay_seconds" else change.value),
            )
            for change in patch.changes
        ),
    )
    with pytest.raises(ProposalContractError, match="coordinated_strike_delay_deconfliction_failed"):
        build_coordinated_strike_fixture(PROJECT_ROOT, patch=duplicate_delay)


def test_coordinated_strike_fixture_never_reads_the_legacy_baseline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy = (
        PROJECT_ROOT
        / "baseline"
        / "6v4"
        / "legacy"
        / "baseline_strategy.pre-scenario-ir.json"
    ).resolve()
    original = Path.read_text

    def reject_legacy(path: Path, *args: object, **kwargs: object) -> str:
        if path.resolve() == legacy:
            raise AssertionError("coordinated fixture read legacy baseline")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", reject_legacy)
    assert build_coordinated_strike_fixture(PROJECT_ROOT).validation.valid
