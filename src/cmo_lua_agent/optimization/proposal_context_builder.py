"""Build the compact, deterministic tactical context allowed into proposal prompts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cmo_lua_agent.contract.strategy_models import ScenarioDefinition, StrategySpec
from cmo_lua_agent.generation.runtime_models import canonical_json, canonical_sha256
from cmo_lua_agent.optimization.proposal_models import (
    AcceptedCandidateSummary,
    CandidateRoleSpec,
)
from cmo_lua_agent.optimization.strategy_dimensions import semantic_dimension
from cmo_lua_agent.optimization.strategy_patch import PatchableLeaf


def _operation_key(path: str) -> str | None:
    tokens = path.strip("/").split("/")
    if len(tokens) >= 2 and tokens[0] in {"attacks", "sorties"} and tokens[1].isdecimal():
        return f"{tokens[0]}/{tokens[1]}"
    return None


@dataclass(frozen=True, slots=True)
class ProposalTacticalContext:
    scenario_summary: dict[str, object]
    baseline_operations: tuple[dict[str, object], ...]
    target_summary: tuple[dict[str, object], ...]
    coupling_groups: dict[str, object]
    role_requirements: tuple[dict[str, object], ...]
    accepted_candidate_summaries: tuple[dict[str, object], ...]
    failure_profile: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "scenario_summary": self.scenario_summary,
            "baseline_operations": list(self.baseline_operations),
            "target_summary": list(self.target_summary),
            "coupling_groups": self.coupling_groups,
            "role_requirements": list(self.role_requirements),
            "accepted_candidate_summaries": list(self.accepted_candidate_summaries),
            "failure_profile": self.failure_profile,
        }

    @property
    def canonical_json(self) -> str:
        return canonical_json(self.to_dict())

    @property
    def checksum(self) -> str:
        return canonical_sha256(self.to_dict())


class ProposalTacticalContextBuilder:
    """A pure projection; never exposes strategy, Lua, scoring, or raw evidence."""

    def build(
        self,
        *,
        scenario: ScenarioDefinition,
        baseline: StrategySpec,
        patch_catalog: tuple[PatchableLeaf, ...],
        role_specs: tuple[CandidateRoleSpec, ...],
        accepted_candidates: tuple[AcceptedCandidateSummary, ...],
    ) -> ProposalTacticalContext:
        if scenario.scenario_id != baseline.scenario_id:
            raise ValueError("scenario_baseline_mismatch")
        units = scenario.unit_by_id()
        paths_by_operation: dict[str, list[PatchableLeaf]] = {}
        for leaf in patch_catalog:
            operation = _operation_key(leaf.path)
            if operation is not None:
                paths_by_operation.setdefault(operation, []).append(leaf)

        operations: list[dict[str, object]] = []
        stable_operation_ids: dict[str, str] = {}
        for index, attack in enumerate(baseline.attacks):
            operation_key = f"attacks/{index}"
            stable_operation_ids[operation_key] = f"surface_attack:{attack.attack_id}"
            operations.append(
                self._surface_operation(
                    operation_key=operation_key,
                    operation_id=stable_operation_ids[operation_key],
                    platform=units[attack.shooter_id],
                    target_id=attack.target_ids[0],
                    delay_seconds=attack.delay_seconds,
                    fire_quantity=attack.fire_quantity,
                    reserve_quantity=attack.reserve_quantity,
                    weapon_selection=attack.weapon_selection,
                    leaves=paths_by_operation.get(operation_key, []),
                )
            )
        for index, sortie in enumerate(baseline.sorties):
            operation_key = f"sorties/{index}"
            stable_operation_ids[operation_key] = f"sortie:{sortie.sortie_id}"
            operations.append(
                self._sortie_operation(
                    operation_key=operation_key,
                    operation_id=stable_operation_ids[operation_key],
                    platform=units[sortie.aircraft_id],
                    target_id=sortie.target_id,
                    delay_seconds=sortie.fire_delay_seconds,
                    return_delay_seconds=sortie.return_delay_seconds,
                    leaves=paths_by_operation.get(operation_key, []),
                    route=sortie.route,
                )
            )
        operations.sort(key=lambda item: str(item["operation_id"]))
        target_summary = self._target_summary(scenario, operations)
        return ProposalTacticalContext(
            scenario_summary=self._scenario_summary(scenario),
            baseline_operations=tuple(operations),
            target_summary=target_summary,
            coupling_groups=self._coupling_groups(operations),
            role_requirements=tuple(self._role_requirement(item) for item in role_specs),
            accepted_candidate_summaries=tuple(
                self._accepted_summary(item, stable_operation_ids)
                for item in accepted_candidates
            ),
            failure_profile=self._failure_profile(role_specs),
        )

    @staticmethod
    def _scenario_summary(scenario: ScenarioDefinition) -> dict[str, object]:
        by_side: dict[str, list[dict[str, str]]] = {}
        for unit in sorted(scenario.units, key=lambda item: (item.side_id, item.unit_id)):
            by_side.setdefault(unit.side_id, []).append(
                {"unit_id": unit.unit_id, "platform_type": unit.platform_type}
            )
        sides = sorted(by_side)
        return {
            "scenario_id": scenario.scenario_id,
            "red_side_id": "red" if "red" in by_side else None,
            "blue_side_id": "blue" if "blue" in by_side else None,
            "sides": {side: by_side[side] for side in sides},
        }

    @staticmethod
    def _surface_operation(**values: Any) -> dict[str, object]:
        leaves = values.pop("leaves")
        platform = values.pop("platform")
        return {
            "operation_id": values["operation_id"],
            "operation_type": "surface_attack",
            "platform_id": platform.unit_id,
            "platform_type": platform.platform_type,
            "current_target_id": values["target_id"],
            "delay_seconds": values["delay_seconds"],
            "fire_quantity": values["fire_quantity"],
            "reserve_quantity": values["reserve_quantity"],
            "weapon_selection": values["weapon_selection"],
            "patchable_dimensions": sorted({semantic_dimension(leaf.path) for leaf in leaves}),
            "patchable_paths": sorted(leaf.path for leaf in leaves),
        }

    @staticmethod
    def _sortie_operation(**values: Any) -> dict[str, object]:
        leaves = values.pop("leaves")
        platform = values.pop("platform")
        route = values.pop("route")
        return {
            "operation_id": values["operation_id"],
            "operation_type": "sortie",
            "platform_id": platform.unit_id,
            "platform_type": platform.platform_type,
            "current_target_id": values["target_id"],
            "delay_seconds": values["delay_seconds"],
            "fire_quantity": None,
            "reserve_quantity": None,
            "weapon_selection": "auto",
            "route_summary": {
                "waypoint_count": len(route),
                "first": {"latitude": route[0].latitude, "longitude": route[0].longitude},
                "last": {"latitude": route[-1].latitude, "longitude": route[-1].longitude},
                "return_delay_seconds": values["return_delay_seconds"],
            },
            "patchable_dimensions": sorted({semantic_dimension(leaf.path) for leaf in leaves}),
            "patchable_paths": sorted(leaf.path for leaf in leaves),
        }

    @staticmethod
    def _target_summary(
        scenario: ScenarioDefinition, operations: list[dict[str, object]]
    ) -> tuple[dict[str, object], ...]:
        assignments: dict[str, list[str]] = {}
        for operation in operations:
            assignments.setdefault(str(operation["current_target_id"]), []).append(
                str(operation["operation_id"])
            )
        return tuple(
            {
                "target_id": unit.unit_id,
                "platform_type": unit.platform_type,
                "current_assignment_operations": sorted(assignments.get(unit.unit_id, [])),
                "current_assignment_count": len(assignments.get(unit.unit_id, [])),
            }
            for unit in sorted(scenario.units, key=lambda item: item.unit_id)
            if unit.side_id == "blue"
        )

    @staticmethod
    def _coupling_groups(operations: list[dict[str, object]]) -> dict[str, object]:
        by_target: dict[str, list[str]] = {}
        by_platform: dict[str, list[str]] = {}
        surface: list[str] = []
        sortie: list[str] = []
        for operation in operations:
            operation_id = str(operation["operation_id"])
            by_target.setdefault(str(operation["current_target_id"]), []).append(operation_id)
            by_platform.setdefault(str(operation["platform_id"]), []).append(operation_id)
            (surface if operation["operation_type"] == "surface_attack" else sortie).append(operation_id)
        return {
            "same_target_operations": {
                target: sorted(values) for target, values in sorted(by_target.items())
            },
            "same_platform_operations": {
                platform: sorted(values) for platform, values in sorted(by_platform.items())
            },
            "surface_operations": sorted(surface),
            "sortie_operations": sorted(sortie),
        }

    @staticmethod
    def _role_requirement(spec: CandidateRoleSpec) -> dict[str, object]:
        return {
            "candidate_id": spec.candidate_id,
            "role": spec.role,
            "min_changed_leaves": spec.min_changed_leaves,
            "max_changed_leaves": spec.max_changed_leaves,
            "min_operations": spec.min_operations,
            "min_dimensions": spec.min_dimensions,
            "require_surface": spec.require_surface,
            "require_sortie": spec.require_sortie,
        }

    @staticmethod
    def _accepted_summary(
        summary: AcceptedCandidateSummary, stable_operation_ids: dict[str, str]
    ) -> dict[str, object]:
        return {
            "candidate_id": summary.candidate_id,
            "changed_operation_ids": sorted(
                stable_operation_ids.get(value, value)
                for value in summary.changed_operation_ids
            ),
            "semantic_dimensions": sorted(summary.strategy_dimensions),
            "changed_paths": sorted(summary.changed_paths),
            "target_assignment_summary": sorted(summary.target_assignment_summary),
        }

    @staticmethod
    def _failure_profile(role_specs: tuple[CandidateRoleSpec, ...]) -> dict[str, object]:
        repair = next(item for item in role_specs if item.candidate_id == "candidate_01")
        if repair.failure_profile_mode != "required":
            return {
                "available": False,
                "source_checksum": None,
                "operation_ids": [],
                "semantic_dimensions": [],
            }
        return {
            "available": True,
            "source_checksum": repair.failure_profile_source_checksum,
            "operation_ids": sorted(repair.failure_operation_ids),
            "semantic_dimensions": sorted(repair.failure_semantic_dimensions),
        }
