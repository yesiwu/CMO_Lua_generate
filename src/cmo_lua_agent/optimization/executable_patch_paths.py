"""Execution-semantic gate for candidate patch paths.

``fire_delay_seconds`` support is deferred until it is carried through the
StrategySpec -> ExecutionPlan -> Lua Golden chain.  The Baseline may retain
the field, but candidate patches must not alter it meanwhile.
"""

from __future__ import annotations


def is_executable_patch_path(path: str) -> bool:
    """Whether a supported candidate patch path has runtime semantics."""
    return not _is_deferred_fire_delay(path)


def non_executable_patch_diagnostics(
    *, path: str, candidate_id: str
) -> dict[str, object] | None:
    """Return stable, bounded diagnostics for a known deferred path."""
    tokens = _tokens(path)
    if not _is_deferred_fire_delay(path):
        return None
    sortie_index = tokens[1]
    return {
        "candidate_id": candidate_id,
        "path": path,
        "strategy_field": "fire_delay_seconds",
        "reason": "not_preserved_by_execution_plan",
        "supported_alternatives": [
            f"/sorties/{sortie_index}/route/0/latitude",
            f"/sorties/{sortie_index}/route/0/longitude",
        ],
    }


def _is_deferred_fire_delay(path: str) -> bool:
    tokens = _tokens(path)
    return (
        len(tokens) == 3
        and tokens[0] == "sorties"
        and tokens[1].isdecimal()
        and tokens[2] == "fire_delay_seconds"
    )


def _tokens(path: str) -> tuple[str, ...]:
    if not isinstance(path, str) or not path.startswith("/"):
        return ()
    return tuple(path[1:].split("/"))
