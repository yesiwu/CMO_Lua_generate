from __future__ import annotations

import inspect
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from cmo_lua_agent.contract import load_baseline_strategy, load_scenario_definition
from cmo_lua_agent.contract.strategy_models import strategy_spec_from_dict
from cmo_lua_agent.evolution.production_models import ControlledScenarioAsset
from cmo_lua_agent.evolution.production_preview_builder import (
    ProductionPreviewBuilder,
)
from cmo_lua_agent.evolution.novelty import CandidateNoveltyError
from cmo_lua_agent.evolution.production_knowledge import (
    ProductionKnowledgeSnapshotProvider,
)
from cmo_lua_agent.generation.runtime_models import LuaRuntimeProfile
from cmo_lua_agent.hooks.permission_hook import ApprovalReceipt
from cmo_lua_agent.optimization.bootstrap_skill_loader import BootstrapSkillLoader
from cmo_lua_agent.optimization.phase6_models import StrategyCandidate
import cmo_lua_agent.main as main_module
from cmo_lua_agent.main import (
    _campaign_receipt_persister,
    build_chat_components,
    build_parser,
)
from cmo_lua_agent.learning.store import ExperienceStore
from cmo_lua_agent.evolution.production_service import (
    ProductionDependencyOverrides,
    create_production_evolution_campaign_service,
    create_test_evolution_campaign_service,
)
from cmo_lua_agent.evolution.formal_candidate_evaluator import (
    FormalCandidateEvaluator,
)
from cmo_lua_agent.tools.evolution_campaign_tools import PrepareEvolutionCampaignTool
from cmo_lua_agent.tools.evolution_campaign_tools import (
    PreviewEvolutionGenerationTool,
)


def test_preview_failure_audit_classifies_post_proposal_novelty_failure() -> None:
    proposal = SimpleNamespace(
        last_usage=SimpleNamespace(total_calls=5),
        last_audit={
            "intents": [{"candidate_id": "candidate_02"}],
            "accepted_candidates": [{"candidate_id": "candidate_02"}],
        },
    )

    audit = ProductionPreviewBuilder.failure_audit(
        error=ValueError("novelty_explore_dimension_missing"),
        proposal_agent=proposal,
    )

    assert audit["failure_stage"] == "novelty_validation"
    assert audit["error_code"] == "novelty_explore_dimension_missing"
    assert audit["preview_status"] == "novelty_repair_required"
    assert audit["proposal_llm_calls"] == 5
    assert "intents" not in audit


def test_novelty_error_exposes_a_repairable_candidate_contract() -> None:
    error = CandidateNoveltyError(
        code="novelty_explore_dimension_missing",
        failed_candidate_ids=("candidate_02",),
        required_dimensions=("attacks", "sorties"),
        actual_dimensions=("attacks",),
        related_changed_paths=("/attacks/2/delay_seconds",),
    )

    assert error.code == "novelty_explore_dimension_missing"
    assert error.failed_candidate_ids == ("candidate_02",)
    assert error.related_changed_paths == ("/attacks/2/delay_seconds",)


def test_chat_parser_exposes_explicit_standard_and_campaign_profiles() -> None:
    parser = build_parser()

    standard = parser.parse_args(["chat"])
    campaign = parser.parse_args(["chat", "--profile", "campaign"])

    assert standard.profile == "standard"
    assert campaign.profile == "campaign"


def test_prepare_tool_accepts_only_controlled_package_request_fields() -> None:
    properties = PrepareEvolutionCampaignTool.input_schema["properties"]

    assert set(properties) == {
        "campaign_id",
        "input_package_id",
        "generation_objective",
        "budget",
        "minimum_improvement_delta",
        "no_improvement_patience",
    }
    assert "campaign" not in properties


def test_preview_tool_does_not_expose_internal_artifact_paths() -> None:
    preview = SimpleNamespace(
        campaign_id="campaign",
        generation_index=0,
        preview_revision=0,
        snapshot_checksum="snapshot",
        candidate_set_checksum="candidates",
        baseline_checksum="baseline",
        strategy_diffs=({"candidate_id": "candidate_00"},),
        proposal_operation_id="proposal",
        checksum="preview",
        frozen_candidate_set_ref=r"C:\secret\frozen.json",
        strategy_diff_ref=r"C:\secret\diff.json",
    )
    tool = PreviewEvolutionGenerationTool(
        service=SimpleNamespace(preview_generation=lambda **_kwargs: preview)
    )

    value = json.loads(
        tool.execute(
            {"campaign_id": "campaign", "generation_index": 0}
        ).content
    )

    assert "frozen_candidate_set_ref" not in value
    assert "strategy_diff_ref" not in value
    assert "C:\\secret" not in json.dumps(value)


def test_generation_inspection_summary_strips_internal_paths() -> None:
    from cmo_lua_agent.evolution.control_plane import EvolutionCampaignService

    result = EvolutionCampaignService._generation_result_summary(
        {
            "artifact_provenance": "formal_renderer",
            "outcomes": [
                {
                    "candidate_id": "candidate_00",
                    "execution_success": True,
                    "executable": True,
                    "semantic_valid": True,
                    "scoreable": True,
                    "native_score": 60,
                    "final_lua_path": r"C:\secret\candidate.lua",
                    "candidate_dir": r"C:\secret\candidate_00",
                }
            ],
            "leaderboard": [{"candidate_id": "candidate_00", "rank": 1}],
        }
    )

    serialized = json.dumps(result)
    assert result["outcomes"][0]["native_score"] == 60
    assert "final_lua_path" not in serialized
    assert "candidate_dir" not in serialized
    assert "C:\\\\secret" not in serialized


def test_production_factory_has_no_dependency_override_parameter() -> None:
    parameters = inspect.signature(
        create_production_evolution_campaign_service
    ).parameters

    assert set(parameters) == {"project_root", "app_config", "llm_client"}


@pytest.mark.parametrize(
    ("profile", "expects_production", "expects_standard_application"),
    (("standard", False, True), ("campaign", True, False)),
)
def test_main_constructs_only_the_selected_chat_profile(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    profile: str,
    expects_production: bool,
    expects_standard_application: bool,
) -> None:
    calls = {"production": 0, "application": 0}
    production_service = SimpleNamespace(persist_permission_grant=lambda *_: "approval")

    monkeypatch.setattr(main_module, "ClaudeClient", lambda _config: object())
    monkeypatch.setattr(main_module, "UIState", lambda **_kwargs: object())
    monkeypatch.setattr(
        main_module,
        "TerminalDisplay",
        lambda **_kwargs: SimpleNamespace(
            stop=lambda: None,
            start=lambda: None,
            handle=lambda _event: None,
        ),
    )

    class Hooks:
        def register(self, _hook):
            return None

    monkeypatch.setattr(main_module, "HookManager", Hooks)
    monkeypatch.setattr(main_module, "PermissionHook", lambda **_kwargs: object())
    monkeypatch.setattr(main_module, "TerminalApprover", lambda **_kwargs: object())

    def production_factory(**_kwargs):
        calls["production"] += 1
        return production_service

    def standard_application(_workdir):
        calls["application"] += 1
        return object()

    registry_calls = []
    monkeypatch.setattr(
        main_module,
        "create_production_evolution_campaign_service",
        production_factory,
    )
    monkeypatch.setattr(main_module, "create_application", standard_application)
    monkeypatch.setattr(main_module, "create_tool_services", lambda _app: object())
    monkeypatch.setattr(
        main_module,
        "build_tool_registry",
        lambda **kwargs: registry_calls.append(kwargs) or object(),
    )
    monkeypatch.setattr(
        main_module,
        "AgentLoop",
        lambda **_kwargs: object(),
    )
    config = SimpleNamespace(llm=SimpleNamespace(model_id="fixture"))

    build_chat_components(config=config, workdir=tmp_path, profile=profile)

    assert bool(calls["production"]) is expects_production
    assert bool(calls["application"]) is expects_standard_application
    assert registry_calls[0]["chat_profile"] == profile
    assert (
        registry_calls[0]["evolution_campaign_service"] is production_service
    ) is expects_production


def test_test_factory_rejects_non_fixture_overrides(tmp_path: Path) -> None:
    overrides = ProductionDependencyOverrides(
        test_mode=False,
        artifact_provenance="formal_renderer",
    )

    with pytest.raises(ValueError, match="test_dependency_overrides_required"):
        create_test_evolution_campaign_service(
            project_root=tmp_path,
            overrides=overrides,
        )


def test_formal_candidate_evaluator_preflight_requires_both_executables(
    tmp_path: Path,
) -> None:
    runner = tmp_path / "CmoBatchRunner.exe"
    command = tmp_path / "Command.exe"
    evaluator = FormalCandidateEvaluator(
        json_client=object(),
        cmo_runner_path=runner,
        cmo_executable_path=command,
    )
    with pytest.raises(ValueError, match="cmo_batch_runner_missing"):
        evaluator.preflight()
    runner.write_bytes(b"fixture")
    with pytest.raises(ValueError, match="cmo_executable_missing"):
        evaluator.preflight()
    command.write_bytes(b"fixture")

    assert evaluator.preflight() == {
        "cmo_batch_runner": str(runner.resolve()),
        "cmo_executable": str(command.resolve()),
    }


def test_campaign_receipt_persister_issues_grant_only_for_execute() -> None:
    calls = []
    service = SimpleNamespace(
        persist_permission_grant=lambda receipt, context: (
            calls.append((receipt, context)) or "approval"
        )
    )
    persist = _campaign_receipt_persister(service)
    receipt = SimpleNamespace(receipt_id="receipt")

    assert persist(
        receipt,
        {"tool": SimpleNamespace(name="control_evolution_campaign")},
    ) == "receipt"
    assert calls == []
    execute_context = {
        "tool": SimpleNamespace(name="execute_evolution_generation")
    }
    assert persist(receipt, execute_context) == "approval"
    assert calls == [(receipt, execute_context)]


def test_production_knowledge_snapshot_freezes_empty_store_and_exact_contract(
    tmp_path: Path,
) -> None:
    project = Path(__file__).resolve().parents[4]
    baseline = load_baseline_strategy(
        project / "baseline" / "6v4" / "legacy" / "baseline_strategy.pre-scenario-ir.json"
    )
    package = SimpleNamespace(
        runtime=LuaRuntimeProfile("fixture-runtime", "2.0.0"),
        renderer_version="2.0.0",
        checksums={"score_spec_compiled": "score-checksum"},
        diversity_dimensions=("target_assignment",),
        bootstrap=SimpleNamespace(checksum="bootstrap-checksum"),
        baseline=baseline,
    )
    spec = SimpleNamespace(campaign_id="campaign_knowledge")

    value = ProductionKnowledgeSnapshotProvider(
        project_root=tmp_path,
        experience_store=ExperienceStore(tmp_path / "data" / "experiences"),
    ).freeze(
        path=tmp_path / "snapshot.json",
        spec=spec,
        package=package,
        generation_index=0,
    )

    assert value["active_skills"] == ()
    assert value["experience_cards"] == ()
    assert value["selected_experience_ids"] == ()
    assert value["contract"]["score_spec_compiled"] == "score-checksum"
    assert (tmp_path / "snapshot.json").is_file()


def test_test_factory_runs_frozen_preview_and_generation_without_second_proposal(
    tmp_path: Path,
) -> None:
    project = Path(__file__).resolve().parents[4]
    baseline_root = project / "baseline" / "6v4"
    scenario = load_scenario_definition(baseline_root / "scenario_definition.json")
    baseline = load_baseline_strategy(
        baseline_root / "legacy" / "baseline_strategy.pre-scenario-ir.json"
    )
    source = baseline.strategy.to_dict()

    class Proposal:
        calls = 0
        context = None

        def propose(self, _context):
            self.calls += 1
            self.context = _context
            edits = (
                ("/attacks/0/fire_quantity", lambda value: value - 1),
                ("/attacks/0/delay_seconds", lambda value: value + 3),
                ("/attacks/1/target_ids/0", lambda _value: "blue_cvn70"),
                ("/sorties/0/route/0/latitude", lambda value: value + 0.1),
            )
            rows = []
            for index, (path, change) in enumerate(edits):
                value = deepcopy(source)
                cursor = value
                parts = path.strip("/").split("/")
                for part in parts[:-1]:
                    cursor = cursor[int(part)] if isinstance(cursor, list) else cursor[part]
                key = parts[-1]
                if isinstance(cursor, list):
                    cursor[int(key)] = change(cursor[int(key)])
                else:
                    cursor[key] = change(cursor[key])
                rows.append(
                    StrategyCandidate(
                        f"candidate_{index:02d}",
                        strategy_spec_from_dict(value),
                        f"fixture candidate {index}",
                        (path,),
                    )
                )
            return tuple(rows)

    class Loader:
        def load(self, package_id):
            assert package_id == "red_blue_6v4_liaoning_v1"
            return SimpleNamespace(
                package_id=package_id,
                scenario=scenario,
                baseline=baseline,
                native_score_compilation=object(),
                runtime=LuaRuntimeProfile("fixture-runtime", "2.0.0"),
                renderer_version="fixture-renderer",
                bootstrap=BootstrapSkillLoader(project).load(
                    "src/cmo_lua_agent/skills/bootstrap/cmo_naval_air_strategy_proposal_v1.md"
                ),
                scenario_asset=ControlledScenarioAsset(
                    "fixture-asset",
                    scenario.scenario_id,
                    str(tmp_path / "fixture.scen"),
                    "a" * 64,
                    1,
                    str(tmp_path / "verification.json"),
                    True,
                ),
                allowed_strategy_paths=tuple(path for path, _ in (
                    ("/attacks/0/fire_quantity", None),
                    ("/attacks/0/delay_seconds", None),
                    ("/attacks/1/target_ids/0", None),
                    ("/sorties/0/route/0/latitude", None),
                )),
                diversity_dimensions=(
                    "fire_quantity",
                    "attack_timing",
                    "target_assignment",
                    "air_route",
                ),
                    checksums={
                        "scenario_definition_derived": "scenario",
                    "runtime": "runtime",
                    "renderer": "renderer",
                    "score_spec_compiled": "score",
                },
                git_commit="fixture-commit",
                working_tree_dirty=False,
                diff_checksum=None,
                package_checksum="package",
            )

    evaluated = []

    def evaluate(**kwargs):
        evaluated.append(kwargs["candidate_id"])
        root = Path(kwargs["candidate_dir"])
        root.mkdir(parents=True, exist_ok=True)
        value = {
            "candidate_id": kwargs["candidate_id"],
            "execution_success": True,
            "executable": True,
            "semantic_valid": True,
            "scoreable": True,
            "native_score": len(evaluated),
            "score_source": "execution-summary.json#/official_score/final",
            "execution_fidelity": "verified",
            "artifact_provenance": "formal_renderer",
            "success": True,
            "repair_invocations": 0,
            "execution_attempts": 1,
            "failure_reason": "completed",
        }
        (root / "candidate_outcome.json").write_text(
            json.dumps(value), encoding="utf-8"
        )
        return value

    class Phase:
        def __init__(self, status="completed"):
            self.status = status

        def run(self, **kwargs):
            return {
                "status": self.status,
                "optimization_id": "fixture_optimization",
            }

    proposal = Proposal()

    class Knowledge:
        def freeze(self, *, path, **_kwargs):
            value = {
                "checksum": "knowledge-checksum",
                "experience_cards": [
                    {
                        "experience_key": "fixture.experience",
                        "suggestion": "fixture suggestion",
                    }
                ],
                "active_skills": [
                    {
                        "skill_id": "fixture_skill",
                        "checksum": "fixture-skill-checksum",
                    }
                ],
            }
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(json.dumps(value), encoding="utf-8")
            return value

    service = create_test_evolution_campaign_service(
        project_root=tmp_path,
        overrides=ProductionDependencyOverrides(
            test_mode=True,
            artifact_provenance="test_fixture",
            package_loader=Loader(),
            proposal_agent=proposal,
            candidate_evaluator=evaluate,
            phase7_adapter=Phase(),
            phase8_adapter=Phase("no_eligible_experience"),
            knowledge_snapshot_provider=Knowledge(),
        ),
    )
    budget = {
        "max_generations": 1,
        "max_cmo_runs": 5,
        "max_cmo_attempts_per_candidate": 1,
        "max_cmo_attempts_for_baseline": 1,
        "max_repair_attempts_per_candidate": 0,
        "max_failed_runs": 1,
        "max_llm_total_calls": 9,
        "max_strategy_proposal_calls": 9,
        "max_lua_generation_calls": 0,
        "max_lua_repair_calls": 0,
        "max_comparative_learning_calls": 1,
        "max_skill_author_calls": 1,
        "max_wall_clock_seconds": 60,
        "per_generation_timeout_seconds": 60,
        "per_candidate_timeout_seconds": 30,
    }
    service.prepare_campaign_request(
        campaign_id="campaign_fixture",
        input_package_id="red_blue_6v4_liaoning_v1",
        generation_objective="fixture",
        budget=budget,
        minimum_improvement_delta=1,
        no_improvement_patience=1,
    )
    preview = service.preview_generation(
        campaign_id="campaign_fixture",
        generation_index=0,
    )
    receipt = ApprovalReceipt.issue("execute_evolution_generation")
    approval_id = service.persist_permission_grant(
        receipt,
        {
            "arguments": {
                "campaign_id": "campaign_fixture",
                "generation_index": 0,
            }
        },
    )
    service.execute_generation(
        campaign_id="campaign_fixture",
        generation_index=0,
        approval_id=approval_id,
    )

    assert preview.candidate_set_checksum
    assert proposal.calls == 1
    assert proposal.context.retrieved_experience_cards[0][
        "experience_key"
    ] == "fixture.experience"
    assert proposal.context.active_curated_skill["skill_id"] == "fixture_skill"
    assert evaluated == [
        "baseline",
        "candidate_00",
        "candidate_01",
        "candidate_02",
        "candidate_03",
    ]
    generation_root = (
        tmp_path
        / "runs"
        / "evolution"
        / "campaign_fixture"
        / "generations"
        / "generation_000"
    )
    result = json.loads(
        (generation_root / "generation-result.json").read_text(
            encoding="utf-8"
        )
    )
    assert result["artifact_provenance"] == "test_fixture"
    outcome = json.loads(
        (
            generation_root
            / "phase6"
            / "candidate_00"
            / "candidate_outcome.json"
        ).read_text(encoding="utf-8")
    )
    assert outcome["artifact_provenance"] == "test_fixture"
