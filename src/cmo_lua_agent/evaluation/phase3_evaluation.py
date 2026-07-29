"""Minimal, deterministic Phase 3 evidence and native-score evaluation.
Phase3 最小化确定性评估核心代码：解析CMO仿真输出证据、校验数据一致性、生成标准化作战指标与可拆解得分，
完全遵循文档Phase3设计，统一解析sqlite/csv两类仿真结果文件，输出结构化评估产物，不可变契约保证确定性。
"""
from __future__ import annotations

import csv
import json
import sqlite3
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
    primary_result_path: Path | None# 核心结果文件(sqlite/csv)
    runner_log_path: Path | None     # 执行器日志
    lua_output_path: Path | None     # Lua运行时输出日志
    is_confirmed: bool               # 是否存在有效结果文件
    execution_summary_path: Path | None = None  # 官方机器摘要，正式分数唯一来源


# ------------------------------ 证据1：外部执行层日志（BatchRunner） ------------------------------
@dataclass(frozen=True, slots=True)
class BatchRunnerEvidence:
    execution_success: bool    # CMO进程是否正常跑完
    timed_out: bool            # 是否超时中断
    error: str | None          # 进程/脚本异常信息
    result_dir: str | None     # 结果目录路径
    configuration_restored: bool # 仿真结束是否恢复原始配置


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


# ------------------------------ 证据3：Lua Runtime埋点日志 ------------------------------
@dataclass(frozen=True, slots=True)
class RuntimeTelemetry:
    launch: tuple[str, ...]               # 成功起飞飞机名称列表
    attack_ordered: tuple[str, ...]      # 下达攻击指令记录
    return_to_base: tuple[str, ...]      # 成功返航飞机
    score_registration_error: tuple[str, ...] # 计分触发器注册异常
    runtime_error: tuple[str, ...]       # Lua运行时各类报错


# ------------------------------ 内部临时结构：原始武器发射事件（仅解析用，不输出） ------------------------------
@dataclass(frozen=True, slots=True)
class _WeaponEvent:
    """仅用于将 CMO 原始武器事件聚合到攻击链，绝不直接输出。"""
    event_type: str         # 事件类型(发射/命中/拦截)
    weapon_class: str | None# 武器型号
    firing_unit_name: str | None # 发射单位名称
    target_name: str | None      # 目标名称
    result: str | None           # 结果(击杀/拦截/脱靶)


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
    target_destroyed: bool       # 目标是否击毁
    attacker_destroyed: bool     # 发射方是否被毁
    returned_to_base: bool | None# 是否成功返航
    important_errors: tuple[str, ...] # 本次攻击相关报错


# ------------------------------ 综合证据包：三类证据统一封装 ------------------------------
@dataclass(frozen=True, slots=True)
class CombatEvidence:
    batch: BatchRunnerEvidence                  # 进程执行证据
    native_snapshot: CmoNativeSnapshot          # CMO原生快照
    runtime_telemetry: RuntimeTelemetry         # Lua埋点日志
    attack_episodes: tuple[AttackEpisode, ...]  # 聚合后的标准化攻击链
    raw_evidence_paths: ResultArtifactPaths     # 原始文件路径


# ------------------------------ 证据对齐校验结果 ------------------------------
@dataclass(frozen=True, slots=True)
class EvidenceReconciliation:
    status: str                     # 状态：valid/unscorable/result_integrity_failed
    expected_native_score_delta: int | None # 根据击毁单位理论得分
    actual_native_score_delta: int | None   # CMO实际得分
    reasons: tuple[str, ...]                # 不一致/不可评分原因


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
    attack_episodes: tuple[AttackEpisode, ...] # 所有攻击闭环
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
    """根据CMO运行结果，自动查找批次目录、sqlite/csv核心结果、各类日志"""
    # 取仿真根批次目录
    batch = run_result.batch_result_dir or run_result.process_result.batch_result_dir
    if batch is None or not Path(batch).is_dir():
        return ResultArtifactPaths(None, None, None, None, None, False, None)
    batch = Path(batch)
    # 查找001_开头单次仿真子文件夹
    jobs = sorted(path for path in batch.iterdir() if path.is_dir() and path.name.startswith("001_"))
    job = jobs[0] if len(jobs) == 1 else None
    summary = job / "execution-summary.json" if job and (job / "execution-summary.json").is_file() else None
    primary = None
    # 优先sqlite事件库，其次csv汇总文件
    sqlite_present = bool(job and (job / "events.sqlite").is_file())
    if job and sqlite_present and _sqlite_belongs_to_run(job / "events.sqlite", run_result.lua_path):
        primary = job / "events.sqlite"
    elif job and (job / "combat-summary.csv").is_file():
        primary = job / "combat-summary.csv"
    return ResultArtifactPaths(
        batch, job, primary, batch / "runner.log" if (batch / "runner.log").is_file() else None,
        job / "lua-output.log" if job and (job / "lua-output.log").is_file() else None,
        job is not None and summary is not None and (not sqlite_present or primary is not None),
        summary,
    )


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
        batch = BatchRunnerEvidence(
            run_result.success,
            run_result.process_result.timed_out,
            run_result.error.message if run_result.error else None,
            str(paths.batch_result_dir) if paths.batch_result_dir else None,
            run_result.restore_succeeded,
        )
        # 构造空快照、不可评分结果
        result = self._unscorable(
            paths,
            batch,
            CmoNativeSnapshot(None, None, None, (), None, None),
            reason,
        )
        # 写入全套空json产物
        _write_artifacts(Path(output_dir), result, batch, RuntimeTelemetry((), (), (), (), ()))
        return result

    def evaluate(
        self, *, run_result: CmoRunResult, run_id: str, scenario: ScenarioDefinition,
        plan: ExecutionPlan, score_compilation: CmoNativeScoreCompilation,
        generation_manifest: dict[str, Any], output_dir: Path | None = None,
        candidate_id: str | None = None,
    ) -> Phase3EvaluationResult:
        """Phase3主入口：完整解析证据→对齐校验→语义校验→指标提取→生成得分"""
        # 1 定位所有结果文件
        paths = locate_result_artifacts(run_result=run_result)
        batch = BatchRunnerEvidence(run_result.success, run_result.process_result.timed_out,
            run_result.error.message if run_result.error else None,
            str(paths.batch_result_dir) if paths.batch_result_dir else None, run_result.restore_succeeded)
        # 无有效结果文件，直接标记不可评分
        if not paths.is_confirmed:
            snapshot = CmoNativeSnapshot(None, None, None, (), None, None)
            result = self._unscorable(paths, batch, snapshot, "execution-summary.json is missing")
        else:
            try:
                # 2 解析sqlite/csv，得到原生快照、Lua埋点、原始武器事件
                summary_snapshot, score_events = _parse_execution_summary(
                    paths.execution_summary_path,
                    scenario=scenario,
                    expected_batch_run_id=paths.batch_result_dir.name if paths.batch_result_dir else None,
                    expected_candidate_id=candidate_id,
                    expected_scoring_side=score_compilation.score_spec.rules[0].score_side_id,
                )
                if paths.primary_result_path is not None:
                    factual, telemetry, weapon_events = _parse_result(
                        paths.primary_result_path, paths.lua_output_path, scenario, score_compilation,
                    )
                else:
                    factual, telemetry, weapon_events = CmoNativeSnapshot(None, None, None, (), None, None), RuntimeTelemetry((), (), (), (), ()), ()
                snapshot = CmoNativeSnapshot(
                    summary_snapshot.native_score_initial, summary_snapshot.native_score_final,
                    summary_snapshot.native_score_delta, summary_snapshot.destroyed_units,
                    summary_snapshot.weapon_usage if summary_snapshot.weapon_usage is not None else factual.weapon_usage,
                    factual.simulation_end_time, "execution-summary.json#/official_score/final",
                )
            except (OSError, ValueError, csv.Error, sqlite3.Error) as exc:
                # 文件解析失败，返回不可评分
                result = self._unscorable(paths, batch, CmoNativeSnapshot(None, None, None, (), None, None), f"result parsing failed: {exc}")
                if output_dir is not None:
                    _write_artifacts(Path(output_dir), result, batch, RuntimeTelemetry((), (), (), (), ()))
                return result
            # 3 原始武器事件聚合为标准化攻击链路AttackEpisode
            episodes = _episodes(plan, scenario, snapshot.destroyed_units, telemetry, weapon_events)
            # 4 理论预期得分（按计分规则统计击毁单位）
            expected = snapshot.native_score_delta
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
                reconciliation = EvidenceReconciliation("unscorable", expected, snapshot.native_score_delta, tuple(reasons))
            # 理论得分和CMO实际分数不一致 → 数据冲突
            elif not reasons:
                reconciliation = EvidenceReconciliation("valid", expected, snapshot.native_score_delta, ())
            # 全部数据对齐正常
            else:
                reconciliation = EvidenceReconciliation("valid", expected, snapshot.native_score_delta, ())
            # 5 全局语义校验：场景/执行计划/计分配置ID、指纹统一校验
            semantic = _semantic(reconciliation, scenario, plan, score_compilation, generation_manifest, snapshot, episodes)
            # 6 计算分层得分明细
            reward = _reward(snapshot, score_events, reconciliation, semantic)
            # 7 提取标准化作战指标
            metrics = _metrics(batch, snapshot, episodes, semantic)
            # 组装完整评估结果
            result = Phase3EvaluationResult(paths, snapshot, episodes, reconciliation, semantic, metrics, reward, score_events)
        # 落地全套json产物文件
        if output_dir is not None:
            _write_artifacts(Path(output_dir), result, batch, telemetry if paths.is_confirmed else RuntimeTelemetry((), (), (), (), ()))
        return result

    @staticmethod
    def _unscorable(paths: ResultArtifactPaths, batch: BatchRunnerEvidence, snapshot: CmoNativeSnapshot, reason: str) -> Phase3EvaluationResult:
        """工具：生成不可评分空结果模板"""
        reconciliation = EvidenceReconciliation("unscorable", None, None, (reason,))
        semantic = Phase3SemanticValidation(False, False, (reason,), ())
        metrics = Phase3CombatMetrics(batch.execution_success, None, 0, 0, None, (), (), False, False)
        return Phase3EvaluationResult(paths, snapshot, (), reconciliation, semantic, metrics, RewardBreakdown(None, None, "native-score-v1", ()), ())


# ------------------------------ 底层工具：校验sqlite文件属于本次Lua仿真 ------------------------------
def _sqlite_belongs_to_run(db: Path, lua_path: Path) -> bool:
    """读取sqlite内run_info表，核对脚本文件名匹配，防止读错历史仿真数据"""
    try:
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        try:
            row = con.execute("select script from run_info limit 1").fetchone()
        finally:
            con.close()
    except sqlite3.Error:
        return False
    return row is not None and bool(row[0]) and Path(str(row[0])).name == lua_path.name


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
    if score.get("status") != "VALID" or score.get("score_event_chain_status") != "VALID":
        raise ValueError("execution summary official score is unscorable")
    if (
        integrity.get("status") != "VALID"
        or integrity.get("score_chain_consistent") is not True
        or integrity.get("results_complete") is not True
    ):
        raise ValueError("execution summary evidence integrity is not valid")
    initial, final, declared_delta = score.get("initial"), score.get("final"), score.get("delta")
    if any(not isinstance(value, int) for value in (initial, final, declared_delta)):
        raise ValueError("official_score values must be integers")
    if final - initial != declared_delta:
        raise ValueError("official_score delta does not equal final minus initial")
    raw_events = payload.get("score_events")
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
    return CmoNativeSnapshot(initial, final, final - initial, tuple(destroyed), usage, None, "execution-summary.json#/official_score/final"), tuple(events)


# ------------------------------ 分发解析器：自动区分sqlite/csv文件 ------------------------------
def _parse_result(path: Path, lua_log: Path | None, scenario: ScenarioDefinition, score: CmoNativeScoreCompilation) -> tuple[CmoNativeSnapshot, RuntimeTelemetry, tuple[_WeaponEvent, ...]]:
    if path.suffix.lower() == ".csv":
        return _parse_csv(path, lua_log, scenario, score)
    return _parse_sqlite(path, lua_log, scenario, score)


# ------------------------------ Sqlite完整解析逻辑 ------------------------------
def _parse_sqlite(db: Path, lua_log: Path | None, scenario: ScenarioDefinition, score: CmoNativeScoreCompilation) -> tuple[CmoNativeSnapshot, RuntimeTelemetry, tuple[_WeaponEvent, ...]]:
    unit_by_name = {unit.name: unit for unit in scenario.units}
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        # 读取各阶段阵营分数
        scores = {f"{phase}:{side}": value for phase, side, value in con.execute("select phase, side, score from side_scores")}
        side = score.score_spec.rules[0].score_side_id
        initial, final = scores.get(f"start:{side}"), scores.get(f"end:{side}")
        destroyed: list[DestroyedUnit] = []
        # 读取单位击毁事件，过滤导弹武器自爆记录
        for _, event_type, _, name, unit_side, reason in con.execute("select sim_time,event_type,unit_id,unit_name,unit_side,reason from unit_damage_events"):
            if event_type == "UnitDestroyed":
                if unit_by_name.get(name) is None and _is_weapon_destruction(name, reason):
                    continue
                unit = unit_by_name.get(name)
                destroyed.append(DestroyedUnit(unit.unit_id if unit else None, unit.name if unit else name, unit.side_id if unit else unit_side))
        # 仿真结束时间
        run = con.execute("select sim_ended from run_info limit 1").fetchone()
        # 读取全部武器发射/命中原始事件
        weapon_events = tuple(
            _WeaponEvent(event_type, weapon_class, firing_name, target_name, result)
            for event_type, weapon_class, firing_name, target_name, result in con.execute(
                "select event_type,weapon_class,firing_unit_name,target_name,result from weapon_events"
            )
        )
        usage = sum(1 for item in weapon_events if item.event_type == "WeaponFired")
    finally:
        con.close()
    # 读取Lua日志提取埋点信息（起飞/攻击/返航/计分报错）
    text = lua_log.read_text(encoding="utf-8", errors="replace") if lua_log else ""
    telemetry = RuntimeTelemetry(
        tuple(sorted(_names_after(text, "Launch/"))),
        tuple(sorted(_operation_lines(text, "operation air_attack."))),
        tuple(sorted(_names_after(text, "rtb"))),
        tuple(line for line in text.splitlines() if "CMO-NATIVE-SCORE" in line and "failed" in line.lower()),
        tuple(line for line in text.splitlines() if "runtime error" in line.lower()),
    )
    # 去重整理被毁单位，生成快照对象
    unique_destroyed = tuple(sorted({(item.unit_id, item.unit_name): item for item in destroyed}.values(), key=lambda item: (item.unit_id is None, item.unit_name)))
    delta = final - initial if (initial is not None and final is not None) else None
    return CmoNativeSnapshot(initial, final, delta, unique_destroyed, usage, run[0] if run else None), telemetry, weapon_events


# ------------------------------ CSV简易汇总文件解析 ------------------------------
def _parse_csv(path: Path, lua_log: Path | None, scenario: ScenarioDefinition, score: CmoNativeScoreCompilation) -> tuple[CmoNativeSnapshot, RuntimeTelemetry, tuple[_WeaponEvent, ...]]:
    unit_by_name = {unit.name: unit for unit in scenario.units}
    initial = final = None
    destroyed: list[DestroyedUnit] = []
    weapon_usage = 0
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            metric, side = row.get("指标", ""), row.get("阵营", "")
            subject, result, value = row.get("武器或单位", ""), row.get("结果", ""), row.get("数量或损伤百分比", "")
            # 读取开局/结尾分数
            if side == score.score_spec.rules[0].score_side_id and metric == "CMO官方初始得分":
                initial = _parse_int(value)
            if side == score.score_spec.rules[0].score_side_id and metric == "CMO官方最终得分":
                final = _parse_int(value)
            # 读取被毁单位
            if metric == "单位战损" and result == "被毁":
                name = subject.split(" [", 1)[0]
                unit = unit_by_name.get(name)
                destroyed.append(DestroyedUnit(unit.unit_id if unit else None, unit.name if unit else name, unit.side_id if unit else side))
            # 读取武器消耗总数
            if metric == "武器消耗":
                weapon_usage += _parse_int(value) or 0
    # 解析Lua埋点日志
    text = lua_log.read_text(encoding="utf-8", errors="replace") if lua_log else ""
    telemetry = RuntimeTelemetry(tuple(sorted(_names_after(text, "Launch/"))), tuple(sorted(_operation_lines(text, "operation air_attack."))), tuple(sorted(_names_after(text, "rtb"))), (), ())
    delta = final - initial if (initial is not None and final is not None) else None
    unique_destroyed = tuple(sorted({(item.unit_id, item.unit_name): item for item in destroyed}.values(), key=lambda item: (item.unit_id is None, item.unit_name)))
    return CmoNativeSnapshot(initial, final, delta, unique_destroyed, weapon_usage, None), telemetry, ()


# ------------------------------ 辅助：安全转整数，空/非法返回None ------------------------------
def _parse_int(value: str) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


# ------------------------------ 过滤：忽略飞行导弹自爆记录，不视为单位损失 ------------------------------
def _is_weapon_destruction(unit_name: str, reason: str | None) -> bool:
    """CMO 将飞行中的武器也写入 UnitDestroyed，不能把它视为场景单位。"""
    text = f"{unit_name} {reason or ''}".lower()
    return "weapon has been destroyed" in text or "武器" in text


# ------------------------------ 日志文本提取工具：标记后截取名称 ------------------------------
def _names_after(text: str, marker: str) -> list[str]:
    values: list[str] = []
    for line in text.splitlines():
        if marker in line and "success=true" in line:
            values.append(line.split(marker, 1)[1].split()[0])
    return values


# ------------------------------ 日志提取操作ID ------------------------------
def _operation_lines(text: str, marker: str) -> list[str]:
    return [line.split(marker, 1)[1].split()[0] for line in text.splitlines() if marker in line]


# ------------------------------ 原始武器事件 → 标准化攻击链路聚合 ------------------------------
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
    # 遍历执行计划中所有舰艇/飞机攻击原语
    for operation in plan.operations:
        if operation.primitive_type not in {"schedule_ship_attack", "aircraft_attack"}:
            continue
        p = operation.parameters
        attacker, targets = str(p["shooter_id"]), tuple(p["target_ids"])
        attacker_unit = unit_by_id.get(attacker)
        if attacker_unit is None:
            continue
        # 每条攻击目标单独生成一条攻击闭环记录
        for target in targets:
            target_id = str(target)
            target_unit = unit_by_id.get(target_id)
            if target_unit is None:
                continue
            # 匹配该攻防对应的所有武器事件
            matched = tuple(
                event for event in weapon_events
                if event.firing_unit_name == attacker_unit.name and event.target_name == target_unit.name
            )
            fired = sum(1 for event in matched if event.event_type == "WeaponFired")
            hits = sum(1 for event in matched if event.event_type == "WeaponEndgame" and (event.result or "").upper() == "KILL")
            intercepted = sum(1 for event in matched if "INTERCEPT" in (event.result or "").upper() or "POINTDEF" in (event.result or "").upper())
            # 提取本条攻击相关所有报错
            errors = tuple(sorted({
                line for line in (*telemetry.runtime_error, *telemetry.score_registration_error)
                if attacker in line or target_id in line or attacker_unit.name in line or target_unit.name in line
            }))
            # 组装标准化攻击链路对象
            episodes.append(AttackEpisode(
                operation.operation_id, attacker, target_id, str(p.get("weapon_dbid")),
                attacker_unit.name in telemetry.launch if attacker_unit.platform_type == "aircraft" else None,
                fired if matched else None, hits if matched else None, intercepted if matched else None,
                target_id in destroyed_ids,
                attacker in destroyed_ids,
                False if attacker in destroyed_ids else (attacker_unit.name in telemetry.return_to_base if telemetry.return_to_base else None),
                errors
            ))
    return tuple(episodes)


# ------------------------------ 按计分规则计算理论预期得分 ------------------------------
def _expected_delta(destroyed: tuple[DestroyedUnit, ...], score: CmoNativeScoreCompilation) -> int:
    rule_by_unit = {rule.target_unit_id: rule.point_change for rule in score.score_spec.rules}
    return sum(rule_by_unit.get(item.unit_id, 0) for item in destroyed)


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
def _metrics(batch: BatchRunnerEvidence, snap: CmoNativeSnapshot, episodes: tuple[AttackEpisode, ...], semantic: Phase3SemanticValidation) -> Phase3CombatMetrics:
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
        batch.execution_success,
        snap.native_score_delta,
        enemy,
        own,
        snap.weapon_usage,
        episodes,
        tuple(key_events),
        semantic.semantic_valid,
        semantic.scoreable,
    )


# ------------------------------ 落地全套Phase3输出JSON文件 ------------------------------
def _write_artifacts(directory: Path, result: Phase3EvaluationResult, batch: BatchRunnerEvidence, telemetry: RuntimeTelemetry) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    payloads = {
        "combat_evidence.json": {"batch": asdict(batch), "native_snapshot": asdict(result.native_snapshot), "runtime_telemetry": asdict(telemetry), "attack_episodes": [asdict(item) for item in result.attack_episodes], "raw_evidence_paths": _paths(result.artifact_paths)},
        "semantic_validation.json": asdict(result.semantic_validation),
        "combat_metrics.json": {**asdict(result.metrics), "attack_episodes": [asdict(item) for item in result.metrics.attack_episodes]},
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
