from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from cmo_lua_agent.evolution.production_models import FrozenCandidateSet
from cmo_lua_agent.evolution.production_executor import ProductionGenerationExecutor
from cmo_lua_agent.evolution.production_preview import FrozenCandidateSetProvider


@dataclass
class _Parser:
    calls: int = 0

    def __call__(self, value):
        self.calls += 1
        return dict(value)


def _frozen() -> FrozenCandidateSet:
    return FrozenCandidateSet.create(
        campaign_id="campaign_fixture",
        generation_index=0,
        preview_revision=0,
        baseline={"scenario_id": "fixture", "value": 0},
        candidates=tuple(
            {
                "candidate_id": f"candidate_{index:02d}",
                "strategy": {"scenario_id": "fixture", "value": index + 1},
            }
            for index in range(4)
        ),
        source_proposal_operation_id="g000:strategy_proposal:fixture",
    )


def test_frozen_provider_preserves_ids_order_and_checksums_without_proposal_client() -> None:
    parser = _Parser()
    provider = FrozenCandidateSetProvider(strategy_parser=parser)

    baseline, candidates = provider.load(_frozen())

    assert baseline["value"] == 0
    assert [item[0] for item in candidates] == [f"candidate_{index:02d}" for index in range(4)]
    assert parser.calls == 5
    assert not hasattr(provider, "proposal_agent")


def test_frozen_provider_rejects_candidate_tampering() -> None:
    frozen = _frozen()
    tampered = frozen.to_dict()
    tampered["candidates"][0]["strategy"]["value"] = 99

    with pytest.raises(ValueError, match="frozen_candidate_checksum_mismatch"):
        FrozenCandidateSet.from_dict(tampered)


def test_production_executor_uses_phase5_candidate_root_names() -> None:
    assert ProductionGenerationExecutor.candidate_root_name("baseline") == "candidate_baseline"
    assert ProductionGenerationExecutor.candidate_root_name("candidate_00") == "candidate_00"


def test_production_executor_consumes_pause_after_candidate_boundary(
    tmp_path: Path,
) -> None:
    frozen = _frozen()
    frozen_path = tmp_path / "frozen.json"
    frozen_path.write_text(json.dumps(frozen.to_dict()), encoding="utf-8")
    evaluated: list[str] = []

    class Provider:
        def load(self, _frozen_set):
            return {"value": 0}, tuple(
                (f"candidate_{index:02d}", {"value": index + 1})
                for index in range(4)
            )

    def evaluate(**kwargs):
        evaluated.append(kwargs["candidate_id"])
        return {
            "candidate_id": kwargs["candidate_id"],
            "execution_success": True,
            "semantic_valid": True,
            "scoreable": True,
            "native_score": 0,
            "artifact_provenance": "test_fixture",
        }

    executor = ProductionGenerationExecutor(
        package=object(),
        candidate_evaluator=evaluate,
        phase7_adapter=object(),
        phase8_adapter=object(),
        champion_policy=object(),
        stop_policy=object(),
        frozen_provider=Provider(),
        artifact_provenance="test_fixture",
    )
    context = SimpleNamespace(
        preview=SimpleNamespace(
            generation_index=0,
            preview_revision=0,
            candidate_set_checksum=frozen.candidate_set_checksum,
            baseline_checksum=frozen.baseline_checksum,
            frozen_candidate_set_ref=str(frozen_path),
            strategy_diffs=(),
        ),
        spec=SimpleNamespace(campaign_id="campaign_fixture"),
        campaign_root=tmp_path,
        control_action=lambda: "pause" if evaluated else None,
    )

    result = executor.run(context)

    assert result.status == "paused"
    assert evaluated == ["baseline"]
    assert not (tmp_path / "generations" / "generation_000" / "phase6" / "leaderboard.json").exists()


def test_production_executor_preserves_completed_outcomes_when_approval_expires(
    tmp_path: Path,
) -> None:
    frozen = _frozen()
    frozen_path = tmp_path / "frozen.json"
    frozen_path.write_text(json.dumps(frozen.to_dict()), encoding="utf-8")
    evaluated: list[str] = []

    class Provider:
        def load(self, _frozen_set):
            return {"value": 0}, tuple(
                (f"candidate_{index:02d}", {"value": index + 1})
                for index in range(4)
            )

    def evaluate(**kwargs):
        candidate_id = kwargs["candidate_id"]
        evaluated.append(candidate_id)
        if candidate_id == "candidate_00":
            raise ValueError("generation_approval_expired")
        return {
            "candidate_id": candidate_id,
            "success": True,
            "final_state": "completed",
            "execution_success": True,
            "semantic_valid": True,
            "scoreable": True,
            "native_score": 0,
        }

    executor = ProductionGenerationExecutor(
        package=object(),
        candidate_evaluator=evaluate,
        phase7_adapter=object(),
        phase8_adapter=object(),
        champion_policy=object(),
        stop_policy=object(),
        frozen_provider=Provider(),
        artifact_provenance="test_fixture",
    )
    context = SimpleNamespace(
        preview=SimpleNamespace(
            generation_index=0,
            preview_revision=0,
            candidate_set_checksum=frozen.candidate_set_checksum,
            baseline_checksum=frozen.baseline_checksum,
            frozen_candidate_set_ref=str(frozen_path),
            strategy_diffs=(),
        ),
        spec=SimpleNamespace(campaign_id="campaign_fixture"),
        campaign_root=tmp_path,
        control_action=lambda: None,
    )

    result = executor.run(context)

    assert result.status == "awaiting_approval"
    assert evaluated == ["baseline", "candidate_00"]
    saved = json.loads(
        (tmp_path / "generations" / "generation_000" / "phase6" / "candidate_baseline" / "candidate_outcome.json").read_text(encoding="utf-8")
    )
    assert saved["candidate_id"] == "baseline"
    assert not (tmp_path / "generations" / "generation_000" / "phase6" / "leaderboard.json").exists()


def test_formal_executor_delegates_ranking_to_phase6_comparator(
    tmp_path: Path,
) -> None:
    captured = {}

    class Comparator:
        def compare(self, *, outcomes):
            captured["outcomes"] = tuple(outcomes)
            return ()

    package = SimpleNamespace(
        checksums={"scenario_definition_derived": "scenario-checksum"},
        native_score_compilation=SimpleNamespace(
            score_spec_checksum="score-spec-checksum",
            fragment_checksum="fragment-checksum",
            score_spec=SimpleNamespace(
                rules=(SimpleNamespace(score_side_id="red"),)
            ),
        ),
        runtime=SimpleNamespace(runtime_version="2.0.0"),
    )
    executor = ProductionGenerationExecutor(
        package=package,
        candidate_evaluator=object(),
        phase7_adapter=object(),
        phase8_adapter=object(),
        champion_policy=object(),
        stop_policy=object(),
        artifact_provenance="formal_renderer",
        candidate_comparator=Comparator(),
    )
    outcome = {
        "candidate_id": "baseline",
        "success": True,
        "executable": True,
        "execution_success": True,
        "semantic_valid": True,
        "scoreable": True,
        "native_score": -40,
        "score_source": "execution-summary.json#/official_score/final",
        "failure_reason": "completed",
        "final_state": "COMPLETED",
        "artifact_provenance": "formal_renderer",
        "scenario_reset": {"scenario_reset_verified": True},
    }

    assert executor._build_leaderboard(
        [outcome],
        tmp_path,
        {"baseline": {"strategy": "fixture"}},
    ) == []
    formal_outcome, identity, is_baseline = captured["outcomes"][0]
    assert formal_outcome.native_score == -40
    assert identity.score_spec_checksum == "score-spec-checksum"
    assert identity.score_fragment_checksum == "fragment-checksum"
    assert identity.scoring_side_id == "red"
    assert is_baseline is True
