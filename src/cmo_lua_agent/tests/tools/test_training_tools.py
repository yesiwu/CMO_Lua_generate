from __future__ import annotations

import json
from types import SimpleNamespace

from cmo_lua_agent.tools.training_tools import training_tools
from cmo_lua_agent.tools.tool_base.factory import build_tool_registry


def test_training_tools_expose_only_high_level_unapproved_actions() -> None:
    service = SimpleNamespace(
        start=lambda **kwargs: {"workflow_id": "training-001", **kwargs},
        inspect=lambda workflow_id: {"workflow_id": workflow_id, "status": "RUNNING"},
        control=lambda workflow_id, action: {"workflow_id": workflow_id, "action": action},
    )
    tools = {tool.name: tool for tool in training_tools(service=service)}

    assert set(tools) == {"start_training", "inspect_training", "control_training"}
    assert not any(tool.requires_approval for tool in tools.values())
    assert json.loads(tools["start_training"].execute({
        "input_path": "scenario.json", "objective": "improve", "generation_count": 3,
    }).content)["workflow_id"] == "training-001"
    assert json.loads(tools["control_training"].execute({
        "workflow_id": "training-001", "action": "pause",
    }).content)["action"] == "pause"


def test_training_profile_registers_only_training_tools(tmp_path) -> None:
    service = SimpleNamespace()
    registry = build_tool_registry(
        workdir=tmp_path,
        hook_manager=SimpleNamespace(),
        chat_profile="training",
        training_service=service,
    )

    assert {item["name"] for item in registry.get_definitions()} == {
        "start_training", "inspect_training", "control_training",
    }
