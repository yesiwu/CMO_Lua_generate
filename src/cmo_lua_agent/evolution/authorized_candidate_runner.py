"""CMO runner adapter enforcing Phase 9C approval and per-attempt jobs."""

from __future__ import annotations

from pathlib import Path

from cmo_lua_agent.core.run_artifact_store import RunArtifactStore
from cmo_lua_agent.execution.cmo_job_config import CmoJobConfig
from cmo_lua_agent.execution.cmo_process_runner import CmoProcessRunner
from cmo_lua_agent.execution.cmo_runner import CmoRunner
from cmo_lua_agent.execution.dynamic_batch_job import DynamicBatchJobBuilder


class CampaignAuthorizedCandidateRunner:
    """在 Campaign 授权边界内执行单个候选的 CMO 调用适配器。

它从 PermissionBroker 获取尝试资格并委托执行层；不自行增加额度或绕过 operation
ledger，因此重启和审阅都能追踪每一次外部执行。
    """
    def __init__(
        self,
        *,
        candidate_id: str,
        generation_index: int,
        worker_context,
        scenario_asset,
        cmo_runner_path: Path,
        cmo_executable_path: Path,
        runner_factory=None,
    ) -> None:
        self._candidate_id = candidate_id
        self._generation_index = generation_index
        self._context = worker_context
        self._asset = scenario_asset
        self._runner_path = Path(cmo_runner_path).resolve()
        self._command_path = Path(cmo_executable_path).resolve()
        self._jobs = DynamicBatchJobBuilder()
        self._runner_factory = runner_factory

    def run(
        self,
        *,
        lua_path: Path,
        timeout_seconds: int,
        round_number: int,
        run_id: str,
        audit_profile: dict[str, object] | None = None,
    ):
        operation_id = (
            f"g{self._generation_index:03d}:cmo:"
            f"{self._candidate_id}:a{round_number:02d}"
        )
        job = self._jobs.build(
            attempt_dir=Path(lua_path).resolve().parent,
            source_scenario=self._asset,
            lua_path=lua_path,
            campaign_id=self._context.spec.campaign_id,
            generation_index=self._generation_index,
            candidate_id=self._candidate_id,
            operation_id=operation_id,
            attempt_index=round_number,
            audit_profile=dict(audit_profile or {}),
            cmo_executable=self._command_path,
            wall_timeout_seconds=timeout_seconds,
        )
        runner = (
            self._runner_factory(job)
            if self._runner_factory is not None
            else CmoRunner(
                config_path=job.job_path,
                job_config=CmoJobConfig(job.job_path),
                process_runner=CmoProcessRunner(
                    runner_path=self._runner_path,
                    cleanup_process_names=(),
                ),
                artifact_store=RunArtifactStore(
                    runs_dir=job.results_dir / "runs"
                ),
            )
        )
        return runner.run(
            lua_path=job.lua_path,
            timeout_seconds=timeout_seconds,
            round_number=round_number,
            run_id=run_id,
            audit_profile=audit_profile,
        )
