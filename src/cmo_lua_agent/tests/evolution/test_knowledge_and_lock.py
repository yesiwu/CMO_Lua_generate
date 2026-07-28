from __future__ import annotations

from pathlib import Path

import pytest

from cmo_lua_agent.evolution.cmo_lock import CmoInstanceLock, CmoLockError
from cmo_lua_agent.evolution.knowledge_snapshot import KnowledgeSnapshotService


class _Retriever:
    def __init__(self) -> None:
        self.calls = 0

    def retrieve(self, **_: object) -> tuple[dict[str, object], ...]:
        self.calls += 1
        return (
            {"experience_id": "old", "source_generation_index": 0, "kind": "positive"},
            {"experience_id": "current", "source_generation_index": 1, "kind": "positive"},
        )


def test_snapshot_excludes_current_generation_and_is_reused(tmp_path: Path) -> None:
    retriever = _Retriever()
    service = KnowledgeSnapshotService(retriever=retriever)
    path = tmp_path / "knowledge-snapshot.json"

    first = service.freeze(
        path=path, campaign_id="campaign", generation_index=1,
        bootstrap_checksum="boot", active_skills=(), experience_store_revision="rev",
        experience_index_checksum="index", retrieval_query={"scenario": "6v4"},
        contract={"runtime": "2", "score": "score"}, parent_strategy_checksum="parent",
    )
    second = service.freeze(
        path=path, campaign_id="campaign", generation_index=1,
        bootstrap_checksum="changed-but-must-not-reread", active_skills=(), experience_store_revision="rev2",
        experience_index_checksum="index2", retrieval_query={"scenario": "6v4"},
        contract={"runtime": "2", "score": "score"}, parent_strategy_checksum="parent",
    )

    assert [card["experience_id"] for card in first.experience_cards] == ["old"]
    assert second == first
    assert retriever.calls == 1


def test_production_campaigns_cannot_share_cmo_lock(tmp_path: Path) -> None:
    first = CmoInstanceLock(tmp_path / "cmo.lock", campaign_id="one")
    second = CmoInstanceLock(tmp_path / "cmo.lock", campaign_id="two")
    first.acquire()
    with pytest.raises(CmoLockError, match="cmo_instance_locked"):
        second.acquire()
    first.release()
    second.acquire()
    second.release()
