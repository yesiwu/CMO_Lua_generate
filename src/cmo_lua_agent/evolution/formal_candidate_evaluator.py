"""Adapter from Phase 9C frozen strategies to the Phase 5 evaluator."""

from __future__ import annotations

import json
from pathlib import Path

from cmo_lua_agent.agents.lua_repair_agent import LuaRepairAgent
from cmo_lua_agent.evolution.authorized_candidate_runner import (
    CampaignAuthorizedCandidateRunner,
)
from cmo_lua_agent.optimization.candidate_evaluation_workflow import (
    CandidateEvaluationWorkflow,
)
from cmo_lua_agent.optimization.candidate_models import CandidateRequest
from cmo_lua_agent.generation.manual_template_assembly import (
    ManualTemplateAssemblyService,
)


class FormalCandidateEvaluator:
    """正式候选评估适配器：将冻结策略交给 Phase 6/CMO 评估链。

它处理候选 Lua 修复额度和运行证据收集，但不选择 Champion 或推进 Training 的代数；
这些结论分别属于 Campaign Policy 和 TrainingRunner。
    """
    def __init__(
        self,
        *,
        json_client,
        cmo_runner_path: Path,
        cmo_executable_path: Path,
        runner_factory=None,
    ) -> None:
        self._json_client = json_client
        self._runner_path = Path(cmo_runner_path)
        self._command_path = Path(cmo_executable_path)
        self._runner_factory = runner_factory

    def preflight(self) -> dict[str, str]:
        if not self._runner_path.is_file():
            raise ValueError("cmo_batch_runner_missing")
        if not self._command_path.is_file():
            raise ValueError("cmo_executable_missing")
        return {
            "cmo_batch_runner": str(self._runner_path.resolve()),
            "cmo_executable": str(self._command_path.resolve()),
        }

    def __call__(
        self,
        *,
        candidate_id,
        strategy,
        candidate_dir,
        generation_index,
        context,
        package,
    ) -> dict[str, object]:
        runner = CampaignAuthorizedCandidateRunner(
            candidate_id=candidate_id,
            generation_index=generation_index,
            worker_context=context,
            scenario_asset=package.scenario_asset,
            cmo_runner_path=self._runner_path,
            cmo_executable_path=self._command_path,
            runner_factory=self._runner_factory,
        )
        assembler = (
            ManualTemplateAssemblyService(
                template_root=package.manual_template_root,
                baseline_strategy=package.baseline.strategy,
            )
            if getattr(package, "manual_template_root", None) is not None
            else None
        )
        workflow = CandidateEvaluationWorkflow(
            cmo_runner=runner,
            repair_agent=LuaRepairAgent(self._json_client),
            is_cancelled=lambda: context.control_action() in {"pause", "stop"},
            assembler=assembler,
        )
        request = CandidateRequest(
            candidate_id=candidate_id,
            generation_index=generation_index,
            scenario=package.scenario,
            strategy=strategy,
            runtime=package.runtime,
            native_score_compilation=package.native_score_compilation,
            max_repairs=context.spec.budget.max_repair_attempts_per_candidate,
            timeout_seconds=context.spec.budget.per_candidate_timeout_seconds,
            candidate_dir=Path(candidate_dir),
            allowed_strategy_paths=package.allowed_strategy_paths,
            reuse_existing_artifacts=True,
            official_score_only=True,
        )
        workflow.evaluate(request)
        outcome_path = Path(candidate_dir) / "candidate_outcome.json"
        if not outcome_path.is_file():
            raise ValueError("candidate_outcome_missing")
        value = json.loads(outcome_path.read_text(encoding="utf-8"))
        value["artifact_provenance"] = "formal_renderer"
        value["scenario_reset"] = {
            "scenario_reset_verified": True,
            "scenario_asset_id": package.scenario_asset.asset_id,
            "scenario_checksum": package.scenario_asset.sha256,
        }
        return value
