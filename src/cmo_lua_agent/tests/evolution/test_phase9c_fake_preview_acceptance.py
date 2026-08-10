from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from cmo_lua_agent.contract.baseline_strategy_builder import BaselineStrategyBuilder
from cmo_lua_agent.evolution.novelty import CandidateNoveltyValidator
from cmo_lua_agent.evolution.production_models import FrozenCandidateSet
from cmo_lua_agent.evolution.production_preview_builder import ProductionPreviewBuilder
from cmo_lua_agent.optimization.proposal_models import CandidateProposalError
from cmo_lua_agent.agents.strategy_proposal_agent import StrategyProposalAgent


PROJECT_ROOT = Path(__file__).resolve().parents[4]
ALLOWED_PATHS = (
    "/attacks/0/target_ids/0", "/attacks/0/delay_seconds", "/attacks/0/fire_quantity",
    "/attacks/1/target_ids/0", "/attacks/1/delay_seconds", "/attacks/1/fire_quantity",
    "/attacks/2/target_ids/0", "/attacks/2/delay_seconds", "/attacks/2/fire_quantity",
    "/sorties/0/route/0/latitude", "/sorties/0/route/0/longitude",
    "/sorties/1/route/0/latitude", "/sorties/1/route/0/longitude", "/sorties/1/target_id",
)


class FakeJsonClient:
    def __init__(self, responses: list[dict[str, object]]) -> None:
        self._responses = list(responses)
        self.calls: list[str] = []
        self.prompts: list[str] = []

    def complete_json(self, *, system: str, prompt: str) -> object:
        self.calls.append(system.split(".", 1)[0])
        self.prompts.append(prompt)
        return self._responses.pop(0)


def _intents() -> dict[str, object]:
    return {
        "intents": [
            {"objective": "Retarget and stagger surface attacks.", "strategy_dimensions": ["target_assignment", "attack_timing"]},
            {"objective": "Use a bounded robust timing and target variation.", "strategy_dimensions": ["attack_timing", "target_assignment"]},
            {"objective": "Coordinate surface and sortie actions.", "strategy_dimensions": ["target_assignment", "attack_timing", "fire_quantity", "air_route"]},
            {"objective": "Make one conservative quantity adjustment.", "strategy_dimensions": ["fire_quantity"]},
        ]
    }


def _patch(summary: str, changes: list[tuple[str, object]]) -> dict[str, object]:
    return {
        "proposal_summary": summary,
        "changes": [{"path": path, "value": value} for path, value in changes],
    }


def _valid_responses() -> list[dict[str, object]]:
    return [
        _intents(),
        _patch("Exploit target and timing variation.", [
            ("/attacks/0/target_ids/0", "blue_cg59"),
            ("/attacks/0/delay_seconds", 31),
            ("/attacks/1/delay_seconds", 31),
        ]),
        _patch("Bounded robust adjustment.", [
            ("/attacks/0/delay_seconds", 32),
            ("/attacks/1/target_ids/0", "blue_ddg113_1"),
            ("/attacks/2/delay_seconds", 34),
        ]),
        _patch("Coordinate ship and aircraft paths.", [
            ("/attacks/0/target_ids/0", "blue_cvn70"),
            ("/attacks/0/delay_seconds", 35),
            ("/attacks/1/fire_quantity", 7),
            ("/sorties/0/route/0/latitude", 23.7),
            ("/sorties/1/target_id", "blue_cg59"),
        ]),
        _patch("Conservative quantity adjustment.", [("/attacks/2/fire_quantity", 4)]),
    ]


def _same_operation_responses() -> list[dict[str, object]]:
    return [
        _intents(),
        _patch("Shared operation set one.", [
            ("/attacks/0/target_ids/0", "blue_cg59"),
            ("/attacks/0/delay_seconds", 31),
            ("/attacks/1/delay_seconds", 31),
            ("/sorties/0/route/0/latitude", 23.7),
        ]),
        _patch("Shared operation set two.", [
            ("/attacks/0/delay_seconds", 32),
            ("/attacks/1/target_ids/0", "blue_ddg113_1"),
            ("/sorties/0/route/0/longitude", 129.97),
        ]),
        _patch("Shared operation set three.", [
            ("/attacks/0/target_ids/0", "blue_cvn70"),
            ("/attacks/0/delay_seconds", 35),
            ("/attacks/0/fire_quantity", 7),
            ("/attacks/1/target_ids/0", "blue_ddg113_2"),
            ("/sorties/0/route/0/latitude", 23.8),
        ]),
        _patch("Conservative shared operation adjustment.", [("/attacks/0/fire_quantity", 7)]),
    ]


def _package():
    scenario_ir = json.loads((PROJECT_ROOT / "json_data" / "6v4ScenarioIR.json").read_text(encoding="utf-8"))
    derived = BaselineStrategyBuilder().build(scenario_ir)
    return derived, SimpleNamespace(
        scenario=derived.scenario,
        baseline=SimpleNamespace(strategy=derived.strategy),
        baseline_derivation_manifest=derived.manifest.to_dict(),
        scenario_ir_checksum=derived.manifest.scenario_ir_checksum,
        allowed_strategy_paths=ALLOWED_PATHS,
        diversity_dimensions=("target_assignment", "attack_timing", "fire_quantity", "air_route"),
        runtime=SimpleNamespace(runtime_id="fake-runtime", runtime_version="2.0.0"),
        bootstrap=SimpleNamespace(
            skill_id="fake-bootstrap", version="1.0", checksum="fake-bootstrap", content="fixture rules"
        ),
        checksums={"scenario_definition_derived": derived.manifest.scenario_definition_checksum},
    )


def _builder(tmp_path: Path, responses: list[dict[str, object]]):
    derived, package = _package()
    client = FakeJsonClient(responses)
    builder = ProductionPreviewBuilder(
        package=package,
        proposal_agent=StrategyProposalAgent(client),
        novelty_validator=CandidateNoveltyValidator(),
        campaign_root_provider=lambda _campaign_id: tmp_path,
        proposal_provider="fake",
        production_execution_eligible=False,
    )
    return derived, client, builder


def _spec() -> SimpleNamespace:
    return SimpleNamespace(
        campaign_id="phase9c_fake_preview_quality_acceptance",
        generation_objective="Verify a bounded fake preview.",
    )


def _preview_root(tmp_path: Path) -> Path:
    return tmp_path / "previews" / "generation_000" / "revision_000"


def test_complete_fake_preview_freezes_auditable_non_production_candidates(tmp_path: Path) -> None:
    derived, client, builder = _builder(tmp_path, _valid_responses())

    first = builder.build(spec=_spec(), generation_index=0, preview_revision=0)
    root = _preview_root(tmp_path)
    frozen = FrozenCandidateSet.from_dict(json.loads((root / "frozen-candidate-set.json").read_text(encoding="utf-8")))
    quality = json.loads((root / "candidate-quality-report.json").read_text(encoding="utf-8"))
    trace = json.loads((root / "proposal-trace.json").read_text(encoding="utf-8"))
    context = json.loads((root / "proposal-context.json").read_text(encoding="utf-8"))
    snapshot = json.loads((root / "knowledge-snapshot.json").read_text(encoding="utf-8"))

    assert derived.manifest.scenario_ir_checksum == frozen.scenario_ir_checksum
    assert derived.manifest.baseline_strategy_checksum == frozen.derived_baseline_checksum
    assert context["context_checksum"] == frozen.proposal_context_checksum
    assert snapshot["checksum"] == frozen.knowledge_snapshot_checksum
    assert quality["report_checksum"] == frozen.candidate_quality_report_checksum
    assert frozen.proposal_provider == "fake"
    assert frozen.production_execution_eligible is False
    assert len(frozen.candidate_checksums) == 4
    assert len(set(frozen.candidate_checksums)) == 4
    assert trace["baseline_operation_count"] == 7
    assert trace["patchable_path_count"] == 14
    assert trace["failure_profile_available"] is False
    assert quality["status"] == "passed"
    assert len(quality["candidate_reports"]) == 4
    assert len(quality["pairwise_reports"]) == 6
    assert len(quality["batch_coverage"]["operation_ids"]) >= 4
    assert len(quality["batch_coverage"]["semantic_dimensions"]) >= 3
    assert len(quality["batch_coverage"]["platform_types"]) >= 2
    assert len(json.loads((root / "candidate-intents.json").read_text(encoding="utf-8"))) == 4
    assert len(json.loads((root / "candidate-patches.json").read_text(encoding="utf-8"))) == 4
    assert len(client.calls) == 5
    assert builder.proposal_calls == 5
    assert not (tmp_path / "approvals").exists()
    assert not (tmp_path / "phase7").exists()
    assert not (tmp_path / "phase8").exists()

    replay = builder.build(spec=_spec(), generation_index=0, preview_revision=0)
    assert len(client.calls) == 5
    assert replay.candidate_set_checksum == first.candidate_set_checksum == frozen.candidate_set_checksum
    assert json.loads((root / "candidate-quality-report.json").read_text(encoding="utf-8"))["report_checksum"] == quality["report_checksum"]
    assert replay.proposal_llm_calls == 0


def test_candidate_02_partial_role_quality_is_accepted_without_repair(
    tmp_path: Path,
) -> None:
    responses = _valid_responses()
    responses[3] = _patch("Too few coordinated changes.", [
        ("/attacks/0/target_ids/0", "blue_cvn70"),
        ("/attacks/0/delay_seconds", 35),
        ("/attacks/1/fire_quantity", 7),
        ("/sorties/0/route/0/latitude", 23.7),
    ])
    _derived, client, builder = _builder(tmp_path, responses)

    payload = builder.build(spec=_spec(), generation_index=0, preview_revision=0)

    quality = json.loads((Path(payload.frozen_candidate_set_ref).parent / "candidates" / "candidate_02" / "candidate-quality-report.json").read_text(encoding="utf-8"))
    assert quality["role_quality"]["role_adherence"] == "partial"
    assert quality["repair_summary"]["attempted"] is False


def test_fake_preview_accepts_role_warning_before_freezing(tmp_path: Path) -> None:
    responses = _valid_responses()
    invalid = _patch("Surface-only coordinated candidate.", [
        ("/attacks/0/target_ids/0", "blue_cvn70"),
        ("/attacks/0/delay_seconds", 35),
        ("/attacks/0/fire_quantity", 7),
        ("/attacks/1/target_ids/0", "blue_ddg113_2"),
        ("/attacks/2/delay_seconds", 34),
    ])
    responses[3] = invalid
    responses.insert(4, invalid)
    _derived, client, builder = _builder(tmp_path, responses)

    payload = builder.build(spec=_spec(), generation_index=0, preview_revision=0)

    root = _preview_root(tmp_path)
    quality = json.loads((root / "candidates" / "candidate_02" / "candidate-quality-report.json").read_text(encoding="utf-8"))
    assert quality["role_quality"]["role_adherence"] in {"partial", "weak"}
    assert Path(payload.frozen_candidate_set_ref).is_file()
    assert not (tmp_path / "approvals").exists()
    assert len(client.calls) == 6


def test_fake_preview_persists_quality_warning_without_automatic_reproposal(tmp_path: Path) -> None:
    _derived, client, builder = _builder(tmp_path, _same_operation_responses())

    payload = builder.build(spec=_spec(), generation_index=0, preview_revision=0)

    root = _preview_root(tmp_path)
    quality = json.loads((root / "candidate-quality-report.json").read_text(encoding="utf-8"))
    assert quality["status"] == "passed"
    assert quality["warnings"]
    assert Path(payload.frozen_candidate_set_ref).is_file()
    assert len(client.calls) == 5
    assert builder.proposal_calls == 5


def test_fake_preview_rejects_deferred_fire_delay_without_repair(tmp_path: Path) -> None:
    responses = _valid_responses()
    responses[1] = _patch("Attempt a deferred field.", [
        ("/sorties/0/fire_delay_seconds", 45),
        ("/attacks/0/delay_seconds", 31),
        ("/attacks/1/delay_seconds", 31),
    ])
    _derived, client, builder = _builder(tmp_path, responses)

    with pytest.raises(CandidateProposalError) as raised:
        builder.build(spec=_spec(), generation_index=0, preview_revision=0)

    root = _preview_root(tmp_path)
    failure = json.loads((root / "proposal-failure.json").read_text(encoding="utf-8"))
    assert raised.value.candidate_id == "candidate_00"
    assert raised.value.code == "patch_path_not_executable"
    assert failure["error_code"] == "patch_path_not_executable"
    assert not (root / "candidate-quality-report.json").exists()
    assert not (root / "frozen-candidate-set.json").exists()
    assert len(client.calls) == 2
