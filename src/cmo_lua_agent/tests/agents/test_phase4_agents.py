from __future__ import annotations

from pathlib import Path

import pytest

from cmo_lua_agent.contract import (
    BaselineStrategy,
    StrategySpec,
    load_baseline_strategy,
    load_scenario_definition,
)
from cmo_lua_agent.execution.models import CmoError
from cmo_lua_agent.generation.runtime_models import LuaRuntimeProfile
from cmo_lua_agent.generation.runtime_primitives import RUNTIME_ID, RUNTIME_VERSION
from cmo_lua_agent.generation.phase2_golden_baseline import Phase2GoldenBaselineService


class FakeJsonClient:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls = 0
        self.prompts: list[str] = []

    def complete_json(self, *, system: str, prompt: str) -> object:
        self.calls += 1
        self.prompts.append(system + "\n" + prompt)
        return self.response


def _baseline() -> tuple[Path, object, BaselineStrategy]:
    root = Path(__file__).resolve().parents[4]
    baseline_root = root / "baseline" / "6v4"
    return baseline_root, load_scenario_definition(baseline_root / "scenario_definition.json"), load_baseline_strategy(baseline_root / "baseline_strategy.json")


def _plan(baseline_root: Path):
    return Phase2GoldenBaselineService().render(
        scenario_definition_path=baseline_root / "scenario_definition.json",
        baseline_strategy_path=baseline_root / "baseline_strategy.json",
    ).plan


def test_synthesis_create_uses_structured_strategy_and_writes_atomic_artifacts(tmp_path: Path) -> None:
    from cmo_lua_agent.agents.lua_synthesis_agent import LuaSynthesisAgent, LuaSynthesisMode, LuaSynthesisRequest

    baseline_root, scenario, baseline = _baseline()
    client = FakeJsonClient({"strategy": baseline.strategy.to_dict(), "change_summary": ["使用已验证策略"]})
    result = LuaSynthesisAgent(client).synthesize(LuaSynthesisRequest(
        mode=LuaSynthesisMode.CREATE,
        scenario=scenario,
        user_requirement="生成海空反舰策略",
        baseline_strategy=baseline,
        runtime=LuaRuntimeProfile(RUNTIME_ID, RUNTIME_VERSION),
        allowed_strategy_paths=("/attacks", "/sorties"),
        output_dir=tmp_path,
    ))

    assert result.success is True
    assert result.strategy == baseline.strategy
    assert result.rendered_lua_path is not None and result.rendered_lua_path.is_file()
    assert result.generation_manifest_path is not None and result.generation_manifest_path.is_file()
    assert "score fragment" not in client.prompts[0].lower()


def test_synthesis_revise_applies_only_verified_leaf_patch(tmp_path: Path) -> None:
    from cmo_lua_agent.agents.lua_synthesis_agent import LuaSynthesisAgent, LuaSynthesisMode, LuaSynthesisRequest

    baseline_root, scenario, baseline = _baseline()
    attack = baseline.strategy.attacks[0]
    client = FakeJsonClient({"patches": [{
        "op": "replace", "path": "/attacks/0/fire_quantity",
        "expected_object_id": attack.attack_id, "value": attack.fire_quantity - 1,
    }], "change_summary": ["减少首个攻击任务的发射量"]})
    result = LuaSynthesisAgent(client).synthesize(LuaSynthesisRequest(
        mode=LuaSynthesisMode.REVISE,
        scenario=scenario,
        user_requirement="减少第一波发射量",
        current_strategy=baseline.strategy,
        runtime=LuaRuntimeProfile(RUNTIME_ID, RUNTIME_VERSION),
        allowed_strategy_paths=("/attacks/0/fire_quantity",),
        output_dir=tmp_path,
    ))

    assert result.success is True
    assert result.strategy is not None
    assert result.strategy.attacks[0].fire_quantity == attack.fire_quantity - 1
    assert result.strategy.attacks[1:] == baseline.strategy.attacks[1:]
    assert result.verified_changed_paths == ("/attacks/0/fire_quantity",)


@pytest.mark.parametrize("patch", [
    {"op": "replace", "path": "/attacks/0", "expected_object_id": "ignored", "value": {}},
    {"op": "replace", "path": "/attacks/0/fire_quantity", "expected_object_id": "wrong", "value": 1},
])
def test_synthesis_revise_rejects_non_leaf_and_wrong_stable_id(tmp_path: Path, patch: dict) -> None:
    from cmo_lua_agent.agents.lua_synthesis_agent import LuaSynthesisAgent, LuaSynthesisMode, LuaSynthesisRequest

    _, scenario, baseline = _baseline()
    result = LuaSynthesisAgent(FakeJsonClient({"patches": [patch], "change_summary": []})).synthesize(LuaSynthesisRequest(
        mode=LuaSynthesisMode.REVISE, scenario=scenario, user_requirement="修改", current_strategy=baseline.strategy,
        runtime=LuaRuntimeProfile(RUNTIME_ID, RUNTIME_VERSION), allowed_strategy_paths=("/attacks/0/fire_quantity",), output_dir=tmp_path,
    ))

    assert result.success is False
    assert not list(tmp_path.iterdir())


def test_synthesis_rejects_malformed_or_extra_create_output(tmp_path: Path) -> None:
    from cmo_lua_agent.agents.lua_synthesis_agent import LuaSynthesisAgent, LuaSynthesisMode, LuaSynthesisRequest

    _, scenario, baseline = _baseline()
    payload = {"strategy": {**baseline.strategy.to_dict(), "scenario": scenario.to_dict()}, "change_summary": []}
    result = LuaSynthesisAgent(FakeJsonClient(payload)).synthesize(LuaSynthesisRequest(
        mode=LuaSynthesisMode.CREATE, scenario=scenario, user_requirement="修改场景", baseline_strategy=baseline,
        runtime=LuaRuntimeProfile(RUNTIME_ID, RUNTIME_VERSION), allowed_strategy_paths=("/attacks",), output_dir=tmp_path,
    ))

    assert result.success is False
    assert result.failure_reason is not None
    assert not list(tmp_path.iterdir())


def test_repair_router_and_agent_return_registered_runtime_proposal_once() -> None:
    from cmo_lua_agent.agents.lua_repair_agent import LuaRepairAgent, LuaRepairRequest
    from cmo_lua_agent.agents.repair_models import RepairKind, RepairRoute, RuntimePatchRegistry

    baseline_root, scenario, baseline = _baseline()
    client = FakeJsonClient({"patch_kind": "retry_missing_contact_once", "operation_id": "contact.blue_cvn70", "parameters": {}, "agent_confidence": 0.6, "declared_semantic_impact": "仅增加一次受控重试"})
    request = LuaRepairRequest(
        route=RepairRoute.runtime_patch_eligible(), current_lua="-- generated\n", current_lua_checksum="abc",
        error=CmoError("lua_runtime_error", "contact unavailable", line=1), scenario=scenario,
        strategy=baseline.strategy, plan=_plan(baseline_root), generation_manifest={}, runtime=LuaRuntimeProfile(RUNTIME_ID, RUNTIME_VERSION),
        repair_history_summary=(), related_skills=(),
    )
    result = LuaRepairAgent(client, patch_registry=RuntimePatchRegistry.default()).repair(request)

    assert result.repair_kind is RepairKind.RUNTIME_PATCH_PROPOSAL
    assert result.patch is not None
    assert client.calls == 1
    assert result.retry_eligible is True


def test_repair_runtime_defect_and_not_applicable_do_not_call_llm() -> None:
    from cmo_lua_agent.agents.lua_repair_agent import LuaRepairAgent, LuaRepairRequest
    from cmo_lua_agent.agents.repair_models import RepairKind, RepairRoute

    baseline_root, scenario, baseline = _baseline()
    client = FakeJsonClient({})
    for route, expected in ((RepairRoute.runtime_defect("renderer syntax"), RepairKind.RUNTIME_DEFECT_REPORT), (RepairRoute.not_applicable("timeout"), RepairKind.NOT_APPLICABLE)):
        result = LuaRepairAgent(client).repair(LuaRepairRequest(
            route=route, current_lua="-- generated\n", current_lua_checksum="abc", error=CmoError("process_timeout", "timeout"),
            scenario=scenario, strategy=baseline.strategy, plan=_plan(baseline_root), generation_manifest={}, runtime=LuaRuntimeProfile(RUNTIME_ID, RUNTIME_VERSION), repair_history_summary=(), related_skills=(),
        ))
        assert result.repair_kind is expected
    assert client.calls == 0


def test_repair_error_router_keeps_retry_eligibility_deterministic() -> None:
    from cmo_lua_agent.agents.repair_models import RepairErrorRouter, RepairKind

    router = RepairErrorRouter()
    assert router.route(CmoError("process_timeout", "timeout")).kind is RepairKind.NOT_APPLICABLE
    assert router.route(CmoError("lua_syntax_error", "syntax error")).kind is RepairKind.RUNTIME_DEFECT_REPORT
    assert router.route(CmoError("lua_runtime_error", "contact unavailable")).kind is RepairKind.STRATEGY_PATCH
    assert router.route(CmoError("lua_runtime_error", "runtime compatibility missing contact")).kind is RepairKind.RUNTIME_PATCH_PROPOSAL


def test_repair_unknown_runtime_patch_is_rejected_without_application() -> None:
    from cmo_lua_agent.agents.lua_repair_agent import LuaRepairAgent, LuaRepairRequest
    from cmo_lua_agent.agents.repair_models import RepairKind, RepairRoute

    baseline_root, scenario, baseline = _baseline()
    client = FakeJsonClient({"patch_kind": "invented", "operation_id": "contact.blue_cvn70", "parameters": {}})
    result = LuaRepairAgent(client).repair(LuaRepairRequest(
        route=RepairRoute.runtime_patch_eligible(), current_lua="-- generated\n", current_lua_checksum="abc",
        error=CmoError("lua_runtime_error", "contact unavailable"), scenario=scenario,
        strategy=baseline.strategy, plan=_plan(baseline_root), generation_manifest={},
        runtime=LuaRuntimeProfile(RUNTIME_ID, RUNTIME_VERSION), repair_history_summary=(), related_skills=(),
    ))

    assert result.repair_kind is RepairKind.RUNTIME_DEFECT_REPORT
    assert result.retry_eligible is False
    assert client.calls == 1
