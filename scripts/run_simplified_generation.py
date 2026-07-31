"""Run one existing Campaign generation from its frozen slot strategies.

This is intentionally an execution-only entry point: it does not create a
preview, call an LLM, or issue an approval.  It rebuilds plans and Lua for the
baseline plus the four frozen candidates, then starts the five serial CMO jobs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from cmo_lua_agent.evolution.control_plane import EvolutionCampaignService
from cmo_lua_agent.evolution.production_service import (
    create_production_evolution_campaign_service,
)
from cmo_lua_agent.llm.client import ClaudeClient
from cmo_lua_agent.llm_config import load_config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("campaign_id")
    parser.add_argument("--timeout-seconds", type=int, default=1500)
    args = parser.parse_args()

    root = Path.cwd().resolve()
    campaign_root = root / "runs" / "evolution" / args.campaign_id
    spec_data = json.loads((campaign_root / "campaign-spec.json").read_text(encoding="utf-8"))
    spec = EvolutionCampaignService._spec_from_dict(spec_data)
    service = create_production_evolution_campaign_service(
        project_root=root,
        app_config=load_config(),
        llm_client=ClaudeClient(load_config().llm),
    )
    package = service._package_loader.load(spec.scenario_ref)
    service._services[args.campaign_id] = service._build_core(spec, package)
    service.resume_campaign(args.campaign_id)
    worker = service.execute_generation(
        campaign_id=args.campaign_id,
        generation_index=0,
    )
    print(json.dumps({"operation_id": worker.operation_id, "status": worker.status}, ensure_ascii=False))

    core = service._services[args.campaign_id]
    store, _ = core._load(args.campaign_id)
    deadline = time.monotonic() + args.timeout_seconds
    while time.monotonic() < deadline:
        current = store.get_worker(worker.operation_id)
        if current is not None and current.status != "running":
            print(json.dumps({"status": current.status, "error": current.error, "result": current.result}, ensure_ascii=False, default=str))
            return
        time.sleep(5)
    raise TimeoutError("generation_worker_poll_timeout")


if __name__ == "__main__":
    main()
