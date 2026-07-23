from __future__ import annotations

from pathlib import Path

import pytest

from cmo_lua_agent.agents.repair_models import RuntimePatchProposal
from cmo_lua_agent.contract import load_baseline_strategy, load_scenario_definition
from cmo_lua_agent.generation.phase32_scored_golden import Phase32ScoredGoldenService
from cmo_lua_agent.optimization.runtime_patch_applier import RuntimePatchApplier


def _golden():
    root = Path(__file__).resolve().parents[4] / "baseline" / "6v4"
    result = Phase32ScoredGoldenService().render(baseline_root=root)
    return result.plan, result.rendered


def _proposal(checksum: str, operation: str = "contact.blue_cvn70"):
    return RuntimePatchProposal("retry_missing_contact_once", operation, checksum, {}, ("missing_contact",))


def test_contact_patch_creates_new_plan_without_mutating_original() -> None:
    plan, rendered = _golden()
    patched, audit = RuntimePatchApplier().apply(candidate_id="c1", proposal=_proposal(rendered.lua_checksum), plan=plan, rendered=rendered, applied_keys=set())
    original = next(item for item in plan.operations if item.operation_id == "contact.blue_cvn70")
    changed = next(item for item in patched.operations if item.operation_id == "contact.blue_cvn70")
    assert "contact_retry_attempts" not in original.parameters
    assert changed.parameters["contact_retry_attempts"] == 1
    assert audit.old_plan_checksum == plan.checksum
    assert audit.new_plan_checksum == patched.checksum


@pytest.mark.parametrize("proposal", [
    lambda rendered: _proposal("wrong"),
    lambda rendered: _proposal(rendered.lua_checksum, "missing.operation"),
])
def test_contact_patch_rejects_bad_checksum_or_operation(proposal) -> None:
    plan, rendered = _golden()
    with pytest.raises(ValueError):
        RuntimePatchApplier().apply(candidate_id="c1", proposal=proposal(rendered), plan=plan, rendered=rendered, applied_keys=set())


def test_contact_patch_cannot_be_applied_twice() -> None:
    plan, rendered = _golden()
    keys: set[tuple[str, str]] = set()
    RuntimePatchApplier().apply(candidate_id="c1", proposal=_proposal(rendered.lua_checksum), plan=plan, rendered=rendered, applied_keys=keys)
    with pytest.raises(ValueError, match="runtime_patch_already_applied"):
        RuntimePatchApplier().apply(candidate_id="c1", proposal=_proposal(rendered.lua_checksum), plan=plan, rendered=rendered, applied_keys=keys)
