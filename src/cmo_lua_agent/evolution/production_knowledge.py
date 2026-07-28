"""Production knowledge snapshot assembly for Phase 9C previews."""

from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
from pathlib import Path

from cmo_lua_agent.evolution.knowledge_snapshot import KnowledgeSnapshotService
from cmo_lua_agent.evolution.production_models import canonical_checksum
from cmo_lua_agent.learning.skill_evolution.active_loader import (
    ActiveSkillLoader,
    make_compatibility_cohort,
)
from cmo_lua_agent.learning.store import ExperienceRetriever, ExperienceStore


class _GenerationExperienceRetriever:
    def __init__(self, store: ExperienceStore, environment: dict[str, str]) -> None:
        self._retriever = ExperienceRetriever(store)
        self._environment = environment

    def retrieve(self, **kwargs: object) -> tuple[dict[str, object], ...]:
        query = dict(kwargs.get("query", {}))
        groups = self._retriever.retrieve(
            current_optimization_id=str(query["current_optimization_id"]),
            environment=self._environment,
            allowed_dimensions=tuple(query["allowed_dimensions"]),
        )
        return tuple(asdict(card) for group in groups for card in group)


class ProductionKnowledgeSnapshotProvider:
    """Freeze production experience and exact-cohort curated skill visibility."""

    _SKILL_ID = "cmo_naval_air_strategy_patterns"

    def __init__(self, *, project_root: Path, experience_store: ExperienceStore) -> None:
        self._root = Path(project_root).resolve()
        self._store = experience_store

    def freeze(
        self,
        *,
        path: Path,
        spec: object,
        package: object,
        generation_index: int,
    ) -> dict[str, object]:
        environment = {
            "runtime_version": package.runtime.runtime_version,
            "renderer_version": package.renderer_version,
            "score_spec_checksum": package.checksums["score_spec_compiled"],
        }
        cohort = make_compatibility_cohort(
            score_spec_version="1.0.0",
            score_spec_checksum=environment["score_spec_checksum"],
            runtime_version=environment["runtime_version"],
            renderer_version=environment["renderer_version"],
        )
        active = ActiveSkillLoader(
            self._root / "data" / "skills",
            expected_provenance="production",
        ).load(skill_id=self._SKILL_ID, cohort=cohort)
        active_skills = (
            (active.to_prompt_dict(),) if active is not None else ()
        )
        index = self._store.index
        index_bytes = index.read_bytes() if index.is_file() else b""
        index_checksum = sha256(index_bytes).hexdigest()
        query = {
            "current_optimization_id": (
                f"{spec.campaign_id}_generation_{generation_index:03d}"
            ),
            "allowed_dimensions": list(package.diversity_dimensions),
            "compatibility_cohort": cohort.cohort_id,
        }
        snapshot = KnowledgeSnapshotService(
            retriever=_GenerationExperienceRetriever(self._store, environment)
        ).freeze(
            path=path,
            campaign_id=spec.campaign_id,
            generation_index=generation_index,
            bootstrap_checksum=package.bootstrap.checksum,
            active_skills=active_skills,
            experience_store_revision=index_checksum,
            experience_index_checksum=index_checksum,
            retrieval_query=query,
            contract=dict(package.checksums),
            parent_strategy_checksum=canonical_checksum(
                package.baseline.strategy.to_dict()
            ),
        )
        return snapshot.to_dict()
