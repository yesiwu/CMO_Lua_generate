"""Resolve a generation's rolling baseline from the preceding Champion."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from cmo_lua_agent.contract.strategy_models import BaselineStrategy, strategy_spec_from_dict


@dataclass(frozen=True, slots=True)
class ResolvedRollingBaseline:
    """某一代 Preview 必须使用的已解析滚动基线引用及其来源证据。"""
    source_generation_index: int
    champion_id: str
    strategy_path: Path
    strategy: dict[str, Any]


class RollingBaselineResolver:
    """Read only persisted Campaign results; never infer a Champion."""

    def __init__(self, campaign_root: Path) -> None:
        self._root = Path(campaign_root).resolve()

    def resolve_for_generation(self, generation_index: int) -> ResolvedRollingBaseline:
        if generation_index < 1:
            raise ValueError("rolling_baseline_not_applicable")
        previous = generation_index - 1
        generation_root = self._root / "generations" / f"generation_{previous:03d}"
        result_path = generation_root / "generation-result.json"
        if not result_path.is_file():
            raise ValueError("previous_generation_result_missing")
        result = self._load_object(result_path, "previous_generation_result_invalid")
        decision = result.get("champion_decision")
        if not isinstance(decision, dict):
            raise ValueError("previous_generation_champion_missing")
        champion_id = decision.get("selected_champion_id")
        if not isinstance(champion_id, str) or not champion_id:
            raise ValueError("previous_generation_champion_missing")
        directory = "candidate_baseline" if champion_id == "baseline" else champion_id
        strategy_path = (
            generation_root / "phase6" / directory / "strategy" / "final_strategy.json"
        )
        if not strategy_path.is_file():
            raise ValueError("previous_champion_strategy_missing")
        return ResolvedRollingBaseline(
            source_generation_index=previous,
            champion_id=champion_id,
            strategy_path=strategy_path,
            strategy=self._load_object(strategy_path, "previous_champion_strategy_invalid"),
        )

    @staticmethod
    def _load_object(path: Path, error_code: str) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(error_code) from exc
        if not isinstance(value, dict):
            raise ValueError(error_code)
        return value


def apply_rolling_baseline(package: Any, resolved: ResolvedRollingBaseline) -> Any:
    """Return a package copy whose baseline is the preceding Champion.

    The source package is not mutated.  Scenario, score contract, renderer and
    controlled asset remain the same for the next generation.
    """
    if not hasattr(package, "baseline"):
        raise ValueError("campaign_package_baseline_missing")
    baseline = BaselineStrategy(
        strategy=strategy_spec_from_dict(resolved.strategy),
        source_lua=str(resolved.strategy_path),
        verified=True,
    )
    try:
        return replace(package, baseline=baseline)
    except TypeError as exc:
        raise ValueError("campaign_package_not_replaceable") from exc
