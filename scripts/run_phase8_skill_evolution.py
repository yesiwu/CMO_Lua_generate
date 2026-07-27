"""Run offline Phase 8 Skill evolution from an existing Experience Store."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase8_run_id")
    parser.add_argument(
        "--experiences-root",
        type=Path,
        default=PROJECT_ROOT / "data" / "experiences",
    )
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=PROJECT_ROOT / "runs",
    )
    parser.add_argument(
        "--proposal-regression-fixture",
        type=Path,
        help=(
            "optional reviewed proposal-regression result; without it an "
            "eligible pending Skill is retained with regression failed"
        ),
    )
    return parser.parse_args()


def _proposal_validator(path: Path | None):
    required = {
        "strategy_schema_valid",
        "semantic_validation_passed",
        "diversity_validation_passed",
        "scenario_facts_unchanged",
        "known_entities_only",
        "inventory_within_limits",
        "allowed_strategy_paths_only",
        "counterexamples_respected",
    }

    def validate(_package) -> bool:
        if path is None or not path.is_file():
            return False
        value = json.loads(path.read_text(encoding="utf-8"))
        return (
            isinstance(value, dict)
            and set(value) == required
            and all(value[field] is True for field in required)
        )

    return validate


class _NoCallAuthor:
    def create(self, _context):
        raise AssertionError("empty Experience Store must not call an LLM")

    def revise(self, _context):
        raise AssertionError("empty Experience Store must not call an LLM")


def main() -> int:
    args = _parse_args()
    from cmo_lua_agent.agents.skill_author_agent import SkillAuthorAgent
    from cmo_lua_agent.learning.skill_evolution.assets import SkillAssetStore
    from cmo_lua_agent.learning.skill_evolution.config import (
        SkillStorageConfig,
    )
    from cmo_lua_agent.learning.skill_evolution.regression import (
        SkillRegressionService,
    )
    from cmo_lua_agent.learning.skill_evolution.workflow import (
        SkillEvolutionWorkflow,
    )
    from cmo_lua_agent.learning.store import ExperienceStore

    experience_store = ExperienceStore(args.experiences_root.resolve())
    has_records = (
        experience_store.records.is_dir()
        and any(experience_store.records.glob("*.json"))
    )
    if has_records:
        from cmo_lua_agent.llm.client import ClaudeClient
        from cmo_lua_agent.llm.json_client import ClaudeJsonClient
        from cmo_lua_agent.llm_config import load_config

        author = SkillAuthorAgent(
            ClaudeJsonClient(ClaudeClient(load_config().llm))
        )
    else:
        author = _NoCallAuthor()
    workflow = SkillEvolutionWorkflow(
        author_agent=author,
        asset_store=SkillAssetStore(
            SkillStorageConfig.production(PROJECT_ROOT)
        ),
        regression_service=SkillRegressionService(
            proposal_validator=_proposal_validator(
                args.proposal_regression_fixture
            )
        ),
    )
    result = workflow.run(
        phase8_run_id=args.phase8_run_id,
        runs_root=args.runs_root.resolve(),
        experience_store=experience_store,
    )
    print(json.dumps(
        result.to_dict(),
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
