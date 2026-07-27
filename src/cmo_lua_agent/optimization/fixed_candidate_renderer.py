"""Render the reviewed fixed Phase 6 proposal through the formal pipeline."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from cmo_lua_agent.contract import StrategyValidator, load_baseline_strategy, load_scenario_definition
from cmo_lua_agent.contract.strategy_models import strategy_spec_from_dict
from cmo_lua_agent.generation.capability_validator import CapabilityValidator
from cmo_lua_agent.generation.execution_plan_compiler import ExecutionPlanCompiler
from cmo_lua_agent.generation.runtime_models import LuaRuntimeProfile, canonical_sha256
from cmo_lua_agent.generation.runtime_primitives import runtime_primitive_registry_for
from cmo_lua_agent.generation.scored_lua_assembly import SCORED_RUNTIME_ID, SCORED_RUNTIME_VERSION, ScoredLuaAssemblyService
from cmo_lua_agent.optimization.candidate_set_validator import CandidateSetValidator, strategy_leaf_diff
from cmo_lua_agent.optimization.phase6_models import StrategyCandidate
from cmo_lua_agent.scoring.baseline import compile_score_baseline

_ALLOWED = (
    "/attacks/0/target_ids/0", "/attacks/0/fire_quantity", "/attacks/0/delay_seconds", "/attacks/0/reserve_quantity",
    "/attacks/1/target_ids/0", "/attacks/1/fire_quantity", "/attacks/1/delay_seconds", "/attacks/1/reserve_quantity",
    "/attacks/2/target_ids/0", "/attacks/2/fire_quantity", "/attacks/2/delay_seconds", "/attacks/2/reserve_quantity",
    "/attacks/3/target_ids/0", "/attacks/3/fire_quantity", "/attacks/4/target_ids/0", "/attacks/4/fire_quantity",
    "/sorties/0/target_id", "/sorties/0/fire_delay_seconds", "/sorties/1/target_id", "/sorties/1/fire_delay_seconds",
)


class FixedCandidateRenderer:
    def render(self, *, baseline_root: Path) -> dict[str, Any]:
        root = Path(baseline_root)
        proposal = json.loads((root / "phase6" / "fixed_strategy_proposal.json").read_text(encoding="utf-8"))
        scenario = load_scenario_definition(root / "scenario_definition.json")
        baseline = load_baseline_strategy(root / "baseline_strategy.json")
        candidates = tuple(StrategyCandidate(row["candidate_id"], strategy_spec_from_dict(row["strategy"]), row["proposal_summary"], tuple(row["intended_difference"])) for row in proposal["candidates"])
        set_report = CandidateSetValidator().validate(scenario=scenario, baseline=baseline.strategy, candidates=candidates, allowed_paths=_ALLOWED, diversity_dimensions=("target_assignment", "attack_timing", "fire_quantity", "ammunition_reserve"))
        if not set_report.diversity_report.valid:
            raise ValueError("fixed proposal failed validation")
        runtime = LuaRuntimeProfile(SCORED_RUNTIME_ID, SCORED_RUNTIME_VERSION)
        score = compile_score_baseline(root).compilation
        output = root / "phase6" / "formal_rendered"
        output.mkdir(parents=True, exist_ok=True)
        report: list[dict[str, Any]] = []
        for candidate in candidates:
            validation = StrategyValidator().validate(candidate.strategy_spec, scenario)
            if not validation.valid:
                raise ValueError(f"invalid candidate {candidate.candidate_id}")
            compiled = ExecutionPlanCompiler().compile(scenario=scenario, strategy=candidate.strategy_spec, runtime=runtime)
            if compiled.plan is None:
                raise ValueError(f"capability gap for {candidate.candidate_id}")
            capability = CapabilityValidator(runtime_primitive_registry_for(runtime.runtime_id, runtime.runtime_version)).validate(plan=compiled.plan, runtime=runtime)
            if not capability.is_valid:
                raise ValueError(f"invalid plan for {candidate.candidate_id}")
            assembled = ScoredLuaAssemblyService().render(scenario=scenario, strategy=candidate.strategy_spec, plan=compiled.plan, runtime=runtime, native_score_compilation=score)
            candidate_dir = output / candidate.candidate_id
            _write(candidate_dir / "candidate.lua", assembled.rendered.content)
            _write_json(candidate_dir / "strategy_spec.json", candidate.strategy_spec.to_dict())
            _write_json(candidate_dir / "execution_plan.json", assembled.plan.to_dict())
            _write_json(candidate_dir / "generation_manifest.json", assembled.generation_manifest)
            _write_json(candidate_dir / "strategy_diff.json", {"paths": list(strategy_leaf_diff(baseline.strategy, candidate.strategy_spec, _ALLOWED))})
            report.append({"candidate_id": candidate.candidate_id, "artifact_provenance": "formal_renderer", "strategy_checksum": candidate.strategy_checksum, "execution_plan_checksum": assembled.plan.checksum, "lua_checksum": assembled.rendered.lua_checksum, "score_fragment_checksum": score.fragment_checksum, "runtime_version": runtime.runtime_version})
        _write_json(root / "phase6" / "candidate_render_report.json", {"candidates": report, "diversity_report": set_report.diversity_report.to_dict()})
        return {"candidates": report}


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", delete=False, dir=path.parent) as handle:
        handle.write(value)
        temp = handle.name
    os.replace(temp, path)


def _write_json(path: Path, value: Any) -> None:
    _write(path, json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
