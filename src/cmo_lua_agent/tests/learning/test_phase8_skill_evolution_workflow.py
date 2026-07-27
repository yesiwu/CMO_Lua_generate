from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from cmo_lua_agent.agents.skill_author_agent import (
    SkillAuthorContext,
    SkillDraftContent,
    SkillRevisionOperation,
    SkillRevisionProposal,
    SkillRule,
)
from cmo_lua_agent.learning.skill_evolution.assets import (
    SkillAssetStore,
    SkillPackageAssembler,
)
from cmo_lua_agent.learning.skill_evolution.config import SkillStorageConfig
from cmo_lua_agent.learning.skill_evolution.models import (
    PromotionAction,
    PromotionDecision,
)
from cmo_lua_agent.skill_evolution_errors import SkillEvolutionError
from cmo_lua_agent.learning.skill_evolution.regression import (
    SkillRegressionService,
)
from cmo_lua_agent.learning.skill_evolution.workflow import (
    SkillEvolutionWorkflow,
)
from cmo_lua_agent.learning.store import ExperienceRetriever, ExperienceStore
from cmo_lua_agent.learning.skill_evolution.active_loader import (
    ActiveSkillLoader,
    make_compatibility_cohort,
)
from cmo_lua_agent.learning.skill_evolution.aggregation import (
    ExperienceAggregator,
)
from cmo_lua_agent.learning.skill_evolution.catalog import ExperienceKeyCatalog

from .phase8_fixture_factory import Phase8ExperienceFixtureFactory


class _Author:
    def __init__(self) -> None:
        self.calls = 0

    def create(self, context: SkillAuthorContext) -> SkillDraftContent:
        self.calls += 1
        support = next(
            slot for slot in context.source_slots if "support" in slot
        )
        rule = SkillRule(
            "target_deconfliction.avoid_duplicate",
            "避免多个攻击单元无意重复选择同一首要目标",
            (support,),
        )
        return SkillDraftContent(
            "海空协同反舰策略模式",
            "面向 StrategySpec 的受控战术规划规则。",
            (rule,),
            (rule,),
            (rule,),
            (),
            (rule,),
        )

    def revise(self, context: SkillAuthorContext) -> object:
        raise AssertionError("fixture does not revise an active Skill")


class _RevisionAuthor(_Author):
    def revise(
        self, context: SkillAuthorContext
    ) -> SkillRevisionProposal:
        self.calls += 1
        support = next(
            slot for slot in context.source_slots if "support" in slot
        )
        return SkillRevisionProposal((
            SkillRevisionOperation(
                "add_strategy_pattern",
                rule=SkillRule(
                    "salvo_timing.coordinate_waves",
                    "协调现有攻击任务的时序以减少攻击波相互干扰",
                    (support,),
                ),
            ),
        ))


def _record(index: int) -> dict:
    optimization = f"opt-{index}"
    return {
        "experience_id": f"exp-{index}",
        "experience_key": "target_deconfliction",
        "experience_type": "tactical_positive",
        "evidence_stance": "support",
        "schema_version": "2",
        "source_optimization_id": optimization,
        "hypothesis": "舰机目标去冲突能够减少无意重复分配",
        "applicable_conditions": ["海空协同反舰"],
        "recommended_pattern": {"target_assignment": "deconflict"},
        "counter_conditions": [],
        "observed_effect": {
            "supporting_candidate_ids": [f"candidate_{index:02d}"],
            "score_delta_vs_baseline": 20,
        },
        "environment": {
            "mission_type": "naval_air_anti_surface",
            "scenario_id": f"scene-{index % 3}",
            "score_spec_version": "1.0.0",
            "score_spec_checksum": "score-rules",
            "runtime_version": "2.0.0",
            "renderer_version": "2.0.0",
            "scenario_schema_version": "1.0",
            "score_source": "execution_summary",
        },
        "evidence_refs": [
            f"runs/{optimization}/execution-summary.json"
        ],
        "evidence_quality": 0.9,
        "model_confidence": 0.8,
        "execution_success": True,
        "semantic_valid": True,
        "execution_fidelity": "verified",
    }


def _write_records(store: ExperienceStore, records: tuple[dict, ...]) -> None:
    store.records.mkdir(parents=True, exist_ok=True)
    for record in records:
        (store.records / f"{record['experience_id']}.json").write_text(
            json.dumps(record, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )


def _workflow(
    tmp_path: Path,
    author: _Author,
    regression_service: object | None = None,
) -> SkillEvolutionWorkflow:
    return SkillEvolutionWorkflow(
        author_agent=author,
        asset_store=SkillAssetStore(
            SkillStorageConfig.test(tmp_path / "data" / "skills")
        ),
        regression_service=regression_service
        or SkillRegressionService(proposal_validator=lambda _: True),
    )


def test_empty_real_store_finishes_without_llm_or_pending_skill(
    tmp_path: Path,
) -> None:
    store = ExperienceStore(tmp_path / "data" / "experiences")
    store.records.mkdir(parents=True)
    author = _Author()

    result = _workflow(tmp_path, author).run(
        phase8_run_id="phase8-empty",
        runs_root=tmp_path / "runs",
        experience_store=store,
    )

    assert result.status == "no_eligible_experience"
    assert author.calls == 0
    assert not (tmp_path / "data" / "skills" / "pending").exists()
    assert (
        tmp_path
        / "runs"
        / "phase8-empty"
        / "skill-evolution"
        / "phase8-result.json"
    ).is_file()


def test_fixture_creates_pending_once_and_resumes_idempotently(
    tmp_path: Path,
) -> None:
    store = ExperienceStore(tmp_path / "data" / "experiences")
    _write_records(store, tuple(_record(index) for index in range(1, 6)))
    author = _Author()
    workflow = _workflow(tmp_path, author)

    first = workflow.run(
        phase8_run_id="phase8-fixture",
        runs_root=tmp_path / "runs",
        experience_store=store,
    )
    second = workflow.run(
        phase8_run_id="phase8-fixture",
        runs_root=tmp_path / "runs",
        experience_store=store,
    )

    assert first.status == second.status == "pending_review"
    assert author.calls == 1
    assert len(first.pending_packages) == 1
    package = Path(first.pending_packages[0])
    assert package.is_dir()
    assert "data\\skills\\pending" in str(package)
    output = (
        tmp_path
        / "runs"
        / "phase8-fixture"
        / "skill-evolution"
    )
    expected = {
        "aggregation-manifest.json",
        "experience-aggregates.json",
        "validated-experiences.json",
        "promotion-decisions.json",
        "skill-author-response.json",
        "pending-skill-manifest.json",
        "skill-regression-report.json",
        "phase8-result.json",
    }
    assert expected <= {path.name for path in output.iterdir()}


def test_rerun_reuses_author_checkpoint_after_post_llm_failure(
    tmp_path: Path,
) -> None:
    class FailingRegression:
        def validate(self, *_: object, **__: object) -> object:
            raise RuntimeError("simulated post-LLM interruption")

    store = ExperienceStore(tmp_path / "data" / "experiences")
    _write_records(store, tuple(_record(index) for index in range(1, 6)))
    author = _Author()
    with pytest.raises(RuntimeError):
        _workflow(
            tmp_path,
            author,
            regression_service=FailingRegression(),
        ).run(
            phase8_run_id="phase8-resume",
            runs_root=tmp_path / "runs",
            experience_store=store,
        )

    checkpoint = (
        tmp_path
        / "runs"
        / "phase8-resume"
        / "skill-evolution"
        / "skill-author-response.json"
    )
    assert checkpoint.is_file()
    result = _workflow(tmp_path, author).run(
        phase8_run_id="phase8-resume",
        runs_root=tmp_path / "runs",
        experience_store=store,
    )

    assert result.status == "pending_review"
    assert author.calls == 1


def test_revision_preserves_active_rules_and_creates_minor_version(
    tmp_path: Path,
) -> None:
    store = ExperienceStore(tmp_path / "data" / "experiences")
    _write_records(store, tuple(_record(index) for index in range(1, 6)))
    author = _Author()
    first = _workflow(tmp_path, author).run(
        phase8_run_id="phase8-create",
        runs_root=tmp_path / "runs",
        experience_store=store,
    )
    asset_store = SkillAssetStore(
        SkillStorageConfig.test(tmp_path / "data" / "skills")
    )
    package = Path(first.pending_packages[0])
    metadata = json.loads(
        (package / "metadata.json").read_text(encoding="utf-8")
    )
    asset_store.approve(
        skill_id=metadata["skill_id"],
        cohort_id=metadata["compatibility_cohort"]["cohort_id"],
        version=metadata["version"],
        expected_checksum=metadata["package_checksum"],
        actor="reviewer",
        reason="fixture approval",
    )

    revised_store = ExperienceStore(
        tmp_path / "data" / "revision-experiences"
    )
    revision_records = []
    for index in range(11, 16):
        record = _record(index)
        record["experience_key"] = "salvo_timing"
        revision_records.append(record)
    _write_records(revised_store, tuple(revision_records))
    revision_author = _RevisionAuthor()
    second = _workflow(tmp_path, revision_author).run(
        phase8_run_id="phase8-revise",
        runs_root=tmp_path / "runs",
        experience_store=revised_store,
    )

    revised = Path(second.pending_packages[0])
    content = json.loads(
        (revised / "content.json").read_text(encoding="utf-8")
    )
    assert revised.name == "0.2.0"
    assert len(content["strategy_patterns"]) == 2
    assert revision_author.calls == 1


def test_same_run_id_with_different_input_is_a_conflict(
    tmp_path: Path,
) -> None:
    store = ExperienceStore(tmp_path / "data" / "experiences")
    _write_records(store, tuple(_record(index) for index in range(1, 6)))
    workflow = _workflow(tmp_path, _Author())
    workflow.run(
        phase8_run_id="phase8-conflict",
        runs_root=tmp_path / "runs",
        experience_store=store,
    )
    manifest = (
        tmp_path
        / "runs"
        / "phase8-conflict"
        / "skill-evolution"
        / "aggregation-manifest.json"
    )
    before = manifest.read_text(encoding="utf-8")
    changed = json.loads(
        (store.records / "exp-1.json").read_text(encoding="utf-8")
    )
    changed["evidence_quality"] = 0.8
    (store.records / "exp-1.json").write_text(
        json.dumps(changed, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )

    with pytest.raises(SkillEvolutionError) as captured:
        workflow.run(
            phase8_run_id="phase8-conflict",
            runs_root=tmp_path / "runs",
            experience_store=store,
        )
    assert captured.value.error_code == "phase8_input_conflict"

    assert manifest.read_text(encoding="utf-8") == before


def test_phase8_offline_entrypoint_exposes_no_cmo_execution() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/run_phase8_skill_evolution.py", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "experience" in completed.stdout.lower()
    assert "execute_cmo" not in completed.stdout


def test_isolated_promotable_fixture_runs_to_pending_review(
    tmp_path: Path,
) -> None:
    store = ExperienceStore(tmp_path / "fixture-store" / "experiences")
    records = Phase8ExperienceFixtureFactory.promotable_records()
    _write_records(store, records)

    assert len(records) == 6
    assert {record["evidence_stance"] for record in records} == {
        "support", "contradict"
    }
    assert sum(record["evidence_stance"] == "support" for record in records) == 5
    assert sum(record["evidence_stance"] == "contradict" for record in records) == 1
    assert {record["source_optimization_id"] for record in records} == {
        f"opt_fixture_{index:03d}" for index in range(1, 7)
    }
    assert len({record["environment"]["scenario_id"] for record in records}) == 3
    assert all(record["artifact_provenance"] == "test_fixture" for record in records)
    assert all(record["store_mode"] == "test" for record in records)
    assert all(record["scoreable"] for record in records)

    author = _Author()
    result = _workflow(tmp_path, author).run(
        phase8_run_id="phase8-promotable-fixture",
        runs_root=tmp_path / "runs",
        experience_store=store,
    )

    output = tmp_path / "runs" / "phase8-promotable-fixture" / "skill-evolution"
    aggregate = json.loads((output / "experience-aggregates.json").read_text(encoding="utf-8"))["aggregates"][0]
    validated = json.loads((output / "validated-experiences.json").read_text(encoding="utf-8"))[0]
    decision = json.loads((output / "promotion-decisions.json").read_text(encoding="utf-8"))[0]
    package = Path(result.pending_packages[0])
    report = json.loads((package / "regression-report.json").read_text(encoding="utf-8"))

    assert result.status == "pending_review"
    assert author.calls == 1
    assert aggregate["support_count"] == 5
    assert aggregate["contradict_count"] == 1
    assert aggregate["independent_optimization_count"] == 6
    assert aggregate["independent_scenario_count"] == 3
    assert validated["eligible"] is True
    assert decision["eligible"] is True
    assert decision["action"] == "create_pending_skill"
    assert all(report[field] is True for field in (
        "static_validation_passed",
        "traceability_validation_passed",
        "proposal_regression_passed",
    ))
    assert not (tmp_path / "data" / "skills" / "curated").exists()
    assert not (tmp_path / "data" / "skills" / "curated" / "current.json").exists()


def test_fixture_evidence_safety_cases_are_isolated_and_structured() -> None:
    aggregator = ExperienceAggregator(ExperienceKeyCatalog.default())
    records = list(Phase8ExperienceFixtureFactory.promotable_records())
    records.append(Phase8ExperienceFixtureFactory.duplicate_evidence())
    aggregate = aggregator.aggregate(records).aggregates[0]

    assert aggregate.independent_optimization_count == 6
    assert aggregate.support_count == 5

    cohort_result = aggregator.aggregate(
        [*Phase8ExperienceFixtureFactory.promotable_records(), Phase8ExperienceFixtureFactory.different_cohort()]
    )
    assert len(cohort_result.aggregates) == 2

    missing_stance = Phase8ExperienceFixtureFactory.record(index=8)
    del missing_stance["evidence_stance"]
    missing_result = aggregator.aggregate([missing_stance])
    assert missing_result.aggregates == ()
    assert missing_result.exclusions[0].error_code == "missing_or_invalid_evidence_stance"

    unscoreable = Phase8ExperienceFixtureFactory.record(index=9)
    unscoreable["scoreable"] = False
    unscoreable_result = aggregator.aggregate([unscoreable])
    assert unscoreable_result.aggregates == ()
    assert unscoreable_result.exclusions[0].error_code == "unscoreable_experience"


def test_semantic_invalid_fixture_is_ineligible_and_never_authored(
    tmp_path: Path,
) -> None:
    records = list(Phase8ExperienceFixtureFactory.promotable_records())
    records[0]["semantic_valid"] = False
    store = ExperienceStore(tmp_path / "fixture-store" / "experiences")
    _write_records(store, tuple(records))
    author = _Author()

    result = _workflow(tmp_path, author).run(
        phase8_run_id="phase8-semantic-invalid",
        runs_root=tmp_path / "runs",
        experience_store=store,
    )

    assert result.status == "no_eligible_experience"
    assert result.pending_packages == ()
    assert author.calls == 0


def test_fixture_pending_cannot_be_promoted_or_loaded_by_production(
    tmp_path: Path,
) -> None:
    fixture_store = ExperienceStore(tmp_path / "fixture-store" / "experiences")
    _write_records(fixture_store, Phase8ExperienceFixtureFactory.promotable_records())
    result = _workflow(tmp_path, _Author()).run(
        phase8_run_id="phase8-production-boundary",
        runs_root=tmp_path / "runs",
        experience_store=fixture_store,
    )
    package = Path(result.pending_packages[0])
    metadata = json.loads((package / "metadata.json").read_text(encoding="utf-8"))
    cohort_id = metadata["compatibility_cohort"]["cohort_id"]

    fake_project = tmp_path / "fake-production-project"
    production_config = SkillStorageConfig.production(fake_project)
    production_pending = (
        production_config.root / "pending" / metadata["skill_id"] / cohort_id / metadata["version"]
    )
    production_pending.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(package, production_pending)
    production_assets = SkillAssetStore(production_config)

    with pytest.raises(SkillEvolutionError) as captured:
        production_assets.approve(
            skill_id=metadata["skill_id"],
            cohort_id=cohort_id,
            version=metadata["version"],
            expected_checksum=metadata["package_checksum"],
            actor="test-reviewer",
            reason="must reject fixture provenance",
        )
    assert captured.value.error_code == "skill_provenance_mismatch"
    assert not (production_config.root / "curated").exists()

    cohort = make_compatibility_cohort(
        score_spec_version="1.0.0",
        score_spec_checksum="fixture-score-spec-v1",
        runtime_version="2.0.0",
        renderer_version="2.0.0",
    )
    assert ActiveSkillLoader(production_config.root).load(
        skill_id=metadata["skill_id"], cohort=cohort
    ) is None
    assert ExperienceRetriever(
        ExperienceStore(fake_project / "data" / "experiences")
    ).retrieve(
        current_optimization_id="new-optimization",
        environment=Phase8ExperienceFixtureFactory.record(index=1)["environment"],
        allowed_dimensions=("target_assignment",),
    ) == ((), (), ())


@pytest.mark.parametrize("tampered_file", ["SKILL.md", "regression-report.json"])
def test_fixture_package_tampering_and_checksum_conflict_are_rejected(
    tmp_path: Path,
    tampered_file: str,
) -> None:
    store = ExperienceStore(tmp_path / "fixture-store" / "experiences")
    _write_records(store, Phase8ExperienceFixtureFactory.promotable_records())
    result = _workflow(tmp_path, _Author()).run(
        phase8_run_id=f"phase8-tamper-{tampered_file}",
        runs_root=tmp_path / "runs",
        experience_store=store,
    )
    package = Path(result.pending_packages[0])
    metadata = json.loads((package / "metadata.json").read_text(encoding="utf-8"))
    asset_store = SkillAssetStore(SkillStorageConfig.test(tmp_path / "data" / "skills"))

    target = package / tampered_file
    if tampered_file == "regression-report.json":
        report = json.loads(target.read_text(encoding="utf-8"))
        report["proposal_regression_passed"] = False
        target.write_text(
            json.dumps(report, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
    else:
        target.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(SkillEvolutionError) as captured:
        asset_store.approve(
            skill_id=metadata["skill_id"],
            cohort_id=metadata["compatibility_cohort"]["cohort_id"],
            version=metadata["version"],
            expected_checksum=metadata["package_checksum"],
            actor="test-reviewer",
            reason="integrity check",
        )
    assert captured.value.error_code == "skill_package_checksum_mismatch"
    assert not (tmp_path / "data" / "skills" / "curated").exists()

    with pytest.raises(SkillEvolutionError) as conflict:
        asset_store.write_pending(package, {}, "different-draft-checksum")
    assert conflict.value.error_code == "pending_skill_conflict"


def test_ineligible_promotion_decision_is_rejected_with_error_code(
    tmp_path: Path,
) -> None:
    assembler = SkillPackageAssembler(
        SkillAssetStore(SkillStorageConfig.test(tmp_path / "data" / "skills"))
    )
    decision = PromotionDecision(
        decision_id="decision_fixture_ineligible",
        eligible=False,
        validated_experience_ids=(),
        family_id="cmo_naval_air_strategy_patterns",
        cohort_id="cohort_fixture",
        action=PromotionAction.CONTINUE_ACCUMULATING,
        target_version=None,
        reasons=("fixture_ineligible",),
        profile_id="naval_air_skill_promotion_v1",
        provenance="test_fixture",
        checksum="fixture-checksum",
    )
    content = SkillDraftContent("fixture", "fixture", (), (), (), (), ())

    with pytest.raises(SkillEvolutionError) as captured:
        assembler.assemble_pending(
            decision=decision,
            validated=(),
            content=content,
            evidence_records={},
        )
    assert captured.value.error_code == "promotion_decision_not_eligible"
