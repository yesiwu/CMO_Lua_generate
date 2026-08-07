"""Reconstruct Phase 7 facts from published CMO CSV results, then run Phase 7."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from cmo_lua_agent.agents.comparative_learning_agent import ComparativeLearningAgent
from cmo_lua_agent.learning.evidence_reconstruction import ResultEvidenceReconstructor
from cmo_lua_agent.learning.store import ExperienceStore
from cmo_lua_agent.learning.workflow import GenerationLearningWorkflow
from cmo_lua_agent.llm.client import ClaudeClient
from cmo_lua_agent.llm.json_client import ClaudeJsonClient
from cmo_lua_agent.llm_config import load_config


def _atomic_json(path: Path, value: dict[str, object]) -> None:
    import os
    import tempfile

    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent) as stream:
        stream.write(payload)
        temp = stream.name
    os.replace(temp, path)


def rebuild(phase6_dir: Path) -> list[dict[str, object]]:
    root = Path(phase6_dir)
    result = json.loads((root / "generation_result.json").read_text(encoding="utf-8"))
    outcomes = [Path(result["baseline_outcome_path"]), *(Path(item) for item in result["candidate_outcome_paths"])]
    audit: list[dict[str, object]] = []
    for outcome_path in outcomes:
        candidate_dir = outcome_path.parent
        attempt = candidate_dir / "attempts" / "attempt_00"
        result_summary = next((attempt / "batch-results").rglob("execution-summary.json"), None)
        if result_summary is None:
            raise ValueError(f"missing published execution summary: {candidate_dir.name}")
        rules = ResultEvidenceReconstructor.rules_from_rendered_lua(attempt / "candidate.lua")
        if not rules:
            raise ValueError(f"missing rendered native score rules: {candidate_dir.name}")
        updated = ResultEvidenceReconstructor(score_rules=rules).apply(result_summary.parent)
        # CandidateLearningView reads the attempt-local copy.  Synchronize only
        # the reconstructed evidence fields, never raw logs or SQLite content.
        attempt_summary = attempt / "execution-summary.json"
        local = json.loads(attempt_summary.read_text(encoding="utf-8"))
        for key in ("losses", "target_damage", "score_events", "scoring_evidence_status", "phase7_reconstruction"):
            local[key] = updated[key]
        local["official_score"] = updated["official_score"]
        local["evidence_integrity"] = updated["evidence_integrity"]
        _atomic_json(attempt_summary, local)
        audit.append({
            "candidate_id": candidate_dir.name.removeprefix("candidate_"),
            "summary": str(attempt_summary),
            "score_event_count": len(updated["score_events"]),
            "scoring_evidence_status": updated["scoring_evidence_status"],
        })
    return audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase6_dir", type=Path)
    parser.add_argument("--experiences-root", type=Path, default=PROJECT_ROOT / "data" / "experiences")
    parser.add_argument("--skip-learning", action="store_true")
    args = parser.parse_args()
    phase6_dir = args.phase6_dir.resolve()
    audit = rebuild(phase6_dir)
    payload: dict[str, object] = {"reconstructed": audit, "phase6_dir": str(phase6_dir)}
    if not args.skip_learning:
        workflow = GenerationLearningWorkflow(
            agent=ComparativeLearningAgent(ClaudeJsonClient(ClaudeClient(load_config().llm))),
            store=ExperienceStore(args.experiences_root.resolve()),
        )
        bundle, experiences = workflow.run(phase6_dir)
        payload["optimization_id"] = bundle.optimization_id
        payload["experience_count"] = len(experiences)
        payload["learning_dir"] = str(phase6_dir / "learning")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
