"""CMO runner adapter enforcing Phase 9C approval and per-attempt jobs."""

from __future__ import annotations

from pathlib import Path

from cmo_lua_agent.core.run_artifact_store import RunArtifactStore
from cmo_lua_agent.execution.cmo_job_config import CmoJobConfig
from cmo_lua_agent.execution.cmo_process_runner import CmoProcessRunner
from cmo_lua_agent.execution.cmo_runner import CmoRunner
from cmo_lua_agent.execution.dynamic_batch_job import DynamicBatchJobBuilder


class CampaignAuthorizedCandidateRunner:
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
        preview = self._context.preview
        self._context.permission_broker.authorize_attempt_slot(
            operation_id=operation_id,
            snapshot_checksum=preview.snapshot_checksum,
            candidate_set_checksum=preview.candidate_set_checksum,
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
            audit_profile=str((audit_profile or {}).get("profile", "phase9c")),
            cmo_executable=self._command_path,
            wall_timeout_seconds=timeout_seconds,
        )
        self._context.permission_broker.mark_attempt_started(operation_id)
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
        try:
            record = runner.run(
                lua_path=job.lua_path,
                timeout_seconds=timeout_seconds,
                round_number=round_number,
                run_id=run_id,
                audit_profile=audit_profile,
            )
        except (KeyboardInterrupt, SystemExit):
            self._context.permission_broker.mark_attempt_unknown(
                operation_id,
                reason="runner_interrupted",
            )
            raise
        except Exception as exc:
            self._context.permission_broker.mark_attempt_unknown(
                operation_id,
                reason=f"{type(exc).__name__}: {exc}",
            )
            raise
        else:
            if record.result.success:
                self._context.permission_broker.mark_attempt_completed(
                    operation_id,
                    output_ref=str(job.results_dir),
                )
            else:
                self._context.permission_broker.mark_attempt_failed(
                    operation_id,
                    reason=(
                        record.result.error.category
                        if record.result.error is not None
                        else "cmo_failed"
                    ),
                )
            return record
        finally:
            self._jobs.verify_source_unchanged(self._asset)
