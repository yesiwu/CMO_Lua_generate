"""Run one native-Points-scored generation from frozen StrategySpecs.

This is intentionally a narrow operational entrypoint: it does not propose
strategies, call DeepSeek, run Phase 8, or mutate the source generation.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from cmo_lua_agent.contract.strategy_models import strategy_spec_from_dict
from cmo_lua_agent.evolution.production_service import create_production_evolution_campaign_service
from cmo_lua_agent.llm.client import ClaudeClient
from cmo_lua_agent.llm_config import load_config
from cmo_lua_agent.optimization.candidate_set_validator import strategy_leaf_diff


SOURCE_CAMPAIGN = "phase9_blackbox_generation_001_v2_rerun_20260803"
# Keep BatchRunner result paths below Windows' legacy 260-character limit.
CAMPAIGN_ID = "g1_native_points_0803"
GENERATION_INDEX = 1


def _read_strategy(path: Path):
    return strategy_spec_from_dict(json.loads(path.read_text(encoding="utf-8-sig")))


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"strategy root must be an object: {path}")
    return value


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _official_score(outcome_path: Path) -> int | None:
    value = json.loads(outcome_path.read_text(encoding="utf-8"))
    score = value.get("native_score")
    return score if isinstance(score, int) else None


def main() -> None:
    root = Path.cwd()
    source_phase6 = root / "runs" / "evolution" / SOURCE_CAMPAIGN / "generations" / "generation_001" / "phase6"
    phase6 = root / "runs" / "evolution" / CAMPAIGN_ID / "generations" / "generation_001" / "phase6"
    if phase6.exists():
        raise RuntimeError(f"refusing to overwrite existing generation: {phase6}")

    config = load_config()
    service = create_production_evolution_campaign_service(
        project_root=root,
        app_config=config,
        llm_client=ClaudeClient(config.llm),
    )
    package = service._package_loader.load("red_blue_6v4_liaoning_v1")

    baseline = _read_strategy(source_phase6 / "candidate_baseline" / "strategy" / "final_strategy.json")
    strategies = {
        candidate_id: _read_strategy(source_phase6 / candidate_id / "strategy" / "final_strategy.json")
        for candidate_id in ("candidate_00", "candidate_01", "candidate_02", "candidate_03")
    }

    context = SimpleNamespace(
        spec=SimpleNamespace(
            campaign_id=CAMPAIGN_ID,
            budget=SimpleNamespace(per_candidate_timeout_seconds=1200),
        ),
        control_action=lambda: None,
    )
    # The production factory owns the only configured CMO evaluator. It is
    # reused here without invoking the proposal client or campaign worker.
    evaluator = service._candidate_evaluator
    _write(
        phase6 / "generation-input.json",
        {
            "campaign_id": CAMPAIGN_ID,
            "generation_index": GENERATION_INDEX,
            "source_campaign_id": SOURCE_CAMPAIGN,
            "execution_mode": "blackbox_outcome_comparison_native_points",
            "deepseek_calls": 0,
            "scoring_mode": "native_unit_destroyed_points",
        },
    )

    rows: list[dict[str, object]] = []
    all_strategies = {"baseline": baseline, **strategies}
    for slot, strategy in all_strategies.items():
        candidate_dir = phase6 / ("candidate_baseline" if slot == "baseline" else slot)
        result = evaluator(
            candidate_id="baseline" if slot == "baseline" else slot,
            strategy=strategy,
            candidate_dir=candidate_dir,
            generation_index=GENERATION_INDEX,
            context=context,
            package=package,
        )
        outcome_path = candidate_dir / "candidate_outcome.json"
        score = _official_score(outcome_path)
        rows.append(
            {
                "candidate_id": "baseline" if slot == "baseline" else slot,
                "outcome_path": str(outcome_path),
                "official_score": score,
                "execution_success": bool(result.get("execution_success")),
                "scoreable": bool(result.get("scoreable")),
                "semantic_valid": bool(result.get("semantic_valid")),
            }
        )

    baseline_score = next(row["official_score"] for row in rows if row["candidate_id"] == "baseline")
    ranked = sorted(
        (row for row in rows if row["candidate_id"] != "baseline" and row["official_score"] is not None),
        key=lambda row: (-int(row["official_score"]), str(row["candidate_id"])),
    )
    for index, row in enumerate(ranked, 1):
        row["rank"] = index
        row["delta_vs_baseline"] = int(row["official_score"]) - int(baseline_score)
    _write(phase6 / "leaderboard.json", {"baseline_score": baseline_score, "entries": ranked})
    _write(
        phase6 / "generation_result.json",
        {
            "optimization_id": CAMPAIGN_ID,
            "baseline_outcome_path": str(phase6 / "candidate_baseline" / "candidate_outcome.json"),
            "candidate_outcome_paths": [
                str(phase6 / cid / "candidate_outcome.json")
                for cid in ("candidate_00", "candidate_01", "candidate_02", "candidate_03")
            ],
            "execution_mode": "blackbox_outcome_comparison",
            "cmo_run_count": 5,
        },
    )
    _write(
        phase6 / "strategy_diff.json",
        {
            cid: list(strategy_leaf_diff(baseline, strategy, package.allowed_strategy_paths))
            for cid, strategy in strategies.items()
        },
    )
    _write(phase6 / "generation-result.json", {"slots": rows, "leaderboard": ranked})
    print(json.dumps({"phase6": str(phase6), "slots": rows, "leaderboard": ranked}, ensure_ascii=False))


if __name__ == "__main__":
    main()
