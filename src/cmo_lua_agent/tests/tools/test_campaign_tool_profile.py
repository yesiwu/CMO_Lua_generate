from __future__ import annotations

from pathlib import Path

from cmo_lua_agent.evolution.control_plane import (
    EvolutionCampaignService,
    GenerationExecutionResult,
    GenerationPreviewPayload,
)
from cmo_lua_agent.hooks.manager import HookManager
from cmo_lua_agent.tools.tool_base.factory import build_tool_registry


class _Preview:
    def build(self, **_: object) -> GenerationPreviewPayload:
        return GenerationPreviewPayload("snapshot", "candidates", (), 1)


class _Executor:
    def run(self, _context: object) -> GenerationExecutionResult:
        return GenerationExecutionResult.completed({})


def test_campaign_profile_exposes_exactly_six_high_level_tools_and_no_execute_cmo(tmp_path: Path) -> None:
    service = EvolutionCampaignService(
        campaigns_root=tmp_path / "runs" / "evolution",
        preview_builder=_Preview(),
        generation_executor=_Executor(),
        synchronous_fake_workers=True,
    )
    registry = build_tool_registry(
        workdir=tmp_path,
        hook_manager=HookManager(),
        chat_profile="campaign",
        evolution_campaign_service=service,
    )

    assert {definition["name"] for definition in registry.get_definitions()} == {
        "prepare_evolution_campaign",
        "preview_evolution_generation",
        "execute_evolution_generation",
        "inspect_evolution_campaign",
        "inspect_evolution_generation",
        "control_evolution_campaign",
    }
    assert registry.get("execute_cmo") is None
