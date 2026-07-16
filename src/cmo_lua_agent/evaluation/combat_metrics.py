"""
Combat metrics: dataclass definitions for structured combat output.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WeaponMetric:
    """Aggregated weapon-level performance."""

    weapon_name: str
    weapon_side: str
    shots_fired: int = 0
    hits: int = 0
    kills: int = 0
    intercepts: int = 0
    intercept_attempts: int = 0
    intercept_kills: int = 0

    @property
    def hit_rate(self) -> float:
        if self.shots_fired == 0:
            return 0.0
        return self.hits / self.shots_fired

    @property
    def intercept_rate(self) -> float:
        if self.intercept_attempts == 0:
            return 0.0
        return self.intercept_kills / self.intercept_attempts


@dataclass
class UnitLoss:
    """Record of a unit destroyed or damaged."""

    unit_name: str
    unit_class: str
    side: str
    destroyed: bool = False
    damage_percent: float = 0.0
    damage_dp: float = 0.0


@dataclass
class CombatMetrics:
    """Top-level container for all metrics from a single run."""

    run_id: str = ""
    script_name: str = ""

    # Counts
    total_weapon_events: int = 0
    total_unit_events: int = 0

    # Per-weapon metrics
    weapons: dict[str, WeaponMetric] = field(default_factory=dict)

    # Per-unit metrics
    losses: list[UnitLoss] = field(default_factory=list)

    # Side scores (from AAR)
    side_scores: dict[str, int] = field(default_factory=dict)

    # Simulation outcome
    status: str = ""           # "Success", "Timeout", "LuaFailed", …
    end_reason: str = ""      # "ScenarioEnded", "WallTimeout", …
    simulation_duration_s: float = 0.0
    wall_duration_s: float = 0.0

    def add_weapon(self, wm: WeaponMetric) -> None:
        self.weapons[wm.weapon_name] = wm

    def total_hits(self) -> int:
        return sum(w.hits for w in self.weapons.values())

    def total_kills(self) -> int:
        return sum(w.kills for w in self.weapons.values())

    def total_intercept_kills(self) -> int:
        return sum(w.intercept_kills for w in self.weapons.values())

    def destroyed_count(self) -> int:
        return sum(1 for u in self.losses if u.destroyed)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "end_reason": self.end_reason,
            "total_hits": self.total_hits(),
            "total_kills": self.total_kills(),
            "intercept_kills": self.total_intercept_kills(),
            "destroyed_units": self.destroyed_count(),
            "sim_duration_s": self.simulation_duration_s,
            "wall_duration_s": self.wall_duration_s,
        }
