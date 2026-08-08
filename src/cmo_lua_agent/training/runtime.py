"""Production adapter between the persistent TrainingRunner and Campaign service."""

from __future__ import annotations

from typing import Any

from cmo_lua_agent.training.models import TrainingRequest


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
        self._service.preview_generation(
            campaign_id=campaign_id,
            generation_index=generation_index,
        )

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
