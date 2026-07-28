"""
Phase9 顶层演化编排器；通过注入Phase6/7/8适配器实现流程调度，整体流程具备确定性。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Callable, Protocol

from cmo_lua_agent.evolution.campaign_store import CampaignStore
from cmo_lua_agent.evolution.champion_selection import ChampionSelectionPolicy
from cmo_lua_agent.evolution.cmo_lock import CmoInstanceLock
from cmo_lua_agent.evolution.models import (
    CampaignExecutionMode, CandidateScore, EvolutionCampaignSpec, OperationKind, Phase6GenerationArtifact,
)
from cmo_lua_agent.evolution.stop_policy import StopPolicy


# 适配器协议：定义外部Phase6/7/8需要实现的接口，实现解耦依赖
class Phase6Adapter(Protocol):
    """Phase6适配器协议：执行一代候选策略CMO仿真、输出打分结果"""
    def run(self, *, generation_index: int, rolling_baseline_id: str, **kwargs: object) -> tuple[CandidateScore, tuple[CandidateScore, ...]]: ...


class Phase7Adapter(Protocol):
    """Phase7适配器协议：对比学习、经验提取流程"""
    def run(self, *, generation_index: int, **kwargs: object) -> tuple[dict[str, object], ...]: ...


class Phase8Adapter(Protocol):
    """Phase8适配器协议：技能库更新、知识沉淀流程"""
    def run(self, *, generation_index: int, **kwargs: object) -> str: ...


@dataclass(frozen=True, slots=True)
class CampaignResult:
    """推演任务最终汇总结果载体"""
    campaign_id: str                     # 推演任务ID
    anchor_score: int                    # 初始锚点基线分数
    rolling_scores: tuple[int, ...]      # 每一代迭代后的基线分数序列
    global_best_score: int               # 全流程全局最优分数
    completed_generations: int           # 顺利完成的世代数量
    stopped_early: bool = False          # 是否提前终止（未跑完最大世代）


class EvolutionWorkflow:
    """
    Phase9顶层演化循环工作流
    循环驱动完整世代流水线：Phase6仿真择优 → Phase7学习 → Phase8知识更新
    通过外部注入适配器，将渲染、仿真、学习逻辑隔离在下层Phase6–8；
    本类只负责循环编排、账本登记、配额管控、基线迭代、产物持久化。
    """
    def __init__(self, *, phase6: Phase6Adapter, phase7: Phase7Adapter, phase8: Phase8Adapter,
                 stop_requested: Callable[[], bool] | None = None) -> None:
        self._phase6 = phase6
        self._phase7 = phase7
        self._phase8 = phase8
        # 外部停止信号回调，检测是否收到人工终止指令
        self._stop_requested = stop_requested or (lambda: False)

    def run(self, spec: EvolutionCampaignSpec, *, root: Path) -> CampaignResult:
        """
        启动整套推演演化循环
        :param spec: 推演任务顶层契约
        :param root: 当前campaign持久化根目录
        :return: 推演最终汇总结果
        """
        root = Path(root).resolve()
        store = CampaignStore(root)
        root.mkdir(parents=True, exist_ok=True)
        # 标记产物来源：测试虚拟模式 / 正式CMO推演模式
        provenance = "phase9_fake_fixture" if spec.execution_mode is CampaignExecutionMode.FAKE_FIXTURE else "formal_renderer"
        # 持久化基础契约摘要
        self._write_json(root / "campaign-spec.json", {"checksum": spec.checksum, "execution_mode": spec.execution_mode.value, "artifact_provenance": provenance})

        # 生产模式抢占CMO全局独占锁，保证同一任务同时仅有一套兵棋实例运行
        lock = CmoInstanceLock(root.parent / ".cmo-instance.lock", campaign_id=spec.campaign_id) if spec.execution_mode is CampaignExecutionMode.PRODUCTION_CMO else None
        if lock is not None:
            lock.acquire()
        try:
            return self._run_locked(spec, root, store, provenance)
        finally:
            # 无论正常/异常退出，释放CMO锁
            if lock is not None:
                lock.release()

    def _run_locked(self, spec: EvolutionCampaignSpec, root: Path, store: CampaignStore, provenance: str) -> CampaignResult:
        """持有CMO锁时执行主演化循环"""
        available_cmo = spec.budget.max_cmo_runs  # 剩余可用CMO仿真次数
        rolling_id, rolling_score, anchor_score = "baseline", 0, 0
        history: list[int] = []    # 记录每一代迭代后的基线分数
        stopped_early = False

        # 世代主循环，依次迭代0～max_generations-1
        for generation_index in range(spec.budget.max_generations):
            # 检测外部停止信号，提前跳出循环
            if self._stop_requested():
                stopped_early = True
                break
            # 校验剩余CMO次数是否足够支撑完整一代运行，算力不足直接终止循环
            if not spec.budget.can_reserve_generation(available_cmo_runs=available_cmo):
                break

            # 在操作账本注册PHASE6世代顶层操作
            phase6_operation = store.prepare_operation(generation_index=generation_index, kind=OperationKind.PHASE6, input_checksum=spec.contract_checksum)
            store.mark_operation_started(phase6_operation.operation_id)
            # 调用Phase6：执行候选策略批量CMO推演
            phase6_result = self._phase6.run(generation_index=generation_index, rolling_baseline_id=rolling_id)

            # 兼容两种返回格式：标准化Phase6GenerationArtifact / 简易元组返回
            if isinstance(phase6_result, Phase6GenerationArtifact):
                baseline, candidates = phase6_result.rolling_baseline, phase6_result.candidates
                actual_attempts = phase6_result.cmo_attempts
            else:
                baseline, candidates = phase6_result
                actual_attempts = 5

            # 校验：实际消耗仿真次数不能超过本世代预留上限，防止算力透支
            if actual_attempts > spec.budget.required_cmo_attempts_per_generation:
                raise RuntimeError("phase6_exceeded_reserved_cmo_budget")
            available_cmo -= actual_attempts

            # 保存本世代Phase6执行引用文件，用于后续对账
            generation = root / "generations" / f"generation_{generation_index:03d}"
            generation.mkdir(parents=True, exist_ok=True)
            phase6_ref = generation / "phase6-ref.json"
            self._write_json(phase6_ref, {"input_checksum": spec.contract_checksum, "baseline": baseline.candidate_id, "candidates": [item.candidate_id for item in candidates]})
            store.reconcile_operation(phase6_operation.operation_id, phase6_ref)

            # Phase6完成后再次检测停止信号；若收到终止指令，保留现有推演证据，但跳过择优、学习、基线更新
            if self._stop_requested():
                stopped_early = True
                break

            # 冠军策略选择：选出本代最优，并判断是否更新滚动基线
            decision = ChampionSelectionPolicy(minimum_improvement_delta=spec.minimum_improvement_delta).select(rolling_baseline=baseline, candidates=candidates)
            if decision.improved:
                rolling_id, rolling_score = decision.selected_champion_id, decision.selected_score
            history.append(rolling_score)

            # 追加世代演化谱系记录，留存基线更替轨迹
            self._append_jsonl(root / "lineage.jsonl", {
                "generation_index": generation_index,
                "selected_champion_id": decision.selected_champion_id,
                "rolling_baseline_id": baseline.candidate_id,
                "artifact_provenance": provenance
            })

            # ===== Phase7：对比学习、经验提取 =====
            phase7_operation = store.prepare_operation(generation_index=generation_index, kind=OperationKind.PHASE7, input_checksum=spec.contract_checksum)
            store.mark_operation_started(phase7_operation.operation_id)
            self._phase7.run(generation_index=generation_index)
            phase7_ref = generation / "phase7-ref.json"
            self._write_json(phase7_ref, {"input_checksum": spec.contract_checksum, "artifact_provenance": provenance})
            store.reconcile_operation(phase7_operation.operation_id, phase7_ref)

            # ===== Phase8：战术技能库更新、知识沉淀 =====
            phase8_operation = store.prepare_operation(generation_index=generation_index, kind=OperationKind.PHASE8, input_checksum=spec.contract_checksum)
            store.mark_operation_started(phase8_operation.operation_id)
            phase8_result = self._phase8.run(generation_index=generation_index)
            phase8_ref = generation / "phase8-ref.json"
            self._write_json(phase8_ref, {"input_checksum": spec.contract_checksum, "result": phase8_result, "artifact_provenance": provenance})
            store.reconcile_operation(phase8_operation.operation_id, phase8_ref)

        # 循环结束，组装最终推演结果并持久化
        result = CampaignResult(
            spec.campaign_id,
            anchor_score,
            tuple(history),
            max(history, default=anchor_score),
            len(history),
            stopped_early
        )
        self._write_json(root / "campaign-result.json", asdict(result) | {"artifact_provenance": provenance})
        return result

    @staticmethod
    def _write_json(path: Path, value: object) -> None:
        """写入标准JSON文件"""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8", newline="\n")

    @staticmethod
    def _append_jsonl(path: Path, value: object) -> None:
        """追加一行JSON至jsonl谱系日志"""
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
