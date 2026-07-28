"""Build the optional rolling-baseline failure profile from formal artifacts."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from cmo_lua_agent.evolution.production_models import BaselineFailureProfile


class BaselineFailureProfileBuilder:
    """Read only the three reviewed Phase 3 machine interfaces."""

    _FILES = (
        "execution-summary.json",
        "semantic-validation.json",
        "planned-vs-actual.json",
    )

    def build(self, result_root: Path) -> BaselineFailureProfile | None:
        root = Path(result_root)
        paths = {name: root / name for name in self._FILES}
        if not all(path.is_file() for path in paths.values()):
            return None
        values = {
            name: self._load_object(path) for name, path in paths.items()
        }
        summary = values["execution-summary.json"]
        semantic = values["semantic-validation.json"]
        actual = values["planned-vs-actual.json"]
        integrity = summary.get("evidence_integrity", {})
        if isinstance(integrity, dict) and integrity.get("valid") is False:
            return None
        score = summary.get("official_score")
        run = summary.get("run")
        if not isinstance(score, dict) or not isinstance(run, dict):
            return None
        if score.get("final") is None or not run.get("run_id"):
            return None
        indicators = semantic.get("failure_indicators", ())
        deviations = actual.get("deviations", ())
        if not isinstance(indicators, list) or not isinstance(deviations, list):
            return None
        return BaselineFailureProfile.create(
            run_id=str(run["run_id"]),
            official_score=score["final"],
            semantic_valid=bool(semantic.get("semantic_valid", False)),
            execution_fidelity=str(
                actual.get("execution_fidelity", "unknown")
            ),
            failure_indicators=tuple(str(item) for item in indicators),
            deviations=tuple(
                dict(item) for item in deviations if isinstance(item, dict)
            ),
            source_checksums={
                name: sha256(path.read_bytes()).hexdigest()
                for name, path in paths.items()
            },
        )

    @staticmethod
    def _load_object(path: Path) -> dict[str, Any]:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("baseline_failure_profile_artifact_invalid")
        return value
