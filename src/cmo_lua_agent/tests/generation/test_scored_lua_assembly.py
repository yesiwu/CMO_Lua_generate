from __future__ import annotations

from pathlib import Path

import pytest

from cmo_lua_agent.contract import load_baseline_strategy, load_scenario_definition
from cmo_lua_agent.generation.execution_plan_compiler import ExecutionPlanCompiler
from cmo_lua_agent.generation.phase2_golden_baseline import Phase2GoldenBaselineService
from cmo_lua_agent.generation.runtime_models import LuaRuntimeProfile
from cmo_lua_agent.generation.scored_lua_assembly import (
    SCORED_RENDERER_VERSION,
    SCORED_RUNTIME_ID,
    SCORED_RUNTIME_VERSION,
    ScoredLuaAssemblyError,
    ScoredLuaAssemblyService,
)
from cmo_lua_agent.scoring.baseline import compile_score_baseline


ROOT = Path(__file__).resolve().parents[4]
BASELINE_ROOT = ROOT / "baseline" / "6v4"


def _inputs():
    scenario = load_scenario_definition(BASELINE_ROOT / "scenario_definition.json")
    strategy = load_baseline_strategy(BASELINE_ROOT / "legacy" / "baseline_strategy.pre-scenario-ir.json").strategy
    runtime = LuaRuntimeProfile(SCORED_RUNTIME_ID, SCORED_RUNTIME_VERSION)
    plan = ExecutionPlanCompiler().compile(
        scenario=scenario, strategy=strategy, runtime=runtime
    ).plan
    assert plan is not None
    compilation = compile_score_baseline(BASELINE_ROOT).compilation
    return scenario, strategy, runtime, plan, compilation


def test_phase2_render_without_instrumentation_is_byte_identical() -> None:
    result = Phase2GoldenBaselineService().render(
        scenario_definition_path=BASELINE_ROOT / "scenario_definition.json",
        baseline_strategy_path=BASELINE_ROOT / "legacy" / "baseline_strategy.pre-scenario-ir.json",
    )
    expected = (BASELINE_ROOT / "rendered_baseline.lua").read_text(encoding="utf-8")

    assert result.rendered.content == expected


def test_scored_assembly_places_one_fragment_after_initialization_and_before_attack() -> None:
    scenario, _, runtime, plan, compilation = _inputs()
    result = ScoredLuaAssemblyService().render(
        scenario=scenario,
        strategy=load_baseline_strategy(BASELINE_ROOT / "legacy" / "baseline_strategy.pre-scenario-ir.json").strategy,
        plan=plan,
        runtime=runtime,
        native_score_compilation=compilation,
    )

    content = result.rendered.content
    marker = "-- CMO native scoring instrumentation; generated deterministically."
    assert content.count(marker) == 1
    assert content.index("-- BEGIN OP unit.red_liaoning") < content.index(marker)
    assert content.index("-- BEGIN OP unit.red_liaoning") < content.index("-- BEGIN OP unit.red_j15_1")
    assert content.index("-- BEGIN OP aircraft.j15-1-cvn70.configure") < content.index(marker)
    assert content.index(marker) < content.index("-- BEGIN OP attack.")
    assert "-- BEGIN OP native_score/" not in content
    assert result.rendered.metadata["renderer_version"] == SCORED_RENDERER_VERSION
    assert "ScenEdit_AddUnit" in content
    assert "ScenEdit_SetTrigger" in content


def test_scored_assembly_rejects_scenario_or_checksum_mismatch() -> None:
    scenario, _, runtime, plan, compilation = _inputs()
    wrong_plan = ExecutionPlanCompiler().compile(
        scenario=scenario,
        strategy=load_baseline_strategy(BASELINE_ROOT / "legacy" / "baseline_strategy.pre-scenario-ir.json").strategy,
        runtime=runtime,
    ).plan
    assert wrong_plan is not None
    object.__setattr__(wrong_plan, "scenario_id", "other")

    with pytest.raises(ScoredLuaAssemblyError, match="scenario_id_mismatch"):
        ScoredLuaAssemblyService().render(
            scenario=scenario,
            strategy=load_baseline_strategy(BASELINE_ROOT / "legacy" / "baseline_strategy.pre-scenario-ir.json").strategy,
            plan=wrong_plan,
            runtime=runtime,
            native_score_compilation=compilation,
        )

    object.__setattr__(compilation, "fragment_checksum", "0" * 64)
    with pytest.raises(ScoredLuaAssemblyError, match="fragment_checksum_mismatch"):
        ScoredLuaAssemblyService().render(
            scenario=scenario,
            strategy=load_baseline_strategy(BASELINE_ROOT / "legacy" / "baseline_strategy.pre-scenario-ir.json").strategy,
            plan=plan,
            runtime=runtime,
            native_score_compilation=compilation,
        )


def test_scored_assembly_is_deterministic_and_records_score_checksums() -> None:
    scenario, _, runtime, plan, compilation = _inputs()
    service = ScoredLuaAssemblyService()
    first = service.render(
        scenario=scenario, strategy=load_baseline_strategy(BASELINE_ROOT / "legacy" / "baseline_strategy.pre-scenario-ir.json").strategy, plan=plan, runtime=runtime, native_score_compilation=compilation
    )
    second = service.render(
        scenario=scenario, strategy=load_baseline_strategy(BASELINE_ROOT / "legacy" / "baseline_strategy.pre-scenario-ir.json").strategy, plan=plan, runtime=runtime, native_score_compilation=compilation
    )

    assert first.rendered.content == second.rendered.content
    assert first.rendered.lua_checksum == second.rendered.lua_checksum
    assert first.generation_manifest["instrumentation_enabled"] is True
    for field in (
        "scenario_checksum", "strategy_checksum", "execution_plan_checksum",
        "role_catalog_checksum", "score_profile_checksum", "objectives_checksum",
        "score_spec_checksum", "native_score_fragment_checksum", "lua_checksum",
    ):
        assert len(first.generation_manifest[field]) == 64


def test_scored_assembly_rejects_candidate_supplied_score_text() -> None:
    scenario, strategy, runtime, plan, _ = _inputs()

    with pytest.raises(ScoredLuaAssemblyError, match="native_score_compilation_type"):
        ScoredLuaAssemblyService().render(
            scenario=scenario,
            strategy=strategy,
            plan=plan,
            runtime=runtime,
            native_score_compilation="print('candidate score override')",  # type: ignore[arg-type]
        )
