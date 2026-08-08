#!/usr/bin/env python3
"""Start and control the persistent CMO training harness without chat."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from cmo_lua_agent.training.service import TrainingService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Persistent CMO training workflow")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("start")
    start.add_argument("--input-path", required=True)
    start.add_argument("--objective", required=True)
    start.add_argument("--generation-count", type=int, required=True)
    for command in ("status", "pause", "resume", "stop"):
        child = commands.add_parser(command)
        child.add_argument("--workflow-id", required=True)
    args = parser.parse_args(argv)
    service = TrainingService(project_root=args.project_root)
    if args.command == "start":
        result = service.start(
            input_path=args.input_path,
            objective=args.objective,
            generation_count=args.generation_count,
        )
    elif args.command == "status":
        result = service.inspect(args.workflow_id)
    else:
        result = service.control(args.workflow_id, args.command)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
