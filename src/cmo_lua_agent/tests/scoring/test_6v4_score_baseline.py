from __future__ import annotations

import json
from pathlib import Path

from cmo_lua_agent.scoring.baseline import compile_score_baseline


PROJECT_ROOT = Path(__file__).parents[4]
BASELINE_ROOT = PROJECT_ROOT / "baseline" / "6v4"


def test_6v4_score_baseline_matches_reviewed_score_snapshots() -> None:
    result = compile_score_baseline(BASELINE_ROOT)

    assert len(result.score_spec.rules) == 10
    assert result.score_spec.to_dict() == json.loads(
        (BASELINE_ROOT / "scenario_score_spec.json").read_text(encoding="utf-8")
    )
    assert result.fragment.content == (BASELINE_ROOT / "native_score_fragment.lua").read_text(
        encoding="utf-8"
    )
    assert result.manifest == json.loads(
        (BASELINE_ROOT / "native_score_compilation_manifest.json").read_text(encoding="utf-8")
    )
