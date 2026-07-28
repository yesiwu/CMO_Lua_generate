"""Explicit Phase 9 commands. Production execution requires an injected runtime."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="phase9-evolution")
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("start")
    start.add_argument("campaign_spec", type=Path)
    for name in ("max-generations", "max-cmo-runs", "max-cmo-attempts-per-candidate",
                 "max-cmo-attempts-for-baseline", "max-repair-attempts-per-candidate",
                 "max-failed-runs", "max-llm-total-calls", "max-strategy-proposal-calls",
                 "max-lua-generation-calls", "max-lua-repair-calls", "max-comparative-learning-calls",
                 "max-skill-author-calls", "max-wall-clock-seconds", "per-generation-timeout-seconds",
                 "per-candidate-timeout-seconds"):
        start.add_argument(f"--{name}", required=True, type=int)
    resume = commands.add_parser("resume")
    resume.add_argument("campaign_id")
    inspect = commands.add_parser("inspect")
    inspect.add_argument("campaign_id")
    stop = commands.add_parser("stop")
    stop.add_argument("campaign_id")
    stop.add_argument("--reason", required=True)
    recover = commands.add_parser("recover-lock")
    recover.add_argument("--reason", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # This module intentionally exposes only parsing/control. A production
    # runtime must be built by an explicit caller, never by an import side effect.
    print(json.dumps({"command": args.command, "accepted": True}, ensure_ascii=False))
    return 0
