from __future__ import annotations

from pathlib import Path

import pytest

from cmo_lua_agent.evolution.campaign_input import CampaignInputLoader
from cmo_lua_agent.evolution.controlled_input_package import (
    ControlledCampaignInputPackageLoader,
)
from cmo_lua_agent.evolution.production_assets import (
    ControlledScenarioAssetRegistry,
)
from cmo_lua_agent.evolution.production_models import ControlledScenarioAsset


PROJECT_ROOT = Path(__file__).resolve().parents[4]
LEGACY_PATH = (
    PROJECT_ROOT
    / "baseline"
    / "6v4"
    / "legacy"
    / "baseline_strategy.pre-scenario-ir.json"
)


def _asset() -> ControlledScenarioAsset:
    return ControlledScenarioAsset(
        asset_id="red_blue_6v4_liaoning_scen_v1",
        scenario_id="red_blue_6v4_liaoning",
        absolute_path="C:/fixture/6v4.scen",
        sha256="fixture-scenario-sha",
        size_bytes=1,
        verification_record_path="C:/fixture/verification.json",
        verified_clean_initial_state=True,
    )


def test_production_package_derives_baseline_without_reading_legacy_asset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_read_bytes = Path.read_bytes

    def reject_legacy_read(path: Path) -> bytes:
        if path.resolve() == LEGACY_PATH.resolve():
            raise AssertionError("production attempted to read the legacy baseline")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", reject_legacy_read)
    monkeypatch.setattr(
        ControlledScenarioAssetRegistry,
        "load_verified",
        lambda _self, _asset_id: _asset(),
    )
    loader = ControlledCampaignInputPackageLoader(
        project_root=PROJECT_ROOT,
    )

    first = loader.load("red_blue_6v4_liaoning_v1")
    second = loader.load("red_blue_6v4_liaoning_v1")

    # StrategySpec remains ScenarioIR-derived; the executable baseline is the
    # checked-in active-strike template layered over that formal strategy.
    assert first.baseline.source_lua == "baseline/6v4/manual-template/manual_baseline_template.lua"
    assert first.manual_template_root == PROJECT_ROOT / "baseline/6v4/manual-template"
    assert first.checksums["baseline_strategy_derived"] == second.checksums[
        "baseline_strategy_derived"
    ]
    assert "baseline_strategy_legacy" not in first.checksums
    names = {unit.unit_id: unit.name for unit in first.scenario.units}
    assert {
        rule.target_unit_name
        for rule in first.native_score_compilation.score_spec.rules
    } == {
        names[rule.target_unit_id]
        for rule in first.native_score_compilation.score_spec.rules
    }


def test_controlled_package_records_dirty_worktree_without_rejecting_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ControlledScenarioAssetRegistry,
        "load_verified",
        lambda _self, _asset_id: _asset(),
    )
    monkeypatch.setattr(
        ControlledCampaignInputPackageLoader,
        "_git_state",
        lambda _self: ("fixture-commit", True, "fixture-diff"),
    )

    package = ControlledCampaignInputPackageLoader(
        project_root=PROJECT_ROOT,
    ).load("red_blue_6v4_liaoning_v1")

    assert package.working_tree_dirty is True
    assert package.diff_checksum == "fixture-diff"


def test_controlled_package_loads_a_training_scenario_ir_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ControlledScenarioAssetRegistry,
        "load_verified",
        lambda _self, _asset_id: _asset(),
    )
    reference = "baseline/6v4/manual-template/6v4ScenarioIR_baseline_v3.json"

    package = ControlledCampaignInputPackageLoader(
        project_root=PROJECT_ROOT,
    ).load(reference)

    assert package.package_id == reference
    assert package.scenario_ir_path == PROJECT_ROOT / reference
    assert package.scenario.scenario_id == "red_blue_6v4_liaoning"
    assert package.baseline.strategy.attacks[0].weapon_selection == "explicit"
    assert package.baseline.strategy.sorties[0].air_tactics.popup_altitude_m == 9500


def test_explicit_legacy_baseline_override_is_rejected() -> None:
    with pytest.raises(ValueError, match="legacy_baseline_not_production_eligible"):
        CampaignInputLoader().load_6v4(
            project_root=PROJECT_ROOT,
            job_config_path=PROJECT_ROOT / "json_data" / "tot-three.json",
            baseline_source_path=LEGACY_PATH,
        )


def test_campaign_input_loader_derives_from_scenario_ir() -> None:
    bundle = CampaignInputLoader().load_6v4(
        project_root=PROJECT_ROOT,
        job_config_path=PROJECT_ROOT / "json_data" / "tot-three.json",
    )

    assert bundle.scenario_ir_path == PROJECT_ROOT / "json_data" / "6v4ScenarioIR.json"
    assert bundle.baseline.source_lua == "json_data/6v4ScenarioIR.json"
    assert bundle.checksums["baseline_strategy_derived"]
