from __future__ import annotations

import importlib.util
from pathlib import Path


def _cli_module():
    path = Path(__file__).parents[4] / "scripts" / "run_manual_campaign_generation.py"
    spec = importlib.util.spec_from_file_location("manual_campaign_cli", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_budget_json_accepts_powershell_utf8_bom(tmp_path: Path) -> None:
    budget = tmp_path / "budget.json"
    budget.write_bytes(b"\xef\xbb\xbf{\"max_generations\": 3}")

    assert _cli_module()._json(budget) == {"max_generations": 3}
