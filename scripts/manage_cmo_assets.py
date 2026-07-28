"""Inspect and manually verify local CMO scenario assets."""

from __future__ import annotations

import argparse
import getpass
import json
from pathlib import Path

from cmo_lua_agent.evolution.production_assets import (
    ScenarioAssetVerificationService,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path("config/cmo-assets.local.json"),
    )
    parser.add_argument(
        "--verification-root",
        type=Path,
        default=Path("data/asset-verifications"),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("asset_id")
    verify = subparsers.add_parser("verify")
    verify.add_argument("asset_id")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    service = ScenarioAssetVerificationService(
        registry_path=args.registry,
        verification_root=args.verification_root,
    )
    if args.command == "inspect":
        print(json.dumps(service.inspect(args.asset_id), ensure_ascii=False, indent=2))
        return 0
    inspection = service.inspect(args.asset_id)
    checklist = [
        "asset_id and scenario_id are correct",
        "the absolute path points to the intended .scen file",
        "the scenario opens from a clean initial state",
        "unit positions and damage states are pristine",
        "weapon inventories are pristine",
        "side points are at their documented initial values",
        "no prior Trigger, Action, or Event remains",
        "aircraft flight, base, and loadout state is pristine",
        "scenario start time is correct",
        "this checksum is approved for the controlled 6v4 package",
    ]
    print(json.dumps(inspection, ensure_ascii=False, indent=2))
    for index, item in enumerate(checklist, start=1):
        print(f"{index}. {item}")
    if input("Type y to create the verification record: ").strip().lower() != "y":
        print("Verification cancelled.")
        return 2
    record = service.verify(
        asset_id=args.asset_id,
        actor=getpass.getuser(),
        confirmed=True,
        verified_clean_initial_state=True,
    )
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
