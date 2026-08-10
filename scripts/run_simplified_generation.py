"""Run one existing Campaign generation from its frozen slot strategies.

This is intentionally an execution-only entry point: it does not create a
preview, call an LLM, or issue an approval.  It rebuilds plans and Lua for the
baseline plus the four frozen candidates, then starts the five serial CMO jobs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

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
    service = create_production_evolution_campaign_service(
        project_root=root,
        app_config=load_config(),
        llm_client=ClaudeClient(load_config().llm),
    )
    service.load_campaign(args.campaign_id)
    service.resume_campaign(args.campaign_id)
    worker = service.execute_generation(
        campaign_id=args.campaign_id,
        generation_index=0,
    )
    print(json.dumps({"operation_id": worker.operation_id, "status": worker.status}, ensure_ascii=False))

    generation = service.wait_for_generation(
        campaign_id=args.campaign_id,
        generation_index=0,
        operation_id=worker.operation_id,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(generation, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
