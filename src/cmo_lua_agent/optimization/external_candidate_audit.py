"""Static trust-boundary audit for external Phase 6 Lua fixtures."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from cmo_lua_agent.contract.strategy_models import ScenarioDefinition

_FORBIDDEN = ("ScenEdit_DestroyUnit", "ScenEdit_SetSidePosture", "ScenEdit_SetScore")


def audit_external_candidates(*, rendered_dir: Path, scenario: ScenarioDefinition,
                              official_runtime_checksum: str, official_fragment_checksum: str) -> dict[str, Any]:
    """Audit untrusted fixtures without treating manifest claims as facts."""
    rows: list[dict[str, Any]] = []
    facts = hashlib.sha256(json.dumps(scenario.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    for index in range(4):
        candidate_id = f"candidate_{index:02d}"
        lua_path = Path(rendered_dir) / f"{candidate_id}.lua"
        manifest_path = Path(rendered_dir) / f"{candidate_id}.manifest.json"
        lua = lua_path.read_text(encoding="utf-8")
        declared = json.loads(manifest_path.read_text(encoding="utf-8"))
        lua_checksum = hashlib.sha256(lua.encode("utf-8")).hexdigest()
        runtime = _section(lua, "local function runtime_log", "-- CMO native scoring instrumentation")
        fragment = _section(lua, "-- CMO native scoring instrumentation", "-- BEGIN OP")
        computed_runtime = hashlib.sha256(runtime.encode("utf-8")).hexdigest()
        computed_fragment = hashlib.sha256(fragment.encode("utf-8")).hexdigest()
        violations = [api for api in _FORBIDDEN if api in lua]
        declared_lua = declared.get("artifact", {}).get("lua_sha256")
        invariants = declared.get("invariants", {})
        rows.append({
            "candidate_id": candidate_id,
            "artifact_provenance": "external_fixture",
            "declared": {"lua_checksum": declared_lua, "runtime_invariant_checksum": invariants.get("runtime_invariant_sha256"), "native_score_fragment_checksum": invariants.get("native_score_fragment_sha256")},
            "computed": {"lua_checksum": lua_checksum, "runtime_invariant_checksum": computed_runtime, "native_score_fragment_checksum": computed_fragment, "scenario_unit_state_checksum": facts, "score_rule_bindings": _score_bindings(fragment)},
            "manifest_checksum_match": declared_lua == lua_checksum,
            "runtime_invariant_match": invariants.get("runtime_invariant_sha256") == computed_runtime == official_runtime_checksum,
            "native_score_fragment_match": invariants.get("native_score_fragment_sha256") == computed_fragment == official_fragment_checksum,
            "forbidden_change_detected": bool(violations), "audit_violations": violations,
            "formal_scoreable": False, "formal_comparison_eligible": False,
            "comparison_exclusion_reason": "score_contract_mismatch",
        })
    return {"artifact_provenance": "external_fixture", "candidates": rows}


def write_external_audit(*, output_path: Path, report: dict[str, Any]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", delete=False, dir=output_path.parent) as handle:
        json.dump(report, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")
        temp = handle.name
    os.replace(temp, output_path)


def _section(text: str, start: str, end: str) -> str:
    begin = text.find(start)
    if begin < 0:
        return ""
    finish = text.find(end, begin + len(start))
    return text[begin: finish if finish >= 0 else len(text)]


def _score_bindings(fragment: str) -> list[dict[str, str]]:
    """Canonical rule comparison surface: trigger, unit, side, points and bindings."""
    return [
        {"trigger": trigger, "unit": unit, "award_side": side, "points": points,
         "event": event, "action": action}
        for trigger, unit, side, points, event, action in re.findall(
            r'\["trigger_kind"\]="([^"]+)".*?\["target_unit_id"\]="([^"]+)".*?'
            r'\["score_side_id"\]="([^"]+)".*?\["point_change"\]=(-?\d+).*?'
            r'\["event_name"\]="([^"]+)".*?\["action_name"\]="([^"]+)"', fragment, re.S)
    ]
