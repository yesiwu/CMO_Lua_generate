from __future__ import annotations

import json
from pathlib import Path

import pytest

from cmo_lua_agent.contract.baseline_strategy_builder import BaselineStrategyBuilder
from cmo_lua_agent.optimization.candidate_intent_conformance import (
    CandidateIntentConformanceError,
    CandidateIntentConformanceValidator,
)
from cmo_lua_agent.optimization.phase6_models import (
    BootstrapSkillSnapshot,
    StrategyProposalContext,
)
from cmo_lua_agent.optimization.proposal_models import (
    CandidateIntent,
    ProposalContractError,
)
from cmo_lua_agent.optimization.strategy_patch import build_patchable_leaf_catalog
from cmo_lua_agent.optimization.strategy_proposal_agent import StrategyProposalAgent


PROJECT_ROOT = Path(__file__).resolve().parents[4]
_PATHS = (
    "/attacks/0/target_ids/0",
    "/attacks/0/delay_seconds",
    "/attacks/0/fire_quantity",
    "/attacks/1/target_ids/0",
    "/attacks/1/delay_seconds",
    "/attacks/1/fire_quantity",
    "/attacks/2/target_ids/0",
    "/attacks/2/delay_seconds",
    "/attacks/2/fire_quantity",
    "/sorties/0/route/0/latitude",
    "/sorties/0/route/0/longitude",
    "/sorties/1/route/0/latitude",
    "/sorties/1/route/0/longitude",
    "/sorties/1/target_id",
)


def _context(*, paths: tuple[str, ...] = _PATHS, generation_context=None):
    scenario_ir = json.loads(
        (PROJECT_ROOT / "json_data" / "6v4ScenarioIR.json").read_text(
            encoding="utf-8"
        )
    )
    derived = BaselineStrategyBuilder().build(scenario_ir)
    return StrategyProposalContext(
        derived.scenario,
        derived.strategy,
        "Exercise bounded candidate roles.",
        paths,
        (
            "target_assignment",
            "attack_timing",
            "fire_quantity",
            "air_route",
        ),
        "runtime",
        "2.0.0",
        BootstrapSkillSnapshot(
            "bootstrap", "1", "bootstrap", "human-authored", "none",
            ("StrategyProposalAgent",), "bootstrap.md", "rules", "checksum",
        ),
        generation_context={} if generation_context is None else generation_context,
    )


def _catalog(context):
    return build_patchable_leaf_catalog(
        baseline=context.baseline,
        scenario=context.scenario,
        allowed_paths=context.allowed_strategy_paths,
    )


def _intent(
    candidate_id: str,
    *,
    failure_profile_mode: str = "unavailable",
    failure_operation_ids: tuple[str, ...] = (),
    failure_semantic_dimensions: tuple[str, ...] = (),
) -> CandidateIntent:
    values = {
        "candidate_00": ("exploit", 3, 5, 2, 2, False, False),
        "candidate_01": ("robust_repair", 3, 5, 2, 2, False, False),
        "candidate_02": ("coordinated_explore", 5, 8, 3, 3, True, True),
        "candidate_03": ("conservative_control", 1, 2, 1, 1, False, False),
    }
    role, minimum, maximum, operations, dimensions, surface, sortie = values[candidate_id]
    return CandidateIntent(
        candidate_id,
        role,
        "fixture intent",
        ("target_assignment", "attack_timing", "fire_quantity", "air_route"),
        minimum,
        maximum,
        min_operations=operations,
        min_dimensions=dimensions,
        require_surface=surface,
        require_sortie=sortie,
        max_operations=1 if candidate_id == "candidate_03" else None,
        max_dimensions=1 if candidate_id == "candidate_03" else None,
        failure_profile_mode=failure_profile_mode,
        failure_operation_ids=failure_operation_ids,
        failure_semantic_dimensions=failure_semantic_dimensions,
        failure_profile_source_checksum=(
            "failure-checksum" if failure_profile_mode == "required" else None
        ),
    )


def _validate(intent: CandidateIntent, paths: tuple[str, ...]) -> None:
    context = _context()
    CandidateIntentConformanceValidator().validate(
        intent=intent,
        changed_paths=paths,
        catalog=_catalog(context),
    )


def test_exploit_role_bounds_are_quality_preferences() -> None:
    report = CandidateIntentConformanceValidator().validate(
        intent=_intent("candidate_00"),
        changed_paths=(
            "/attacks/0/target_ids/0", "/attacks/1/fire_quantity",
        ),
        catalog=_catalog(_context()),
    )
    assert report.role_adherence == "partial"
    assert report.repair_recommended is False
    _validate(
        _intent("candidate_00"),
        (
            "/attacks/0/target_ids/0",
            "/attacks/0/delay_seconds",
            "/attacks/1/fire_quantity",
        ),
    )


def test_robust_repair_failure_profile_is_quality_preference() -> None:
    paths = (
        "/attacks/0/target_ids/0",
        "/attacks/0/delay_seconds",
        "/attacks/1/fire_quantity",
    )
    _validate(_intent("candidate_01"), paths)
    _validate(
        _intent(
            "candidate_01",
            failure_profile_mode="required",
            failure_semantic_dimensions=("attack_timing",),
        ),
        paths,
    )
    report = CandidateIntentConformanceValidator().validate(
        intent=_intent("candidate_01", failure_profile_mode="required", failure_semantic_dimensions=("air_route",)),
        changed_paths=paths, catalog=_catalog(_context()),
    )
    assert "failure_profile_not_covered" in report.role_warnings


@pytest.mark.parametrize(
    ("paths", "code"),
    (
        (
            (
                "/attacks/0/target_ids/0",
                "/attacks/0/delay_seconds",
                "/attacks/0/fire_quantity",
                "/attacks/1/target_ids/0",
                "/attacks/1/delay_seconds",
            ),
            "candidate_intent_sortie_required",
        ),
        (
            (
                "/sorties/0/route/0/latitude",
                "/sorties/0/route/0/longitude",
                "/sorties/1/route/0/latitude",
                "/sorties/1/route/0/longitude",
                "/sorties/1/target_id",
            ),
            "candidate_intent_surface_required",
        ),
        (
            (
                "/attacks/0/target_ids/0",
                "/attacks/0/delay_seconds",
                "/attacks/0/fire_quantity",
                "/sorties/0/route/0/latitude",
                "/sorties/0/route/0/longitude",
            ),
            "candidate_intent_operation_count_invalid",
        ),
        (
            (
                "/attacks/0/target_ids/0",
                "/attacks/1/target_ids/0",
                "/attacks/2/target_ids/0",
                "/sorties/0/route/0/latitude",
                "/sorties/1/route/0/longitude",
            ),
            "candidate_intent_dimension_missing",
        ),
    ),
)
def test_coordinated_explore_reports_incomplete_multiplatform_shapes(
    paths: tuple[str, ...], code: str
) -> None:
    report = CandidateIntentConformanceValidator().validate(
        intent=_intent("candidate_02"), changed_paths=paths, catalog=_catalog(_context())
    )
    assert report.role_adherence in {"partial", "weak"}


def test_coordinated_explore_accepts_surface_sortie_three_operation_three_dimension_patch() -> None:
    _validate(
        _intent("candidate_02"),
        (
            "/attacks/0/target_ids/0",
            "/attacks/0/delay_seconds",
            "/attacks/0/fire_quantity",
            "/attacks/1/target_ids/0",
            "/sorties/0/route/0/latitude",
        ),
    )


def test_conservative_control_scope_is_quality_not_freeze_gate() -> None:
    _validate(_intent("candidate_03"), ("/sorties/0/route/0/latitude",))
    _validate(
        _intent("candidate_03"),
        ("/sorties/0/route/0/latitude", "/sorties/0/route/0/longitude"),
    )
    report = CandidateIntentConformanceValidator().validate(
        intent=_intent("candidate_03"),
        changed_paths=("/attacks/0/target_ids/0", "/attacks/1/target_ids/0"),
        catalog=_catalog(_context()),
    )
    assert report.role_adherence == "partial"


def test_global_effective_leaf_range_is_hard_while_role_shape_is_not() -> None:
    context = _context()
    catalog = _catalog(context)
    intent = _intent("candidate_03")
    with pytest.raises(CandidateIntentConformanceError) as empty:
        CandidateIntentConformanceValidator().validate(
            intent=intent, changed_paths=(), catalog=catalog
        )
    assert empty.value.code == "candidate_intent_change_count_invalid"
    with pytest.raises(CandidateIntentConformanceError) as oversized:
        CandidateIntentConformanceValidator().validate(
            intent=intent,
            changed_paths=tuple(leaf.path for leaf in catalog[:11]),
            catalog=catalog,
        )
    assert oversized.value.code == "candidate_intent_change_count_invalid"
    report = CandidateIntentConformanceValidator().validate(
        intent=intent,
        changed_paths=("/attacks/0/target_ids/0", "/attacks/0/fire_quantity"),
        catalog=catalog,
    )
    assert len(report.changed_paths) == 2
    assert len(report.actual_operations) == 1
    assert len(report.actual_dimensions) == 2
    assert report.role_adherence == "partial"


def test_infeasible_role_is_recorded_without_preflight_block() -> None:
    class FakeClient:
        calls = 0

        def complete_json(self, **_: object) -> object:
            self.calls += 1
            return {"intents": []}

    client = FakeClient()
    agent = StrategyProposalAgent(client)
    context = _context(
        paths=(
            "/attacks/0/target_ids/0",
            "/attacks/0/delay_seconds",
            "/attacks/0/fire_quantity",
        )
    )

    with pytest.raises(ProposalContractError) as raised:
        agent.propose(context)
    assert raised.value.code == "intent_count_must_be_four"
    assert client.calls == 1
