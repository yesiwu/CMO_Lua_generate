"""The single authoritative mapping from StrategySpec leaf paths to semantic dimensions."""

from __future__ import annotations


def semantic_dimension(path: str) -> str:
    if "/air_tactics/launch_delay_seconds" in path:
        return "air_launch_timing"
    if "/air_tactics/ingress_altitude_m" in path:
        return "air_ingress_altitude"
    if "/air_tactics/popup_" in path or "/air_tactics/attack_range_nm" in path:
        return "air_attack_range"
    if path.endswith("/target_id") or path.endswith("/target_ids") or "/target_ids/" in path:
        return "target_assignment"
    if path.endswith("/fire_quantity"):
        return "fire_quantity"
    if path.endswith("/delay_seconds") or path.endswith("/fire_delay_seconds"):
        return "attack_timing"
    if "/route/" in path:
        return "air_route"
    if path.endswith("/reserve_quantity"):
        return "ammunition_reserve"
    if path.endswith("/return_delay_seconds"):
        return "risk_policy"
    return "other"


def semantic_dimensions(paths: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({semantic_dimension(path) for path in paths}))
