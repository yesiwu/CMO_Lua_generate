"""
ExperienceStore: persistent experience memory for the CMO Lua agent.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Iterator, Optional

logger = logging.getLogger(__name__)


class ExperienceStore:
    """
    Long-term memory for (task, script, reward) triples.

    Provides semantic retrieval by task description so that similar
    historical tasks can be used as few-shot examples.

    Schema
    ------
    experiences(id INTEGER PK, task_description TEXT, lua_script TEXT,
                reward REAL, mission_type TEXT, side TEXT,
                created_at TEXT, tags TEXT)
    """

    def __init__(self, db_path: Path | str = ":memory:") -> None:
        self.db_path = Path(db_path)
        self._conn: Optional[sqlite3.Connection] = None
        self._open()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def add(
        self,
        task_description: str,
        lua_script: str,
        reward: float,
        mission_type: str = "",
        side: str = "",
        tags: list[str] | None = None,
    ) -> None:
        """Store a new experience."""
        from datetime import datetime, timezone

        created_at = datetime.now(timezone.utc).isoformat()
        tag_str = json.dumps(tags or [], ensure_ascii=False)
        self._conn.execute(
            """
            INSERT INTO experiences
                (task_description, lua_script, reward, mission_type, side, created_at, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (task_description, lua_script, reward, mission_type, side, created_at, tag_str),
        )
        self._conn.commit()

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_reward: float = -1.0,
    ) -> Iterator[dict[str, Any]]:
        """
        Retrieve the top-k most relevant experiences by keyword overlap.

        Parameters
        ----------
        query : str
            Task description to match against.
        top_k : int
            Maximum number of results.
        min_reward : float
            Drop experiences below this reward.

        Yields
        ------
        dict with keys: task_description, lua_script, reward, mission_type, side
        """
        query_words = set(query.lower().split())
        scored: list[tuple[int, dict[str, Any]]] = []

        rows = self._conn.execute(
            "SELECT id, task_description, lua_script, reward, mission_type, side "
            "FROM experiences WHERE reward >= ?",
            (min_reward,),
        ).fetchall()

        for row in rows:
            desc_words = set((row[1] or "").lower().split())
            score = len(query_words & desc_words)
            if score > 0:
                scored.append(
                    (
                        -score,
                        {
                            "task_description": row[1],
                            "lua_script": row[2],
                            "reward": row[3],
                            "mission_type": row[4],
                            "side": row[5],
                        },
                    )
                )

        scored.sort(key=lambda x: x[0])
        for _, exp in scored[:top_k]:
            yield exp

    def best_for_mission(
        self, mission_type: str, side: str, top_k: int = 3
    ) -> Iterator[dict[str, Any]]:
        """Return highest-reward experiences for a specific mission + side."""
        rows = self._conn.execute(
            """
            SELECT task_description, lua_script, reward
            FROM experiences
            WHERE mission_type=? AND side=? AND reward >= 0
            ORDER BY reward DESC
            LIMIT ?
            """,
            (mission_type, side, top_k),
        ).fetchall()
        for row in rows:
            yield {
                "task_description": row[0],
                "lua_script": row[1],
                "reward": row[2],
            }

    def save(self, path: Path | str) -> None:
        """Export as JSON Lines."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = self._conn.execute(
            "SELECT task_description, lua_script, reward, mission_type, side, created_at "
            "FROM experiences"
        ).fetchall()
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(
                    json.dumps(
                        {
                            "task_description": row[0],
                            "lua_script": row[1],
                            "reward": row[2],
                            "mission_type": row[3],
                            "side": row[4],
                            "created_at": row[5],
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        logger.info("[ExperienceStore] Saved %d entries to %s", len(rows), path)

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------
    def _open(self) -> None:
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS experiences(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_description TEXT,
                lua_script TEXT,
                reward REAL,
                mission_type TEXT,
                side TEXT,
                created_at TEXT,
                tags TEXT
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mission_side ON experiences(mission_type, side)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_reward ON experiences(reward DESC)"
        )
        self._conn.commit()
