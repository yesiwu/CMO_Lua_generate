"""Run one read-only Phase 7 learning pass for an existing Phase 6 run."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from cmo_lua_agent.agents.comparative_learning_agent import ComparativeLearningAgent
from cmo_lua_agent.learning.store import ExperienceStore
from cmo_lua_agent.learning.workflow import GenerationLearningWorkflow
from cmo_lua_agent.llm.client import ClaudeClient
from cmo_lua_agent.llm.json_client import ClaudeJsonClient
from cmo_lua_agent.llm_config import load_config


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _skill_snapshot() -> dict[str, str]:
    return {
        str(path.relative_to(PROJECT_ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in PROJECT_ROOT.rglob("SKILL.md")
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "optimization_dir",
        type=Path,
        help="existing runs/<optimization_id> directory to analyze",
    )
    parser.add_argument(
        "--experiences-root",
        type=Path,
        default=PROJECT_ROOT / "data" / "experiences",
        help="Phase 7 ExperienceStore root",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    optimization_dir = args.optimization_dir.resolve()
    runs_root = (PROJECT_ROOT / "runs").resolve()
    if not optimization_dir.is_dir() or optimization_dir.parent != runs_root:
        raise ValueError("optimization_dir must be an existing direct child of project runs/")

    skills_before = _skill_snapshot()
    client = ClaudeJsonClient(ClaudeClient(load_config().llm))
    workflow = GenerationLearningWorkflow(
        agent=ComparativeLearningAgent(client),
        store=ExperienceStore(args.experiences_root.resolve()),
    )
    bundle, first = workflow.run(optimization_dir)
    _, replay = workflow.run(optimization_dir, reuse_saved_response=True)
    if first != replay:
        raise RuntimeError("Phase 7 replay is not idempotent")
    if skills_before != _skill_snapshot():
        raise RuntimeError("Phase 7 must not create or modify Skill files")

    print(json.dumps({
        "optimization_id": bundle.optimization_id,
        "candidate_ids": [bundle.baseline_view.candidate_id, *(view.candidate_id for view in bundle.candidate_views)],
        "proposal_count": len(json.loads((optimization_dir / "learning" / "experience-proposals.json").read_text(encoding="utf-8"))),
        "experience_count": len(first),
        "experience_types": sorted({item.experience_type for item in first}),
        "learning_dir": str(optimization_dir / "learning"),
        "experiences_root": str(args.experiences_root.resolve()),
        "replay_idempotent": True,
    }, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
