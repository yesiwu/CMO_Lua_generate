"""Offline Phase 7 evidence reconstruction from published CMO result files.

This module intentionally never opens ``events.sqlite``.  It only consumes the
human/exported result artefacts that are already present beside a completed
attempt: ``execution-summary.json`` and ``combat-summary.csv``.  Reconstructed
facts remain explicitly derived rather than pretending to be native score-log
events.
"""
from __future__ import annotations

import csv
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Iterable


class ResultEvidenceReconstructor:
    """Rebuild loss, damage and score evidence without rerunning CMO."""

    def __init__(self, *, score_rules: Iterable[dict[str, Any]]) -> None:
        self._rules = tuple(dict(rule) for rule in score_rules)

    def reconstruct(self, result_dir: Path) -> dict[str, Any]:
        root = Path(result_dir)
        summary = self._read_json(root / "execution-summary.json")
        official = summary.get("official_score") if isinstance(summary.get("official_score"), dict) else {}
        initial = official.get("initial")
        final = official.get("final")
        if not isinstance(initial, int) or not isinstance(final, int):
            raise ValueError("official score is unavailable for reconstruction")

        losses, target_damage = self._read_combat_summary(root / "combat-summary.csv")
        events = self._derive_score_events(losses, target_damage, initial)
        total = sum(item["point_delta"] for item in events)
        if total != final - initial:
            chain_status = "INVALID"
            evidence_status = "CONFLICTING"
        elif events:
            chain_status = "DERIVED_VALID"
            evidence_status = "DERIVED"
        elif final == initial:
            chain_status = "DERIVED_VALID"
            evidence_status = "DERIVED"
        else:
            chain_status = "INVALID"
            evidence_status = "MISSING"
        return {
            "losses": losses,
            "target_damage": target_damage,
            "score_events": events,
            "score_event_chain_status": chain_status,
            "scoring_evidence_status": evidence_status,
            "score_chain_consistent": chain_status == "DERIVED_VALID",
        }

    def apply(self, result_dir: Path) -> dict[str, Any]:
        """Atomically enrich the published summary and retain its original copy."""
        root = Path(result_dir)
        summary_path = root / "execution-summary.json"
        summary = self._read_json(summary_path)
        rebuilt = self.reconstruct(root)
        backup = root / "execution-summary.pre-phase7-reconstruction.json"
        if not backup.exists():
            self._atomic_text(backup, summary_path.read_text(encoding="utf-8"))
        summary.update({key: rebuilt[key] for key in ("losses", "target_damage", "score_events")})
        official = summary.setdefault("official_score", {})
        official["score_event_chain_status"] = rebuilt["score_event_chain_status"]
        summary["scoring_evidence_status"] = rebuilt["scoring_evidence_status"]
        integrity = summary.setdefault("evidence_integrity", {})
        integrity["score_chain_consistent"] = rebuilt["score_chain_consistent"]
        integrity["status"] = "DERIVED" if rebuilt["scoring_evidence_status"] == "DERIVED" else rebuilt["scoring_evidence_status"]
        integrity["results_complete"] = True
        summary["phase7_reconstruction"] = {
            "evidence_source": "reconstructed_from_cmo_results",
            "source_files": ["combat-summary.csv", "execution-summary.pre-phase7-reconstruction.json"],
        }
        self._atomic_json(summary_path, summary)
        return summary

    def _derive_score_events(
        self,
        losses: dict[str, list[dict[str, Any]]],
        target_damage: list[dict[str, Any]],
        initial: int,
    ) -> list[dict[str, Any]]:
        facts = [*losses.get("red", []), *losses.get("blue", []), *target_damage]
        events: list[dict[str, Any]] = []
        seen_rules: set[str] = set()
        score = initial
        for fact in facts:
            for rule in self._rules:
                rule_id = rule.get("rule_id")
                if not isinstance(rule_id, str) or rule_id in seen_rules:
                    continue
                if not self._matches_rule(rule, fact):
                    continue
                delta = rule.get("point_change", rule.get("delta"))
                if not isinstance(delta, int):
                    continue
                seen_rules.add(rule_id)
                before = score
                score += delta
                events.append({
                    "event_id": f"derived:{len(events) + 1:04d}",
                    "event_sequence": len(events) + 1,
                    "sim_time": fact.get("sim_time"),
                    "rule_id": rule_id,
                    "target_unit_id": rule.get("target_unit_id"),
                    "event_kind": "damage_threshold" if rule.get("damage_threshold_percent") is not None else "unit_destroyed",
                    "damage_threshold": rule.get("damage_threshold_percent"),
                    "point_delta": delta,
                    "delta": delta,
                    "score_before": before,
                    "score_after": score,
                    "evidence_source": "reconstructed_from_cmo_results",
                    "evidence_ref": "combat-summary.csv",
                })
                break
        return events

    @staticmethod
    def _matches_rule(rule: dict[str, Any], fact: dict[str, Any]) -> bool:
        target = str(rule.get("target_unit_name", "")).strip()
        name = str(fact.get("unit_name", "")).strip()
        if not target or not name or target not in name and name not in target:
            return False
        threshold = rule.get("damage_threshold_percent")
        if threshold is None:
            return fact.get("result") == "destroyed"
        damage = fact.get("damage_percent")
        return isinstance(damage, (int, float)) and damage >= threshold

    @staticmethod
    def _read_combat_summary(path: Path) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
        losses: dict[str, list[dict[str, Any]]] = {"red": [], "blue": []}
        damage: list[dict[str, Any]] = []
        if not path.is_file():
            return losses, damage
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                metric = (row.get("指标") or "").strip()
                side = (row.get("阵营") or "").strip()
                name = (row.get("武器或单位") or "").strip()
                result = (row.get("结果") or "").strip()
                value = (row.get("数量或损伤百分比") or "").strip()
                if metric == "单位战损" and side in losses and result == "被毁":
                    losses[side].append({
                        "unit_name": ResultEvidenceReconstructor._plain_name(name),
                        "quantity": int(value) if value.isdigit() else 1,
                        "result": "destroyed",
                        "evidence_source": "reconstructed_from_cmo_results",
                        "evidence_ref": "combat-summary.csv",
                    })
                elif metric == "存活单位最终损伤" and side in losses:
                    try:
                        percent = float(value)
                    except ValueError:
                        continue
                    damage.append({
                        "unit_name": ResultEvidenceReconstructor._plain_name(name),
                        "side_id": side,
                        "damage_percent": percent,
                        "result": "damaged",
                        "evidence_source": "reconstructed_from_cmo_results",
                        "evidence_ref": "combat-summary.csv",
                    })
        return losses, damage

    @staticmethod
    def _plain_name(value: str) -> str:
        return value.split(" [", 1)[0].strip()

    @staticmethod
    def rules_from_rendered_lua(path: Path) -> tuple[dict[str, Any], ...]:
        """Extract only the declared native-score rule facts from rendered Lua."""
        text = Path(path).read_text(encoding="utf-8")
        section = re.search(r"local SCORE_RULES\s*=\s*\{(.*?)\}\s*\nlocal function", text, re.S)
        if not section:
            return ()
        rules = []
        for point, rule_id, unit_id, unit_name in re.findall(
            r'\["point_change"\]=(-?\d+).*?\["rule_id"\]="([^"]+)".*?\["target_unit_id"\]="([^"]+)".*?\["target_unit_name"\]="([^"]+)"',
            section.group(1),
        ):
            rules.append({"rule_id": rule_id, "target_unit_id": unit_id, "target_unit_name": unit_name, "point_change": int(point)})
        return tuple(rules)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"expected JSON object: {path}")
        return data

    @staticmethod
    def _atomic_json(path: Path, value: dict[str, Any]) -> None:
        ResultEvidenceReconstructor._atomic_text(path, json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")

    @staticmethod
    def _atomic_text(path: Path, value: str) -> None:
        directory = ResultEvidenceReconstructor._windows_path(path.parent)
        descriptor, temp_path = tempfile.mkstemp(dir=directory, prefix=".phase7-")
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(value)
        os.replace(temp_path, ResultEvidenceReconstructor._windows_path(path))

    @staticmethod
    def _windows_path(path: Path) -> str:
        value = str(Path(path).resolve())
        if os.name == "nt" and not value.startswith("\\\\?\\"):
            return "\\\\?\\" + value
        return value
