"""Run one explicit Phase 9 Campaign generation from the command line.

Generation zero uses the ScenarioIR-derived baseline.  Every later generation
uses the Champion persisted by the immediately preceding generation and the
knowledge snapshot retrieves already stored ExperienceCards.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Any

from cmo_lua_agent.evolution.control_plane import EvolutionCampaignService
from cmo_lua_agent.evolution.production_service import (
    create_production_evolution_campaign_service,
)
from cmo_lua_agent.llm.client import ClaudeClient
from cmo_lua_agent.llm_config import load_config


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("json_object_required")
    return value


def _service(root: Path, campaign_id: str):
    config = load_config()
    service = create_production_evolution_campaign_service(
        project_root=root,
        app_config=config,
        llm_client=ClaudeClient(config.llm),
    )
    campaign_root = root / "runs" / "evolution" / campaign_id
    spec = EvolutionCampaignService._spec_from_dict(
        _json(campaign_root / "campaign-spec.json")
    )
    package = service._package_loader.load(spec.scenario_ref)
    service._services[campaign_id] = service._build_core(spec, package)
    return service


def _print(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare")
    prepare.add_argument("campaign_id")
    prepare.add_argument("--budget-file", required=True, type=Path)
    prepare.add_argument(
        "--objective",
        default="Improve the red-side official score while retaining valid execution.",
    )
    prepare.add_argument("--minimum-improvement-delta", type=int, default=1)
    prepare.add_argument("--no-improvement-patience", type=int, default=2)

    preview = commands.add_parser("preview")
    preview.add_argument("campaign_id")
    preview.add_argument("--generation", required=True, type=int)
    preview.add_argument("--regenerate", action="store_true")

    execute = commands.add_parser("execute")
    execute.add_argument("campaign_id")
    execute.add_argument("--generation", required=True, type=int)
    execute.add_argument("--confirm-cmo", action="store_true")
    execute.add_argument("--timeout-seconds", type=int, default=3600)

    inspect = commands.add_parser("inspect")
    inspect.add_argument("campaign_id")
    inspect.add_argument("--generation", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path.cwd().resolve()

    if args.command == "prepare":
        config = load_config()
        service = create_production_evolution_campaign_service(
            project_root=root,
            app_config=config,
            llm_client=ClaudeClient(config.llm),
        )
        _print(service.prepare_campaign_request(
            campaign_id=args.campaign_id,
            input_package_id="red_blue_6v4_liaoning_v1",
            generation_objective=args.objective,
            budget=_json(args.budget_file),
            minimum_improvement_delta=args.minimum_improvement_delta,
            no_improvement_patience=args.no_improvement_patience,
        ))
        return 0

    service = _service(root, args.campaign_id)
    if args.command == "preview":
        preview = service.preview_generation(
            campaign_id=args.campaign_id,
            generation_index=args.generation,
            regenerate_preview=args.regenerate,
        )
        _print(preview)
        return 0
    if args.command == "inspect":
        if args.generation is None:
            _print(service.inspect_campaign(args.campaign_id))
        else:
            _print(service.inspect_generation(args.campaign_id, args.generation))
        return 0

    if not args.confirm_cmo:
        raise SystemExit("Refusing CMO launch: pass --confirm-cmo after reviewing Preview.")
    worker = service.execute_generation(
        campaign_id=args.campaign_id,
        generation_index=args.generation,
    )
    deadline = time.monotonic() + args.timeout_seconds
    campaign_root = root / "runs" / "evolution" / args.campaign_id
    store, _ = service._services[args.campaign_id]._load(args.campaign_id)
    while time.monotonic() < deadline:
        current = store.get_worker(worker.operation_id)
        if current is not None and current.status != "running":
            _print({"campaign_root": str(campaign_root), "worker": current})
            return 0 if current.status == "completed" else 1
        time.sleep(5)
    raise TimeoutError("generation_worker_poll_timeout")


if __name__ == "__main__":
    raise SystemExit(main())
