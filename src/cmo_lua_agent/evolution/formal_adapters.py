"""Thin production adapters; all rendering, CMO, learning and promotion remain owned by Phase 6-8."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from cmo_lua_agent.evolution.models import CandidateScore, Phase6GenerationArtifact


@dataclass
class FormalPhase6Adapter:
    """Call the existing OptimizationGenerationWorkflow once and project its durable outcomes."""
    workflow: object
    request_factory: Callable[..., object]

    def run(self, *, generation_index: int, rolling_baseline_id: str, **kwargs: object) -> Phase6GenerationArtifact:
        request = self.request_factory(generation_index=generation_index, rolling_baseline_id=rolling_baseline_id, **kwargs)
        result = self.workflow.run(request)
        if not result.workflow_completed:
            raise RuntimeError(f"phase6_failed:{result.failure_reason or 'unknown'}")
        paths = [Path(result.baseline_outcome_path), *(Path(path) for path in result.candidate_outcome_paths)]
        outcomes = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
        scores = tuple(self._score(item) for item in outcomes)
        attempts = sum(int(item.get("execution_attempts", 0)) for item in outcomes)
        failed = sum(1 for item in outcomes if not item.get("execution_success", False))
        return Phase6GenerationArtifact(scores[0], scores[1:], str(request.optimization_dir), attempts, failed)

    @staticmethod
    def _score(outcome: dict[str, object]) -> CandidateScore:
        return CandidateScore(
            candidate_id=str(outcome["candidate_id"]), official_score=outcome.get("native_score"),
            execution_success=bool(outcome.get("execution_success")), scoreable=bool(outcome.get("scoreable")),
            semantic_valid=bool(outcome.get("semantic_valid")),
            artifact_provenance=str(outcome.get("artifact_provenance", "formal_renderer")),
            score_source=outcome.get("score_source"), execution_fidelity=str(outcome.get("execution_fidelity", "unknown")),
        )
