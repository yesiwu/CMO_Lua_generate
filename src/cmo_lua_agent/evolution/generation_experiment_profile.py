"""Frozen, deterministic experiment constraints for one generation preview.

This module deliberately does not choose a baseline, inspect scores, write a
StrategySpec, or learn causality.  EvolutionCampaignWorkflow owns rolling
baseline selection; the profile only narrows the already formal patch surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cmo_lua_agent.generation.runtime_models import canonical_sha256


@dataclass(frozen=True, slots=True)
class GenerationExperimentProfile:
    generation_index: int
    objective: str
    roles: dict[str, dict[str, Any]]

    @property
    def checksum(self) -> str:
        return canonical_sha256(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "generation_index": self.generation_index,
            "objective": self.objective,
            "roles": self.roles,
        }


class GenerationExperimentProfileBuilder:
    """Builds system-owned role constraints without selecting strategy values."""

    _OBJECTIVE = "retain_strike_success_and_reduce_j15_losses"

    def build(self, *, generation_index: int) -> GenerationExperimentProfile:
        if generation_index < 0:
            raise ValueError("generation_index_invalid")
        roles = {
            "candidate_00": {
                "role": "exploit",
                "hypothesis": "Lower ingress altitude may retain strike success while reducing J-15 loss.",
                "allowed_capabilities": ["air_tactics.ingress_altitude_m"],
                "required_capabilities": ["air_tactics.ingress_altitude_m"],
            },
            "candidate_01": {
                "role": "robust_repair",
                "hypothesis": "Popup and attack range may reduce exposure time.",
                "allowed_capabilities": ["air_tactics.popup_range_nm", "air_tactics.attack_range_nm"],
                "required_capabilities": ["air_tactics.popup_range_nm"],
            },
            "candidate_02": {
                "role": "coordinated_explore",
                "hypothesis": "Launch delay may improve ship-air timing coordination.",
                "allowed_capabilities": ["air_tactics.launch_delay_seconds"],
                "required_capabilities": ["air_tactics.launch_delay_seconds"],
            },
            "candidate_03": {
                "role": "conservative_control",
                "hypothesis": "A bounded altitude and timing combination tests interaction effects.",
                "allowed_capabilities": ["air_tactics.ingress_altitude_m", "air_tactics.launch_delay_seconds"],
                "required_capabilities": [],
                "max_changed_capabilities": 2,
            },
        }
        return GenerationExperimentProfile(generation_index, self._OBJECTIVE, roles)
