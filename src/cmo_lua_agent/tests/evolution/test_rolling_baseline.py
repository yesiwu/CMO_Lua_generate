from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from cmo_lua_agent.evolution.rolling_baseline import (
    RollingBaselineResolver,
    apply_rolling_baseline,
)


@dataclass(frozen=True)
class _Baseline:
    strategy: object
    source_lua: str
    verified: bool


@dataclass(frozen=True)
class _Package:
    baseline: _Baseline


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_generation_two_uses_generation_one_champion_strategy(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    strategy = {"scenario_id": "six_v_four", "attacks": [], "sorties": []}
    _write_json(
        root / "generations" / "generation_001" / "generation-result.json",
        {"champion_decision": {"selected_champion_id": "candidate_02"}},
    )
    _write_json(
        root / "generations" / "generation_001" / "phase6" / "candidate_02" / "strategy" / "final_strategy.json",
        strategy,
    )

    resolved = RollingBaselineResolver(root).resolve_for_generation(2)

    assert resolved.source_generation_index == 1
    assert resolved.champion_id == "candidate_02"
    assert resolved.strategy == strategy


def test_generation_after_zero_requires_a_persisted_champion(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "campaign" / "generations" / "generation_001" / "generation-result.json",
        {"champion_decision": None},
    )
    with pytest.raises(ValueError, match="previous_generation_champion_missing"):
        RollingBaselineResolver(tmp_path / "campaign").resolve_for_generation(2)


def test_resolved_champion_replaces_only_the_next_generation_baseline(tmp_path: Path) -> None:
    strategy = {"scenario_id": "six_v_four", "attacks": [], "sorties": []}
    _write_json(
        tmp_path / "campaign" / "generations" / "generation_001" / "generation-result.json",
        {"champion_decision": {"selected_champion_id": "candidate_01"}},
    )
    _write_json(
        tmp_path / "campaign" / "generations" / "generation_001" / "phase6" / "candidate_01" / "strategy" / "final_strategy.json",
        strategy,
    )
    package = _Package(_Baseline(strategy={"scenario_id": "initial"}, source_lua="initial.lua", verified=True))

    updated = apply_rolling_baseline(
        package,
        RollingBaselineResolver(tmp_path / "campaign").resolve_for_generation(2),
    )

    assert updated.baseline.strategy.to_dict() == strategy
    assert package.baseline.strategy == {"scenario_id": "initial"}
