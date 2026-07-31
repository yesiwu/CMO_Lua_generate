"""Frozen preview consumption for Phase 9C execution."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cmo_lua_agent.contract.strategy_models import strategy_spec_from_dict
from cmo_lua_agent.evolution.production_models import FrozenCandidateSet


class FrozenCandidateSetProvider:
    """Parse and verify a frozen set without any proposal dependency."""

    def __init__(
        self,
        *,
        strategy_parser: Callable[[dict[str, Any]], Any] = strategy_spec_from_dict,
        verify_checksum_metadata: bool = True,
    ) -> None:
        self._strategy_parser = strategy_parser
        self._verify_checksum_metadata = verify_checksum_metadata

    def load(self, frozen: FrozenCandidateSet) -> tuple[Any, tuple[tuple[str, Any], ...]]:
        verified = FrozenCandidateSet.from_dict(
            frozen.to_dict(),
            verify_checksums=self._verify_checksum_metadata,
        )
        baseline = self._strategy_parser(dict(verified.baseline))
        candidates = tuple(
            (str(item["candidate_id"]), self._strategy_parser(dict(item["strategy"])))
            for item in verified.candidates
        )
        if [item[0] for item in candidates] != [f"candidate_{index:02d}" for index in range(4)]:
            raise ValueError("frozen_candidate_ids_invalid")
        return baseline, candidates
