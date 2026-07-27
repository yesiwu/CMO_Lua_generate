from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from cmo_lua_agent.agents.skill_author_agent import (
    SkillDraftContent,
    SkillRule,
)
from cmo_lua_agent.learning.skill_evolution.assets import (
    compute_skill_package_checksum,
    SkillAssetStore,
    SkillPackageAssembler,
)
from cmo_lua_agent.learning.skill_evolution.config import (
    SkillStorageConfig,
    SkillStoreMode,
)
from cmo_lua_agent.learning.skill_evolution.models import (
    CompatibilityCohort,
    PromotionDecision,
    ValidatedExperience,
)
from cmo_lua_agent.learning.skill_evolution.regression import (
    SkillRegressionService,
)
from cmo_lua_agent.learning.skill_evolution.promotion import (
    PromotionProfile,
    SkillPromotionPolicy,
)
from cmo_lua_agent.skill_evolution_errors import SkillEvolutionError
from cmo_lua_agent.learning.skill_evolution.cli import main as skill_cli_main


def _validated() -> ValidatedExperience:
    cohort = CompatibilityCohort(
        "cohort_abc",
        1,
        "score",
        2,
        3,
        "1.0",
        "execution_summary",
    )
    return ValidatedExperience(
        validation_id="validated_1",
        aggregate_id="aggregate_1",
        experience_key="naval_air_anti_surface.target_deconfliction",
        mission_type="naval_air_anti_surface",
        family="cmo_naval_air_strategy_patterns",
        canonical_hypothesis="避免重复目标分配",
        compatibility_cohort=cohort,
        eligible=True,
        validation_status="eligible",
        validation_reasons=(),
        deterministic_confidence=0.9,
        supporting_slots=("support_01",),
        contradicting_slots=(),
        qualifying_slots=("qualify_01",),
        evidence_slot_map={
            "support_01": ("exp-1",),
            "qualify_01": ("exp-2",),
        },
        aggregate_checksum="aggregate-checksum",
        checksum="validated-checksum",
    )


def _decision() -> PromotionDecision:
    return SkillPromotionPolicy(PromotionProfile.default()).decide(
        _validated(),
        active_version=None,
        provenance="test_fixture",
    )


def _store(tmp_path: Path) -> SkillAssetStore:
    return SkillAssetStore(
        SkillStorageConfig.test(tmp_path / "data" / "skills")
    )


def _finalized_package(tmp_path: Path):
    store = _store(tmp_path)
    package = SkillPackageAssembler(store).assemble_pending(
        decision=_decision(),
        validated=(_validated(),),
        content=_draft(),
        evidence_records=_evidence(),
    )
    report = SkillRegressionService(
        proposal_validator=lambda _: True
    ).validate(package, evidence_records=_evidence())
    return store, store.save_regression_report(package, report)


def _reseal(path: Path) -> str:
    metadata_path = path / "metadata.json"
    report_path = path / "regression-report.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    metadata["package_checksum"] = "<skill-package-checksum>"
    report["package_checksum"] = "<skill-package-checksum>"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    report_path.write_text(json.dumps(report), encoding="utf-8")
    checksum = compute_skill_package_checksum(path)
    metadata["package_checksum"] = checksum
    report["package_checksum"] = checksum
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    report_path.write_text(json.dumps(report), encoding="utf-8")
    return checksum


def _draft() -> SkillDraftContent:
    support = SkillRule(
        "target_deconfliction.avoid_duplicate",
        "避免多个攻击单元无意重复选择同一首要目标",
        ("support_01",),
    )
    qualify = SkillRule(
        "target_deconfliction.priority_exception",
        "仅存在单个首要目标时允许集中火力",
        ("qualify_01",),
    )
    return SkillDraftContent(
        title="海空协同反舰策略模式",
        description="面向 StrategySpec 的受控战术规划规则。",
        when_to_use=(support,),
        strategy_patterns=(support,),
        conditions=(support,),
        counterexamples=(qualify,),
        verification_rules=(support,),
    )


def _evidence() -> dict[str, dict]:
    return {
        "exp-1": {
            "experience_id": "exp-1",
            "evidence_refs": ["runs/opt-1/execution-summary.json"],
        },
        "exp-2": {
            "experience_id": "exp-2",
            "evidence_refs": ["runs/opt-2/execution-summary.json"],
        },
    }


def test_assembler_writes_only_to_data_skills_and_regression_is_explicit(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    package = SkillPackageAssembler(store).assemble_pending(
        decision=_decision(),
        validated=(_validated(),),
        content=_draft(),
        evidence_records=_evidence(),
    )
    report = SkillRegressionService(
        proposal_validator=lambda _: True
    ).validate(package, evidence_records=_evidence())
    package = store.save_regression_report(package, report)
    current = (
        store.root
        / "curated"
        / package.skill_id
        / package.cohort_id
        / "current.json"
    )
    assert not current.exists()

    expected = (
        tmp_path
        / "data"
        / "skills"
        / "pending"
        / "cmo_naval_air_strategy_patterns"
        / "cohort_abc"
        / "0.1.0"
    )
    assert package.path == expected
    assert (expected / "SKILL.md").is_file()
    assert (expected / "content.json").is_file()
    assert (expected / "references" / "validated-experiences.md").is_file()
    assert report.static_validation_passed
    assert report.traceability_validation_passed
    assert report.proposal_regression_passed
    assert report.cmo_effectiveness_validation == "not_run"
    assert not (tmp_path / "src").exists()


def test_approval_requires_checksum_actor_reason_and_is_cohort_scoped(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    package = SkillPackageAssembler(store).assemble_pending(
        decision=_decision(),
        validated=(_validated(),),
        content=_draft(),
        evidence_records=_evidence(),
    )
    report = SkillRegressionService(
        proposal_validator=lambda _: True
    ).validate(package, evidence_records=_evidence())
    package = store.save_regression_report(package, report)
    current = (
        store.root
        / "curated"
        / package.skill_id
        / package.cohort_id
        / "current.json"
    )
    assert not current.exists()

    with pytest.raises(SkillEvolutionError) as captured:
        store.approve(
            skill_id=package.skill_id,
            cohort_id=package.cohort_id,
            version=package.version,
            expected_checksum="wrong",
            actor="tester",
            reason="reviewed",
        )
    assert captured.value.error_code == "skill_package_checksum_mismatch"

    approval = store.approve(
        skill_id=package.skill_id,
        cohort_id=package.cohort_id,
        version=package.version,
        expected_checksum=package.checksum,
        actor="tester",
        reason="reviewed",
    )
    assert current.is_file()
    assert json.loads(current.read_text(encoding="utf-8"))["version"] == "0.1.0"
    assert approval["actor"] == "tester"
    assert package.path.is_dir()
    assert {row["event_type"] for row in store.ledger_rows()} == {
        "approved",
        "pending_created",
        "regression_completed",
    }


def test_reject_preserves_active_version_and_records_reason(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    package = SkillPackageAssembler(store).assemble_pending(
        decision=_decision(),
        validated=(_validated(),),
        content=_draft(),
        evidence_records=_evidence(),
    )
    report = SkillRegressionService(
        proposal_validator=lambda _: True
    ).validate(package, evidence_records=_evidence())
    package = store.save_regression_report(package, report)
    result = store.reject(
        skill_id=package.skill_id,
        cohort_id=package.cohort_id,
        version=package.version,
        expected_checksum=package.checksum,
        actor="reviewer",
        reason="insufficient wording quality",
    )
    replay = store.reject(
        skill_id=package.skill_id,
        cohort_id=package.cohort_id,
        version=package.version,
        expected_checksum=package.checksum,
        actor="reviewer",
        reason="insufficient wording quality",
    )

    rejected = (
        store.root
        / "rejected"
        / package.skill_id
        / package.cohort_id
        / package.version
    )
    assert rejected.is_dir()
    assert not package.path.exists()
    assert result["reason"] == "insufficient wording quality"
    assert replay == result
    assert not (
        store.root
        / "curated"
        / package.skill_id
        / package.cohort_id
        / "current.json"
    ).exists()


def test_approval_is_idempotent_and_ledger_has_no_duplicates(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    package = SkillPackageAssembler(store).assemble_pending(
        decision=_decision(),
        validated=(_validated(),),
        content=_draft(),
        evidence_records=_evidence(),
    )
    report = SkillRegressionService(
        proposal_validator=lambda _: True
    ).validate(package, evidence_records=_evidence())
    package = store.save_regression_report(package, report)
    kwargs = {
        "skill_id": package.skill_id,
        "cohort_id": package.cohort_id,
        "version": package.version,
        "expected_checksum": package.checksum,
        "actor": "tester",
        "reason": "reviewed",
    }

    store.approve(**kwargs)
    store.approve(**kwargs)

    assert len(store.ledger_rows()) == 3
    assert len(
        (
            store.root / "indexes" / "curated.jsonl"
        ).read_text(encoding="utf-8").splitlines()
    ) == 1


def test_cli_requires_explicit_approval_identity_and_checksum(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    package = SkillPackageAssembler(store).assemble_pending(
        decision=_decision(),
        validated=(_validated(),),
        content=_draft(),
        evidence_records=_evidence(),
    )
    report = SkillRegressionService(
        proposal_validator=lambda _: True
    ).validate(package, evidence_records=_evidence())
    package = store.save_regression_report(package, report)

    exit_code = skill_cli_main(
        [
            "approve",
            "--skill-id",
            package.skill_id,
            "--cohort-id",
            package.cohort_id,
            "--version",
            package.version,
            "--expected-checksum",
            package.checksum,
            "--actor",
            "operator",
            "--reason",
            "manual review passed",
        ],
        store=store,
    )

    assert exit_code == 0


@pytest.mark.parametrize(
    "relative_path",
    (
        "SKILL.md",
        "content.json",
        "evidence-manifest.json",
        "promotion-decision.json",
        "regression-cases.json",
        "regression-report.json",
        "metadata.json",
        "references/validated-experiences.md",
    ),
)
def test_any_protected_file_tamper_blocks_approval(
    tmp_path: Path,
    relative_path: str,
) -> None:
    store, package = _finalized_package(tmp_path)
    path = package.path / relative_path
    if path.suffix == ".json":
        value = json.loads(path.read_text(encoding="utf-8"))
        value["tampered"] = True
        path.write_text(json.dumps(value), encoding="utf-8")
    else:
        path.write_text(
            path.read_text(encoding="utf-8") + "\ntampered\n",
            encoding="utf-8",
        )

    with pytest.raises(SkillEvolutionError):
        store.approve(
            skill_id=package.skill_id,
            cohort_id=package.cohort_id,
            version=package.version,
            expected_checksum=package.checksum,
            actor="reviewer",
            reason="reviewed",
        )


def test_approve_rejects_resealed_ineligible_decision(
    tmp_path: Path,
) -> None:
    store, package = _finalized_package(tmp_path)
    decision_path = package.path / "promotion-decision.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["eligible"] = False
    body = {
        key: decision[key]
        for key in (
            "eligible",
            "validated_experience_ids",
            "family_id",
            "cohort_id",
            "action",
            "target_version",
            "reasons",
            "profile_id",
            "provenance",
        )
    }
    from cmo_lua_agent.learning.skill_evolution.aggregation import (
        canonical_sha256,
    )

    decision["checksum"] = canonical_sha256(body)
    decision["decision_id"] = f"decision_{decision['checksum'][:20]}"
    decision_path.write_text(json.dumps(decision), encoding="utf-8")
    expected = _reseal(package.path)

    with pytest.raises(SkillEvolutionError) as captured:
        store.approve(
            skill_id=package.skill_id,
            cohort_id=package.cohort_id,
            version=package.version,
            expected_checksum=expected,
            actor="reviewer",
            reason="reviewed",
        )
    assert captured.value.error_code == "promotion_decision_not_eligible"


def test_production_store_rejects_test_fixture_package(
    tmp_path: Path,
) -> None:
    _, package = _finalized_package(tmp_path / "fixture")
    project_root = tmp_path / "production-project"
    production = SkillAssetStore(
        SkillStorageConfig.production(project_root)
    )
    destination = (
        production.root
        / "pending"
        / package.skill_id
        / package.cohort_id
        / package.version
    )
    destination.parent.mkdir(parents=True)
    shutil.copytree(package.path, destination)

    with pytest.raises(SkillEvolutionError) as captured:
        production.approve(
            skill_id=package.skill_id,
            cohort_id=package.cohort_id,
            version=package.version,
            expected_checksum=package.checksum,
            actor="reviewer",
            reason="reviewed",
        )
    assert captured.value.error_code == "skill_provenance_mismatch"


def test_regression_report_must_bind_actual_package(
    tmp_path: Path,
) -> None:
    store, package = _finalized_package(tmp_path)
    report_path = package.path / "regression-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["package_checksum"] = "wrong"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(SkillEvolutionError) as captured:
        store.approve(
            skill_id=package.skill_id,
            cohort_id=package.cohort_id,
            version=package.version,
            expected_checksum=package.checksum,
            actor="reviewer",
            reason="reviewed",
        )
    assert captured.value.error_code == "skill_package_checksum_mismatch"


def test_production_store_rejects_noncanonical_root(
    tmp_path: Path,
) -> None:
    config = SkillStorageConfig(
        project_root=tmp_path,
        root=tmp_path / "runs" / "skills",
        mode=SkillStoreMode.PRODUCTION,
    )

    with pytest.raises(SkillEvolutionError) as captured:
        SkillAssetStore(config)

    assert captured.value.error_code == "production_skill_root_invalid"


def test_test_store_cannot_target_real_project_data_skills() -> None:
    project_root = Path(__file__).resolve().parents[4]
    config = SkillStorageConfig.test(
        project_root / "data" / "skills"
    )

    with pytest.raises(SkillEvolutionError) as captured:
        SkillAssetStore(config)

    assert captured.value.error_code == "test_store_targets_production"
