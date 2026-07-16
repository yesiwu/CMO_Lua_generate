"""
CombatResultParser: parses raw CMO execution output into structured CombatMetrics.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from cmo_lua_agent.evaluation.combat_metrics import (
    CombatMetrics,
    WeaponMetric,
    UnitLoss,
)

logger = logging.getLogger(__name__)


class CombatResultParser:
    """
    Reads SQLite + text-log output from a CMO batch run and produces a
    unified CombatMetrics object.
    """

    def parse(
        self,
        db_path: Path | str,
        text_log_path: Path | str | None = None,
        run_id: str = "",
        script_name: str = "",
    ) -> CombatMetrics:
        """
        Parameters
        ----------
        db_path : Path
            Path to the events SQLite database.
        text_log_path : Path, optional
            Plain-text event log (for quick diagnostics).
        run_id, script_name : str
            Metadata copied into the output.

        Returns
        -------
        CombatMetrics
        """
        db_path = Path(db_path)
        metrics = CombatMetrics(run_id=run_id, script_name=script_name)

        if not db_path.exists():
            logger.warning("[parser] DB not found: %s", db_path)
            metrics.status = "DBNotFound"
            return metrics

        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row

            # Run info
            rows = conn.execute(
                "SELECT status, end_reason, sim_started, sim_ended FROM run_info LIMIT 1"
            ).fetchall()
            if rows:
                r = rows[0]
                metrics.status = r["status"] or ""
                metrics.end_reason = r["end_reason"] or ""

            # Weapon events
            weapon_rows = conn.execute(
                """
                SELECT weapon_name, weapon_side, result,
                       COUNT(*) as cnt
                FROM weapon_events
                WHERE weapon_name <> ''
                GROUP BY weapon_name, weapon_side, result
                """
            ).fetchall()
            for row in weapon_rows:
                wm = metrics.weapons.get(row["weapon_name"])
                if wm is None:
                    wm = WeaponMetric(weapon_name=row["weapon_name"], weapon_side=row["weapon_side"])
                    metrics.weapons[row["weapon_name"]] = wm
                result = row["result"] or ""
                cnt = row["cnt"]
                if "Fire" in result:
                    wm.shots_fired += cnt
                if "Hit" in result:
                    wm.hits += cnt
                if "Kill" in result or "Destroy" in result:
                    wm.kills += cnt

            # Unit damage / destruction events
            unit_rows = conn.execute(
                "SELECT unit_name, unit_side, event_type, damage_percent FROM unit_damage_events"
            ).fetchall()
            seen = {}
            for row in unit_rows:
                name = row["unit_name"] or "<unknown>"
                key = name
                if key not in seen:
                    seen[key] = UnitLoss(
                        unit_name=name,
                        side=row["unit_side"] or "",
                    )
                ev_type = row["event_type"] or ""
                if "Destroyed" in ev_type:
                    seen[key].destroyed = True
                try:
                    seen[key].damage_percent = max(
                        seen[key].damage_percent, float(row["damage_percent"] or 0)
                    )
                except (TypeError, ValueError):
                    pass
            metrics.losses.extend(seen.values())

            # Side scores
            score_rows = conn.execute(
                """
                SELECT side, score FROM side_scores
                WHERE phase = 'end'
                """
            ).fetchall()
            for row in score_rows:
                if row["side"]:
                    metrics.side_scores[row["side"]] = int(row["score"] or 0)

            # Counts
            metrics.total_weapon_events = conn.execute(
                "SELECT COUNT(*) FROM weapon_events"
            ).fetchone()[0]
            metrics.total_unit_events = conn.execute(
                "SELECT COUNT(*) FROM unit_damage_events"
            ).fetchone()[0]

            conn.close()

        except Exception as ex:
            logger.error("[parser] Error parsing DB: %s", ex)
            metrics.status = f"ParseError:{ex}"

        return metrics
