"""Freeze only pre-generation, cohort-compatible knowledge inputs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, Protocol


class ExperienceCardRetriever(Protocol):
    def retrieve(self, **kwargs: object) -> tuple[dict[str, object], ...]: ...


@dataclass(frozen=True, slots=True)
class KnowledgeSnapshot:
    campaign_id: str
    generation_index: int
    bootstrap_checksum: str
    active_skills: tuple[dict[str, object], ...]
    experience_cards: tuple[dict[str, object], ...]
    experience_store_revision: str
    experience_index_checksum: str
    selected_experience_ids: tuple[str, ...]
    retrieval_query_checksum: str
    contract: dict[str, str]
    parent_strategy_checksum: str
    checksum: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class KnowledgeSnapshotService:
    def __init__(self, *, retriever: ExperienceCardRetriever) -> None:
        self._retriever = retriever

    def freeze(self, *, path: Path, campaign_id: str, generation_index: int, bootstrap_checksum: str,
               active_skills: tuple[dict[str, object], ...], experience_store_revision: str,
               experience_index_checksum: str, retrieval_query: dict[str, object],
               contract: dict[str, str], parent_strategy_checksum: str) -> KnowledgeSnapshot:
        path = Path(path)
        if path.is_file():
            return self._from_dict(json.loads(path.read_text(encoding="utf-8")))
        query_checksum = self._checksum(retrieval_query)
        cards = self._retriever.retrieve(query=dict(retrieval_query), current_generation=generation_index)
        visible = tuple(
            dict(card) for card in cards
            if int(card.get("source_generation_index", -1)) < generation_index
        )
        selected = tuple(str(card["experience_id"]) for card in visible if "experience_id" in card)
        body = {
            "campaign_id": campaign_id, "generation_index": generation_index,
            "bootstrap_checksum": bootstrap_checksum, "active_skills": active_skills,
            "experience_cards": visible, "experience_store_revision": experience_store_revision,
            "experience_index_checksum": experience_index_checksum, "selected_experience_ids": selected,
            "retrieval_query_checksum": query_checksum, "contract": dict(contract),
            "parent_strategy_checksum": parent_strategy_checksum,
        }
        snapshot = KnowledgeSnapshot(**body, checksum=self._checksum(body))
        self._write_atomic(path, snapshot.to_dict())
        return snapshot

    @staticmethod
    def _checksum(value: object) -> str:
        return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    @staticmethod
    def _write_atomic(path: Path, value: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8", newline="\n")
        os.replace(temporary, path)

    @staticmethod
    def _from_dict(value: dict[str, Any]) -> KnowledgeSnapshot:
        return KnowledgeSnapshot(
            campaign_id=value["campaign_id"], generation_index=int(value["generation_index"]),
            bootstrap_checksum=value["bootstrap_checksum"], active_skills=tuple(dict(item) for item in value["active_skills"]),
            experience_cards=tuple(dict(item) for item in value["experience_cards"]), experience_store_revision=value["experience_store_revision"],
            experience_index_checksum=value["experience_index_checksum"], selected_experience_ids=tuple(value["selected_experience_ids"]),
            retrieval_query_checksum=value["retrieval_query_checksum"], contract=dict(value["contract"]),
            parent_strategy_checksum=value["parent_strategy_checksum"], checksum=value["checksum"],
        )
