from __future__ import annotations

from dataclasses import replace

from cmo_lua_agent.learning.skill_evolution.aggregation import ExperienceAggregator
from cmo_lua_agent.learning.skill_evolution.catalog import ExperienceKeyCatalog
from cmo_lua_agent.learning.skill_evolution.models import PromotionAction
from cmo_lua_agent.learning.skill_evolution.promotion import (
    PromotionProfile,
    SkillVersionPolicy,
    SkillPromotionPolicy,
)
from cmo_lua_agent.learning.skill_evolution.validation import (
    ExperienceValidationService,
)


def _record(
    optimization: str,
    scenario: str,
    *,
    record_id: str | None = None,
    key: str = "target_deconfliction",
    kind: str = "tactical_positive",
    stance: str | None = "support",
    candidate_ids: tuple[str, ...] = ("candidate_00",),
    quality: float = 0.9,
) -> dict:
    value = {
        "experience_id": record_id or f"exp_{optimization}_{candidate_ids[0]}",
        "experience_key": key,
        "experience_type": kind,
        "source_optimization_id": optimization,
        "hypothesis": "舰机目标去冲突能够减少无意的重复目标分配",
        "applicable_conditions": ["海空协同反舰"],
        "recommended_pattern": {"target_assignment": "deconflict"},
        "counter_conditions": [],
        "observed_effect": {
            "supporting_candidate_ids": list(candidate_ids),
            "score_delta_vs_baseline": 20,
        },
        "environment": {
            "mission_type": "naval_air_anti_surface",
            "scenario_id": scenario,
            "score_spec_version": "1.2.0",
            "score_spec_checksum": "score-rules",
            "runtime_version": "2.1.0",
            "renderer_version": "3.0.0",
            "scenario_schema_version": "1.0",
            "score_source": "execution_summary",
        },
        "evidence_refs": [f"runs/{optimization}/execution-summary.json"],
        "evidence_quality": quality,
        "model_confidence": 0.8,
        "execution_success": True,
        "semantic_valid": True,
        "execution_fidelity": "verified",
    }
    if stance is not None:
        value["evidence_stance"] = stance
    return value


def test_catalog_normalizes_only_controlled_keys() -> None:
    catalog = ExperienceKeyCatalog.default()
    assert catalog.normalize("target_deconfliction") == (
        "naval_air_anti_surface.target_deconfliction"
    )
    assert catalog.normalize("free_form_idea") == "unclassified"
    assert catalog.definition(
        "naval_air_anti_surface.target_deconfliction"
    ).family == "cmo_naval_air_strategy_patterns"


def test_aggregator_deduplicates_one_optimization_and_uses_stance() -> None:
    records = (
        _record("opt-1", "scene-a", candidate_ids=("candidate_00",)),
        _record(
            "opt-1",
            "scene-a",
            record_id="exp_opt-1_candidate_01",
            candidate_ids=("candidate_01",),
        ),
        _record("opt-2", "scene-b", stance="qualify"),
        _record("opt-3", "scene-c", stance="contradict"),
    )
    aggregate = ExperienceAggregator(
        ExperienceKeyCatalog.default()
    ).aggregate(records).aggregates[0]

    assert aggregate.support_count == 1
    assert aggregate.qualify_count == 1
    assert aggregate.contradict_count == 1
    assert aggregate.independent_optimization_count == 3
    assert aggregate.independent_scenario_count == 3
    assert aggregate.supporting_evidence[0].supporting_candidates == (
        "candidate_00",
        "candidate_01",
    )
    assert aggregate.contradiction_ratio == 0.5


def test_conflicting_stances_in_one_optimization_use_conservative_precedence() -> None:
    records = (
        _record("opt-1", "scene-a", stance="support"),
        _record(
            "opt-1",
            "scene-a",
            record_id="exp_opt-1-b",
            stance="contradict",
        ),
    )
    aggregate = ExperienceAggregator(
        ExperienceKeyCatalog.default()
    ).aggregate(records).aggregates[0]

    assert aggregate.support_count == 0
    assert aggregate.contradict_count == 1
    assert aggregate.stance_conflicts == ("opt-1",)


def test_validation_and_promotion_require_independent_evidence() -> None:
    records = tuple(
        _record(f"opt-{index}", f"scene-{index % 3}")
        for index in range(1, 6)
    )
    aggregate = ExperienceAggregator(
        ExperienceKeyCatalog.default()
    ).aggregate(records).aggregates[0]
    validated = ExperienceValidationService(
        PromotionProfile.default()
    ).validate(aggregate)
    decision = SkillPromotionPolicy(PromotionProfile.default()).decide(
        validated,
        active_version=None,
    )

    assert validated.eligible
    assert decision.action is PromotionAction.CREATE_PENDING_SKILL
    assert decision.eligible is True
    assert decision.provenance == "production"
    assert decision.target_version == "0.1.0"


def test_validation_rejects_non_official_score_source() -> None:
    record = _record("opt-1", "scene-a")
    record["environment"]["score_source"] = "legacy_csv"
    aggregate = ExperienceAggregator(
        ExperienceKeyCatalog.default()
    ).aggregate((record,)).aggregates[0]
    validated = ExperienceValidationService(
        PromotionProfile.default()
    ).validate(aggregate)

    assert not validated.eligible
    assert "untrusted_score_source" in validated.validation_reasons


def test_policy_accumulates_when_threshold_is_not_met() -> None:
    aggregate = ExperienceAggregator(
        ExperienceKeyCatalog.default()
    ).aggregate((_record("opt-1", "scene-a"),)).aggregates[0]
    validated = ExperienceValidationService(
        PromotionProfile.default()
    ).validate(aggregate)
    decision = SkillPromotionPolicy(PromotionProfile.default()).decide(
        validated,
        active_version=None,
    )

    assert decision.action is PromotionAction.CONTINUE_ACCUMULATING
    assert decision.target_version is None


def test_existing_skill_revision_increments_minor_version() -> None:
    records = tuple(
        _record(f"opt-{index}", f"scene-{index % 3}")
        for index in range(1, 6)
    )
    aggregate = ExperienceAggregator(
        ExperienceKeyCatalog.default()
    ).aggregate(records).aggregates[0]
    validated = ExperienceValidationService(
        PromotionProfile.default()
    ).validate(aggregate)
    decision = SkillPromotionPolicy(PromotionProfile.default()).decide(
        validated,
        active_version="0.3.2",
    )

    assert decision.action is PromotionAction.REVISE_EXISTING_SKILL
    assert decision.target_version == "0.4.0"


def test_severe_contradiction_requires_review() -> None:
    records = tuple(
        _record(f"opt-{index}", f"scene-{index % 3}")
        for index in range(1, 6)
    ) + (
        _record("opt-6", "scene-4", stance="contradict"),
        _record("opt-7", "scene-5", stance="contradict"),
    )
    aggregate = ExperienceAggregator(
        ExperienceKeyCatalog.default()
    ).aggregate(records).aggregates[0]
    validated = ExperienceValidationService(
        PromotionProfile.default()
    ).validate(aggregate)
    decision = SkillPromotionPolicy(PromotionProfile.default()).decide(
        validated,
        active_version="0.1.0",
    )

    assert not validated.eligible
    assert decision.action is PromotionAction.REQUIRE_REVIEW


def test_missing_stance_is_excluded_without_type_inference() -> None:
    result = ExperienceAggregator(
        ExperienceKeyCatalog.default()
    ).aggregate((_record("opt-1", "scene-a", stance=None),))

    assert result.aggregates == ()
    assert result.exclusions[0].error_code == (
        "missing_or_invalid_evidence_stance"
    )


def test_version_policy_reserves_patch_and_major_for_human_requests() -> None:
    versions = SkillVersionPolicy()

    assert versions.automatic(None) == "0.1.0"
    assert versions.automatic("0.1.4") == "0.2.0"
    assert versions.manual(
        current_version="0.2.0",
        target_version="0.2.1",
        change_kind="patch",
    ) == "0.2.1"
    assert versions.manual(
        current_version="0.2.1",
        target_version="1.0.0",
        change_kind="major",
    ) == "1.0.0"
