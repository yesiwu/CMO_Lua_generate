"""Legacy CLI compatibility wrapper backed by the persistent TrainingRunner."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from cmo_lua_agent.training.service import TrainingService

_SCENARIOS = {
    "red_blue_6v4_liaoning_v1": "baseline/6v4/manual-template/6v4ScenarioIR_baseline_v3.json",
}


def _service(args: argparse.Namespace) -> TrainingService:
    return TrainingService(
        project_root=Path.cwd(),
        workflow_id_factory=lambda: str(args.campaign_id),
    )


def cmd_start(args: argparse.Namespace) -> int:
    result = _service(args).start(
        input_path=_SCENARIOS[args.scenario],
        objective=args.objective,
        generation_count=args.max_generations,
        execution_mode=args.mode,
    )
    print(result)
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    print(_service(args).inspect(args.campaign_id))
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    print(_service(args).control(args.campaign_id, "stop"))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="run_auto_evolution")
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start")
    start.add_argument("--campaign-id", required=True)
    start.add_argument("--scenario", choices=tuple(_SCENARIOS), default="red_blue_6v4_liaoning_v1")
    start.add_argument("--max-generations", type=int, default=20)
    start.add_argument("--mode", choices=("PRODUCTION_CMO", "FAKE_FIXTURE"), default="FAKE_FIXTURE")
    start.add_argument("--objective", default="Improve red-side score through persistent training.")
    for name in ("--experiences", "--max-cmo-runs", "--max-repair-attempts", "--min-improvement-delta", "--patience"):
        start.add_argument(name, type=int, help="Deprecated legacy option; ignored by TrainingRunner.")
    for command in ("status", "stop"):
        sub.add_parser(command).add_argument("--campaign-id", required=True)
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    raise SystemExit({"start": cmd_start, "status": cmd_status, "stop": cmd_stop}[args.command](args))
