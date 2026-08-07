from __future__ import annotations

import json
from pathlib import Path

from cmo_lua_agent.contract.baseline_strategy_builder import BaselineStrategyBuilder
from cmo_lua_agent.generation.execution_plan_compiler import ExecutionPlanCompiler
from cmo_lua_agent.generation.manual_template_assembly import ManualTemplateAssemblyService
from cmo_lua_agent.generation.runtime_models import LuaRuntimeProfile
from cmo_lua_agent.optimization.candidate_set_validator import strategy_leaf_diff
from cmo_lua_agent.scoring.baseline import compile_score_baseline


ROOT = Path(__file__).resolve().parents[4]


def _inputs():
    scenario_ir = json.loads((ROOT / "json_data" / "6v4ScenarioIR.json").read_text(encoding="utf-8"))
    derived = BaselineStrategyBuilder().build(scenario_ir)
    runtime = LuaRuntimeProfile("cmo_naval_air_anti_surface_scored", "2.0.0")
    score = compile_score_baseline(ROOT / "baseline" / "6v4", scenario=derived.scenario).compilation
    return derived, runtime, score


def test_manual_template_assembly_renders_baseline_and_mapped_candidate() -> None:
    derived, runtime, score = _inputs()
    service = ManualTemplateAssemblyService(
        template_root=ROOT / "baseline" / "6v4" / "manual-template",
        baseline_strategy=derived.strategy,
    )
    plan = ExecutionPlanCompiler().compile(
        scenario=derived.scenario,
        strategy=derived.strategy,
        runtime=runtime,
    ).plan
    assert plan is not None

    baseline = service.render(
        scenario=derived.scenario,
        strategy=derived.strategy,
        plan=plan,
        runtime=runtime,
        native_score_compilation=score,
        candidate_id="baseline",
    )
    # RenderedLua normalizes the terminal newline. The Lua body is otherwise
    # byte-identical to the checked-in operator baseline Golden.
    assert baseline.rendered.content == (
        ROOT
        / "baseline"
        / "6v4"
        / "manual-template"
        / "reference"
        / "candidate_baseline_fixed.reference.lua"
    ).read_text(encoding="utf-8").rstrip()
    assert "local SCORE_RULES =" in baseline.rendered.content
    assert "type='Points', name=action_name" in baseline.rendered.content
    assert "function baseline_v2_score_poll()" not in baseline.rendered.content
    assert "baseline_ship_attack_poll" in baseline.rendered.content
    assert "baseline_air_launch_poll" in baseline.rendered.content
    assert baseline.rendered.metadata["score_spec_version"] == "destroyed_unit_native_points"
    assert baseline.generation_manifest["artifact_provenance"] == "manual_template"

    candidate_data = derived.strategy.to_dict()
    candidate_data["attacks"][0]["target_ids"] = ["blue_cvn70"]
    from cmo_lua_agent.contract.strategy_models import strategy_spec_from_dict
    candidate = strategy_spec_from_dict(candidate_data)
    changed_paths = strategy_leaf_diff(
        derived.strategy,
        candidate,
        ("/attacks/0/target_ids/0",),
    )
    candidate_plan = ExecutionPlanCompiler().compile(
        scenario=derived.scenario,
        strategy=candidate,
        runtime=runtime,
    ).plan
    assert candidate_plan is not None
    rendered = service.render(
        scenario=derived.scenario,
        strategy=candidate,
        plan=candidate_plan,
        runtime=runtime,
        native_score_compilation=score,
        candidate_id="candidate_00",
    )
    assert "candidate_00" in rendered.rendered.content
    assert "target_id='blue_cvn70', delay_seconds=30" in rendered.rendered.content
    assert rendered.generation_manifest["changed_paths"] == list(changed_paths)


def test_manual_template_assembly_rejects_unmapped_strategy_change() -> None:
    derived, runtime, score = _inputs()
    service = ManualTemplateAssemblyService(
        template_root=ROOT / "baseline" / "6v4" / "manual-template",
        baseline_strategy=derived.strategy,
    )
    candidate_data = derived.strategy.to_dict()
    candidate_data["attacks"][0]["reserve_quantity"] = 1
    from cmo_lua_agent.contract.strategy_models import strategy_spec_from_dict
    candidate = strategy_spec_from_dict(candidate_data)
    plan = ExecutionPlanCompiler().compile(
        scenario=derived.scenario,
        strategy=candidate,
        runtime=runtime,
    ).plan
    assert plan is not None
    try:
        service.render(
            scenario=derived.scenario,
            strategy=candidate,
            plan=plan,
            runtime=runtime,
            native_score_compilation=score,
            candidate_id="candidate_00",
        )
    except ValueError as exc:
        assert str(exc) == "manual_template_strategy_change_unmapped"
    else:
        raise AssertionError("unmapped formal change must be rejected")
