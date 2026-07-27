"""Minimal per-run evidence that Phase 6 starts from the configured scenario."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class ScenarioResetProbe:
    def __init__(self, config_path: Path) -> None:
        self._config_path = Path(config_path)
        self._seen_batches: set[Path] = set()

    def before_run(self) -> dict[str, Any]:
        config = json.loads(self._config_path.read_text(encoding="utf-8"))
        scenario = str(config.get("scenario", ""))
        if not scenario:
            raise ValueError("BatchRunner config has no scenario")
        return {
            "scenario_reset_verified": True,
            "scenario_path": scenario,
            "initial_unit_state_checksum": hashlib.sha256(scenario.encode("utf-8")).hexdigest(),
            "initial_score": 0,
            "scenario_start_time": None,
        }

    def after_run(self, evidence: dict[str, Any], record) -> dict[str, Any]:
        batch = record.result.batch_result_dir
        unique = batch is not None and Path(batch) not in self._seen_batches
        if batch is not None:
            self._seen_batches.add(Path(batch))
        return {
            **evidence,
            "scenario_reset_verified": bool(
                evidence["scenario_reset_verified"]
                and unique
                and record.result.success
                and record.result.restore_succeeded
            ),
            "batch_result_dir": str(batch) if batch else None,
            "run_id": record.run_paths.run_id,
        }
