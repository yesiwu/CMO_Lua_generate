"""Minimal, deterministic Phase 3 evidence and native-score evaluation."""

from __future__ import annotations

import csv
import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from cmo_lua_agent.contract.strategy_models import ScenarioDefinition
from cmo_lua_agent.execution.models import CmoRunResult
from cmo_lua_agent.generation.runtime_models import ExecutionPlan
from cmo_lua_agent.scoring.native_score_compiler import CmoNativeScoreCompilation


@dataclass(frozen=True, slots=True)
class ResultArtifactPaths:
    batch_result_dir: Path | None
    job_result_dir: Path | None
    primary_result_path: Path | None
    runner_log_path: Path | None
    lua_output_path: Path | None
    is_confirmed: bool


@dataclass(frozen=True, slots=True)
class BatchRunnerEvidence:
    execution_success: bool
    timed_out: bool
    error: str | None
    result_dir: str | None
    configuration_restored: bool


@dataclass(frozen=True, slots=True)
class DestroyedUnit:
    unit_id: str | None
    unit_name: str
    side_id: str


@dataclass(frozen=True, slots=True)
class CmoNativeSnapshot:
    native_score_initial: int | None
    native_score_final: int | None
    native_score_delta: int | None
    destroyed_units: tuple[DestroyedUnit, ...]
    weapon_usage: int | None
    simulation_end_time: str | None


@dataclass(frozen=True, slots=True)
class RuntimeTelemetry:
    launch: tuple[str, ...]
    attack_ordered: tuple[str, ...]
    return_to_base: tuple[str, ...]
    score_registration_error: tuple[str, ...]
    runtime_error: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _WeaponEvent:
    """仅用于将 CMO 原始武器事件聚合到攻击链，绝不直接输出。"""

    event_type: str
    weapon_class: str | None
    firing_unit_name: str | None
    target_name: str | None
    result: str | None


@dataclass(frozen=True, slots=True)
class AttackEpisode:
    operation_id: str | None
    attacker_id: str
    target_id: str
    weapon_id: str | None
    launch_succeeded: bool | None
    weapons_fired: int | None
    hits: int | None
    intercepted: int | None
    target_destroyed: bool
    attacker_destroyed: bool
    returned_to_base: bool | None
    important_errors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CombatEvidence:
    batch: BatchRunnerEvidence
    native_snapshot: CmoNativeSnapshot
    runtime_telemetry: RuntimeTelemetry
    attack_episodes: tuple[AttackEpisode, ...]
    raw_evidence_paths: ResultArtifactPaths


@dataclass(frozen=True, slots=True)
class EvidenceReconciliation:
    status: str
    expected_native_score_delta: int | None
    actual_native_score_delta: int | None
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Phase3SemanticValidation:
    semantic_valid: bool
    scoreable: bool
    violations: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Phase3CombatMetrics:
    execution_success: bool
    native_score_delta: int | None
    enemy_units_destroyed: int
    own_units_destroyed: int
    weapon_expended: int | None
    attack_episodes: tuple[AttackEpisode, ...]
    key_events: tuple[str, ...]
    semantic_valid: bool
    scoreable: bool


@dataclass(frozen=True, slots=True)
class RewardItem:
    rule_id: str
    unit_id: str
    point_change: int
    event_type: str


@dataclass(frozen=True, slots=True)
class RewardBreakdown:
    raw_score: int | None
    normalized_reward: float | None
    normalization_version: str
    breakdown: tuple[RewardItem, ...]


@dataclass(frozen=True, slots=True)
class Phase3EvaluationResult:
    artifact_paths: ResultArtifactPaths
    native_snapshot: CmoNativeSnapshot
    attack_episodes: tuple[AttackEpisode, ...]
    reconciliation: EvidenceReconciliation
    semantic_validation: Phase3SemanticValidation
    metrics: Phase3CombatMetrics
    reward_breakdown: RewardBreakdown


def locate_result_artifacts(*, run_result: CmoRunResult) -> ResultArtifactPaths:
    batch = run_result.batch_result_dir or run_result.process_result.batch_result_dir
    if batch is None or not Path(batch).is_dir():
        return ResultArtifactPaths(None, None, None, None, None, False)
    batch = Path(batch)
    jobs = sorted(path for path in batch.iterdir() if path.is_dir() and path.name.startswith("001_"))
    job = jobs[0] if len(jobs) == 1 else None
    primary = None
    if job and (job / "events.sqlite").is_file() and _sqlite_belongs_to_run(job / "events.sqlite", run_result.lua_path):
        primary = job / "events.sqlite"
    elif job and (job / "combat-summary.csv").is_file():
        primary = job / "combat-summary.csv"
    return ResultArtifactPaths(
        batch, job, primary, batch / "runner.log" if (batch / "runner.log").is_file() else None,
        job / "lua-output.log" if job and (job / "lua-output.log").is_file() else None,
        job is not None and primary is not None,
    )


class Phase3EvaluationService:
    def record_unscorable(
        self,
        *,
        run_result: CmoRunResult,
        output_dir: Path,
        reason: str,
    ) -> Phase3EvaluationResult:
        """为完成 Hook 的基础设施异常留下可审计的不可评分产物。"""
        paths = locate_result_artifacts(run_result=run_result)
        batch = BatchRunnerEvidence(
            run_result.success,
            run_result.process_result.timed_out,
            run_result.error.message if run_result.error else None,
            str(paths.batch_result_dir) if paths.batch_result_dir else None,
            run_result.restore_succeeded,
        )
        result = self._unscorable(
            paths,
            batch,
            CmoNativeSnapshot(None, None, None, (), None, None),
            reason,
        )
        _write_artifacts(Path(output_dir), result, batch, RuntimeTelemetry((), (), (), (), ()))
        return result

    def evaluate(
        self, *, run_result: CmoRunResult, run_id: str, scenario: ScenarioDefinition,
        plan: ExecutionPlan, score_compilation: CmoNativeScoreCompilation,
        generation_manifest: dict[str, Any], output_dir: Path | None = None,
    ) -> Phase3EvaluationResult:
        paths = locate_result_artifacts(run_result=run_result)
        batch = BatchRunnerEvidence(run_result.success, run_result.process_result.timed_out,
            run_result.error.message if run_result.error else None,
            str(paths.batch_result_dir) if paths.batch_result_dir else None, run_result.restore_succeeded)
        if not paths.is_confirmed:
            snapshot = CmoNativeSnapshot(None, None, None, (), None, None)
            result = self._unscorable(paths, batch, snapshot, "result artifacts are not confirmed")
        else:
            try:
                snapshot, telemetry, weapon_events = _parse_result(
                    paths.primary_result_path,
                    paths.lua_output_path,
                    scenario,
                    score_compilation,
                )
            except (OSError, ValueError, csv.Error, sqlite3.Error) as exc:
                result = self._unscorable(paths, batch, CmoNativeSnapshot(None, None, None, (), None, None), f"result parsing failed: {exc}")
                if output_dir is not None:
                    _write_artifacts(Path(output_dir), result, batch, RuntimeTelemetry((), (), (), (), ()))
                return result
            episodes = _episodes(plan, scenario, snapshot.destroyed_units, telemetry, weapon_events)
            expected = _expected_delta(snapshot.destroyed_units, score_compilation)
            reasons: list[str] = []
            if not run_result.success or run_result.process_result.timed_out:
                reasons.append("CMO execution did not succeed")
            if snapshot.native_score_delta is None or not snapshot.destroyed_units:
                reasons.append("native score or destroyed units are missing")
            if generation_manifest.get("native_score_fragment_checksum") != score_compilation.fragment_checksum:
                reasons.append("native score fragment checksum mismatch")
            if reasons:
                reconciliation = EvidenceReconciliation("unscorable", expected, snapshot.native_score_delta, tuple(reasons))
            elif expected != snapshot.native_score_delta:
                reconciliation = EvidenceReconciliation("result_integrity_failed", expected, snapshot.native_score_delta, ("expected native score differs from CMO score",))
            else:
                reconciliation = EvidenceReconciliation("valid", expected, snapshot.native_score_delta, ())
            semantic = _semantic(reconciliation, scenario, plan, score_compilation, generation_manifest, snapshot, episodes)
            reward = _reward(snapshot, score_compilation, reconciliation, semantic)
            metrics = _metrics(batch, snapshot, episodes, semantic)
            result = Phase3EvaluationResult(paths, snapshot, episodes, reconciliation, semantic, metrics, reward)
        if output_dir is not None:
            _write_artifacts(Path(output_dir), result, batch, telemetry if paths.is_confirmed else RuntimeTelemetry((), (), (), (), ()))
        return result

    @staticmethod
    def _unscorable(paths: ResultArtifactPaths, batch: BatchRunnerEvidence, snapshot: CmoNativeSnapshot, reason: str) -> Phase3EvaluationResult:
        reconciliation = EvidenceReconciliation("unscorable", None, None, (reason,))
        semantic = Phase3SemanticValidation(False, False, (reason,), ())
        metrics = Phase3CombatMetrics(batch.execution_success, None, 0, 0, None, (), (), False, False)
        return Phase3EvaluationResult(paths, snapshot, (), reconciliation, semantic, metrics, RewardBreakdown(None, None, "native-score-v1", ()))


def _sqlite_belongs_to_run(db: Path, lua_path: Path) -> bool:
    try:
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        try:
            row = con.execute("select script from run_info limit 1").fetchone()
        finally:
            con.close()
    except sqlite3.Error:
        return False
    return row is not None and bool(row[0]) and Path(str(row[0])).name == lua_path.name


def _parse_result(path: Path, lua_log: Path | None, scenario: ScenarioDefinition, score: CmoNativeScoreCompilation) -> tuple[CmoNativeSnapshot, RuntimeTelemetry, tuple[_WeaponEvent, ...]]:
    if path.suffix.lower() == ".csv":
        return _parse_csv(path, lua_log, scenario, score)
    return _parse_sqlite(path, lua_log, scenario, score)


def _parse_sqlite(db: Path, lua_log: Path | None, scenario: ScenarioDefinition, score: CmoNativeScoreCompilation) -> tuple[CmoNativeSnapshot, RuntimeTelemetry, tuple[_WeaponEvent, ...]]:
    unit_by_name = {unit.name: unit for unit in scenario.units}
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        scores = {f"{phase}:{side}": value for phase, side, value in con.execute("select phase, side, score from side_scores")}
        side = score.score_spec.rules[0].score_side_id
        initial, final = scores.get(f"start:{side}"), scores.get(f"end:{side}")
        destroyed: list[DestroyedUnit] = []
        for _, event_type, _, name, unit_side, reason in con.execute("select sim_time,event_type,unit_id,unit_name,unit_side,reason from unit_damage_events"):
            unit = unit_by_name.get(name)
            if event_type == "UnitDestroyed":
                if unit is None and _is_weapon_destruction(name, reason):
                    continue
                destroyed.append(DestroyedUnit(unit.unit_id if unit else None, unit.name if unit else name, unit.side_id if unit else unit_side))
        run = con.execute("select sim_ended from run_info limit 1").fetchone()
        weapon_events = tuple(
            _WeaponEvent(event_type, weapon_class, firing_name, target_name, result)
            for event_type, weapon_class, firing_name, target_name, result in con.execute(
                "select event_type,weapon_class,firing_unit_name,target_name,result from weapon_events"
            )
        )
        usage = sum(1 for item in weapon_events if item.event_type == "WeaponFired")
    finally:
        con.close()
    text = lua_log.read_text(encoding="utf-8", errors="replace") if lua_log else ""
    telemetry = RuntimeTelemetry(
        tuple(sorted(_names_after(text, "Launch/"))),
        tuple(sorted(_operation_lines(text, "operation air_attack."))),
        tuple(sorted(_names_after(text, "rtb"))),
        tuple(line for line in text.splitlines() if "CMO-NATIVE-SCORE" in line and "failed" in line.lower()),
        tuple(line for line in text.splitlines() if "runtime error" in line.lower() or "missing contact" in line.lower()),
    )
    return CmoNativeSnapshot(initial, final, None if initial is None or final is None else final - initial,
        tuple(sorted({(item.unit_id, item.unit_name): item for item in destroyed}.values(), key=lambda item: (item.unit_id is None, item.unit_name))), usage,
        run[0] if run else None), telemetry, weapon_events


def _parse_csv(path: Path, lua_log: Path | None, scenario: ScenarioDefinition, score: CmoNativeScoreCompilation) -> tuple[CmoNativeSnapshot, RuntimeTelemetry, tuple[_WeaponEvent, ...]]:
    unit_by_name = {unit.name: unit for unit in scenario.units}
    initial = final = None
    destroyed: list[DestroyedUnit] = []
    weapon_usage = 0
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            metric, side = row.get("指标", ""), row.get("阵营", "")
            subject, result, value = row.get("武器或单位", ""), row.get("结果", ""), row.get("数量或损伤百分比", "")
            if side == score.score_spec.rules[0].score_side_id and metric == "CMO官方初始得分": initial = _parse_int(value)
            if side == score.score_spec.rules[0].score_side_id and metric == "CMO官方最终得分": final = _parse_int(value)
            if metric == "单位战损" and result == "被毁":
                name = subject.split(" [", 1)[0]
                unit = unit_by_name.get(name)
                destroyed.append(DestroyedUnit(unit.unit_id if unit else None, unit.name if unit else name, unit.side_id if unit else side))
            if metric == "武器消耗": weapon_usage += _parse_int(value) or 0
    text = lua_log.read_text(encoding="utf-8", errors="replace") if lua_log else ""
    telemetry = RuntimeTelemetry(tuple(sorted(_names_after(text, "Launch/"))), tuple(sorted(_operation_lines(text, "operation air_attack."))), tuple(sorted(_names_after(text, "rtb"))), (), ())
    return CmoNativeSnapshot(initial, final, None if initial is None or final is None else final - initial,
        tuple(sorted({(item.unit_id, item.unit_name): item for item in destroyed}.values(), key=lambda item: (item.unit_id is None, item.unit_name))), weapon_usage, None), telemetry, ()


def _parse_int(value: str) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _is_weapon_destruction(unit_name: str, reason: str | None) -> bool:
    """CMO 将飞行中的武器也写入 UnitDestroyed，不能把它视为场景单位。"""
    text = f"{unit_name} {reason or ''}".lower()
    return "weapon has been destroyed" in text or "武器" in text


def _names_after(text: str, marker: str) -> list[str]:
    values: list[str] = []
    for line in text.splitlines():
        if marker in line and "success=true" in line:
            values.append(line.split(marker, 1)[1].split()[0])
    return values


def _operation_lines(text: str, marker: str) -> list[str]:
    return [line.split(marker, 1)[1].split()[0] for line in text.splitlines() if marker in line]


def _episodes(
    plan: ExecutionPlan,
    scenario: ScenarioDefinition,
    destroyed: tuple[DestroyedUnit, ...],
    telemetry: RuntimeTelemetry,
    weapon_events: tuple[_WeaponEvent, ...],
) -> tuple[AttackEpisode, ...]:
    destroyed_ids = {item.unit_id for item in destroyed}
    unit_by_id = scenario.unit_by_id()
    episodes: list[AttackEpisode] = []
    for operation in plan.operations:
        if operation.primitive_type not in {"schedule_ship_attack", "aircraft_attack"}:
            continue
        p = operation.parameters
        attacker, targets = str(p["shooter_id"]), tuple(p["target_ids"])
        attacker_unit = unit_by_id.get(attacker)
        if attacker_unit is None:
            continue
        for target in targets:
            target_id = str(target)
            target_unit = unit_by_id.get(target_id)
            if target_unit is None:
                continue
            matched = tuple(
                event for event in weapon_events
                if event.firing_unit_name == attacker_unit.name and event.target_name == target_unit.name
            )
            fired = sum(1 for event in matched if event.event_type == "WeaponFired")
            hits = sum(1 for event in matched if event.event_type == "WeaponEndgame" and (event.result or "").upper() == "KILL")
            intercepted = sum(
                1 for event in matched
                if "INTERCEPT" in (event.result or "").upper() or "POINTDEF" in (event.result or "").upper()
            )
            errors = tuple(sorted({
                line for line in (*telemetry.runtime_error, *telemetry.score_registration_error)
                if attacker in line or target_id in line or attacker_unit.name in line or target_unit.name in line
            }))
            episodes.append(AttackEpisode(operation.operation_id, attacker, str(target), str(p.get("weapon_dbid")),
                attacker_unit.name in telemetry.launch if attacker_unit.platform_type == "aircraft" else None,
                fired if matched else None, hits if matched else None, intercepted if matched else None,
                target_id in destroyed_ids, attacker in destroyed_ids,
                False if attacker in destroyed_ids else (attacker_unit.name in telemetry.return_to_base if telemetry.return_to_base else None), errors))
    return tuple(episodes)


def _expected_delta(destroyed: tuple[DestroyedUnit, ...], score: CmoNativeScoreCompilation) -> int:
    rule_by_unit = {rule.target_unit_id: rule.point_change for rule in score.score_spec.rules}
    return sum(rule_by_unit.get(item.unit_id, 0) for item in destroyed)


def _semantic(rec: EvidenceReconciliation, scenario: ScenarioDefinition, plan: ExecutionPlan, score: CmoNativeScoreCompilation, manifest: dict[str, Any], snapshot: CmoNativeSnapshot, episodes: tuple[AttackEpisode, ...]) -> Phase3SemanticValidation:
    violations: list[str] = []
    units = scenario.unit_by_id()
    if plan.scenario_id != scenario.scenario_id or score.score_spec.scenario_id != scenario.scenario_id:
        violations.append("scenario_id mismatch")
    if manifest.get("scenario_id") != scenario.scenario_id:
        violations.append("generation manifest scenario_id mismatch")
    if manifest.get("runtime_id") != plan.runtime_id or manifest.get("runtime_version") != plan.runtime_version:
        violations.append("generation manifest runtime mismatch")
    if any(item.unit_id not in units for item in snapshot.destroyed_units): violations.append("destroyed unit is outside ScenarioDefinition")
    if any(item.attacker_id not in units or item.target_id not in units for item in episodes): violations.append("episode unit is outside ExecutionPlan scenario")
    if manifest.get("score_spec_checksum") != score.score_spec_checksum: violations.append("score spec checksum mismatch")
    if manifest.get("native_score_fragment_checksum") != score.fragment_checksum: violations.append("score fragment checksum mismatch")
    if rec.status != "valid": violations.extend(rec.reasons)
    return Phase3SemanticValidation(not violations, rec.status == "valid" and not violations, tuple(dict.fromkeys(violations)), ())


def _reward(snapshot: CmoNativeSnapshot, score: CmoNativeScoreCompilation, rec: EvidenceReconciliation, semantic: Phase3SemanticValidation) -> RewardBreakdown:
    if rec.status != "valid" or not semantic.scoreable: return RewardBreakdown(None, None, "native-score-v1", ())
    rules = {rule.target_unit_id: rule for rule in score.score_spec.rules}
    items = tuple(RewardItem(rules[item.unit_id].rule_id, item.unit_id, rules[item.unit_id].point_change, "UnitDestroyed") for item in snapshot.destroyed_units if item.unit_id in rules)
    raw = sum(item.point_change for item in items)
    return RewardBreakdown(raw, raw / 400.0, "native-score-v1", items)


def _metrics(batch: BatchRunnerEvidence, snap: CmoNativeSnapshot, episodes: tuple[AttackEpisode, ...], semantic: Phase3SemanticValidation) -> Phase3CombatMetrics:
    own = sum(1 for item in snap.destroyed_units if item.side_id == "red")
    enemy = len(snap.destroyed_units) - own
    key = tuple(
        f"{item.attacker_id} attack chain: target={item.target_id}, fired={item.weapons_fired}, hits={item.hits}, intercepted={item.intercepted}, attacker_destroyed={item.attacker_destroyed}"
        for item in episodes
        if item.attacker_destroyed or item.target_destroyed or item.important_errors or item.weapons_fired is not None
    )
    if snap.native_score_delta is not None: key += (f"native score delta={snap.native_score_delta}",)
    return Phase3CombatMetrics(batch.execution_success, snap.native_score_delta, enemy, own, snap.weapon_usage, episodes, key, semantic.semantic_valid, semantic.scoreable)


def _write_artifacts(directory: Path, result: Phase3EvaluationResult, batch: BatchRunnerEvidence, telemetry: RuntimeTelemetry) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    payloads = {
        "combat_evidence.json": {"batch": asdict(batch), "native_snapshot": asdict(result.native_snapshot), "runtime_telemetry": asdict(telemetry), "attack_episodes": [asdict(item) for item in result.attack_episodes], "raw_evidence_paths": _paths(result.artifact_paths)},
        "semantic_validation.json": asdict(result.semantic_validation),
        "combat_metrics.json": {**asdict(result.metrics), "attack_episodes": [asdict(item) for item in result.metrics.attack_episodes]},
        "reward_breakdown.json": {**asdict(result.reward_breakdown), "breakdown": [asdict(item) for item in result.reward_breakdown.breakdown]},
    }
    for name, payload in payloads.items():
        (directory / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def _paths(paths: ResultArtifactPaths) -> dict[str, str | None]:
    return {key: str(value) if value else None for key, value in asdict(paths).items() if key != "is_confirmed"}
