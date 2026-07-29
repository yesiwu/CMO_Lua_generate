from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

from cmo_lua_agent.contract import load_baseline_strategy, load_scenario_definition
from cmo_lua_agent.core.run_artifact_store import RunArtifactStore
from cmo_lua_agent.execution.cmo_runner import CmoExecutionRecord
from cmo_lua_agent.execution.models import CmoProcessResult, CmoRunResult
from cmo_lua_agent.generation.phase32_scored_golden import Phase32ScoredGoldenService
from cmo_lua_agent.scoring.baseline import compile_score_baseline


def _create_result(root: Path) -> Path:
    job = root / "001_all"
    job.mkdir(parents=True)
    (root / "runner.log").write_text("batch", encoding="utf-8")
    (job / "lua-output.log").write_text(
        "[P2] Launch/J-15-1 success=true\n"
        "[P2] Launch/J-15-2 success=true\n"
        "[P2] operation air_attack.air-j15-1-cvn70\n"
        "[P2] operation air_attack.air-j15-2-ddg113-2\n",
        encoding="utf-8",
    )
    con = sqlite3.connect(job / "events.sqlite")
    con.executescript("""
    create table side_scores(phase text, side text, score integer);
    create table unit_damage_events(sim_time text, event_type text, unit_id text, unit_name text, unit_side text, reason text);
    create table weapon_events(sim_time text, event_type text, weapon_name text, weapon_class text, weapon_side text, firing_unit_name text, target_name text, target_side text, result text);
    create table run_info(script text, scenario text, status text, end_reason text, sim_ended text);
    """)
    con.executemany("insert into side_scores values(?,?,?)", [("start", "red", 0), ("end", "red", -40)])
    con.executemany("insert into unit_damage_events values(?,?,?,?,?,?)", [
        ("2026-07-01T00:27:10Z", "UnitDestroyed", "x1", "J-15-1", "red", "Weapon Interaction"),
        ("2026-07-01T00:27:42Z", "UnitDestroyed", "x2", "J-15-2", "red", "Weapon Interaction"),
    ])
    con.executemany("insert into weapon_events values(?,?,?,?,?,?,?,?,?)", [
        ("t", "WeaponFired", "SM-6", "SM-6", "blue", "Blue DDG-113-2 John Finn", "J-15-1", "red", ""),
        ("t", "WeaponEndgame", "SM-6", "SM-6", "blue", "Blue DDG-113-2 John Finn", "J-15-1", "red", "KILL"),
    ])
    con.execute("insert into run_info values(?,?,?,?,?)", ("x.lua", "s", "Success", "ScenarioEnded", "2026-07-02T00:00:00Z"))
    con.commit(); con.close()
    (job / "execution-summary.json").write_text(json.dumps({
        "schema_version": "1.0",
        "run": {"run_id": root.name, "scenario_id": "red_blue_6v4_liaoning", "candidate_id": "candidate_test", "scoring_side_id": "red"},
        "official_score": {
            "stable_side_id": "red", "cmo_side_id": "red", "display_name": "红方",
            "initial": 0, "final": -40, "delta": -40,
            "status": "VALID", "score_event_chain_status": "VALID",
        },
        "score_events": [
            {"event_id": "evt:1", "event_sequence": 1, "sim_time": "2026-07-01T00:27:10Z", "rule_id": "native_score/red_j15_1", "raw_rule_name": "SCORE_LOSS_RED_J15_1_MINUS20", "unit_id": "red_j15_1", "delta": -20, "score_before": 0, "score_after": -20, "evidence_ref": "events.sqlite#1"},
            {"event_id": "evt:2", "event_sequence": 2, "sim_time": "2026-07-01T00:27:42Z", "rule_id": "native_score/red_j15_2", "raw_rule_name": "SCORE_LOSS_RED_J15_2_MINUS20", "unit_id": "red_j15_2", "delta": -20, "score_before": -20, "score_after": -40, "evidence_ref": "events.sqlite#2"},
        ],
        "losses": {"red": [{"unit_id": "red_j15_1"}, {"unit_id": "red_j15_2"}]},
        "target_damage": [], "weapon_expenditures": [],
        "evidence_integrity": {"status": "VALID", "score_chain_consistent": True, "results_complete": True},
    }), encoding="utf-8")
    return root


def test_execution_summary_uses_last_official_score_not_minimum(tmp_path: Path) -> None:
    from cmo_lua_agent.evaluation.phase3_evaluation import _parse_execution_summary

    scenario = load_scenario_definition(Path(__file__).resolve().parents[4] / "baseline" / "6v4" / "scenario_definition.json")
    for final, chain in ((35, (-20, -20, 75)), (60, (-20, -20, 100)), (260, (-20, -20, 200, 100))):
        path = tmp_path / f"summary_{final}.json"
        before = 0
        events = []
        for sequence, delta in enumerate(chain, 1):
            after = before + delta
            events.append({"event_id": f"e{sequence}", "event_sequence": sequence, "sim_time": f"t{sequence}", "rule_id": f"native_score/r{sequence}", "raw_rule_name": f"SCORE_{sequence}", "unit_id": None, "delta": delta, "score_before": before, "score_after": after})
            before = after
        path.write_text(json.dumps({
            "run": {"run_id": "batch", "scenario_id": scenario.scenario_id, "candidate_id": "candidate_00", "scoring_side_id": "red"},
            "official_score": {"stable_side_id": "red", "cmo_side_id": "red", "display_name": "红方", "initial": 0, "final": final, "delta": final, "status": "VALID", "score_event_chain_status": "VALID"},
            "score_events": events, "losses": {}, "weapon_expenditures": [],
            "evidence_integrity": {"status": "VALID", "score_chain_consistent": True, "results_complete": True},
        }), encoding="utf-8")
        snapshot, parsed = _parse_execution_summary(path, scenario=scenario, expected_batch_run_id="batch", expected_candidate_id="candidate_00", expected_scoring_side="red")
        assert snapshot.native_score_final == final
        assert min(event.score_after for event in parsed) == -40


def test_execution_summary_rejects_inconsistent_score_chain(tmp_path: Path) -> None:
    from cmo_lua_agent.evaluation.phase3_evaluation import _parse_execution_summary

    scenario = load_scenario_definition(Path(__file__).resolve().parents[4] / "baseline" / "6v4" / "scenario_definition.json")
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({
        "run": {"run_id": "batch", "scenario_id": scenario.scenario_id, "candidate_id": "candidate_00", "scoring_side_id": "red"},
        "official_score": {"stable_side_id": "red", "cmo_side_id": "red", "display_name": "红方", "initial": 0, "final": 60, "delta": 60, "status": "VALID", "score_event_chain_status": "VALID"},
        "score_events": [{"event_id": "e1", "event_sequence": 1, "sim_time": "t", "rule_id": "native_score/r", "raw_rule_name": "R", "delta": -40, "score_before": 0, "score_after": -40}],
        "evidence_integrity": {"status": "VALID", "score_chain_consistent": True, "results_complete": True},
    }), encoding="utf-8")
    import pytest
    with pytest.raises(ValueError, match="endpoints|deltas"):
        _parse_execution_summary(path, scenario=scenario, expected_batch_run_id="batch", expected_candidate_id="candidate_00", expected_scoring_side="red")


def test_execution_summary_accepts_zero_score_without_events(tmp_path: Path) -> None:
    from cmo_lua_agent.evaluation.phase3_evaluation import _parse_execution_summary

    scenario = load_scenario_definition(Path(__file__).resolve().parents[4] / "baseline" / "6v4" / "scenario_definition.json")
    path = tmp_path / "zero-score.json"
    path.write_text(json.dumps({
        "run": {"run_id": "batch", "scenario_id": scenario.scenario_id, "candidate_id": "candidate_00", "scoring_side_id": "red"},
        "official_score": {"stable_side_id": "red", "cmo_side_id": "red", "display_name": "红方", "initial": 0, "final": 0, "delta": 0, "status": "VALID", "score_event_chain_status": "VALID"},
        "score_events": [],
        "evidence_integrity": {"status": "VALID", "score_chain_consistent": True, "results_complete": True},
    }), encoding="utf-8")

    snapshot, events = _parse_execution_summary(
        path, scenario=scenario, expected_batch_run_id="batch", expected_candidate_id="candidate_00", expected_scoring_side="red"
    )

    assert snapshot.native_score_final == 0
    assert events == ()


def test_execution_summary_preserves_runtime_execution_fidelity_without_rescoring(tmp_path: Path) -> None:
    from cmo_lua_agent.evaluation.phase3_evaluation import _parse_execution_summary

    scenario = load_scenario_definition(Path(__file__).resolve().parents[4] / "baseline" / "6v4" / "scenario_definition.json")
    path = tmp_path / "runtime-summary.json"
    path.write_text(json.dumps({
        "run": {"run_id": "batch", "scenario_id": scenario.scenario_id, "candidate_id": "candidate_00", "scoring_side_id": "red"},
        "official_score": {"stable_side_id": "red", "cmo_side_id": "red", "display_name": "红方", "initial": 0, "final": 35, "delta": 35, "status": "VALID", "score_event_chain_status": "VALID"},
        "score_events": [
            {"event_id": "e1", "event_sequence": 1, "sim_time": "t1", "rule_id": "native_score/red_j15_1", "raw_rule_name": "LOSS", "delta": -20, "score_before": 0, "score_after": -20},
            {"event_id": "e2", "event_sequence": 2, "sim_time": "t2", "rule_id": "native_score/red_j15_2", "raw_rule_name": "LOSS", "delta": -20, "score_before": -20, "score_after": -40},
            {"event_id": "e3", "event_sequence": 3, "sim_time": "t3", "rule_id": "native_score/blue_ddg113_1", "raw_rule_name": "KILL", "delta": 75, "score_before": -40, "score_after": 35},
        ],
        "losses": {}, "weapon_expenditures": [],
        "runtime_execution": {
            "simulation_start_time": "2026-07-29T00:00:00Z",
            "simulation_end_time": "2026-07-29T00:03:01Z",
            "simulation_elapsed_seconds": 181,
            "stop_reason": "ScenarioEnded",
            "last_runtime_event_time": "2026-07-29T00:03:00Z",
            "last_scheduled_operation_time": "2026-07-29T00:03:00Z",
            "scheduled_operation_count": 1,
            "started_operation_count": 1,
            "completed_operation_count": 1,
            "pending_operation_count": 0,
            "lua_bootstrap_seen": True,
            "score_fragment_registered": True,
            "execution_fidelity": "complete",
        },
        "evidence_integrity": {"status": "VALID", "score_chain_consistent": True, "results_complete": True},
    }), encoding="utf-8")

    snapshot, _ = _parse_execution_summary(
        path,
        scenario=scenario,
        expected_batch_run_id="batch",
        expected_candidate_id="candidate_00",
        expected_scoring_side="red",
    )

    assert snapshot.native_score_final == 35
    assert snapshot.execution_fidelity == "verified"


def test_phase3_rejects_unscorable_or_display_side_summary_without_repair(tmp_path: Path) -> None:
    """Phase 3 consumes the source contract and never falls back to display names."""
    import pytest
    from cmo_lua_agent.evaluation.phase3_evaluation import _parse_execution_summary

    scenario = load_scenario_definition(Path(__file__).resolve().parents[4] / "baseline" / "6v4" / "scenario_definition.json")
    path = tmp_path / "unscorable-summary.json"
    payload = {
        "run": {"run_id": "batch", "scenario_id": scenario.scenario_id, "candidate_id": "candidate_00", "scoring_side_id": "red"},
        "official_score": {
            "stable_side_id": "red", "cmo_side_id": "红方", "display_name": "红方",
            "initial": None, "final": None, "delta": None,
            "status": "UNSCORABLE", "score_event_chain_status": "INVALID",
        },
        "score_events": [],
        "evidence_integrity": {"status": "UNSCORABLE", "score_chain_consistent": False, "results_complete": True},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    original = path.read_bytes()

    with pytest.raises(ValueError):
        _parse_execution_summary(
            path, scenario=scenario, expected_batch_run_id="batch",
            expected_candidate_id="candidate_00", expected_scoring_side="red",
        )

    assert path.read_bytes() == original
    assert not (tmp_path / "execution-summary.source.json").exists()


def test_phase3_evaluation_builds_minimal_evidence_and_reward_artifacts(tmp_path: Path) -> None:
    from cmo_lua_agent.evaluation.phase3_evaluation import Phase3EvaluationService

    project = Path(__file__).resolve().parents[4]
    baseline = project / "baseline" / "6v4"
    golden = Phase32ScoredGoldenService().render(baseline_root=baseline)
    scenario = load_scenario_definition(baseline / "scenario_definition.json")
    score = compile_score_baseline(baseline).compilation
    result_dir = _create_result(tmp_path / "Results" / "this_run")
    run = CmoRunResult(
        success=True, lua_path=tmp_path / "x.lua", log_path=tmp_path / "console.txt",
        process_result=CmoProcessResult(0, False, 1.0, "", batch_result_dir=result_dir),
        restore_succeeded=True, batch_result_dir=result_dir, batch_success_count=1, batch_failure_count=0,
    )

    outcome = Phase3EvaluationService().evaluate(
        run_result=run, run_id="run-1", scenario=scenario, plan=golden.plan,
        score_compilation=score, generation_manifest=golden.generation_manifest,
        output_dir=tmp_path / "artifacts",
    )

    assert outcome.reconciliation.status == "valid"
    assert outcome.native_snapshot.native_score_delta == -40
    assert {unit.unit_id for unit in outcome.native_snapshot.destroyed_units} == {"red_j15_1", "red_j15_2"}
    assert len(outcome.attack_episodes) == 5
    assert {episode.attacker_id for episode in outcome.attack_episodes if episode.attacker_id.startswith("red_j15")} == {
        "red_j15_1", "red_j15_2",
    }
    assert outcome.reward_breakdown.raw_score == -40
    assert [item.point_change for item in outcome.reward_breakdown.breakdown] == [-20, -20]
    assert outcome.metrics.semantic_valid is True
    assert len(outcome.metrics.key_events) <= 3
    assert {path.name for path in (tmp_path / "artifacts").iterdir()} == {
        "combat_evidence.json", "semantic_validation.json", "combat_metrics.json", "reward_breakdown.json", "native_score_diagnostics.json",
    }


def test_phase3_marks_missing_or_mismatched_results_unscorable(tmp_path: Path) -> None:
    from cmo_lua_agent.evaluation.phase3_evaluation import locate_result_artifacts

    run = CmoRunResult(
        success=True, lua_path=tmp_path / "x.lua", log_path=tmp_path / "console.txt",
        process_result=CmoProcessResult(0, False, 1.0, ""), restore_succeeded=True,
    )
    paths = locate_result_artifacts(run_result=run)
    assert paths.is_confirmed is False


def test_phase3_rejects_inconsistent_execution_summary_score_chain(tmp_path: Path) -> None:
    from cmo_lua_agent.evaluation.phase3_evaluation import Phase3EvaluationService

    project = Path(__file__).resolve().parents[4]
    baseline = project / "baseline" / "6v4"
    golden = Phase32ScoredGoldenService().render(baseline_root=baseline)
    result_dir = _create_result(tmp_path / "Results" / "this_run")
    summary_path = result_dir / "001_all" / "execution-summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["official_score"]["final"] = -39
    summary["official_score"]["delta"] = -39
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    run = CmoRunResult(True, tmp_path / "x.lua", tmp_path / "console.txt", CmoProcessResult(0, False, 1.0, "", batch_result_dir=result_dir), True, batch_result_dir=result_dir)

    outcome = Phase3EvaluationService().evaluate(
        run_result=run, run_id="run-2", scenario=load_scenario_definition(baseline / "scenario_definition.json"),
        plan=golden.plan, score_compilation=compile_score_baseline(baseline).compilation,
        generation_manifest=golden.generation_manifest,
    )

    assert outcome.reconciliation.status == "unscorable"
    assert outcome.metrics.scoreable is False


def test_phase3_uses_csv_when_events_sqlite_is_absent(tmp_path: Path) -> None:
    from cmo_lua_agent.evaluation.phase3_evaluation import Phase3EvaluationService

    project = Path(__file__).resolve().parents[4]
    baseline = project / "baseline" / "6v4"
    golden = Phase32ScoredGoldenService().render(baseline_root=baseline)
    result_dir = tmp_path / "Results" / "this_run"
    job = result_dir / "001_all"; job.mkdir(parents=True)
    (result_dir / "runner.log").write_text("batch", encoding="utf-8")
    (job / "lua-output.log").write_text("", encoding="utf-8")
    with (job / "combat-summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["指标", "阵营", "武器或单位", "结果", "数量或损伤百分比"])
        writer.writeheader()
        writer.writerows([
            {"指标": "单位战损", "阵营": "red", "武器或单位": "J-15-1 [x]", "结果": "被毁", "数量或损伤百分比": "1"},
            {"指标": "单位战损", "阵营": "red", "武器或单位": "J-15-2 [x]", "结果": "被毁", "数量或损伤百分比": "1"},
            {"指标": "CMO官方初始得分", "阵营": "red", "武器或单位": "官方评分", "结果": "推演开始", "数量或损伤百分比": "0"},
            {"指标": "CMO官方最终得分", "阵营": "red", "武器或单位": "官方评分", "结果": "推演结束", "数量或损伤百分比": "-40"},
        ])
    run = CmoRunResult(True, tmp_path / "x.lua", tmp_path / "console.txt", CmoProcessResult(0, False, 1.0, "", batch_result_dir=result_dir), True, batch_result_dir=result_dir)

    outcome = Phase3EvaluationService().evaluate(
        run_result=run, run_id="csv", scenario=load_scenario_definition(baseline / "scenario_definition.json"),
        plan=golden.plan, score_compilation=compile_score_baseline(baseline).compilation,
        generation_manifest=golden.generation_manifest,
    )

    assert outcome.artifact_paths.primary_result_path.suffix == ".csv"
    assert outcome.reconciliation.status == "unscorable"


def test_phase3_rejects_result_script_that_does_not_match_this_run(tmp_path: Path) -> None:
    from cmo_lua_agent.evaluation.phase3_evaluation import locate_result_artifacts

    result_dir = _create_result(tmp_path / "Results" / "this_run")
    con = sqlite3.connect(result_dir / "001_all" / "events.sqlite")
    con.execute("update run_info set script='C:/wrong.lua'"); con.commit(); con.close()
    run = CmoRunResult(True, tmp_path / "right.lua", tmp_path / "console.txt", CmoProcessResult(0, False, 1.0, "", batch_result_dir=result_dir), True, batch_result_dir=result_dir)

    assert locate_result_artifacts(run_result=run).is_confirmed is False


def test_phase3_preserves_unknown_destroyed_unit_as_semantic_violation(tmp_path: Path) -> None:
    from cmo_lua_agent.evaluation.phase3_evaluation import Phase3EvaluationService

    project = Path(__file__).resolve().parents[4]; baseline = project / "baseline" / "6v4"
    golden = Phase32ScoredGoldenService().render(baseline_root=baseline); result_dir = _create_result(tmp_path / "Results" / "this_run")
    con = sqlite3.connect(result_dir / "001_all" / "events.sqlite")
    con.execute("insert into unit_damage_events values(?,?,?,?,?,?)", ("t", "UnitDestroyed", "z", "Unknown", "red", "x")); con.commit(); con.close()
    summary_path = result_dir / "001_all" / "execution-summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["losses"]["red"].append({"unit_id": "unknown_unit", "name": "Unknown"})
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    run = CmoRunResult(True, tmp_path / "x.lua", tmp_path / "console.txt", CmoProcessResult(0, False, 1.0, "", batch_result_dir=result_dir), True, batch_result_dir=result_dir)

    outcome = Phase3EvaluationService().evaluate(run_result=run, run_id="unknown", scenario=load_scenario_definition(baseline / "scenario_definition.json"), plan=golden.plan, score_compilation=compile_score_baseline(baseline).compilation, generation_manifest=golden.generation_manifest)

    assert outcome.semantic_validation.semantic_valid is False
    assert "destroyed unit is outside ScenarioDefinition" in outcome.semantic_validation.violations
    assert outcome.semantic_validation.scoreable is False
    assert outcome.reward_breakdown.breakdown == ()


def test_phase3_ignores_destroyed_weapon_objects_not_in_scenario(tmp_path: Path) -> None:
    from cmo_lua_agent.evaluation.phase3_evaluation import Phase3EvaluationService

    project = Path(__file__).resolve().parents[4]; baseline = project / "baseline" / "6v4"
    golden = Phase32ScoredGoldenService().render(baseline_root=baseline); result_dir = _create_result(tmp_path / "Results" / "this_run")
    con = sqlite3.connect(result_dir / "001_all" / "events.sqlite")
    con.execute("insert into unit_damage_events values(?,?,?,?,?,?)", ("t", "UnitDestroyed", "weapon", "SM-6 #1", "blue", "Weapon has been destroyed though interaction")); con.commit(); con.close()
    run = CmoRunResult(True, tmp_path / "x.lua", tmp_path / "console.txt", CmoProcessResult(0, False, 1.0, "", batch_result_dir=result_dir), True, batch_result_dir=result_dir)

    outcome = Phase3EvaluationService().evaluate(run_result=run, run_id="weapon", scenario=load_scenario_definition(baseline / "scenario_definition.json"), plan=golden.plan, score_compilation=compile_score_baseline(baseline).compilation, generation_manifest=golden.generation_manifest)

    assert outcome.semantic_validation.scoreable is True
    assert {item.unit_id for item in outcome.native_snapshot.destroyed_units} == {"red_j15_1", "red_j15_2"}


def test_phase3_aggregates_only_plan_related_weapon_events(tmp_path: Path) -> None:
    from cmo_lua_agent.evaluation.phase3_evaluation import Phase3EvaluationService

    project = Path(__file__).resolve().parents[4]
    baseline = project / "baseline" / "6v4"
    golden = Phase32ScoredGoldenService().render(baseline_root=baseline)
    result_dir = _create_result(tmp_path / "Results" / "this_run")
    con = sqlite3.connect(result_dir / "001_all" / "events.sqlite")
    con.executemany("insert into weapon_events values(?,?,?,?,?,?,?,?,?)", [
        ("t", "WeaponFired", "YJ-83K", "YJ-83K", "red", "J-15-1", "Blue CVN-70 Carl Vinson", "blue", ""),
        ("t", "WeaponEndgame", "YJ-83K", "YJ-83K", "red", "J-15-1", "Blue CVN-70 Carl Vinson", "blue", "KILL"),
        ("t", "WeaponEndgame", "YJ-83K", "YJ-83K", "red", "J-15-1", "Blue CVN-70 Carl Vinson", "blue", "POINTDEF:SUCCESS"),
        ("t", "WeaponFired", "irrelevant", "irrelevant", "blue", "Other", "Other target", "red", ""),
    ])
    con.commit(); con.close()
    run = CmoRunResult(True, tmp_path / "x.lua", tmp_path / "console.txt", CmoProcessResult(0, False, 1.0, "", batch_result_dir=result_dir), True, batch_result_dir=result_dir)

    outcome = Phase3EvaluationService().evaluate(
        run_result=run, run_id="events", scenario=load_scenario_definition(baseline / "scenario_definition.json"),
        plan=golden.plan, score_compilation=compile_score_baseline(baseline).compilation,
        generation_manifest=golden.generation_manifest,
    )

    episode = next(item for item in outcome.attack_episodes if item.attacker_id == "red_j15_1" and item.target_id == "blue_cvn70")
    assert (episode.weapons_fired, episode.hits, episode.intercepted) == (1, 1, 1)
    assert all("irrelevant" not in item for item in outcome.metrics.key_events)


def test_phase3_hook_writes_evaluation_to_actual_run_directory(tmp_path: Path) -> None:
    from cmo_lua_agent.evaluation.phase3_evaluation import Phase3EvaluationService
    from cmo_lua_agent.evaluation.phase3_hook import Phase3EvaluationHook

    project = Path(__file__).resolve().parents[4]
    baseline = project / "baseline" / "6v4"
    golden = Phase32ScoredGoldenService().render(baseline_root=baseline)
    source_lua = tmp_path / "x.lua"; source_lua.write_text("-- lua\n", encoding="utf-8")
    store = RunArtifactStore(runs_dir=tmp_path / "runs")
    run_paths = store.create_run(original_lua=source_lua, run_id="phase3_hook")
    round_paths = store.prepare_round(run_paths=run_paths, round_number=0)
    result_dir = _create_result(tmp_path / "Results" / "this_run")
    run = CmoRunResult(True, source_lua, tmp_path / "console.txt", CmoProcessResult(0, False, 1.0, "", batch_result_dir=result_dir), True, batch_result_dir=result_dir)
    hook = Phase3EvaluationHook(
        scenario=load_scenario_definition(baseline / "scenario_definition.json"),
        plan=golden.plan,
        score_compilation=compile_score_baseline(baseline).compilation,
        generation_manifest=golden.generation_manifest,
        service=Phase3EvaluationService(),
    )

    outcome = hook(CmoExecutionRecord(run, run_paths, round_paths))

    assert outcome.reconciliation.status == "valid"
    assert {item.name for item in (run_paths.run_dir / "phase3").iterdir()} == {
        "combat_evidence.json", "semantic_validation.json", "combat_metrics.json", "reward_breakdown.json", "native_score_diagnostics.json",
    }
