from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from cmo_lua_agent.contract.baseline_strategy_builder import BaselineStrategyBuilder
from cmo_lua_agent.optimization.candidate_quality import (
    CandidateBatchQualityError,
    CandidateQualityEvaluator,
)
from cmo_lua_agent.evolution.novelty import CandidateNoveltyValidator
from cmo_lua_agent.evolution.production_preview_builder import ProductionPreviewBuilder
from cmo_lua_agent.optimization.phase6_models import StrategyCandidate
from cmo_lua_agent.optimization.proposal_context_builder import (
    ProposalTacticalContextBuilder,
)
from cmo_lua_agent.optimization.proposal_models import (
    CandidatePatch,
    StrategyPatchOperation,
    candidate_role_specs,
)
from cmo_lua_agent.optimization.strategy_patch import (
    StrategyPatchAssembler,
    build_patchable_leaf_catalog,
)


PROJECT_ROOT = Path(__file__).resolve().parents[4]
PATHS = (
    "/attacks/0/target_ids/0", "/attacks/0/delay_seconds", "/attacks/0/fire_quantity",
    "/attacks/1/target_ids/0", "/attacks/1/delay_seconds", "/attacks/1/fire_quantity",
    "/attacks/2/target_ids/0", "/attacks/2/delay_seconds", "/attacks/2/fire_quantity",
    "/sorties/0/route/0/latitude", "/sorties/0/route/0/longitude",
    "/sorties/1/route/0/latitude", "/sorties/1/route/0/longitude", "/sorties/1/target_id",
)


def _inputs():
    scenario_ir = json.loads((PROJECT_ROOT / "json_data" / "6v4ScenarioIR.json").read_text(encoding="utf-8"))
    derived = BaselineStrategyBuilder().build(scenario_ir)
    catalog = build_patchable_leaf_catalog(
        baseline=derived.strategy, scenario=derived.scenario, allowed_paths=PATHS
    )
    tactical = ProposalTacticalContextBuilder().build(
        scenario=derived.scenario,
        baseline=derived.strategy,
        patch_catalog=catalog,
        role_specs=candidate_role_specs({}),
        accepted_candidates=(),
    ).to_dict()
    return derived, catalog, tactical


def _candidate(candidate_id: str, catalog, *changes: tuple[str, object]) -> StrategyCandidate:
    derived, _catalog, _tactical = _inputs()
    assembled = StrategyPatchAssembler(baseline=derived.strategy, catalog=catalog).assemble(
        CandidatePatch(
            candidate_id,
            "quality fixture",
            tuple(StrategyPatchOperation(path, value) for path, value in changes),
        )
    )
    return StrategyCandidate(candidate_id, assembled.strategy, "quality fixture", assembled.changed_paths)


def _valid_candidates():
    derived, catalog, tactical = _inputs()
    candidates = (
        _candidate("candidate_00", catalog,
            ("/attacks/0/target_ids/0", "blue_cg59"),
            ("/attacks/0/delay_seconds", 31),
            ("/attacks/1/delay_seconds", 31)),
        _candidate("candidate_01", catalog,
            ("/attacks/0/delay_seconds", 32),
            ("/attacks/1/target_ids/0", "blue_ddg113_1"),
            ("/attacks/2/delay_seconds", 34)),
        _candidate("candidate_02", catalog,
            ("/attacks/0/target_ids/0", "blue_cvn70"),
            ("/attacks/0/delay_seconds", 35),
            ("/attacks/1/fire_quantity", 7),
            ("/sorties/0/route/0/latitude", 23.7),
            ("/sorties/1/target_id", "blue_cg59")),
        _candidate("candidate_03", catalog, ("/attacks/2/fire_quantity", 4)),
    )
    return derived, candidates, tactical


def _evaluate(candidates=None):
    derived, valid, tactical = _valid_candidates()
    return CandidateQualityEvaluator().evaluate(
        baseline=derived.strategy,
        candidates=valid if candidates is None else candidates,
        intents=candidate_role_specs({}),
        proposal_context=tactical,
    )


def test_valid_batch_has_stable_coverage_and_pairwise_value_difference() -> None:
    report = _evaluate()

    assert report.status == "passed"
    assert report.batch_coverage["operation_ids"] == tuple(sorted((
        "surface_attack:red_052d_1_attack_cg59",
        "surface_attack:red_052d_2_attack_cg59",
        "surface_attack:red_055_attack_ddg113_1",
        "sortie:red_j15_1_attack_cvn70",
        "sortie:red_j15_2_attack_ddg113_2",
    )))
    assert len(report.batch_coverage["semantic_dimensions"]) >= 3
    assert len(report.batch_coverage["platform_types"]) >= 2
    coordinated = next(item for item in report.candidate_reports if item.candidate_id == "candidate_02")
    assert coordinated.surface_operation_count > 0
    assert coordinated.sortie_operation_count > 0
    control = next(item for item in report.candidate_reports if item.candidate_id == "candidate_03")
    assert control.changed_leaf_count == 1
    assert control.role_conformance["role_adherence"] == "full"
    pair = next(
        item for item in report.pairwise_reports
        if (item.left_candidate_id, item.right_candidate_id) == ("candidate_00", "candidate_01")
    )
    assert pair.path_jaccard > 0
    assert pair.value_difference_count == 1
    assert report.to_dict() == _evaluate().to_dict()
    assert report.report_checksum == _evaluate().report_checksum


def test_quality_warns_same_primary_operation_set() -> None:
    derived, catalog, tactical = _inputs()
    candidates = (
        _candidate("candidate_00", catalog, ("/attacks/0/target_ids/0", "blue_cg59"), ("/attacks/0/delay_seconds", 31), ("/attacks/1/delay_seconds", 31), ("/sorties/0/route/0/latitude", 23.7)),
        _candidate("candidate_01", catalog, ("/attacks/0/delay_seconds", 32), ("/attacks/1/target_ids/0", "blue_ddg113_1"), ("/sorties/0/route/0/longitude", 129.97)),
        _candidate("candidate_02", catalog, ("/attacks/0/target_ids/0", "blue_cvn70"), ("/attacks/0/delay_seconds", 35), ("/attacks/0/fire_quantity", 7), ("/attacks/1/target_ids/0", "blue_ddg113_2"), ("/sorties/0/route/0/latitude", 23.8)),
        _candidate("candidate_03", catalog, ("/attacks/0/fire_quantity", 7)),
    )
    report = CandidateQualityEvaluator().evaluate(
        baseline=derived.strategy, candidates=candidates,
        intents=candidate_role_specs({}), proposal_context=tactical,
    )
    assert report.status == "passed"
    assert "candidate_00_01_02_same_operation_set" in report.warnings
    report.require_passed()


def test_quality_rejects_duplicate_strategy_checksums() -> None:
    derived, candidates, tactical = _valid_candidates()
    duplicate = StrategyCandidate(
        "candidate_01",
        candidates[0].strategy_spec,
        "duplicate fixture",
        candidates[0].intended_difference,
    )
    report = CandidateQualityEvaluator().evaluate(
        baseline=derived.strategy,
        candidates=(candidates[0], duplicate, candidates[2], candidates[3]),
        intents=candidate_role_specs({}),
        proposal_context=tactical,
    )
    assert "unique_strategy_checksums_required" in report.failed_rules


@pytest.mark.parametrize(
    ("mutator", "expected"),
    (
        ("operation", "minimum_batch_operation_coverage"),
        ("dimension", "minimum_batch_dimension_coverage"),
        ("surface_sortie", "surface_sortie_candidate_required"),
    ),
)
def test_quality_reports_structured_batch_failures(mutator: str, expected: str) -> None:
    derived, catalog, tactical = _inputs()
    if mutator == "operation":
        candidates = (
            _candidate("candidate_00", catalog, ("/attacks/0/target_ids/0", "blue_cg59"), ("/attacks/0/delay_seconds", 31), ("/attacks/1/delay_seconds", 31), ("/sorties/0/route/0/latitude", 23.7)),
            _candidate("candidate_01", catalog, ("/attacks/0/delay_seconds", 32), ("/attacks/1/target_ids/0", "blue_ddg113_1"), ("/sorties/0/route/0/longitude", 129.97)),
            _candidate("candidate_02", catalog, ("/attacks/0/target_ids/0", "blue_cvn70"), ("/attacks/0/delay_seconds", 35), ("/attacks/0/fire_quantity", 7), ("/attacks/1/target_ids/0", "blue_ddg113_2"), ("/sorties/0/route/0/latitude", 23.8)),
            _candidate("candidate_03", catalog, ("/attacks/0/fire_quantity", 7)),
        )
    elif mutator == "dimension":
        candidates = (
            _candidate("candidate_00", catalog, ("/attacks/0/target_ids/0", "blue_cg59"), ("/attacks/1/target_ids/0", "blue_ddg113_1"), ("/attacks/2/target_ids/0", "blue_cvn70")),
            _candidate("candidate_01", catalog, ("/attacks/0/target_ids/0", "blue_cg59"), ("/attacks/1/target_ids/0", "blue_ddg113_1"), ("/attacks/2/target_ids/0", "blue_ddg113_2")),
            _candidate("candidate_02", catalog, ("/attacks/0/target_ids/0", "blue_cg59"), ("/attacks/1/target_ids/0", "blue_ddg113_1"), ("/attacks/2/target_ids/0", "blue_cvn70"), ("/sorties/1/target_id", "blue_cg59")),
            _candidate("candidate_03", catalog, ("/attacks/0/target_ids/0", "blue_cg59")),
        )
    else:
        candidates = (
            _candidate("candidate_00", catalog, ("/attacks/0/target_ids/0", "blue_cg59"), ("/attacks/0/delay_seconds", 31), ("/attacks/1/delay_seconds", 31)),
            _candidate("candidate_01", catalog, ("/attacks/0/delay_seconds", 32), ("/attacks/1/target_ids/0", "blue_ddg113_1"), ("/attacks/2/delay_seconds", 34)),
            _candidate("candidate_02", catalog, ("/attacks/0/target_ids/0", "blue_cvn70"), ("/attacks/0/delay_seconds", 35), ("/attacks/1/fire_quantity", 7), ("/attacks/1/target_ids/0", "blue_ddg113_2"), ("/attacks/2/fire_quantity", 4)),
            _candidate("candidate_03", catalog, ("/attacks/2/fire_quantity", 4)),
        )
    intents = candidate_role_specs({})
    if mutator == "dimension":
        from dataclasses import replace
        intents = tuple(
            replace(item, min_changed_leaves=4, min_dimensions=1)
            if item.candidate_id == "candidate_02" else item
            for item in intents
        )
    report = CandidateQualityEvaluator().evaluate(baseline=derived.strategy, candidates=candidates, intents=intents, proposal_context=tactical)
    assert report.status == "passed"
    assert expected in report.warnings


def test_preview_quality_warnings_persist_and_freeze_without_extra_calls(tmp_path: Path) -> None:
    derived, catalog, tactical = _inputs()
    candidates = (
        _candidate("candidate_00", catalog, ("/attacks/0/target_ids/0", "blue_cg59"), ("/attacks/0/delay_seconds", 31), ("/attacks/1/delay_seconds", 31), ("/sorties/0/route/0/latitude", 23.7)),
        _candidate("candidate_01", catalog, ("/attacks/0/delay_seconds", 32), ("/attacks/1/target_ids/0", "blue_ddg113_1"), ("/sorties/0/route/0/longitude", 129.97)),
        _candidate("candidate_02", catalog, ("/attacks/0/target_ids/0", "blue_cvn70"), ("/attacks/0/delay_seconds", 35), ("/attacks/0/fire_quantity", 7), ("/attacks/1/target_ids/0", "blue_ddg113_2"), ("/sorties/0/route/0/latitude", 23.8)),
        _candidate("candidate_03", catalog, ("/attacks/0/fire_quantity", 7)),
    )

    class Proposal:
        last_usage = SimpleNamespace(total_calls=5)
        last_audit = {}
        last_tactical_context = tactical
        calls = 0

        def propose(self, _context):
            self.calls += 1
            return candidates

    proposal = Proposal()
    package = SimpleNamespace(
        scenario=derived.scenario,
        baseline=SimpleNamespace(strategy=derived.strategy),
        allowed_strategy_paths=PATHS,
        diversity_dimensions=("target_assignment", "attack_timing", "fire_quantity", "air_route"),
        runtime=SimpleNamespace(runtime_id="fixture", runtime_version="1.0"),
        bootstrap=SimpleNamespace(checksum="fixture-bootstrap"),
        checksums={},
    )
    builder = ProductionPreviewBuilder(
        package=package,
        proposal_agent=proposal,
        novelty_validator=CandidateNoveltyValidator(),
        campaign_root_provider=lambda _campaign_id: tmp_path,
    )
    spec = SimpleNamespace(campaign_id="quality_fixture", generation_objective="fixture")

    builder.build(spec=spec, generation_index=0, preview_revision=0)

    root = tmp_path / "previews" / "generation_000" / "revision_000"
    report = json.loads((root / "candidate-quality-report.json").read_text(encoding="utf-8"))
    trace = json.loads((root / "proposal-trace.json").read_text(encoding="utf-8"))
    assert report["status"] == "passed"
    assert trace["candidate_quality_status"] == "passed"
    assert trace["candidate_quality_report_checksum"] == report["report_checksum"]
    assert (root / "candidate-quality-index.json").is_file()
    for candidate_id in ("candidate_00", "candidate_01", "candidate_02", "candidate_03"):
        assert (root / "candidates" / candidate_id / "strategy-diff.json").is_file()
        assert (root / "candidates" / candidate_id / "candidate-quality-report.json").is_file()
    assert (root / "frozen-candidate-set.json").is_file()
    assert proposal.calls == 1
    assert builder.proposal_calls == 5
