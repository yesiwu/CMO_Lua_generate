"""Request a cooperative stop; a running Campaign checks it between calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("campaign_dir", type=Path)
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()
    path = args.campaign_dir / "manual-stop.json"
    path.write_text(json.dumps({"reason": args.reason}, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
