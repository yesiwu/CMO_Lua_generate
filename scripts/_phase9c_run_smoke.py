from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import json
import time

from cmo_lua_agent.cli.terminal_approval import TerminalApprover
from cmo_lua_agent.evolution.control_plane import EvolutionCampaignService
from cmo_lua_agent.evolution.production_service import (
    create_production_evolution_campaign_service,
)
from cmo_lua_agent.hooks.permission_hook import PermissionHook
from cmo_lua_agent.llm.client import ClaudeClient
from cmo_lua_agent.llm_config import load_config


def main() -> None:
    root = Path.cwd()
    campaign_id = "phase9c1_a00_smoke_20260729"
    config = load_config()
    service = create_production_evolution_campaign_service(
        project_root=root,
        app_config=config,
        llm_client=ClaudeClient(config.llm),
    )
    package = service._package_loader.load("red_blue_6v4_liaoning_v1")
    spec = EvolutionCampaignService._spec_from_dict(
        json.loads(
            (root / "runs" / "evolution" / campaign_id / "campaign-spec.json").read_text(
                encoding="utf-8"
            )
        )
    )
    if package.git_commit != spec.code_revision:
        raise RuntimeError("contract_changed: code_revision")
    service._services[campaign_id] = service._build_core(spec, package)
    context = {
        "tool": SimpleNamespace(
            name="execute_evolution_generation", requires_approval=True
        ),
        "arguments": {"campaign_id": campaign_id, "generation_index": 0},
    }
    hook = PermissionHook(
        approval_function=TerminalApprover(),
        receipt_persister=service.persist_permission_grant,
    )
    hook.handle("before_tool_call", context)
    approval_id = context["approval_receipt"].approval_id
    worker = service.execute_generation(
        campaign_id=campaign_id,
        generation_index=0,
        approval_id=approval_id,
    )
    print(
        json.dumps(
            {
                "approval_id": approval_id,
                "worker_operation_id": worker.operation_id,
                "worker_status": worker.status,
            },
            ensure_ascii=False,
        )
    )
    store = service._services[campaign_id]._load(campaign_id)[0]
    deadline = time.monotonic() + 1250
    while time.monotonic() < deadline:
        current = store.get_worker(worker.operation_id)
        if current is not None and current.status != "running":
            print(
                json.dumps(
                    {
                        "worker_terminal": {
                            "status": current.status,
                            "error": current.error,
                            "result": current.result,
                        }
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return
        time.sleep(5)
    print(json.dumps({"worker_terminal": {"status": "poll_timeout"}}))


if __name__ == "__main__":
    main()
