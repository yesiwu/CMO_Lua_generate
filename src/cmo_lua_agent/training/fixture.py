"""Deterministic no-CMO driver used only by the legacy CLI fixture mode."""

from __future__ import annotations


class FixtureCampaignDriver:
    def prepare(self, request): return f"{request.workflow_id}-campaign"
    def preview(self, campaign_id: str, generation_index: int) -> None: pass
    def execute(self, campaign_id: str, generation_index: int) -> None: pass
    def inspect_generation(self, campaign_id: str, generation_index: int) -> dict[str, object]: return {"status": "completed"}
    def pause(self, campaign_id: str) -> None: pass
    def resume(self, campaign_id: str) -> None: pass
    def stop(self, campaign_id: str) -> None: pass
    def reconcile(self, campaign_id: str) -> dict[str, object]: return {"status": "completed"}
    def run_phase8(self, campaign_id: str, completed_generations: tuple[int, ...]) -> dict[str, object]:
        return {"status": "completed", "phase8_run_id": f"{campaign_id.removesuffix('-campaign')}_phase8"}
