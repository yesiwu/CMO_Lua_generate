"""
StrategySpec: structured specification of a Lua generation task.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StrategySpec:
    """
    Input specification for the Lua generator.

    Attributes
    ----------
    mission_type : str
        e.g. "TOT", "CAP", "SEAD", "STRIKE"
    side : str
        "Blue" or "Red"
    objectives : list[str]
        Human-readable objectives.
    weapon_dbid : Optional[int]
        DBID of the primary weapon to use.
    weapon_name : Optional[str]
        Human-readable weapon name.
    time_window : Optional[tuple[float, float]]
        (start_hour, end_hour) in simulation time.
    patrol_radius : Optional[float]
        nm, for patrol missions.
    contact_mode : str
        "BOL" or "MANUAL".  Defaults to "MANUAL".
    allow_fallback : bool
        Whether to fall back to BOL if MANUAL lookup fails.
    constraints : list[str]
        Hard constraints expressed as strings (for the LLM prompt).
    """

    mission_type: str = "TOT"
    side: str = "Blue"
    objectives: list[str] = field(default_factory=list)
    weapon_dbid: Optional[int] = None
    weapon_name: Optional[str] = None
    time_window: Optional[tuple[float, float]] = None
    patrol_radius: Optional[float] = None
    contact_mode: str = "MANUAL"
    allow_fallback: bool = False
    constraints: list[str] = field(default_factory=list)

    def to_prompt_context(self) -> str:
        parts = [
            f"Mission: {self.mission_type}",
            f"Side: {self.side}",
            f"Objectives: {', '.join(self.objectives) or 'none'}",
        ]
        if self.weapon_name:
            parts.append(f"Weapon: {self.weapon_name} (DBID {self.weapon_dbid})")
        if self.time_window:
            parts.append(
                f"Time window: {self.time_window[0]:.1f}h – {self.time_window[1]:.1f}h"
            )
        if self.patrol_radius:
            parts.append(f"Patrol radius: {self.patrol_radius} nm")
        parts.append(f"Contact mode: {self.contact_mode}")
        if self.constraints:
            parts.append("Constraints: " + "; ".join(self.constraints))
        return "\n".join(parts)
