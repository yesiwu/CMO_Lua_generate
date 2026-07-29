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
        require_clean_worktree=False,
    )

    first = loader.load("red_blue_6v4_liaoning_v1")
    second = loader.load("red_blue_6v4_liaoning_v1")

    assert first.baseline.source_lua == "json_data/6v4ScenarioIR.json"
    assert first.checksums["baseline_strategy_derived"] == second.checksums[
        "baseline_strategy_derived"
    ]
    assert "baseline_strategy_legacy" not in first.checksums


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
