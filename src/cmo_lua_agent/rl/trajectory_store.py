"""
TrajectoryStore: persistent in-memory store for all trajectories.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Iterator, Optional

from cmo_lua_agent.rl.trajectory import Trajectory, TrajectoryStep

logger = logging.getLogger(__name__)


class TrajectoryStore:
    """
    Append-only store for Trajectory objects.

    Backed by an SQLite database so trajectories survive restarts.

    Schema
    ------
    trajectories(run_id TEXT PK, created_at TEXT, num_steps INT)
    steps(iteration INT, run_id TEXT, lua_script TEXT, script_path TEXT,
          reward REAL, combat_metrics TEXT, timestamp TEXT)
    """

    def __init__(self, db_path: Path | str = ":memory:") -> None:
        self.db_path = Path(db_path)
        self._conn: Optional[sqlite3.Connection] = None
        self._open()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def add(self, trajectory: Trajectory) -> None:
        """Append a trajectory."""
        self._insert_trajectory(trajectory)
        for step in trajectory.steps:
            self._insert_step(trajectory.run_id, step)

    def trajectories(self) -> Iterator[Trajectory]:
        """Yield all trajectories."""
        cur = self._conn.execute(
            "SELECT run_id, created_at FROM trajectories ORDER BY created_at"
        )
        for row in cur.fetchall():
            run_id, created_at = row
            steps = list(self._fetch_steps(run_id))
            from datetime import datetime

            yield Trajectory(
                run_id=run_id,
                steps=steps,
                created_at=datetime.fromisoformat(created_at),
            )

    def save(self, path: Path | str) -> None:
        """Export all trajectories as JSON Lines."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for traj in self.trajectories():
                fh.write(json.dumps(traj.to_dict(), ensure_ascii=False) + "\n")
        logger.info("[TrajectoryStore] Saved %s", path)

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Private DB helpers
    # ------------------------------------------------------------------
    def _open(self) -> None:
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trajectories(
                run_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                num_steps INTEGER DEFAULT 0
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS steps(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                iteration INTEGER,
                run_id TEXT,
                lua_script TEXT,
                script_path TEXT,
                reward REAL,
                combat_metrics TEXT,
                timestamp TEXT
            )
            """
        )
        self._conn.commit()

    def _insert_trajectory(self, t: Trajectory) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO trajectories(run_id, created_at, num_steps) VALUES(?, ?, ?)",
            (t.run_id, t.created_at.isoformat(), len(t.steps)),
        )
        self._conn.commit()

    def _insert_step(self, run_id: str, step: TrajectoryStep) -> None:
        self._conn.execute(
            """
            INSERT INTO steps(iteration, run_id, lua_script, script_path, reward, combat_metrics, timestamp)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                step.iteration,
                run_id,
                step.lua_script,
                step.script_path,
                step.reward,
                json.dumps(step.combat_metrics, ensure_ascii=False),
                step.timestamp.isoformat(),
            ),
        )
        self._conn.commit()

    def _fetch_steps(self, run_id: str) -> Iterator[TrajectoryStep]:
        from datetime import datetime

        cur = self._conn.execute(
            "SELECT iteration, lua_script, script_path, reward, combat_metrics, timestamp "
            "FROM steps WHERE run_id=? ORDER BY iteration",
            (run_id,),
        )
        for row in cur.fetchall():
            yield TrajectoryStep(
                iteration=row[0],
                lua_script=row[1],
                script_path=row[2],
                reward=row[3],
                combat_metrics=json.loads(row[4] or "{}"),
                timestamp=datetime.fromisoformat(row[5]),
            )
