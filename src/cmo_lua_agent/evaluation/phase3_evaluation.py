"""Phase 3 确定性评估。

正式路径只认可 BatchRunner 生成的 ``execution-summary.json`` 作为分数事实来源，
并把官方分数、计分事件和直接过程证据投影为候选评估结果。缺少官方摘要时
直接返回不可评分，不再从 SQLite、CSV 或 Lua 日志重新推测战果。

候选评估链调用本模块；Phase 7 会读取同一份 execution summary 生成经验，
因此这里不移动、覆盖或删除上游 CMO Artifact。
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

# 上层契约模型
from cmo_lua_agent.contract.strategy_models import ScenarioDefinition
from cmo_lua_agent.execution.models import CmoRunResult
from cmo_lua_agent.generation.runtime_models import ExecutionPlan
from cmo_lua_agent.scoring.native_score_compiler import CmoNativeScoreCompilation


# ------------------------------ 路径契约：仿真产物文件路径集合 ------------------------------
@dataclass(frozen=True, slots=True)
class ResultArtifactPaths:
    batch_result_dir: Path | None    # 批次总目录
    job_result_dir: Path | None      # 单次仿真子目录
    execution_summary_path: Path | None # 官方机器摘要，正式分数唯一来源
    is_confirmed: bool               # 是否存在有效官方摘要


# ------------------------------ 通用数据载体：被毁单位 ------------------------------
@dataclass(frozen=True, slots=True)
class DestroyedUnit:
    unit_id: str | None  # 场景内唯一ID
    unit_name: str       # 单位名称
    side_id: str         # 所属阵营


# ------------------------------ 证据2：CMO引擎原生快照（最高权威数据源） ------------------------------
@dataclass(frozen=True, slots=True)
class CmoNativeSnapshot:
    native_score_initial: int | None # 仿真开局原生分数
    native_score_final: int | None   # 仿真结束原生分数
    native_score_delta: int | None   # 分数变化量
    destroyed_units: tuple[DestroyedUnit, ...] # 所有被毁实体
    weapon_usage: int | None         # 武器总发射次数
    simulation_end_time: str | None # 仿真结束时间
    score_source: str | None = None
    execution_fidelity: str = "unknown"


@dataclass(frozen=True, slots=True)
class NativeScoreEvent:
    """来自 execution-summary.json 的已验证 CMO 原生计分事件。"""
    event_id: str
    event_sequence: int
    sim_time: str
    rule_id: str
    unit_id: str | None
    delta: int
    score_before: int
    score_after: int
    evidence_ref: str | None


# ------------------------------ 标准化攻击链路：单次完整攻击闭环 ------------------------------
@dataclass(frozen=True, slots=True)
class AttackEpisode:
    operation_id: str | None # 对应ExecutionPlan操作ID
    attacker_id: str         # 攻击者unit_id
    target_id: str           # 目标unit_id
    weapon_id: str | None    # 武器DBID
    launch_succeeded: bool | None # 飞机是否成功起飞
    weapons_fired: int | None    # 发射弹药总数
    hits: int | None             # 命中击杀数
    intercepted: int | None      # 被拦截弹药数
    target_destroyed: bool | None       # 目标是否击毁
    attacker_destroyed: bool | None     # 发射方是否被毁
    returned_to_base: bool | None# 是否成功返航
    important_errors: tuple[str, ...] # 本次攻击相关报错
    scheduled: bool | None = None
    triggered: bool | None = None
    attacker_found: bool | None = None
    target_found: bool | None = None
    contact_acquired: bool | None = None
    attack_range_reached: bool | None = None
    attack_command_called: bool | None = None
    attack_command_succeeded: bool | None = None
    failure_stage: str | None = None
    evidence_refs: tuple[str, ...] = ()


# ------------------------------ 证据对齐校验结果 ------------------------------
@dataclass(frozen=True, slots=True)
class EvidenceReconciliation:
    """官方执行证据是否足以进入后续评分和语义判断。"""
    status: str              # 状态：valid/unscorable
    reasons: tuple[str, ...] # 不可评分原因；有效时为空


# ------------------------------ 语义校验结果：策略与仿真是否匹配 ------------------------------
@dataclass(frozen=True, slots=True)
class Phase3SemanticValidation:
    semantic_valid: bool    # 整体语义是否合规
    scoreable: bool        # 是否可以正常计算得分
    violations: tuple[str, ...] # 违规项列表
    warnings: tuple[str, ...]   # 警告列表


# ------------------------------ 标准化作战指标集合 ------------------------------
@dataclass(frozen=True, slots=True)
class Phase3CombatMetrics:
    execution_success: bool               # 仿真进程是否成功
    native_score_delta: int | None        # 原生分数变化
    enemy_units_destroyed: int            # 击毁敌方数量
    own_units_destroyed: int              # 己方损失数量
    weapon_expended: int | None           # 总弹药消耗
    key_events: tuple[str, ...]           # 关键作战事件文本
    semantic_valid: bool                  # 语义校验是否通过
    scoreable: bool                       # 是否可打分


# ------------------------------ 单条得分明细项 ------------------------------
@dataclass(frozen=True, slots=True)
class RewardItem:
    rule_id: str     # 计分规则ID
    unit_id: str     # 对应被毁单位
    point_change: int# 加减分数值
    event_type: str  # 触发事件(UnitDestroyed)


# ------------------------------ 总分拆解包 ------------------------------
@dataclass(frozen=True, slots=True)
class RewardBreakdown:
    raw_score: int | None               # 原始总分
    normalized_reward: float | None     # 归一化后奖励值
    normalization_version: str          # 计分版本(保证确定性)
    breakdown: tuple[RewardItem, ...]   # 每条单位得分明细


# ------------------------------ Phase3完整输出结果：全链路统一返回对象 ------------------------------
@dataclass(frozen=True, slots=True)
class Phase3EvaluationResult:
    artifact_paths: ResultArtifactPaths          # 原始文件路径
    native_snapshot: CmoNativeSnapshot           # CMO原生快照
    attack_episodes: tuple[AttackEpisode, ...]    # 攻击链路
    reconciliation: EvidenceReconciliation       # 证据对齐报告
    semantic_validation: Phase3SemanticValidation # 语义校验报告
    metrics: Phase3CombatMetrics                 # 作战指标
    reward_breakdown: RewardBreakdown            # 得分明细
    score_events: tuple[NativeScoreEvent, ...] = ()


# ------------------------------ 工具函数：定位本次仿真所有产物文件 ------------------------------
def locate_result_artifacts(*, run_result: CmoRunResult) -> ResultArtifactPaths:
    """定位唯一任务目录及其官方执行摘要。"""
    batch = run_result.batch_result_dir or run_result.process_result.batch_result_dir
    if batch is None or not Path(batch).is_dir():
        return ResultArtifactPaths(None, None, None, False)
    batch = Path(batch)
    jobs = sorted(path for path in batch.iterdir() if path.is_dir() and path.name.startswith("001_"))
    job = jobs[0] if len(jobs) == 1 else None
    summary = job / "execution-summary.json" if job and (job / "execution-summary.json").is_file() else None
    return ResultArtifactPaths(batch, job, summary, summary is not None)


def _empty_snapshot() -> CmoNativeSnapshot:
    """构造不可评分分支共用的空快照，保证所有异常出口语义一致。"""
    return CmoNativeSnapshot(None, None, None, (), None, None)


def _batch_evidence(
    run_result: CmoRunResult,
    paths: ResultArtifactPaths,
) -> dict[str, object]:
    """投影执行层事实，不在评估层重新解释进程状态。"""
    return {
        "execution_success": run_result.success,
        "timed_out": run_result.process_result.timed_out,
        "error": run_result.error.message if run_result.error else None,
        "result_dir": str(paths.batch_result_dir) if paths.batch_result_dir else None,
        "configuration_restored": run_result.restore_succeeded,
    }


# ------------------------------ Phase3 核心评估服务类 ------------------------------
class Phase3EvaluationService:
    def record_unscorable(
        self,
        *,
        run_result: CmoRunResult,
        output_dir: Path,
        reason: str,
    ) -> Phase3EvaluationResult:
        """仿真数据异常/缺失，生成【不可评分】标准化产物并落地文件"""
        paths = locate_result_artifacts(run_result=run_result)
        batch = _batch_evidence(run_result, paths)
        # 构造空快照、不可评分结果
        result = self._unscorable(
            paths,
            batch,
            _empty_snapshot(),
            reason,
        )
        # 写入全套空json产物
        _write_artifacts(Path(output_dir), result, batch)
        return result

    def evaluate(
        self, *, run_result: CmoRunResult, scenario: ScenarioDefinition,
        plan: ExecutionPlan, score_compilation: CmoNativeScoreCompilation,
        generation_manifest: dict[str, Any], output_dir: Path | None = None,
        candidate_id: str | None = None,
    ) -> Phase3EvaluationResult:
        """Phase3主入口：完整解析证据→对齐校验→语义校验→指标提取→生成得分"""
        # 1 定位所有结果文件
        paths = locate_result_artifacts(run_result=run_result)
        batch = _batch_evidence(run_result, paths)
        # 无有效结果文件，直接标记不可评分
        if not paths.is_confirmed:
            snapshot = _empty_snapshot()
            result = self._unscorable(paths, batch, snapshot, "execution-summary.json is missing")
        else:
            try:
                # summary 同时承担官方分数、战损和直接过程证据的事实来源。
                snapshot, score_events = _parse_execution_summary(
                    paths.execution_summary_path,
                    scenario=scenario,
                    expected_batch_run_id=paths.batch_result_dir.name if paths.batch_result_dir else None,
                    expected_candidate_id=candidate_id,
                    expected_scoring_side=score_compilation.score_spec.rules[0].score_side_id,
                )
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                # 文件解析失败，返回不可评分
                result = self._unscorable(paths, batch, _empty_snapshot(), f"result parsing failed: {exc}")
                if output_dir is not None:
                    _write_artifacts(Path(output_dir), result, batch)
                return result
            episodes = _parse_attack_episodes(paths.execution_summary_path)
            # CMO 官方 summary 是唯一分数事实源。这里仅判断证据是否可用，
            # 不再根据战损反推另一个“理论分数”与官方分数竞争。
            reasons: list[str] = []
            # 多维度数据一致性检查
            if not run_result.success or run_result.process_result.timed_out:
                reasons.append("CMO execution did not succeed")
            if snapshot.native_score_delta is None:
                reasons.append("official native score is missing")
            # 计分Lua指纹不匹配，说明计分代码版本不一致
            if generation_manifest.get("native_score_fragment_checksum") != score_compilation.fragment_checksum:
                reasons.append("native score fragment checksum mismatch")
            # 存在异常 → 不可评分
            if reasons:
                reconciliation = EvidenceReconciliation("unscorable", tuple(reasons))
            else:
                reconciliation = EvidenceReconciliation("valid", ())
            # 5 全局语义校验：场景/执行计划/计分配置ID、指纹统一校验
            semantic = _semantic(reconciliation, scenario, plan, score_compilation, generation_manifest, snapshot, episodes)
            # 6 计算分层得分明细
            reward = _reward(snapshot, score_events, reconciliation, semantic)
            # 7 提取标准化作战指标
            metrics = _metrics(run_result.success, snapshot, episodes, semantic)
            # 组装完整评估结果
            result = Phase3EvaluationResult(paths, snapshot, episodes, reconciliation, semantic, metrics, reward, score_events)
        # 落地全套json产物文件
        if output_dir is not None:
            _write_artifacts(Path(output_dir), result, batch)
        return result

    @staticmethod
    def _unscorable(paths: ResultArtifactPaths, batch: dict[str, object], snapshot: CmoNativeSnapshot, reason: str) -> Phase3EvaluationResult:
        """工具：生成不可评分空结果模板"""
        reconciliation = EvidenceReconciliation("unscorable", (reason,))
        semantic = Phase3SemanticValidation(False, False, (reason,), ())
        metrics = Phase3CombatMetrics(bool(batch["execution_success"]), None, 0, 0, None, (), False, False)
        return Phase3EvaluationResult(paths, snapshot, (), reconciliation, semantic, metrics, RewardBreakdown(None, None, "native-score-v1", ()), ())


def _parse_execution_summary(
    path: Path | None,
    *,
    scenario: ScenarioDefinition,
    expected_batch_run_id: str | None,
    expected_candidate_id: str | None,
    expected_scoring_side: str,
) -> tuple[CmoNativeSnapshot, tuple[NativeScoreEvent, ...]]:
    """Parse and validate the sole authoritative native score source."""
    if path is None:
        raise ValueError("execution-summary.json is missing")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("execution summary must be an object")
    run = payload.get("run")
    score = payload.get("official_score")
    integrity = payload.get("evidence_integrity")
    if not isinstance(run, dict) or not isinstance(score, dict) or not isinstance(integrity, dict):
        raise ValueError("execution summary has missing required sections")
    if expected_batch_run_id and run.get("run_id") != expected_batch_run_id:
        raise ValueError("execution summary run_id does not match Results directory")
    if expected_candidate_id and run.get("candidate_id") != expected_candidate_id:
        raise ValueError("execution summary candidate_id does not match candidate")
    if run.get("scenario_id") != scenario.scenario_id:
        raise ValueError("execution summary scenario_id does not match scenario")
    # `display_name` is presentation-only.  The BatchRunner has already bound
    # the official score to the stable side and the exact CMO side identifier.
    if run.get("scoring_side_id") != expected_scoring_side:
        raise ValueError("execution summary run scoring side does not match score contract")
    if score.get("stable_side_id") != expected_scoring_side:
        raise ValueError("execution summary stable side does not match score contract")
    if score.get("cmo_side_id") != expected_scoring_side:
        raise ValueError("execution summary exact CMO side does not match score contract")
    if not isinstance(score.get("display_name"), str) or not score["display_name"].strip():
        raise ValueError("execution summary display name is missing")
    if score.get("status") != "VALID":
        raise ValueError("execution summary official score is unscorable")
    initial, final, declared_delta = score.get("initial"), score.get("final"), score.get("delta")
    if any(not isinstance(value, int) for value in (initial, final, declared_delta)):
        raise ValueError("official_score values must be integers")
    if final - initial != declared_delta:
        raise ValueError("official_score delta does not equal final minus initial")
    # A native final score remains usable for black-box outcome comparison
    # when Collector-side event provenance is incomplete.
    raw_events = payload.get("score_events")
    if score.get("score_event_chain_status") != "VALID":
        raw_events = []
    if not isinstance(raw_events, list):
        raise ValueError("execution summary score_events must be an array")
    # Zero-score executions have no score transition to report.  They remain
    # valid only when the authoritative summary also reports a zero delta.
    if not raw_events and declared_delta != 0:
        raise ValueError("execution summary score_events are missing for a non-zero score delta")
    events: list[NativeScoreEvent] = []
    for item in raw_events:
        if not isinstance(item, dict):
            raise ValueError("score event must be an object")
        fields = (
            "event_id", "event_sequence", "sim_time", "rule_id", "raw_rule_name",
            "delta", "score_before", "score_after",
        )
        if any(field not in item for field in fields):
            raise ValueError("score event has missing fields")
        if not isinstance(item["rule_id"], str) or not item["rule_id"].startswith("native_score/"):
            raise ValueError("score event rule_id is not a stable native score identifier")
        if not isinstance(item["raw_rule_name"], str) or not item["raw_rule_name"].strip():
            raise ValueError("score event raw_rule_name is missing")
        if not isinstance(item["event_sequence"], int) or any(not isinstance(item[field], int) for field in ("delta", "score_before", "score_after")):
            raise ValueError("score event has invalid numeric fields")
        events.append(NativeScoreEvent(
            str(item["event_id"]), item["event_sequence"], str(item["sim_time"]), str(item["rule_id"]),
            str(item["unit_id"]) if item.get("unit_id") is not None else None,
            item["delta"], item["score_before"], item["score_after"],
            str(item["evidence_ref"]) if item.get("evidence_ref") is not None else None,
        ))
    events.sort(key=lambda event: event.event_sequence)
    if len({event.event_sequence for event in events}) != len(events):
        raise ValueError("score event sequence is not unique")
    if events and (events[0].score_before != initial or events[-1].score_after != final):
        raise ValueError("score event endpoints do not match official score")
    if any(left.score_after != right.score_before for left, right in zip(events, events[1:])):
        raise ValueError("score event chain is discontinuous")
    if sum(event.delta for event in events) != final - initial:
        raise ValueError("score event deltas do not match official score delta")
    units = scenario.unit_by_id()
    destroyed: list[DestroyedUnit] = []
    for side_id, entries in (payload.get("losses") or {}).items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            unit_id = entry.get("unit_id")
            unit = units.get(unit_id)
            destroyed.append(DestroyedUnit(unit_id if unit else None, unit.name if unit else str(entry.get("name", unit_id or "unknown")), unit.side_id if unit else str(side_id)))
    usage = sum(int(item.get("quantity", 0)) for item in payload.get("weapon_expenditures", []) if isinstance(item, dict) and isinstance(item.get("quantity", 0), int))
    runtime_execution = payload.get("runtime_execution")
    execution_fidelity = "unknown"
    if runtime_execution is not None:
        if not isinstance(runtime_execution, dict):
            raise ValueError("execution summary runtime_execution must be an object")
        fidelity = runtime_execution.get("execution_fidelity")
        if fidelity not in {"complete", "partial"}:
            raise ValueError("execution summary execution_fidelity is invalid")
        execution_fidelity = "verified" if fidelity == "complete" else "partial"
    return CmoNativeSnapshot(
        initial,
        final,
        final - initial,
        tuple(destroyed),
        usage,
        None,
        "execution-summary.json#/official_score/final",
        execution_fidelity,
    ), tuple(events)


def _parse_attack_episodes(path: Path | None) -> tuple[AttackEpisode, ...]:
    """只投影 summary 已明确记录的攻击过程，不从其他日志猜测。"""
    if path is None:
        return ()
    payload = json.loads(path.read_text(encoding="utf-8"))
    traces = payload.get("attack_execution_trace")
    if traces is None:
        return ()
    if not isinstance(traces, list):
        raise ValueError("execution summary attack_execution_trace must be an array")

    def stage_value(stages: object, name: str) -> bool | None:
        rows = [
            row for row in stages
            if isinstance(row, dict) and row.get("stage") == name
        ] if isinstance(stages, list) else []
        if not rows:
            return None
        if any(row.get("success") is True for row in rows):
            return True
        if all(row.get("success") is False for row in rows):
            return False
        return None

    episodes: list[AttackEpisode] = []
    for row in traces:
        if not isinstance(row, dict):
            continue
        attacker_id = row.get("attacker_id")
        target_id = row.get("target_id")
        if not isinstance(attacker_id, str) or not isinstance(target_id, str):
            continue
        stages = row.get("attack_stages", row.get("stages", []))
        waves = row.get("attack_waves", [])
        valid_waves = [wave for wave in waves if isinstance(wave, dict)] if isinstance(waves, list) else []
        fired = sum(wave.get("fired_count", 0) for wave in valid_waves if isinstance(wave.get("fired_count", 0), int))
        hits = sum(wave.get("hit_count", 0) for wave in valid_waves if isinstance(wave.get("hit_count", 0), int))
        damage = row.get("target_damage")
        episodes.append(AttackEpisode(
            operation_id=str(row["operation_id"]) if row.get("operation_id") is not None else None,
            attacker_id=attacker_id,
            target_id=target_id,
            weapon_id=str(row["weapon_dbid"]) if row.get("weapon_dbid") is not None else None,
            launch_succeeded=None,
            weapons_fired=fired if valid_waves else None,
            hits=hits if valid_waves else None,
            intercepted=None,
            target_destroyed=(bool(damage.get("destroyed")) if isinstance(damage, dict) and damage.get("destroyed") is not None else None),
            attacker_destroyed=None,
            returned_to_base=None,
            important_errors=(),
            scheduled=stage_value(stages, "scheduled"),
            triggered=stage_value(stages, "triggered"),
            attacker_found=stage_value(stages, "attacker_found"),
            target_found=stage_value(stages, "target_found"),
            contact_acquired=stage_value(stages, "contact_acquired"),
            attack_range_reached=stage_value(stages, "attack_range_reached"),
            attack_command_called=stage_value(stages, "attack_command_called"),
            attack_command_succeeded=row.get("attack_command_accepted", stage_value(stages, "attack_command_succeeded")),
            failure_stage=(str(row["final_stage"]) if row.get("success") is False and row.get("final_stage") is not None else None),
            evidence_refs=tuple(str(value) for value in row.get("evidence_refs", []) if isinstance(value, str)),
        ))
    return tuple(episodes)


# ------------------------------ 全量语义一致性校验 ------------------------------
def _semantic(rec: EvidenceReconciliation, scenario: ScenarioDefinition, plan: ExecutionPlan, score: CmoNativeScoreCompilation, manifest: dict[str, Any], snapshot: CmoNativeSnapshot, episodes: tuple[AttackEpisode, ...]) -> Phase3SemanticValidation:
    violations: list[str] = []
    unit_by_id = scenario.unit_by_id()
    # 场景ID跨文件不一致
    if plan.scenario_id != scenario.scenario_id or score.score_spec.scenario_id != scenario.scenario_id:
        violations.append("scenario_id mismatch")
    # 生成清单场景ID不匹配
    if manifest.get("scenario_id") != scenario.scenario_id:
        violations.append("generation manifest scenario_id mismatch")
    # Runtime版本不统一
    if manifest.get("runtime_id") != plan.runtime_id or manifest.get("runtime_version") != plan.runtime_version:
        violations.append("generation manifest runtime mismatch")
    # 被毁单位不在场景定义内
    if any(item.unit_id not in unit_by_id for item in snapshot.destroyed_units): violations.append("destroyed unit is outside ScenarioDefinition")
    # 攻击链路单位不存在于场景
    if any(item.attacker_id not in unit_by_id or item.target_id not in unit_by_id for item in episodes): violations.append("episode unit is outside ExecutionPlan scenario")
    # 计分配置指纹不匹配
    if manifest.get("score_spec_checksum") != score.score_spec.checksum: violations.append("score spec checksum mismatch")
    # 计分Lua片段指纹不一致
    if manifest.get("native_score_fragment_checksum") != score.fragment_checksum: violations.append("score fragment checksum mismatch")
    # 证据对齐异常一并纳入违规
    if rec.status != "valid": violations.extend(rec.reasons)
    return Phase3SemanticValidation(not violations, rec.status == "valid" and not violations, tuple(dict.fromkeys(violations)), ())


# ------------------------------ 根据校验结果生成分层得分明细 ------------------------------
def _reward(snapshot: CmoNativeSnapshot, score_events: tuple[NativeScoreEvent, ...], rec: EvidenceReconciliation, semantic: Phase3SemanticValidation) -> RewardBreakdown:
    # 校验不通过直接返回空得分
    if rec.status != "valid" or not semantic.scoreable:
        return RewardBreakdown(None, None, "native-score-v1", ())
    # Reward is an audit projection of official score events, never a unit-loss recomputation.
    # 每条被毁单位生成得分项
    items = tuple(
        RewardItem(
            item.rule_id,
            item.unit_id or "unknown",
            item.delta,
            "SCORE_CHANGED",
        )
        for item in score_events
    )
    raw = snapshot.native_score_final
    return RewardBreakdown(raw, raw / 400.0 if raw is not None else None, "native-score-v1", items)


# ------------------------------ 聚合所有标准化作战指标 ------------------------------
def _metrics(execution_success: bool, snap: CmoNativeSnapshot, episodes: tuple[AttackEpisode, ...], semantic: Phase3SemanticValidation) -> Phase3CombatMetrics:
    own = sum(1 for item in snap.destroyed_units if item.side_id == "red")
    enemy = len(snap.destroyed_units) - own
    key_events: list[str] = []
    # 收集关键作战日志
    for item in episodes:
        if item.attacker_destroyed or item.target_destroyed or item.weapons_fired or item.important_errors:
            key_events.append(
                f"{item.attacker_id}攻击{item.target_id},发射{item.weapons_fired},击毁={item.target_destroyed}"
            )
    if snap.native_score_delta is not None:
        key_events.append(f"原生得分变化：{snap.native_score_delta}")
    return Phase3CombatMetrics(
        execution_success,
        snap.native_score_delta,
        enemy,
        own,
        snap.weapon_usage,
        tuple(key_events),
        semantic.semantic_valid,
        semantic.scoreable,
    )


# ------------------------------ 落地全套Phase3输出JSON文件 ------------------------------
def _write_artifacts(
    directory: Path,
    result: Phase3EvaluationResult,
    batch: dict[str, object],
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    payloads = {
        "combat_evidence.json": {"batch": batch, "native_snapshot": asdict(result.native_snapshot), "runtime_telemetry": {}, "attack_episodes": [asdict(item) for item in result.attack_episodes], "raw_evidence_paths": _paths(result.artifact_paths)},
        "semantic_validation.json": asdict(result.semantic_validation),
        "combat_metrics.json": {**asdict(result.metrics), "attack_episodes": [asdict(item) for item in result.attack_episodes]},
        "reward_breakdown.json": {**asdict(result.reward_breakdown), "breakdown": [asdict(item) for item in result.reward_breakdown.breakdown]},
        "native_score_diagnostics.json": {
            "score_source": result.native_snapshot.score_source,
            "first_score": result.native_snapshot.native_score_initial,
            "minimum_score": min((event.score_after for event in result.score_events), default=None),
            "last_score": result.native_snapshot.native_score_final,
            "parsed_final_score": result.native_snapshot.native_score_final,
            "all_score_events": [asdict(event) for event in result.score_events],
            "result_dir": str(result.artifact_paths.job_result_dir) if result.artifact_paths.job_result_dir else None,
            "sources_consistent": result.reconciliation.status == "valid",
        },
    }
    for filename, data in payloads.items():
        (directory / filename).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


# ------------------------------ Path对象转可序列化字符串字典 ------------------------------
def _paths(paths: ResultArtifactPaths) -> dict[str, str | None]:
    return {k: str(v) if v else None for k, v in asdict(paths).items() if k != "is_confirmed"}
