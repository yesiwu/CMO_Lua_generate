from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from cmo_lua_agent.contract.baseline_strategy_builder import BaselineStrategyBuilder
from cmo_lua_agent.optimization.proposal_context_builder import ProposalTacticalContextBuilder
from cmo_lua_agent.agents.strategy_intent_agent import CandidateIntentPlanner
from cmo_lua_agent.agents.strategy_patch_agent import CandidatePatchGenerator
from cmo_lua_agent.optimization.phase6_models import BootstrapSkillSnapshot, StrategyProposalContext
from cmo_lua_agent.optimization.proposal_models import (
    AcceptedCandidateSummary,
    CandidateIntent,
    candidate_role_specs,
)
from cmo_lua_agent.optimization.strategy_patch import build_patchable_leaf_catalog
from cmo_lua_agent.evolution.production_preview_builder import ProductionPreviewBuilder


PROJECT_ROOT = Path(__file__).resolve().parents[4]
PATHS = (
    "/attacks/0/target_ids/0", "/attacks/0/delay_seconds", "/attacks/0/fire_quantity",
    "/attacks/1/target_ids/0", "/attacks/1/delay_seconds", "/attacks/1/fire_quantity",
    "/attacks/2/target_ids/0", "/attacks/2/delay_seconds", "/attacks/2/fire_quantity",
    "/sorties/0/route/0/latitude", "/sorties/0/route/0/longitude",
    "/sorties/1/route/0/latitude", "/sorties/1/route/0/longitude", "/sorties/1/target_id",
)


def _inputs():
    payload = json.loads((PROJECT_ROOT / "json_data" / "6v4ScenarioIR.json").read_text(encoding="utf-8"))
    derived = BaselineStrategyBuilder().build(payload)
    catalog = build_patchable_leaf_catalog(
        baseline=derived.strategy, scenario=derived.scenario, allowed_paths=PATHS
    )
    return derived, catalog


def test_context_is_stable_and_summarizes_formal_6v4_operations() -> None:
    derived, catalog = _inputs()
    builder = ProposalTacticalContextBuilder()
    first = builder.build(
        scenario=derived.scenario,
        baseline=derived.strategy,
        patch_catalog=catalog,
        role_specs=candidate_role_specs({}),
        accepted_candidates=(),
    )
    second = builder.build(
        scenario=derived.scenario,
        baseline=derived.strategy,
        patch_catalog=catalog,
        role_specs=candidate_role_specs({}),
        accepted_candidates=(),
    )

    assert first.canonical_json == second.canonical_json
    assert first.checksum == second.checksum
    assert len(first.baseline_operations) == 7
    assert len({item["operation_id"] for item in first.baseline_operations}) == 7
    assert sum(item["operation_type"] == "surface_attack" for item in first.baseline_operations) == 5
    assert sum(item["operation_type"] == "sortie" for item in first.baseline_operations) == 2
    assert all({"operation_id", "platform_id", "platform_type", "current_target_id", "delay_seconds", "patchable_dimensions", "patchable_paths"} <= set(item) for item in first.baseline_operations)
    assert all("/fire_delay_seconds" not in path for item in first.baseline_operations for path in item["patchable_paths"])
    assert first.failure_profile == {
        "available": False, "source_checksum": None, "operation_ids": [], "semantic_dimensions": [],
    }
    assert set(first.coupling_groups) == {
        "same_target_operations", "same_platform_operations", "surface_operations", "sortie_operations",
    }


def test_context_includes_frozen_failure_and_accepted_candidate_summary() -> None:
    derived, catalog = _inputs()
    context = ProposalTacticalContextBuilder().build(
        scenario=derived.scenario,
        baseline=derived.strategy,
        patch_catalog=catalog,
        role_specs=candidate_role_specs({
            "failure_profile": {
                "operation_ids": ["attacks/0"],
                "semantic_dimensions": ["attack_timing"],
                "source_checksum": "frozen-failure",
            }
        }),
        accepted_candidates=(
            AcceptedCandidateSummary(
                "candidate_00", "strategy", ("/attacks/0/delay_seconds",),
                ("attack_timing",), ("attacks/0",), ("blue_cvn70",),
            ),
        ),
    )
    assert context.failure_profile == {
        "available": True,
        "source_checksum": "frozen-failure",
        "operation_ids": ["attacks/0"],
        "semantic_dimensions": ["attack_timing"],
    }
    accepted = context.accepted_candidate_summaries[0]
    assert accepted["candidate_id"] == "candidate_00"
    assert accepted["changed_operation_ids"] == ["surface_attack:red_055_attack_ddg113_1"]
    assert accepted["target_assignment_summary"] == ["blue_cvn70"]


def test_context_excludes_sensitive_and_full_strategy_content() -> None:
    derived, catalog = _inputs()
    prompt = ProposalTacticalContextBuilder().build(
        scenario=derived.scenario,
        baseline=derived.strategy,
        patch_catalog=catalog,
        role_specs=candidate_role_specs({}),
        accepted_candidates=(),
    ).to_dict()
    encoded = json.dumps(prompt, sort_keys=True)
    for forbidden in (
        "native_score", "score_fragment", "sqlite", "aalog", "legacy", "baseline_strategy", "candidate.lua",
    ):
        assert forbidden not in encoded.lower()
    assert "attacks" not in prompt
    assert "sorties" not in prompt


def test_planner_and_patch_prompt_receive_only_compact_tactical_context() -> None:
    derived, catalog = _inputs()
    tactical = ProposalTacticalContextBuilder().build(
        scenario=derived.scenario, baseline=derived.strategy, patch_catalog=catalog,
        role_specs=candidate_role_specs({}), accepted_candidates=(),
    ).to_dict()
    context = StrategyProposalContext(
        derived.scenario, derived.strategy, "Exercise target coverage.", PATHS,
        ("target_assignment", "attack_timing", "fire_quantity", "air_route"),
        "runtime", "2.0.0",
        BootstrapSkillSnapshot("bootstrap", "1", "bootstrap", "human-authored", "none", ("StrategyProposalAgent",), "bootstrap.md", "rules", "checksum"),
        generation_context={}, proposal_tactical_context=tactical,
    )

    class Client:
        def __init__(self) -> None:
            self.prompts: list[dict[str, object]] = []
            self.responses = [
                {"intents": [
                    {"objective": "Adjust coverage.", "strategy_dimensions": ["target_assignment"]},
                    {"objective": "Adjust timing.", "strategy_dimensions": ["attack_timing"]},
                    {"objective": "Coordinate platforms.", "strategy_dimensions": ["target_assignment", "air_route"]},
                    {"objective": "Use one control.", "strategy_dimensions": ["fire_quantity"]},
                ]},
                {"proposal_summary": "Retarget one attack.", "changes": [{"path": "/attacks/0/target_ids/0", "value": "blue_cvn70"}]},
            ]

        def complete_json(self, *, system: str, prompt: str) -> object:
            self.prompts.append(json.loads(prompt))
            return self.responses.pop(0)

    client = Client()
    intents = CandidateIntentPlanner(client).plan(context, role_specs=candidate_role_specs({}))
    patch = CandidatePatchGenerator(client).generate(
        intent=CandidateIntent("candidate_03", "conservative_control", "Use one control.", ("target_assignment",), 1, 2, min_operations=1, min_dimensions=1, max_operations=1, max_dimensions=1),
        catalog=catalog, accepted=(), tactical_context=tactical,
    )
    assert len(intents) == 4
    assert patch.candidate_id == "candidate_03"
    for prompt in client.prompts:
        assert prompt["proposal_tactical_context"] == tactical
        encoded = json.dumps(prompt, sort_keys=True).lower()
        assert "native_score" not in encoded
        assert "baseline_strategy" not in encoded


def test_preview_persists_context_with_the_agent_audit_checksum(tmp_path: Path) -> None:
    agent = SimpleNamespace(
        last_tactical_context={"scenario_summary": {"scenario_id": "fixture"}},
        last_audit={"proposal_context_checksum": "context-checksum"},
    )
    builder = ProductionPreviewBuilder(
        package=object(), proposal_agent=agent, novelty_validator=object(),
        campaign_root_provider=lambda _campaign_id: tmp_path,
    )
    builder._write_proposal_context(tmp_path)
    value = json.loads((tmp_path / "proposal-context.json").read_text(encoding="utf-8"))
    assert value["context_checksum"] == "context-checksum"
    assert value["scenario_summary"]["scenario_id"] == "fixture"
