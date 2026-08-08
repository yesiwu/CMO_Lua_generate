"""Resolve a user supplied ScenarioIR into a restartable Campaign reference."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from cmo_lua_agent.contract.baseline_strategy_builder import BaselineStrategyBuilder


@dataclass(frozen=True, slots=True)
class ResolvedScenarioInput:
    """Validated ScenarioIR identity retained in a Training request."""

    reference: str
    absolute_path: Path
    scenario_id: str


class ScenarioInputResolver:
    """Validate compatible ScenarioIR input without copying or mutating it."""

    def __init__(self, project_root: Path) -> None:
        self._project_root = Path(project_root).resolve()

    def resolve(self, path: str | Path) -> ResolvedScenarioInput:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self._project_root / candidate
        candidate = candidate.resolve()
        if not candidate.is_file():
            raise ValueError("scenario_ir_not_found")
        if candidate.suffix.lower() != ".json":
            raise ValueError("scenario_ir_json_required")
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            raise ValueError("scenario_ir_invalid_json") from exc
        if not isinstance(payload, dict):
            raise ValueError("scenario_ir_json_object_required")
        try:
            derived = BaselineStrategyBuilder().build(payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("scenario_ir_incompatible") from exc
        try:
            reference = candidate.relative_to(self._project_root).as_posix()
        except ValueError:
            reference = str(candidate)
        return ResolvedScenarioInput(
            reference=reference,
            absolute_path=candidate,
            scenario_id=str(derived.scenario.scenario_id),
        )
