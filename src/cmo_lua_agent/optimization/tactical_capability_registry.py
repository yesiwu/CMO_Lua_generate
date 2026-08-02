"""Single source of truth for registered, executable tactical parameters.

The registry deliberately exposes parameters, not Lua statements.  A capability
may be patchable only when the formal plan and its declared executor preserve it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TacticalCapability:
    capability_id: str
    path_suffix: str
    semantic_dimension: str
    minimum: int
    maximum: int
    default: int
    allowed_roles: tuple[str, ...]
    template_slot_field: str

    def concrete_path(self, sortie_index: int) -> str:
        return f"/sorties/{sortie_index}/air_tactics/{self.path_suffix}"


class TacticalCapabilityRegistry:
    """Registry for the first constrained air-tactics surface."""

    _AIR_TACTICS = (
        TacticalCapability("air_tactics.launch_delay_seconds", "launch_delay_seconds", "air_launch_timing", 0, 120, 5, ("coordinated_explore", "conservative_control"), "launch_delay_seconds"),
        TacticalCapability("air_tactics.ingress_altitude_m", "ingress_altitude_m", "air_ingress_altitude", 100, 2000, 200, ("exploit", "conservative_control"), "ingress_altitude_m"),
        TacticalCapability("air_tactics.popup_altitude_m", "popup_altitude_m", "air_popup_profile", 3000, 12000, 9500, (), "popup_altitude_m"),
        TacticalCapability("air_tactics.popup_range_nm", "popup_range_nm", "air_attack_range", 30, 140, 95, ("robust_repair",), "popup_range_nm"),
        TacticalCapability("air_tactics.attack_range_nm", "attack_range_nm", "air_attack_range", 30, 140, 80, ("robust_repair",), "attack_range_nm"),
    )

    @classmethod
    def default(cls) -> "TacticalCapabilityRegistry":
        return cls()

    @property
    def capabilities(self) -> tuple[TacticalCapability, ...]:
        return self._AIR_TACTICS

    def capability_for_path(self, path: str) -> TacticalCapability | None:
        for capability in self._AIR_TACTICS:
            if path.endswith("/air_tactics/" + capability.path_suffix):
                return capability
        return None

    def paths_for_role(self, *, role: str, sortie_count: int) -> tuple[str, ...]:
        return tuple(
            capability.concrete_path(index)
            for capability in self._AIR_TACTICS
            if role in capability.allowed_roles
            for index in range(sortie_count)
        )
