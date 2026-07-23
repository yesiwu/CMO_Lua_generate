from __future__ import annotations

import json
from pathlib import Path

from cmo_lua_agent.generation.phase32_scored_golden import Phase32ScoredGoldenService


ROOT = Path(__file__).resolve().parents[4]
BASELINE_ROOT = ROOT / "baseline" / "6v4"
SCORED_ROOT = BASELINE_ROOT / "scored"


def test_scored_golden_matches_reviewed_artifacts_without_rewriting_them() -> None:
    result = Phase32ScoredGoldenService().render(baseline_root=BASELINE_ROOT)
    expected_lua = (SCORED_ROOT / "rendered_scored_baseline.lua").read_text(encoding="utf-8")
    expected_manifest = json.loads((SCORED_ROOT / "generation_manifest.json").read_text(encoding="utf-8"))
    golden_manifest = json.loads((SCORED_ROOT / "golden_manifest.json").read_text(encoding="utf-8"))

    assert result.rendered.content == expected_lua
    assert result.generation_manifest == expected_manifest
    assert golden_manifest["lua_checksum"] == result.rendered.lua_checksum
    assert golden_manifest["score_spec_checksum"] == result.generation_manifest["score_spec_checksum"]
    assert golden_manifest["instrumentation_enabled"] if "instrumentation_enabled" in golden_manifest else True


def test_scored_golden_contains_all_ten_native_rules_once() -> None:
    result = Phase32ScoredGoldenService().render(baseline_root=BASELINE_ROOT)

    assert result.rendered.content.count("score_log('installed native score rules='") == 1
    assert result.rendered.content.count("native_score/") == 10
    assert "-- BEGIN OP native_score/" not in result.rendered.content
