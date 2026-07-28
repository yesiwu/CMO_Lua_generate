"""Print the durable state of one Phase 9 campaign without running it."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("campaign_dir", type=Path)
    args = parser.parse_args()
    for name in ("campaign-spec.json", "campaign-result.json", "operation-ledger.jsonl"):
        path = args.campaign_dir / name
        if path.is_file():
            print(path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
