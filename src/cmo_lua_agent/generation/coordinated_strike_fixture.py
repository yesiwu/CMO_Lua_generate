"""Build the checked-in coordinated-strike regression through the formal chain."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from cmo_lua_agent.contract import StrategyValidator
from cmo_lua_agent.contract.baseline_strategy_builder import BaselineStrategyBuilder
from cmo_lua_agent.contract.models import ValidationResult
from cmo_lua_agent.contract.strategy_models import StrategySpec
from cmo_lua_agent.generation.capability_validator import CapabilityValidator
from cmo_lua_agent.generation.execution_plan_compiler import ExecutionPlanCompiler
from cmo_lua_agent.generation.runtime_models import (
    ExecutionPlan,
    LuaRuntimeProfile,
    RenderedLua,
    canonical_sha256,
)
from cmo_lua_agent.generation.runtime_primitives import runtime_primitive_registry_for
from cmo_lua_agent.generation.scored_lua_assembly import (
    SCORED_RUNTIME_ID,
    SCORED_RUNTIME_VERSION,
    ScoredLuaAssemblyService,
)
from cmo_lua_agent.optimization.proposal_models import (
    CandidatePatch,
    ProposalContractError,
    StrategyPatchOperation,
)
from cmo_lua_agent.optimization.strategy_dimensions import semantic_dimensions
from cmo_lua_agent.optimization.strategy_patch import (
    StrategyPatchAssembler,
    build_patchable_leaf_catalog,
)
from cmo_lua_agent.scoring.baseline import compile_score_baseline


_PATCH_RELATIVE_PATH = Path("baseline/6v4/regressions/coordinated-strike-patch.json")
_COORDINATED_STRIKE_ALLOWED_PATHS = (
    "/attacks/0/delay_seconds",
    "/attacks/0/fire_quantity",
    "/attacks/0/target_ids/0",
    "/attacks/1/delay_seconds",
    "/attacks/1/fire_quantity",
    "/attacks/1/target_ids/0",
    "/attacks/2/delay_seconds",
    "/attacks/2/fire_quantity",
    "/attacks/2/target_ids/0",
    "/sorties/0/route/0/latitude",
    "/sorties/1/route/0/longitude",
)


@dataclass(frozen=True, slots=True)
class CoordinatedStrikeFixtureResult:
    strategy: StrategySpec
    plan: ExecutionPlan
    rendered: RenderedLua
    validation: ValidationResult
    assembler: StrategyPatchAssembler
    changed_paths: tuple[str, ...]
    semantic_dimensions: tuple[str, ...]
    changed_operation_ids: tuple[str, ...]
    changed_platform_ids: tuple[str, ...]
    surface_operation_count: int
    sortie_operation_count: int
    manifest: dict[str, Any]


def load_coordinated_strike_patch(project_root: Path) -> CandidatePatch:
    path = Path(project_root).resolve() / _PATCH_RELATIVE_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) != {
        "candidate_id", "proposal_summary", "changes"
    }:
        raise ProposalContractError("coordinated_strike_patch_schema_invalid")
    changes = payload["changes"]
    if not isinstance(changes, list):
        raise ProposalContractError("coordinated_strike_patch_schema_invalid")
    try:
        return CandidatePatch(
            candidate_id=payload["candidate_id"],
            proposal_summary=payload["proposal_summary"],
            changes=tuple(
                StrategyPatchOperation(path=item["path"], value=item["value"])
                for item in changes
                if isinstance(item, dict) and set(item) == {"path", "value"}
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ProposalContractError("coordinated_strike_patch_schema_invalid") from exc


def build_coordinated_strike_fixture(
    project_root: Path, *, patch: CandidatePatch | None = None
) -> CoordinatedStrikeFixtureResult:
    root = Path(project_root).resolve()
    baseline_root = root / "baseline" / "6v4"
    scenario_ir_path = root / "json_data" / "6v4ScenarioIR.json"
    scenario_ir = json.loads(scenario_ir_path.read_text(encoding="utf-8"))
    derived = BaselineStrategyBuilder().build(scenario_ir)
    selected_patch = patch or load_coordinated_strike_patch(root)
    catalog = build_patchable_leaf_catalog(
        baseline=derived.strategy,
        scenario=derived.scenario,
        allowed_paths=_COORDINATED_STRIKE_ALLOWED_PATHS,
    )
    assembler = StrategyPatchAssembler(baseline=derived.strategy, catalog=catalog)
    assembled = assembler.assemble(selected_patch)
    _validate_coordinated_strike(assembled.strategy)
    validation = StrategyValidator().validate(
        strategy=assembled.strategy, scenario_definition=derived.scenario
    )
    if not validation.valid:
        raise ProposalContractError("coordinated_strike_strategy_invalid")
    runtime = LuaRuntimeProfile(SCORED_RUNTIME_ID, SCORED_RUNTIME_VERSION)
    compiled = ExecutionPlanCompiler().compile(
        scenario=derived.scenario, strategy=assembled.strategy, runtime=runtime
    )
    if compiled.plan is None:
        raise ProposalContractError("coordinated_strike_capability_gap")
    capability = CapabilityValidator(
        runtime_primitive_registry_for(runtime.runtime_id, runtime.runtime_version)
    ).validate(plan=compiled.plan, runtime=runtime)
    if not capability.is_valid:
        raise ProposalContractError("coordinated_strike_plan_invalid")
    score = compile_score_baseline(baseline_root, scenario=derived.scenario).compilation
    rendered = ScoredLuaAssemblyService().render(
        scenario=derived.scenario,
        strategy=assembled.strategy,
        plan=compiled.plan,
        runtime=runtime,
        native_score_compilation=score,
    )
    changed_operation_ids, changed_platform_ids = _changed_operations(
        assembled.changed_paths, assembled.strategy
    )
    surface_operation_count, sortie_operation_count = _changed_operation_counts(
        assembled.changed_paths
    )
    manifest = {
        "source_scenario_ir_checksum": derived.manifest.scenario_ir_checksum,
        "derived_baseline_checksum": derived.manifest.baseline_strategy_checksum,
        "patch_checksum": canonical_sha256(_patch_to_dict(selected_patch)),
        "strategy_checksum": canonical_sha256(assembled.strategy.to_dict()),
        "execution_plan_checksum": rendered.plan.checksum,
        "lua_checksum": rendered.rendered.lua_checksum,
        "runtime_version": runtime.runtime_version,
        "score_spec_checksum": score.score_spec_checksum,
        "native_score_fragment_checksum": score.fragment_checksum,
        "changed_operation_ids": list(changed_operation_ids),
        "changed_platform_ids": list(changed_platform_ids),
        "semantic_dimensions": list(semantic_dimensions(assembled.changed_paths)),
        "surface_operation_count": surface_operation_count,
        "sortie_operation_count": sortie_operation_count,
        "formal_comparison_eligible": False,
        "fixture_purpose": "formal_chain_expression_regression",
    }
    return CoordinatedStrikeFixtureResult(
        strategy=assembled.strategy,
        plan=rendered.plan,
        rendered=rendered.rendered,
        validation=validation,
        assembler=assembler,
        changed_paths=assembled.changed_paths,
        semantic_dimensions=semantic_dimensions(assembled.changed_paths),
        changed_operation_ids=changed_operation_ids,
        changed_platform_ids=changed_platform_ids,
        surface_operation_count=surface_operation_count,
        sortie_operation_count=sortie_operation_count,
        manifest=manifest,
    )


def _patch_to_dict(patch: CandidatePatch) -> dict[str, Any]:
    return {
        "candidate_id": patch.candidate_id,
        "proposal_summary": patch.proposal_summary,
        "changes": [
            {"path": change.path, "value": change.value}
            for change in patch.changes
        ],
    }


def _changed_operations(
    paths: tuple[str, ...], strategy: StrategySpec
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    operation_ids: set[str] = set()
    platform_ids: set[str] = set()
    for path in paths:
        parts = path.split("/")
        if len(parts) < 3:
            raise ProposalContractError("coordinated_strike_patch_path_invalid")
        if parts[1] == "attacks":
            attack = strategy.attacks[int(parts[2])]
            operation_ids.add(f"attack.{attack.attack_id}")
            platform_ids.add(attack.shooter_id)
        elif parts[1] == "sorties":
            sortie = strategy.sorties[int(parts[2])]
            operation_ids.add(f"air_launch.{sortie.sortie_id}")
            platform_ids.add(sortie.aircraft_id)
        else:
            raise ProposalContractError("coordinated_strike_patch_path_invalid")
    return tuple(sorted(operation_ids)), tuple(sorted(platform_ids))


def _changed_operation_counts(paths: tuple[str, ...]) -> tuple[int, int]:
    surface = {
        path.split("/")[2] for path in paths if path.startswith("/attacks/")
    }
    sorties = {
        path.split("/")[2] for path in paths if path.startswith("/sorties/")
    }
    return len(surface), len(sorties)


def _validate_coordinated_strike(strategy: StrategySpec) -> None:
    surface = strategy.attacks[:3]
    targets = tuple(attack.target_ids[0] for attack in surface)
    delays = tuple(attack.delay_seconds for attack in surface)
    if len(set(targets)) != 3:
        raise ProposalContractError("coordinated_strike_target_deconfliction_failed")
    if len(set(delays)) != 3:
        raise ProposalContractError("coordinated_strike_delay_deconfliction_failed")
