"""Explicit real-CMO smoke test for the formal Phase 6 path."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from cmo_lua_agent.contract import load_baseline_strategy, load_scenario_definition
from cmo_lua_agent.core.run_artifact_store import RunArtifactStore
from cmo_lua_agent.execution.cmo_job_config import CmoJobConfig
from cmo_lua_agent.execution.cmo_process_runner import CmoProcessRunner
from cmo_lua_agent.execution.cmo_runner import CmoRunner
from cmo_lua_agent.generation.runtime_models import LuaRuntimeProfile
from cmo_lua_agent.generation.scored_lua_assembly import SCORED_RUNTIME_ID, SCORED_RUNTIME_VERSION
from cmo_lua_agent.optimization.candidate_evaluation_workflow import CandidateEvaluationWorkflow
from cmo_lua_agent.optimization.optimization_generation_workflow import OptimizationGenerationWorkflow
from cmo_lua_agent.optimization.phase6_models import PlanningRequest
from cmo_lua_agent.optimization.scenario_reset_probe import ScenarioResetProbe
from cmo_lua_agent.agents.strategy_proposal_agent import StrategyProposalAgent
from cmo_lua_agent.scoring.baseline import compile_score_baseline

pytestmark = pytest.mark.cmo_integration
ROOT = Path(__file__).resolve().parents[4]


class _FixedClient:
    def __init__(self, path: Path) -> None:
        self.calls = 0
        self._payload = json.loads(path.read_text(encoding="utf-8"))

    def complete_json(self, **_: object) -> object:
        self.calls += 1
        return self._payload


class _NoRepair:
    def repair(self, request):  # pragma: no cover - smoke test must not repair.
        raise AssertionError("Phase 6 smoke must not invoke repair")


@pytest.mark.skipif(os.environ.get("CMO_PHASE6_SMOKE") != "1", reason="set CMO_PHASE6_SMOKE=1 to run real CMO")
def test_phase6_formal_generation_cmo_smoke() -> None:
    baseline_root = ROOT / "baseline" / "6v4"
    config_path = ROOT / "json_data" / "tot-three.json"
    runner_path = Path(r"C:\CMO\CmoBatchRunner\CmoBatchRunner.exe")
    if not runner_path.is_file():
        pytest.skip("CmoBatchRunner.exe unavailable")
    optimization_id = os.environ.get("CMO_PHASE6_SMOKE_ID", "phase6_smoke_20260724")
    optimization_dir = ROOT / "runs" / optimization_id
    if optimization_dir.exists():
        pytest.skip(f"existing smoke artifacts: {optimization_dir}")
    scenario = load_scenario_definition(baseline_root / "scenario_definition.json")
    baseline = load_baseline_strategy(
        baseline_root / "legacy" / "baseline_strategy.pre-scenario-ir.json"
    )
    runtime = LuaRuntimeProfile(SCORED_RUNTIME_ID, SCORED_RUNTIME_VERSION)
    process = CmoProcessRunner(runner_path=runner_path, cleanup_process_names=())
    runner = CmoRunner(
        config_path=config_path,
        job_config=CmoJobConfig(config_path),
        process_runner=process,
        artifact_store=RunArtifactStore(runs_dir=ROOT / "runs" / "_phase6_cmo_runs" / optimization_id),
    )
    client = _FixedClient(baseline_root / "phase6" / "fixed_strategy_proposal.json")
    workflow = OptimizationGenerationWorkflow(
        project_root=ROOT,
        proposal_agent=StrategyProposalAgent(client),
        candidate_evaluator=CandidateEvaluationWorkflow(
            cmo_runner=runner,
            repair_agent=_NoRepair(),
            scenario_reset_probe=ScenarioResetProbe(config_path),
        ),
    )
    request = PlanningRequest(optimization_id, scenario, baseline, "验证固定四候选正式链", (
        "/attacks/0/target_ids/0", "/attacks/0/fire_quantity", "/attacks/0/delay_seconds", "/attacks/0/reserve_quantity",
        "/attacks/1/target_ids/0", "/attacks/1/fire_quantity", "/attacks/1/delay_seconds", "/attacks/1/reserve_quantity",
        "/attacks/2/target_ids/0", "/attacks/2/fire_quantity", "/attacks/2/delay_seconds", "/attacks/2/reserve_quantity",
        "/attacks/3/target_ids/0", "/attacks/3/fire_quantity", "/attacks/4/target_ids/0", "/attacks/4/fire_quantity",
        "/sorties/0/target_id", "/sorties/0/fire_delay_seconds", "/sorties/1/target_id", "/sorties/1/fire_delay_seconds",
    ), ("target_assignment", "attack_timing", "fire_quantity", "ammunition_reserve"), runtime, compile_score_baseline(baseline_root).compilation, 600, optimization_dir)
    result = workflow.run(request)
    assert client.calls == 1
    assert result.workflow_completed
    assert (optimization_dir / "leaderboard.json").is_file()
    assert (optimization_dir / "generation_result.json").is_file()
    assert (optimization_dir / "optimization_summary.json").is_file()
    assert any(not entry.is_baseline and entry.category == "ranked_success" for entry in result.leaderboard)
