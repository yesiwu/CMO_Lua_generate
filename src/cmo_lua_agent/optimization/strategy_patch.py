"""Deep JSON-Pointer assembly for the formal proposal path."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from cmo_lua_agent.contract.strategy_models import ScenarioDefinition, StrategySpec, strategy_spec_from_dict
from cmo_lua_agent.optimization.candidate_set_validator import strategy_leaf_diff
from cmo_lua_agent.optimization.proposal_models import AssembledStrategyPatch, CandidatePatch, JsonScalar, ProposalContractError


_STABLE_FIELD_NAMES = {"scenario_id", "attack_id", "sortie_id", "shooter_id", "aircraft_id", "base_unit_id", "weapon_dbid"}


@dataclass(frozen=True, slots=True)
class PatchableLeaf:
    path: str
    current_value: JsonScalar
    value_type: str
    minimum: int | float | None = None
    maximum: int | float | None = None
    allowed_values: tuple[JsonScalar, ...] = ()

    def to_prompt_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "path": self.path,
            "current_value": self.current_value,
            "value_type": self.value_type,
        }
        if self.minimum is not None:
            payload["minimum"] = self.minimum
        if self.maximum is not None:
            payload["maximum"] = self.maximum
        if self.allowed_values:
            payload["allowed_values"] = list(self.allowed_values)
        return payload


def build_patchable_leaf_catalog(*, baseline: StrategySpec, scenario: ScenarioDefinition, allowed_paths: tuple[str, ...]) -> tuple[PatchableLeaf, ...]:
    """Expose only concrete scalar leaves and deterministic safe constraints."""
    if baseline.scenario_id != scenario.scenario_id:
        raise ProposalContractError("scenario_baseline_mismatch")
    payload = baseline.to_dict()
    units = scenario.unit_by_id()
    catalog: list[PatchableLeaf] = []
    for path in sorted(set(allowed_paths)):
        tokens = _tokens(path)
        if not tokens or tokens[-1] in _STABLE_FIELD_NAMES:
            raise ProposalContractError("stable_field_not_patchable")
        value = _get(payload, tokens)
        if type(value) not in (str, int, float, bool):
            raise ProposalContractError("patch_path_not_scalar")
        catalog.append(_leaf_constraint(path, value, payload, units))
    if len(catalog) != len(allowed_paths):
        raise ProposalContractError("duplicate_allowed_patch_path")
    return tuple(catalog)


class StrategyPatchAssembler:
    def __init__(self, *, baseline: StrategySpec, catalog: tuple[PatchableLeaf, ...]) -> None:
        self._baseline = baseline
        self._catalog = {leaf.path: leaf for leaf in catalog}

    @property
    def catalog(self) -> tuple[PatchableLeaf, ...]:
        return tuple(self._catalog[path] for path in sorted(self._catalog))

    def assemble(self, patch: CandidatePatch) -> AssembledStrategyPatch:
        payload = deepcopy(self._baseline.to_dict())
        expected_paths: list[str] = []
        for operation in patch.changes:
            leaf = self._catalog.get(operation.path)
            if leaf is None:
                raise ProposalContractError("path_not_catalogued")
            if type(operation.value) is not type(leaf.current_value):
                raise ProposalContractError("scalar_type_mismatch")
            self._validate_value(leaf, operation.value)
            if operation.value == leaf.current_value:
                raise ProposalContractError("no_effective_change")
            _set(payload, _tokens(operation.path), operation.value)
            expected_paths.append(operation.path)
        try:
            strategy = strategy_spec_from_dict(payload)
        except (KeyError, TypeError, ValueError) as error:
            raise ProposalContractError("strategy_rebuild_failed", str(error)) from error
        actual_paths = strategy_leaf_diff(self._baseline, strategy, tuple(self._catalog))
        if tuple(sorted(expected_paths)) != actual_paths:
            raise ProposalContractError("actual_diff_mismatch")
        return AssembledStrategyPatch(strategy=strategy, changed_paths=actual_paths)

    @staticmethod
    def _validate_value(leaf: PatchableLeaf, value: JsonScalar) -> None:
        if leaf.allowed_values and value not in leaf.allowed_values:
            raise ProposalContractError("value_not_allowed")
        if leaf.minimum is not None and value < leaf.minimum:  # type: ignore[operator]
            raise ProposalContractError("value_below_minimum")
        if leaf.maximum is not None and value > leaf.maximum:  # type: ignore[operator]
            raise ProposalContractError("value_above_maximum")


def _leaf_constraint(path: str, value: JsonScalar, payload: dict[str, Any], units: dict[str, Any]) -> PatchableLeaf:
    tokens = _tokens(path)
    if tokens[-1] in {"latitude", "longitude"}:
        return PatchableLeaf(path, value, type(value).__name__, -90 if tokens[-1] == "latitude" else -180, 90 if tokens[-1] == "latitude" else 180)
    if tokens[-1] in {"delay_seconds", "fire_delay_seconds", "return_delay_seconds"}:
        return PatchableLeaf(path, value, type(value).__name__, 0, 86400)
    if tokens[-1] in {"fire_quantity", "reserve_quantity"}:
        maximum = _quantity_maximum(tokens, payload, units)
        return PatchableLeaf(path, value, type(value).__name__, 0, maximum)
    if tokens[-1] in {"target_id"} or "target_ids" in tokens:
        allowed = _enemy_targets(tokens, payload, units)
        return PatchableLeaf(path, value, type(value).__name__, allowed_values=allowed)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return PatchableLeaf(path, value, type(value).__name__, 0, 86400)
    return PatchableLeaf(path, value, type(value).__name__)


def _quantity_maximum(tokens: list[str], payload: dict[str, Any], units: dict[str, Any]) -> int:
    try:
        index = int(tokens[1])
        attack = payload["attacks"][index]
        unit = units[attack["shooter_id"]]
        inventory = next(item for item in unit.weapon_inventory if item.weapon_dbid == attack["weapon_dbid"])
        if tokens[-1] == "fire_quantity":
            return inventory.max_quantity - attack["reserve_quantity"]
        return inventory.max_quantity - attack["fire_quantity"]
    except (IndexError, KeyError, StopIteration, ValueError):
        raise ProposalContractError("inventory_constraint_unavailable") from None


def _enemy_targets(tokens: list[str], payload: dict[str, Any], units: dict[str, Any]) -> tuple[str, ...]:
    try:
        if tokens[0] == "attacks":
            owner_id = payload["attacks"][int(tokens[1])]["shooter_id"]
        else:
            owner_id = payload["sorties"][int(tokens[1])]["aircraft_id"]
        owner_side = units[owner_id].side_id
    except (IndexError, KeyError, ValueError):
        raise ProposalContractError("target_constraint_unavailable") from None
    return tuple(sorted(unit_id for unit_id, unit in units.items() if unit.side_id != owner_side))


def _tokens(path: str) -> list[str]:
    if not isinstance(path, str) or not path.startswith("/") or path == "/":
        raise ProposalContractError("invalid_patch_pointer")
    return [token.replace("~1", "/").replace("~0", "~") for token in path[1:].split("/")]


def _get(payload: Any, tokens: list[str]) -> Any:
    current = payload
    for token in tokens:
        if isinstance(current, list):
            if not token.isdecimal():
                raise ProposalContractError("invalid_array_index")
            try:
                current = current[int(token)]
            except IndexError as error:
                raise ProposalContractError("patch_path_out_of_bounds") from error
        elif isinstance(current, dict):
            if token not in current:
                raise ProposalContractError("patch_path_out_of_bounds")
            current = current[token]
        else:
            raise ProposalContractError("patch_path_out_of_bounds")
    return current


def _set(payload: Any, tokens: list[str], value: JsonScalar) -> None:
    parent = _get(payload, tokens[:-1])
    token = tokens[-1]
    if isinstance(parent, list):
        if not token.isdecimal() or int(token) >= len(parent):
            raise ProposalContractError("patch_path_out_of_bounds")
        parent[int(token)] = value
    elif isinstance(parent, dict):
        if token not in parent:
            raise ProposalContractError("patch_path_out_of_bounds")
        parent[token] = value
    else:
        raise ProposalContractError("patch_path_out_of_bounds")
