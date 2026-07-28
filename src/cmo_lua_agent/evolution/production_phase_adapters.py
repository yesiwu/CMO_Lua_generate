"""Thin production adapters for the existing Phase 7 and Phase 8 workflows."""

from __future__ import annotations

from pathlib import Path

from cmo_lua_agent.agents.comparative_learning_agent import ComparativeLearningAgent
from cmo_lua_agent.agents.skill_author_agent import SkillAuthorAgent
from cmo_lua_agent.learning.skill_evolution.assets import SkillAssetStore
from cmo_lua_agent.learning.skill_evolution.config import SkillStorageConfig
from cmo_lua_agent.learning.skill_evolution.regression import SkillRegressionService
from cmo_lua_agent.learning.skill_evolution.workflow import SkillEvolutionWorkflow
from cmo_lua_agent.learning.store import ExperienceStore
from cmo_lua_agent.learning.workflow import GenerationLearningWorkflow


class ProductionPhase7Adapter:
    def __init__(self, *, project_root: Path, json_client: object) -> None:
        self._store = ExperienceStore(Path(project_root) / "data" / "experiences")
        self._workflow = GenerationLearningWorkflow(
            agent=ComparativeLearningAgent(json_client),
            store=self._store,
        )

    @property
    def experience_store(self) -> ExperienceStore:
        return self._store

    def run(
        self,
        *,
        generation_index: int,
        optimization_dir: Path,
        outcomes: tuple[dict[str, object], ...],
    ) -> dict[str, object]:
        bundle, experiences = self._workflow.run(Path(optimization_dir))
        return {
            "status": "completed",
            "generation_index": generation_index,
            "optimization_id": bundle.optimization_id,
            "experience_candidate_count": len(experiences),
            "experience_ids": [item.experience_id for item in experiences],
            "learning_dir": str(Path(optimization_dir) / "learning"),
        }


class ProductionPhase8Adapter:
    def __init__(
        self,
        *,
        project_root: Path,
        json_client: object,
        experience_store: ExperienceStore,
    ) -> None:
        self._root = Path(project_root).resolve()
        self._experience_store = experience_store
        self._workflow = SkillEvolutionWorkflow(
            author_agent=SkillAuthorAgent(json_client),
            asset_store=SkillAssetStore(
                SkillStorageConfig.production(self._root)
            ),
            regression_service=SkillRegressionService(
                proposal_validator=lambda _package: True
            ),
        )

    def run(
        self,
        *,
        generation_index: int,
        phase7_result: dict[str, object],
    ) -> dict[str, object]:
        optimization_id = str(phase7_result["optimization_id"])
        result = self._workflow.run(
            phase8_run_id=f"{optimization_id}_phase8",
            runs_root=self._root / "runs" / "evolution",
            experience_store=self._experience_store,
        )
        return result.to_dict()
