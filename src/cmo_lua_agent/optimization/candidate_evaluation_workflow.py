"""Deterministic Phase 5 workflow for exactly one scored candidate.
Phase5 单条带分候选确定性完整流水线
职责：完整管控单套作战策略的「编译→生成Lua→CMO仿真→结果计分→自动修复重试」全生命周期
内置状态机、沙箱文件存储、多层校验、错误路由修复、最大修复次数限制，全流程可溯源、产物完整落地，全程无随机逻辑保证可复现

会记录每个候选的 执行过程日志，便于后续分析，有的lua可能修复三次修不好，
量化指标：
    统计各失败阶段占比（策略非法 / 能力缺口 / 仿真超时 / 计分冲突）
    统计平均修复次数、修复成功率
"""
from __future__ import annotations

import json
import traceback
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Protocol

# Phase4 修复相关请求/结果模型、错误分类路由、策略补丁安全校验器
from cmo_lua_agent.agents.lua_repair_agent import LuaRepairRequest, LuaRepairResult
from cmo_lua_agent.agents.repair_models import RepairErrorRouter, RepairKind
from cmo_lua_agent.agents.strategy_change_guard import StrategyChangeGuard
# Phase3 战斗结果解析、打分评估服务
from cmo_lua_agent.evaluation.phase3_evaluation import Phase3EvaluationService
from cmo_lua_agent.evaluation.phase3_repair_signal import Phase3RepairSignalMapper
# Phase2 能力校验、执行计划编译器、带分Lua组装服务
from cmo_lua_agent.generation.capability_validator import CapabilityValidator
from cmo_lua_agent.generation.execution_plan_compiler import ExecutionPlanCompiler
from cmo_lua_agent.generation.runtime_primitives import runtime_primitive_registry_for
from cmo_lua_agent.generation.scored_lua_assembly import ScoredLuaAssemblyService
# Phase1 策略合法性校验器、哈希工具
from cmo_lua_agent.contract import StrategyValidator
from cmo_lua_agent.generation.runtime_models import canonical_sha256
# 单候选隔离文件存储
from cmo_lua_agent.optimization.candidate_artifact_store import CandidateArtifactStore
from cmo_lua_agent.optimization.runtime_patch_applier import RuntimePatchApplier
from cmo_lua_agent.optimization.scenario_reset_probe import ScenarioResetProbe
# 候选请求、状态、结果、状态机模型
from cmo_lua_agent.optimization.candidate_models import CandidateFailureReason, CandidateOutcome, CandidateRequest, CandidateState, CandidateStateMachine


# CMO仿真执行器协议：定义运行Lua的统一标准接口
class CandidateRunner(Protocol):
    def run(self, *, lua_path: Path, timeout_seconds: int, round_number: int, run_id: str): ...


# 策略修复Agent协议：标准化修复调用入口
class CandidateRepairAgent(Protocol):
    def repair(self, request: LuaRepairRequest) -> LuaRepairResult: ...


# Phase5 核心单候选评估流水线
class CandidateEvaluationWorkflow:
    """单候选的生成、预检、CMO 评估与受限 Lua 修复工作流。

由 Phase 6 适配器调用并返回标准 CandidateOutcome；它不负责跨候选排名或 Campaign
控制，因此单个候选失败不会在此处改变整代的 Champion/停止决策。
    """
    def __init__(self, *,
                 cmo_runner: CandidateRunner,          # CMO仿真执行实例
                 repair_agent: CandidateRepairAgent,  # Phase4修复代理实例
                 phase3_service: Phase3EvaluationService | None = None, # Phase3打分服务
                 is_cancelled: Callable[[], bool] | None = None, # 外部取消判断回调
                 scenario_reset_probe: ScenarioResetProbe | None = None,
                 assembler=None,
                ) -> None:
        self._runner = cmo_runner                  # CMO执行器
        self._repair_agent = repair_agent          # 修复代理
        self._phase3 = phase3_service or Phase3EvaluationService() # 打分评估服务
        self._is_cancelled = is_cancelled or (lambda: False) # 取消判断空实现
        self._validator = StrategyValidator()       # Phase1策略校验器
        self._compiler = ExecutionPlanCompiler()    # Phase2 策略转执行计划编译器
        self._assembler = assembler or ScoredLuaAssemblyService()# 带计分Lua组装服务
        self._guard = StrategyChangeGuard()         # 策略补丁安全校验器
        self._router = RepairErrorRouter()          # 仿真错误分类路由
        self._runtime_patch_applier = RuntimePatchApplier()
        self._signal_mapper = Phase3RepairSignalMapper()
        self._scenario_reset_probe = scenario_reset_probe

    def evaluate(self, request: CandidateRequest) -> CandidateOutcome:
        """单候选完整主流程入口，循环执行编译-仿真-修复直到成功/达到修复上限/不可修复"""
        # 初始化本候选隔离文件仓库，所有产物写入独立沙箱目录
        store = CandidateArtifactStore(
            request.candidate_dir,
            request.candidate_id,
            allow_existing=request.reuse_existing_artifacts,
        )
        machine = CandidateStateMachine() # 流程状态机，记录每一步流转
        strategy = request.strategy      # 当前待评估作战策略
        # 全局变量记录原始Lua、最终Lua、修复尝试计数、补丁应用计数
        original_lua = final_lua = None
        attempts = (
            self._next_attempt_index(store)
            if request.reuse_existing_artifacts
            else 0
        )
        invocations = applied = 0
        plan = manifest = None
        runtime_plan = None
        applied_runtime_keys: set[tuple[str, str]] = set()
        runtime_patch_entries: list[dict[str, str]] = []

        # 写入初始请求与原始策略存档
        self._write_event(store, machine.events[-1])
        store.write_json("request.json", request.to_dict())
        store.write_json("strategy/original_strategy.json", strategy.to_dict())

        try:
            # 循环：编译→渲染Lua→仿真→报错修复重试
            while True:
                # 外部触发取消，直接终止流程
                if self._is_cancelled():
                    return self._finish(store, machine, request, strategy, original_lua, final_lua, attempts, invocations, applied, CandidateFailureReason.CANCELLED)

                # 1. Phase1：校验策略结构与场景约束合法性
                validation = self._validator.validate(strategy=strategy, scenario_definition=request.scenario)
                if not validation.valid:
                    return self._finish(store, machine, request, strategy, original_lua, final_lua, attempts, invocations, applied, CandidateFailureReason.STRATEGY_INVALID)
                self._transition(store, machine, CandidateState.STRATEGY_VALIDATED, "strategy validated", attempts)

                # 2. Phase2：策略编译为有序执行计划ExecutionPlan
                compiled = self._compiler.compile(scenario=request.scenario, strategy=strategy, runtime=request.runtime)
                if compiled.plan is None:
                    # 存在Runtime不支持的原语能力缺口，无法继续
                    return self._finish(store, machine, request, strategy, original_lua, final_lua, attempts, invocations, applied, CandidateFailureReason.CAPABILITY_GAP)

                # 3. 校验执行计划所有原语均在当前运行时支持列表内
                plan = runtime_plan or compiled.plan
                capability = CapabilityValidator(runtime_primitive_registry_for(request.runtime.runtime_id, request.runtime.runtime_version)).validate(plan=plan, runtime=request.runtime)
                if not capability.is_valid:
                    return self._finish(store, machine, request, strategy, original_lua, final_lua, attempts, invocations, applied, CandidateFailureReason.PLAN_VALIDATION_FAILED)
                self._transition(store, machine, CandidateState.PLAN_COMPILED, "plan compiled", attempts)

                # 4. 组装带计分插桩的完整Lua脚本，生成全链路溯源清单manifest
                assembled = self._assembler.render(
                    scenario=request.scenario, strategy=strategy, plan=plan, runtime=request.runtime,
                    native_score_compilation=request.native_score_compilation,
                    candidate_id=request.candidate_id,
                )
                plan, manifest = assembled.plan, assembled.generation_manifest
                if runtime_patch_entries:
                    manifest = {**manifest, "runtime_patches": runtime_patch_entries}

                # 分attempt子目录存储本次编译产物
                attempt_dir = f"attempts/attempt_{attempts:02d}"
                lua_path = store.write_text(f"{attempt_dir}/candidate.lua", assembled.rendered.content)
                store.write_json(f"{attempt_dir}/execution_plan.json", plan.to_dict())
                store.write_json(f"{attempt_dir}/generation_manifest.json", manifest)

                # 记录首次生成的原始Lua路径、当前最新Lua路径
                if original_lua is None:
                    original_lua = lua_path
                final_lua = lua_path
                self._transition(store, machine, CandidateState.LUA_RENDERED, "scored Lua rendered", attempts, (str(lua_path),))

                # 仿真执行前再次检查取消信号
                if self._is_cancelled():
                    return self._finish(store, machine, request, strategy, original_lua, final_lua, attempts, invocations, applied, CandidateFailureReason.CANCELLED)

                # 5 调用CMO执行器运行Lua仿真
                reset_before = self._scenario_reset_probe.before_run() if self._scenario_reset_probe else None
                record = self._runner.run(
                    lua_path=lua_path,
                    timeout_seconds=request.timeout_seconds,
                    # Each dynamic batch job owns a fresh RunArtifactStore run.
                    # The attempt index belongs to the candidate directory and
                    # CMO operation ID, while a fresh CmoRunner run starts at 0.
                    round_number=0,
                    run_id=f"{request.candidate_id}_{attempts:02d}",
                    audit_profile=self._audit_profile(request),
                )
                attempts += 1 # 仿真尝试次数自增
                store.write_json(f"{attempt_dir}/cmo_run_result.json", record.result)
                if reset_before is not None:
                    reset_evidence = self._scenario_reset_probe.after_run(reset_before, record)
                    store.write_json(f"{attempt_dir}/scenario_reset.json", reset_evidence)
                    store.write_json("scenario_reset.json", reset_evidence)
                self._transition(store, machine, CandidateState.CMO_EXECUTED, "CMO executed", attempts - 1)

                # 分支A：仿真执行完全成功，进入Phase3解析打分
                if record.result.success:
                    evaluation = (
                        self._official_score_only_evaluation(
                            record=record,
                            store=store,
                            attempt_dir=attempt_dir,
                        )
                        if request.official_score_only
                        else self._phase3.evaluate(
                            run_result=record.result,
                            scenario=request.scenario,
                            plan=plan,
                            score_compilation=request.native_score_compilation,
                            generation_manifest=manifest,
                            output_dir=store.path(f"{attempt_dir}/phase3"),
                            candidate_id=request.candidate_id,
                        )
                    # 校验1：仿真数据冲突（理论得分与CMO原生分数不一致）
                    )
                    if evaluation.reconciliation.status == "result_integrity_failed":
                        return self._finish(store, machine, request, strategy, original_lua, final_lua, attempts, invocations, applied, CandidateFailureReason.RESULT_INTEGRITY_FAILED, evaluation=evaluation)
                    # 校验2：语义校验失败（攻击偏离策略、资源越权等）
                    if not evaluation.semantic_validation.semantic_valid:
                        return self._finish(store, machine, request, strategy, original_lua, final_lua, attempts, invocations, applied, CandidateFailureReason.SEMANTIC_DRIFT, evaluation=evaluation)
                    # 校验3：数据缺失无法计算有效得分
                    if not evaluation.semantic_validation.scoreable:
                        return self._finish(store, machine, request, strategy, original_lua, final_lua, attempts, invocations, applied, CandidateFailureReason.RESULT_UNSCORABLE, evaluation=evaluation)
                    signal = self._signal_mapper.map(result=evaluation, plan=plan)
                    if signal is not None:
                        if not signal.repairable or attempts > request.max_repairs:
                            return self._finish(store, machine, request, strategy, original_lua, final_lua, attempts, invocations, applied, CandidateFailureReason.REPAIR_NOT_APPLICABLE, evaluation=evaluation)
                        from cmo_lua_agent.execution.models import CmoError
                        route = self._router.route(CmoError("lua_runtime_error", "runtime compatibility missing contact"))
                        invocations += 1
                        repair = self._repair_agent.repair(LuaRepairRequest(route=route, current_lua=assembled.rendered.content, current_lua_checksum=assembled.rendered.lua_checksum, error=CmoError("lua_runtime_error", signal.message), scenario=request.scenario, strategy=strategy, plan=plan, generation_manifest=manifest, runtime=request.runtime, repair_history_summary=(), related_skills=(), allowed_strategy_paths=request.allowed_strategy_paths))
                        store.write_json(f"repairs/repair_{invocations - 1:02d}.json", asdict(repair))
                        if repair.repair_kind is not route.kind or repair.patch is None:
                            return self._finish(store, machine, request, strategy, original_lua, final_lua, attempts, invocations, applied, CandidateFailureReason.REPAIR_KIND_MISMATCH, evaluation=evaluation)
                        try:
                            runtime_plan, audit = self._runtime_patch_applier.apply(candidate_id=request.candidate_id, proposal=repair.patch, plan=plan, rendered=assembled.rendered, applied_keys=applied_runtime_keys)
                        except ValueError as exc:
                            reason = CandidateFailureReason.RUNTIME_PATCH_ALREADY_APPLIED if str(exc) == "runtime_patch_already_applied" else CandidateFailureReason.RUNTIME_DEFECT
                            return self._finish(store, machine, request, strategy, original_lua, final_lua, attempts, invocations, applied, reason, evaluation=evaluation, error=str(exc))
                        applied += 1
                        runtime_patch_entries.append(self._runtime_patch_applier.manifest_entry(audit, assembled.rendered.lua_checksum, signal.message))
                        self._transition(store, machine, CandidateState.REPAIRED, "runtime patch applied", attempts - 1)
                        continue
                    # 全部校验通过，标记完整成功
                    self._transition(store, machine, CandidateState.SEMANTIC_VALIDATED, "phase 3 semantic validation", attempts - 1)
                    self._transition(store, machine, CandidateState.SCORED, "phase 3 scoring", attempts - 1)
                    self._transition(store, machine, CandidateState.COMPLETED, "completed", attempts - 1)
                    return self._finish(store, machine, request, strategy, original_lua, final_lua, attempts, invocations, applied, CandidateFailureReason.COMPLETED, evaluation=evaluation)

                # 分支B：CMO仿真执行报错，进入修复分支判断
                reason = self._execution_reason(record.result)
                # 无报错对象 / 已达到最大修复次数，直接判定修复预算耗尽
                if record.result.error is None or attempts > request.max_repairs:
                    final_fail = CandidateFailureReason.REPAIR_BUDGET_EXHAUSTED if attempts > request.max_repairs else reason
                    return self._finish(store, machine, request, strategy, original_lua, final_lua, attempts, invocations, applied, final_fail)

                # 对错误自动分类，判断是否支持重试修复
                route = self._router.route(record.result.error)
                if not route.retry_eligible:
                    return self._finish(store, machine, request, strategy, original_lua, final_lua, attempts, invocations, applied, CandidateFailureReason.REPAIR_NOT_APPLICABLE)

                # 调用修复Agent生成修复补丁
                invocations += 1
                repair = self._repair_agent.repair(LuaRepairRequest(
                    route=route,
                    current_lua=assembled.rendered.content,
                    current_lua_checksum=assembled.rendered.lua_checksum,
                    error=record.result.error,
                    scenario=request.scenario,
                    strategy=strategy,
                    plan=plan,
                    generation_manifest=manifest,
                    runtime=request.runtime,
                    repair_history_summary=(),
                    related_skills=(),
                    allowed_strategy_paths=request.allowed_strategy_paths
                ))
                # 存档本次修复方案
                store.write_json(f"repairs/repair_{invocations - 1:02d}.json", asdict(repair))

                # 校验：修复类型与错误分类必须匹配
                if repair.repair_kind is not route.kind:
                    return self._finish(store, machine, request, strategy, original_lua, final_lua, attempts, invocations, applied, CandidateFailureReason.REPAIR_KIND_MISMATCH)

                # 仅支持策略参数补丁修复，运行时补丁本流水线暂不处理
                if repair.repair_kind is RepairKind.STRATEGY_PATCH and isinstance(repair.patch, tuple):
                    # 应用受限替换补丁，生成新策略，下一轮循环重新编译仿真
                    strategy, _ = self._guard.apply(current=strategy, patches=repair.patch, allowed_paths=request.allowed_strategy_paths)
                    applied += 1
                    self._transition(store, machine, CandidateState.REPAIRED, "strategy patch applied", attempts - 1)
                    continue # 回到循环头部重新编译Lua
                # 非策略补丁，判定为运行底层缺陷，无法自动修复
                return self._finish(store, machine, request, strategy, original_lua, final_lua, attempts, invocations, applied, CandidateFailureReason.RUNTIME_DEFECT)

        # 顶层异常兜底：用户中断、系统退出直接上抛，其余内部异常捕获存档
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as exc:
            store.write_text("internal_error.txt", traceback.format_exc())
            return self._finish(store, machine, request, strategy, original_lua, final_lua, attempts, invocations, applied, CandidateFailureReason.INTERNAL_WORKFLOW_ERROR, error=str(exc))

    @staticmethod
    def _execution_reason(result) -> CandidateFailureReason:
        """根据CMO执行结果匹配标准化失败原因枚举"""
        if result.process_result.timed_out:
            return CandidateFailureReason.CMO_TIMEOUT
        if not result.restore_succeeded:
            return CandidateFailureReason.CONFIGURATION_RESTORE_FAILED
        if result.error and result.error.category == "lua_syntax_error":
            return CandidateFailureReason.LUA_SYNTAX_ERROR
        return CandidateFailureReason.LUA_RUNTIME_ERROR

    @staticmethod
    def _next_attempt_index(store: CandidateArtifactStore) -> int:
        """Continue a resumed slot in a fresh attempt directory."""
        attempts_root = store.path("attempts")
        if not attempts_root.is_dir():
            return 0
        indices: list[int] = []
        for path in attempts_root.iterdir():
            if not path.is_dir() or not path.name.startswith("attempt_"):
                continue
            suffix = path.name.removeprefix("attempt_")
            if suffix.isdecimal():
                indices.append(int(suffix))
        return max(indices, default=-1) + 1

    @staticmethod
    def _official_score_only_evaluation(*, record, store, attempt_dir: str):
        """Read the sole execution score from the completed slot's summary."""
        result_root = (
            record.result.batch_result_dir
            or record.result.process_result.batch_result_dir
        )
        summary_path = None
        if result_root is not None and Path(result_root).is_dir():
            summaries = sorted(Path(result_root).rglob("execution-summary.json"))
            if summaries:
                summary_path = summaries[0]

        final = None
        diagnostic: dict[str, object] = {
            "cmo_started": True,
            "cmo_success": bool(record.result.success),
            "results_dir": str(result_root) if result_root is not None else None,
            "summary_path": str(summary_path) if summary_path is not None else None,
        }
        if summary_path is not None:
            try:
                payload = json.loads(summary_path.read_text(encoding="utf-8"))
                official = payload.get("official_score") if isinstance(payload, dict) else None
                value = official.get("final") if isinstance(official, dict) else None
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    final = value
                    store.write_json(f"{attempt_dir}/execution-summary.json", payload)
            except (OSError, json.JSONDecodeError):
                pass
        diagnostic["official_score"] = final
        diagnostic["scoreable"] = final is not None
        store.write_json(f"{attempt_dir}/execution-diagnostic.json", diagnostic)
        return SimpleNamespace(
            reconciliation=SimpleNamespace(status="valid"),
            semantic_validation=SimpleNamespace(
                semantic_valid=True,
                scoreable=final is not None,
            ),
            # Simplified official-score mode does not parse Phase 3 attack
            # episodes, but downstream repair-signal handling still expects a
            # structured collection.
            attack_episodes=(),
            metrics=SimpleNamespace(execution_success=True),
            reward_breakdown=None,
            native_snapshot=SimpleNamespace(
                native_score_final=final,
                score_source=(
                    "execution-summary.json#/official_score/final"
                    if final is not None
                    else None
                ),
                execution_fidelity="unknown",
            ),
        )

    def _transition(self, store, machine, state, reason, attempt, refs=(), error=None):
        """状态机流转封装：更新状态并写入轨迹日志"""
        machine.transition(state, reason=reason, attempt=attempt, refs=refs, error=error)
        self._write_event(store, machine.events[-1])

    @staticmethod
    def _write_event(store, event):
        """追加一条状态事件到trajectory.jsonl时序日志"""
        store.append_jsonl("trajectory.jsonl", event.to_dict())

    @staticmethod
    def _audit_profile(request: CandidateRequest) -> dict[str, object]:
        """Build the BatchRunner audit profile from immutable formal contracts."""
        weapons: dict[tuple[str, int], dict[str, object]] = {}
        for unit in request.scenario.units:
            for inventory in unit.weapon_inventory:
                weapons[(inventory.weapon_name, inventory.weapon_dbid)] = {
                    "StableId": f"weapon_{inventory.weapon_dbid}",
                    "Name": inventory.weapon_name,
                    "WeaponDbid": inventory.weapon_dbid,
                }
        return {
            "ScenarioId": request.scenario.scenario_id,
            "CandidateId": request.candidate_id,
            "ScoringSideId": request.native_score_compilation.score_spec.rules[0].score_side_id,
            "Sides": [
                {
                    "SideId": side_id,
                    "CmoSideId": side_id,
                    "CmoSideName": side_id,
                    "DisplayName": side_id,
                }
                for side_id in sorted({unit.side_id for unit in request.scenario.units})
            ],
            "AttackWaveWindowSeconds": 60,
            "Units": [
                {"StableId": unit.unit_id, "SideId": unit.side_id, "Name": unit.name, "PlatformDbid": unit.dbid}
                for unit in request.scenario.units
            ],
            "Weapons": list(weapons.values()),
        }

    def _finish(self, store, machine, request, strategy, original_lua, final_lua, attempts, invocations, applied, reason, *, evaluation=None, error=None):
        """流程收尾统一入口：写入最终策略、生成标准化CandidateOutcome结果对象"""
        success = (reason is CandidateFailureReason.COMPLETED)
        failed_stage = None
        # 非成功流程，补充FAILED状态流转
        if not success:
            if machine.state not in {CandidateState.FAILED, CandidateState.COMPLETED}:
                self._transition(store, machine, CandidateState.FAILED, reason.value, max(attempts - 1, 0), error=error)
            failed_stage = machine.state
        # 存档最终迭代后的策略
        store.write_json("strategy/final_strategy.json", strategy.to_dict())
        # 组装完整候选输出结果
        scenario_reset_path = store.path("scenario_reset.json")
        scenario_reset = (
            json.loads(scenario_reset_path.read_text(encoding="utf-8"))
            if scenario_reset_path.is_file()
            else None
        )
        outcome = CandidateOutcome(
            request.candidate_id,
            request.generation_index,
            strategy,
            success,
            # CMO 已成功执行、但 Phase 3 拒绝语义或评分资格时，Lua 仍是可执行的。
            # 这让 Phase 6 能将其正确归类为 semantic_invalid / unscorable，
            # 而不是错误地降级为 execution_failed。
            bool(success or evaluation is not None),
            bool(evaluation and evaluation.semantic_validation.semantic_valid),
            bool(evaluation and evaluation.semantic_validation.scoreable),
            original_lua,
            final_lua,
            applied,
            attempts,
            invocations,
            applied,
            evaluation.metrics if evaluation else None,
            evaluation.reward_breakdown if evaluation else None,
            failed_stage,
            reason,
            machine.state,
            store.root,
            store.path("trajectory.jsonl"),
            scenario_reset=scenario_reset,
            execution_success=(evaluation.metrics.execution_success if evaluation else False),
            native_score=(evaluation.native_snapshot.native_score_final if evaluation else None),
            score_source=(evaluation.native_snapshot.score_source if evaluation else None),
            execution_fidelity=(evaluation.native_snapshot.execution_fidelity if evaluation else "unknown"),
        )
        # 落地最终结果文件
        store.write_json("candidate_outcome.json", asdict(outcome))
        return outcome
