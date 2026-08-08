from __future__ import annotations

from pathlib import Path

import pytest

from cmo_lua_agent.training.input_resolver import ScenarioInputResolver


def test_resolver_returns_a_project_relative_reference_for_compatible_scenario_ir() -> None:
    project_root = Path(__file__).resolve().parents[4]
    source = project_root / "baseline" / "6v4" / "manual-template" / "6v4ScenarioIR_baseline_v3.json"

    resolved = ScenarioInputResolver(project_root).resolve(source)

    assert resolved.reference == "baseline/6v4/manual-template/6v4ScenarioIR_baseline_v3.json"
    assert resolved.absolute_path == source.resolve()
    assert resolved.scenario_id == "red_blue_6v4_liaoning"


def test_resolver_rejects_a_missing_scenario_ir(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="scenario_ir_not_found"):
        ScenarioInputResolver(tmp_path).resolve(tmp_path / "missing.json")
