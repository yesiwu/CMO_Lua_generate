from __future__ import annotations

import json
from pathlib import Path

import pytest

from cmo_lua_agent.learning.skill_evolution.active_loader import (
    ActiveSkillSnapshot,
    ActiveSkillLoader,
)
from cmo_lua_agent.learning.skill_evolution.aggregation import canonical_sha256
from cmo_lua_agent.learning.skill_evolution.assets import (
    compute_skill_package_checksum,
)
from cmo_lua_agent.contract.strategy_models import BaselineStrategy
from cmo_lua_agent.generation.runtime_models import LuaRuntimeProfile
from cmo_lua_agent.optimization.optimization_generation_workflow import (
    OptimizationGenerationWorkflow,
)
from cmo_lua_agent.learning.skill_evolution.models import CompatibilityCohort
from cmo_lua_agent.optimization.phase6_models import (
    BootstrapSkillSnapshot,
    PlanningRequest,
    StrategyProposalContext,
)
from cmo_lua_agent.optimization.strategy_proposal_agent import (
    StrategyProposalAgent,
)
from cmo_lua_agent.tests.optimization.test_phase6_optimization import (
    _Client,
    _Evaluator,
    _scenario,
    _score,
    _strategy,
)
from cmo_lua_agent.skill_evolution_errors import SkillEvolutionError


def _cohort(value: str = "cohort-a") -> CompatibilityCohort:
    return CompatibilityCohort(
        value, 1, "score", 2, 2, "1.0", "execution_summary"
    )


def _write_curated(root: Path, cohort: CompatibilityCohort) -> None:
    base = (
        root
        / "curated"
        / "cmo_naval_air_strategy_patterns"
        / cohort.cohort_id
    )
    version = base / "versions" / "0.1.0"
    version.mkdir(parents=True)
    (version / "SKILL.md").write_text(
        "# Curated\n\nUse target deconfliction.\n", encoding="utf-8"
    )
    (version / "content.json").write_text(
        json.dumps({
            "title": "Curated",
            "description": "Rules",
            "when_to_use": [],
            "strategy_patterns": [],
            "conditions": [],
            "counterexamples": [],
            "verification_rules": [],
        }),
        encoding="utf-8",
    )
    decision_body = {
        "eligible": True,
        "validated_experience_ids": ["validated-1"],
        "family_id": "cmo_naval_air_strategy_patterns",
        "cohort_id": cohort.cohort_id,
        "action": "create_pending_skill",
        "target_version": "0.1.0",
        "reasons": [],
        "profile_id": "naval_air_skill_promotion_v1",
        "provenance": "test_fixture",
    }
    decision_checksum = canonical_sha256(decision_body)
    decision = {
        "decision_id": f"decision_{decision_checksum[:20]}",
        **decision_body,
        "checksum": decision_checksum,
    }
    (version / "promotion-decision.json").write_text(
        json.dumps(decision), encoding="utf-8"
    )
    for name, value in (
        ("evidence-manifest.json", {"source_slots": {}}),
        ("regression-cases.json", {"schema_version": "1"}),
        (
            "regression-report.json",
            {
                "static_validation_passed": True,
                "traceability_validation_passed": True,
                "proposal_regression_passed": True,
                "cmo_effectiveness_validation": "not_run",
                "failures": [],
                "package_checksum": "<skill-package-checksum>",
            },
        ),
    ):
        (version / name).write_text(json.dumps(value), encoding="utf-8")
    (version / "references").mkdir()
    (version / "references" / "validated-experiences.md").write_text(
        "# References\n", encoding="utf-8"
    )
    metadata = {
        "schema_version": "2",
        "skill_id": "cmo_naval_air_strategy_patterns",
        "version": "0.1.0",
        "status": "curated",
        "family_id": "cmo_naval_air_strategy_patterns",
        "consumer": "StrategyProposalAgent",
        "mission_type": "naval_air_anti_surface",
        "compatibility_cohort": cohort.to_dict(),
        "decision_id": decision["decision_id"],
        "validated_experience_ids": ["validated-1"],
        "applicable_experience_keys": [
            "naval_air_anti_surface.target_deconfliction"
        ],
        "provenance": "test_fixture",
        "draft_checksum": "draft",
        "package_checksum": "<skill-package-checksum>",
    }
    (version / "metadata.json").write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )
    checksum = compute_skill_package_checksum(version)
    metadata["package_checksum"] = checksum
    (version / "metadata.json").write_text(
        json.dumps(metadata), encoding="utf-8"
    )
    report = json.loads(
        (version / "regression-report.json").read_text(encoding="utf-8")
    )
    report["package_checksum"] = checksum
    (version / "regression-report.json").write_text(
        json.dumps(report), encoding="utf-8"
    )
    (base / "current.json").write_text(
        json.dumps({
            "skill_id": "cmo_naval_air_strategy_patterns",
            "cohort_id": cohort.cohort_id,
            "version": "0.1.0",
            "package_checksum": checksum,
            "relative_path": "versions/0.1.0",
        }),
        encoding="utf-8",
    )


def test_loader_selects_only_exact_compatibility_cohort(
    tmp_path: Path,
) -> None:
    _write_curated(tmp_path, _cohort())
    loader = ActiveSkillLoader(
        tmp_path,
        expected_provenance="test_fixture",
    )

    active = loader.load(
        skill_id="cmo_naval_air_strategy_patterns",
        cohort=_cohort(),
    )
    missing = loader.load(
        skill_id="cmo_naval_air_strategy_patterns",
        cohort=_cohort("cohort-b"),
    )

    assert active is not None
    assert active.version == "0.1.0"
    assert active.covered_experience_keys == (
        "naval_air_anti_surface.target_deconfliction",
    )
    filtered = active.filter_experience_cards((
        {
            "experience_key": "naval_air_anti_surface.target_deconfliction",
            "experience_type": "tactical_positive",
        },
        {
            "experience_key": "naval_air_anti_surface.target_deconfliction",
            "experience_type": "counterexample",
        },
        {
            "experience_key": "naval_air_anti_surface.salvo_timing",
            "experience_type": "tactical_positive",
        },
    ))
    assert [item["experience_type"] for item in filtered] == [
        "counterexample",
        "tactical_positive",
    ]
    assert missing is None


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
def test_loader_rejects_tampered_protected_file(
    tmp_path: Path,
    relative_path: str,
) -> None:
    cohort = _cohort()
    _write_curated(tmp_path, cohort)
    version = (
        tmp_path
        / "curated"
        / "cmo_naval_air_strategy_patterns"
        / cohort.cohort_id
        / "versions"
        / "0.1.0"
    )
    target = version / relative_path
    if target.suffix == ".json":
        value = json.loads(target.read_text(encoding="utf-8"))
        value["tampered"] = True
        target.write_text(json.dumps(value), encoding="utf-8")
    else:
        target.write_text(
            target.read_text(encoding="utf-8") + "\ntampered\n",
            encoding="utf-8",
        )

    with pytest.raises(SkillEvolutionError):
        ActiveSkillLoader(
            tmp_path,
            expected_provenance="test_fixture",
        ).load(
            skill_id="cmo_naval_air_strategy_patterns",
            cohort=cohort,
        )


def test_strategy_context_adds_active_skill_only_when_present() -> None:
    bootstrap = BootstrapSkillSnapshot(
        "bootstrap",
        "1",
        "bootstrap",
        "human-authored",
        "none",
        ("StrategyProposalAgent",),
        "bootstrap.md",
        "body",
        "checksum",
    )
    base = StrategyProposalContext(
        _scenario(),
        _strategy(),
        "objective",
        ("/attacks/0/fire_quantity",),
        ("fire_quantity",),
        "runtime",
        "v",
        bootstrap,
    )
    assert "active_curated_skill" not in base.to_prompt_dict()

    active_context = StrategyProposalContext(
        _scenario(),
        _strategy(),
        "objective",
        ("/attacks/0/fire_quantity",),
        ("fire_quantity",),
        "runtime",
        "v",
        bootstrap,
        active_curated_skill={
            "skill_id": "cmo_naval_air_strategy_patterns",
            "version": "0.1.0",
            "content": "# Curated",
        },
    )
    assert active_context.to_prompt_dict()["active_curated_skill"][
        "version"
    ] == "0.1.0"


def test_optimization_workflow_loads_matching_active_skill(
    tmp_path: Path,
) -> None:
    class CaptureClient(_Client):
        prompt: dict | None = None

        def complete_json(self, **kwargs: object) -> object:
            self.prompt = json.loads(str(kwargs["prompt"]))
            return super().complete_json(**kwargs)

    class Loader:
        def load(self, **_: object) -> ActiveSkillSnapshot:
            return ActiveSkillSnapshot(
                "cmo_naval_air_strategy_patterns",
                "cohort",
                "0.1.0",
                "checksum",
                "# Curated",
                {},
                (),
                {},
                {},
            )

    client = CaptureClient()
    scenario = _scenario()
    request = PlanningRequest(
        "generation",
        scenario,
        BaselineStrategy(_strategy(), "baseline.lua", True),
        "objective",
        (
            "/attacks/0/fire_quantity",
            "/attacks/0/delay_seconds",
        ),
        ("fire_quantity", "attack_timing"),
        LuaRuntimeProfile("runtime", "2.0.0"),
        _score(scenario),
        10,
        tmp_path / "generation",
    )
    workflow = OptimizationGenerationWorkflow(
        project_root=Path(__file__).resolve().parents[4],
        proposal_agent=StrategyProposalAgent(client),
        candidate_evaluator=_Evaluator(),
        active_skill_loader=Loader(),
    )

    result = workflow.run(request)

    assert result.workflow_completed
    assert client.prompt is not None
    assert client.prompt["active_curated_skill"]["version"] == "0.1.0"
