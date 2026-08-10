"""Production adapter between the persistent TrainingRunner and Campaign service."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
from time import sleep
from typing import Any

from cmo_lua_agent.evolution.production_service import (
    create_production_evolution_campaign_service,
)
from cmo_lua_agent.llm.client import ClaudeClient
from cmo_lua_agent.llm_config import load_config
from cmo_lua_agent.training.models import TrainingRequest
from cmo_lua_agent.training.models import TrainingAction, TrainingStatus
from cmo_lua_agent.training.runner import TrainingRunner
from cmo_lua_agent.training.store import TrainingStore
from cmo_lua_agent.training.repair import CodeRepairCoordinator
from cmo_lua_agent.training.fixture import FixtureCampaignDriver


class ProductionCampaignDriver:
    """Translate scheduler actions to the one supported production Campaign facade."""

    def __init__(self, service: Any) -> None:
        self._service = service

    def prepare(self, request: TrainingRequest) -> str:
        if request.generation_count is None:
            raise ValueError("fixed_generation_count_required")
        campaign_id = f"{request.workflow_id}-campaign"
        self._service.prepare_training_campaign(
            campaign_id=campaign_id,
            input_package_id=request.input_path,
            generation_objective=request.objective,
            generation_count=request.generation_count,
        )
        return campaign_id

    def preview(self, campaign_id: str, generation_index: int) -> None:
        arguments = {
            "campaign_id": campaign_id,
            "generation_index": generation_index,
        }
        try:
            self._service.preview_generation(**arguments)
        except ValueError as exc:
            if str(exc) != "preview_regeneration_required":
                raise
            self._service.preview_generation(**arguments, regenerate_preview=True)

    def execute(self, campaign_id: str, generation_index: int) -> None:
        self._service.execute_generation(
            campaign_id=campaign_id,
            generation_index=generation_index,
        )

    def inspect_generation(self, campaign_id: str, generation_index: int) -> dict[str, object]:
        return self._service.inspect_generation(campaign_id, generation_index)

    def pause(self, campaign_id: str) -> None:
        self._service.pause_campaign(campaign_id)

    def resume(self, campaign_id: str) -> None:
        self._service.resume_campaign(campaign_id)

    def stop(self, campaign_id: str) -> None:
        self._service.stop_campaign(campaign_id)

    def reconcile(self, campaign_id: str) -> dict[str, object]:
        return self._service.reconcile_campaign(campaign_id)

    def run_phase8(
        self,
        campaign_id: str,
        completed_generations: tuple[int, ...],
    ) -> dict[str, object]:
        return self._service.run_training_phase8(
            workflow_id=campaign_id.removesuffix("-campaign"),
            campaign_id=campaign_id,
            completed_generations=completed_generations,
        )


def run_workflow(*, project_root: Path, workflow_id: str) -> TrainingStatus:
    """Run or resume one persisted workflow until it completes or needs intervention."""
    root = Path(project_root).resolve()
    store = TrainingStore(root, workflow_id)
    execution_mode = store.load_request().execution_mode if store.root.is_dir() else "PRODUCTION_CMO"
    if execution_mode == "FAKE_FIXTURE":
        driver = FixtureCampaignDriver()
    else:
        config = load_config()
        service = create_production_evolution_campaign_service(
            project_root=root,
            app_config=config,
            llm_client=ClaudeClient(config.llm),
        )
        driver = ProductionCampaignDriver(service)
    runner = TrainingRunner(
        store,
        driver,
        repair_coordinator=CodeRepairCoordinator(project_root=root),
    )
    runner.reconcile()
    while True:
        state = runner.run()
        if state.status is not TrainingStatus.RUNNING:
            return state.status
        # A RUNNING workflow can be either waiting for CMO or retrying a
        # classified transient provider/process failure.  In both cases its
        # persisted action remains resumable and needs no user confirmation.
        sleep(retry_sleep_seconds(state))


def retry_sleep_seconds(state: object) -> int:
    """Return the persisted retry delay, with normal worker polling as fallback."""
    runner = getattr(state, "runner", {})
    retry = runner.get("retry") if isinstance(runner, dict) else None
    next_retry_at = retry.get("next_retry_at") if isinstance(retry, dict) else None
    if not isinstance(next_retry_at, str):
        return 1
    try:
        target = datetime.fromisoformat(next_retry_at.replace("Z", "+00:00"))
    except ValueError:
        return 1
    if target.tzinfo is None:
        target = target.replace(tzinfo=UTC)
    remaining = int((target - datetime.now(UTC)).total_seconds())
    return max(1, min(remaining, 60))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one persistent CMO training workflow")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--project-root", required=True)
    run.add_argument("--workflow-id", required=True)
    args = parser.parse_args(argv)
    status = run_workflow(
        project_root=Path(args.project_root),
        workflow_id=str(args.workflow_id),
    )
    return 0 if status is TrainingStatus.COMPLETED else 1


if __name__ == "__main__":
    raise SystemExit(main())
