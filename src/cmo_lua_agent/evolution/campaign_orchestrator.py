"""
Phase9C 统一编排器：单工具入口，幂等/可恢复/实时推送/经验目标驱动退出。

幂等规则（基于 campaign_id）：
  - 已完成 + 经验达标  → 打印结果，问是否重跑
  - 进行中              → 续跑（ProductionGenerationExecutor 已有 candidate_outcome.json 断点）
  - 失败                → 续跑（从最后一个完成代数继续）

终端对话使用方式：
  → 启动演化推演，场景用 red_blue_6v4_liaoning，目标积累 100 条经验
  → 启动演化推演（用 FAKE_FIXTURE 模式），目标 20 条经验
  → 继续上次演化推演
  → 查看当前推演状态
  → 停止当前推演
"""

from __future__ import annotations

# LEGACY: retained for historical manual automation only. New unattended
# training must enter through cmo_lua_agent.training.

import json
import logging
import shutil
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from threading import Event
from typing import Any

from cmo_lua_agent.evolution.campaign_store import CampaignStore
from cmo_lua_agent.evolution.models import CampaignBudget, CampaignExecutionMode, EvolutionCampaignSpec
from cmo_lua_agent.evolution.production_service import ProductionEvolutionCampaignService
from cmo_lua_agent.evolution.production_phase_adapters import ProductionPhase7Adapter, ProductionPhase8Adapter
from cmo_lua_agent.evolution.formal_adapters import FormalPhase6Adapter
from cmo_lua_agent.evolution.production_models import GenerationApprovalGrant
from cmo_lua_agent.evolution.formal_candidate_evaluator import FormalCandidateEvaluator
from cmo_lua_agent.evolution.production_knowledge import ProductionKnowledgeSnapshotProvider
from cmo_lua_agent.evolution.champion_selection import ChampionSelectionPolicy
from cmo_lua_agent.evolution.stop_policy import StopPolicy
from cmo_lua_agent.evolution.novelty import CandidateNoveltyValidator
from cmo_lua_agent.evolution.controlled_input_package import ControlledCampaignInputPackageLoader
from cmo_lua_agent.evolution.rolling_baseline import RollingBaselineResolver
from cmo_lua_agent.llm.json_client import ClaudeJsonClient
from cmo_lua_agent.llm.client import ClaudeClient
from cmo_lua_agent.llm_config import load_config
from cmo_lua_agent.learning.store import ExperienceStore

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 进度回调（实现此接口注入进度输出）
# ─────────────────────────────────────────────────────────────────────────────
class ProgressCallback:
    """可注入的进度回调，AgentLoop 通过它实时看到进度"""

    def on_generation_start(self, gen: int, total: int) -> str:
        return f"🟡 代数 {gen}/{total} 开始"

    def on_phase6_scores(self, gen: int, scores: dict[str, int]) -> str:
        best = max(scores.values()) if scores else 0
        return f"  ✅ Phase6 完成，候选分数: {scores}，本代最优: {best}"

    def on_phase7_new_experiences(self, gen: int, new_count: int, total: int, goal: int) -> str:
        bar = "█" * min(total, goal) + "░" * max(0, goal - total)
        return f"  📚 Phase7 完成，新增 {new_count} 条经验  [{bar}] {total}/{goal}"

    def on_phase8_skill(self, gen: int, skill: str | None) -> str:
        if skill:
            return f"  🛠️  Phase8 完成，新技能: {skill}"
        return f"  🛠️  Phase8 完成（本次无新技能）"

    def on_experience_goal_reached(self, total: int, goal: int) -> str:
        return f"\n🎉 经验目标达成！{total}/{goal} 条，优雅退出"

    def on_no_improvement(self, gen: int, consecutive: int, patience: int) -> str:
        return f"  ⚠️  连续 {consecutive} 代无提升（耐心值 {patience}），若再连续 {patience} 代无提升将退出"

    def on_cmo_lock_contested(self, campaign_id: str) -> str:
        return f"❌ CMO 锁被占用：{campaign_id} 正在其他进程中运行。请先 stop 或等待。"

    def on_error(self, gen: int, phase: str, error: str) -> str:
        return f"  ❌ 代 {gen} {phase} 出错: {error}"

    def on_stopped(self, reason: str, generations: int, total_exp: int) -> str:
        return f"\n⏹️  推演结束：{reason}（{generations} 代，{total_exp} 条经验）"

    def on_summary(self, result: dict[str, Any]) -> str:
        lines = [
            "─" * 50,
            "📊 推演汇总",
            f"  经验总数:   {result.get('total_experiences', 0)}",
            f"  完成代数:   {result.get('completed_generations', 0)}",
            f"  全局最优:   {result.get('global_best_score', 'N/A')}",
            f"  最终基线:   {result.get('rolling_score', 'N/A')}",
            f"  推演目录:   {result.get('campaign_root', '')}",
            "─" * 50,
        ]
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# 运行时状态（.orchestrator-state.json）
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class OrchestratorState:
    campaign_id: str
    generation: int = 0
    total_experiences: int = 0
    rolling_score: int = 0
    global_best_score: int = 0
    stopped_reason: str | None = None
    errors: list[dict[str, Any]] = field(default_factory=list)
    lineage: list[dict[str, Any]] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["last_updated"] = datetime.now(UTC).isoformat()
        return d


# ─────────────────────────────────────────────────────────────────────────────
# 统一编排器
# ─────────────────────────────────────────────────────────────────────────────
class CampaignOrchestrator:
    """
    单一入口编排器。

    幂等/恢复全靠现有服务：
      - ProductionEvolutionCampaignService 已内置 campaign 持久化
      - ProductionGenerationExecutor 已内置 candidate_outcome.json 断点
      - 本类只负责：experience goal 退出 + 进度回调 + 统一 CLI 入口
    """

    def __init__(
        self,
        project_root: Path,
        *,
        scenario_package_id: str,
        campaign_id: str,
        experience_goal: int = 100,
        max_generations: int = 20,
        max_cmo_runs: int = 200,
        max_repair_attempts: int = 3,
        execution_mode: str = "PRODUCTION_CMO",
        minimum_improvement_delta: int = 1,
        no_improvement_patience: int = 3,
        progress: ProgressCallback | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.campaign_id = campaign_id
        self.experience_goal = experience_goal
        self.max_generations = max_generations
        self.max_cmo_runs = max_cmo_runs
        self.max_repair_attempts = max_repair_attempts
        self.execution_mode = execution_mode
        self.minimum_improvement_delta = minimum_improvement_delta
        self.no_improvement_patience = no_improvement_patience
        self.progress = progress or ProgressCallback()

        self._output_root = self.project_root / "runs" / "evolution" / campaign_id
        self._state_file = self.project_root / "runs" / "evolution" / campaign_id / ".orchestrator-state.json"
        self._stop_event = Event()
        self._llm_config = load_config()

    # ── 公开 API ──────────────────────────────────────────────────────────────

    def start(self) -> dict[str, Any]:
        """启动新的推演任务（幂等：同名 campaign 已存在则续跑）"""
        store = CampaignStore(self.project_root / "runs" / "evolution")
        existing = self._get_campaign_state(store)

        if existing and existing.get("status") == "completed":
            logger.info("Campaign %s 已完成，续跑视为重跑，直接重新开始", self.campaign_id)
            # 保留 lineage，只重置运行时状态
            self._output_root.mkdir(parents=True, exist_ok=True)
            state = self._load_state()
            state.generation = 0
            state.stopped_reason = None
            self._save_state(state)

        return self._run()

    def resume(self) -> dict[str, Any]:
        """从上次中断处续跑"""
        logger.info("续跑 campaign %s", self.campaign_id)
        return self._run()

    def status(self) -> dict[str, Any]:
        """查询当前推演状态（不执行）"""
        state = self._load_state()
        store = CampaignStore(self.project_root / "runs" / "evolution")
        campaign_state = self._get_campaign_state(store)

        exp_count = self._count_experiences()
        lineage = self._read_lineage()

        return {
            "campaign_id": self.campaign_id,
            "status": campaign_state.get("status") if campaign_state else "unknown",
            "generation": state.generation,
            "total_experiences": exp_count,
            "experience_goal": self.experience_goal,
            "goal_progress_pct": min(100, round(exp_count / self.experience_goal * 100)),
            "rolling_score": state.rolling_score,
            "global_best_score": state.global_best_score,
            "lineage": lineage,
            "errors": state.errors,
            "campaign_root": str(self._output_root),
        }

    def stop(self) -> dict[str, str]:
        """外部终止信号"""
        self._stop_event.set()
        return {"message": f"已发送停止信号到 {self.campaign_id}"}

    # ── 内部执行 ─────────────────────────────────────────────────────────────

    def _run(self) -> dict[str, Any]:
        """封装 ProductionEvolutionCampaignService 执行主循环"""
        service = self._build_service()

        # 构建任务规格（首次创建）
        spec = self._build_spec()
        budget = self._build_budget()

        # 检查 CMO 锁
        lock_path = self.project_root / ".cmo-instance.lock"
        if lock_path.exists() and self.execution_mode == "PRODUCTION_CMO":
            lock_content = lock_path.read_text(encoding="utf-8", errors="replace")
            return {
                "error": "cmo_lock_contested",
                "message": self.progress.on_cmo_lock_contested(self.campaign_id),
                "lock_content": lock_content,
                "hint": "运行 stop 或确保其他进程已退出后再试",
            }

        # 准备 campaign（幂等）
        try:
            service.prepare_campaign_request(
                campaign_id=self.campaign_id,
                input_package_id=spec.scenario_ref,
                generation_objective=spec.generation_objective,
                budget=asdict(budget),
                minimum_improvement_delta=self.minimum_improvement_delta,
                no_improvement_patience=self.no_improvement_patience,
            )
        except Exception as exc:
            # 已存在的 campaign 会抛异常，继续走 resume 路径
            logger.debug("prepare_campaign_request: %s", exc)

        svc = service._services.get(self.campaign_id)
        if svc is None:
            return {"error": "campaign_not_found", "message": f"Campaign {self.campaign_id} 未找到"}

        # 代际主循环（带 experience goal 退出）
        exp_before = self._count_experiences()
        lineage_entries: list[dict[str, Any]] = []

        for gen in range(self.max_generations):
            if self._stop_event.is_set():
                break

            logger.info("执行代数 %d", gen)
            # 执行一代（ProductionGenerationExecutor 已内置断点）
            worker = svc.execute_generation(
                campaign_id=self.campaign_id,
                generation_index=gen,
            )
            done = self._poll_worker(svc, worker, timeout_seconds=3600)
            if not done:
                self._save_error(gen, "execute_generation", "poll_timeout")
                break

            # 读取 Phase6 评分
            phase6_scores = self._read_phase6_scores(gen)
            logger.info("代数 %d Phase6 分数: %s", gen, phase6_scores)

            # 读取 Phase7 新增经验数（从 lineage 或 experience count diff）
            exp_after = self._count_experiences()
            new_exp = exp_after - exp_before
            exp_before = exp_after

            lineage_entries.append({
                "generation": gen,
                "best_score": max(phase6_scores.values()) if phase6_scores else 0,
                "new_experiences": new_exp,
                "total_experiences": exp_after,
            })

            # 检查经验目标
            if exp_after >= self.experience_goal:
                logger.info("经验目标 %d 达成（当前 %d），优雅退出", self.experience_goal, exp_after)
                break

        # 最终汇总
        total_exp = self._count_experiences()
        final_state = self._build_final_result(lineage_entries, total_exp)

        self.progress.on_stopped(
            f"代数耗尽或目标达成",
            generations=len(lineage_entries),
            total_exp=total_exp,
        )
        self.progress.on_summary(final_state)

        return final_state

    # ── 辅助 ─────────────────────────────────────────────────────────────────

    def _build_service(self) -> ProductionEvolutionCampaignService:
        """构建 ProductionEvolutionCampaignService"""
        config = self._llm_config
        llm_client = ClaudeClient(config.llm)
        json_client = ClaudeJsonClient(config.llm)

        package_loader = ControlledCampaignInputPackageLoader(
            project_root=self.project_root,
        )
        candidate_evaluator = FormalCandidateEvaluator(
            project_root=self.project_root,
            json_client=json_client,
        )
        knowledge_snapshot = ProductionKnowledgeSnapshotProvider(
            project_root=self.project_root,
        )

        phase7_adapter = ProductionPhase7Adapter(
            project_root=self.project_root,
            json_client=json_client,
        )
        phase8_adapter = ProductionPhase8Adapter(
            project_root=self.project_root,
            json_client=json_client,
            experience_store=phase7_adapter.experience_store,
        )

        artifact_provenance = (
            "test_fixture"
            if self.execution_mode == "FAKE_FIXTURE"
            else "formal_renderer"
        )

        return ProductionEvolutionCampaignService(
            project_root=self.project_root,
            package_loader=package_loader,
            proposal_agent=None,  # 由 candidate_evaluator 内部处理
            candidate_evaluator=candidate_evaluator,
            phase7_adapter=phase7_adapter,
            phase8_adapter=phase8_adapter,
            champion_policy=None,
            stop_policy=StopPolicy(),
            synchronous_fake_workers=(self.execution_mode == "FAKE_FIXTURE"),
            artifact_provenance=artifact_provenance,
            knowledge_snapshot_provider=knowledge_snapshot,
        )

    def _build_spec(self) -> EvolutionCampaignSpec:
        return EvolutionCampaignSpec(
            campaign_id=self.campaign_id,
            scenario_id="unknown",
            scenario_ref=self.campaign_id.split("_")[0] if "_" in self.campaign_id else self.campaign_id,
            scenario_checksum="",
            initial_strategy_ref="",
            runtime_contract_checksum="",
            renderer_contract_checksum="",
            score_contract_checksum="",
            semantic_contract_checksum="",
            code_revision="",
            allowed_strategy_paths=(),
            generation_objective="Improve red-side score through multi-candidate generation, experience accumulation, and skill evolution.",
            budget=self._build_budget(),
            execution_mode=(
                CampaignExecutionMode.FAKE_FIXTURE
                if self.execution_mode == "FAKE_FIXTURE"
                else CampaignExecutionMode.PRODUCTION_CMO
            ),
            minimum_improvement_delta=self.minimum_improvement_delta,
            no_improvement_patience=self.no_improvement_patience,
        )

    def _build_budget(self) -> CampaignBudget:
        return CampaignBudget(
            max_generations=self.max_generations,
            max_cmo_runs=self.max_cmo_runs,
            max_cmo_attempts_per_candidate=self.max_repair_attempts + 1,
            max_cmo_attempts_for_baseline=3,
            max_repair_attempts_per_candidate=self.max_repair_attempts,
            max_failed_runs=max(1, self.max_cmo_runs // 10),
            max_llm_total_calls=99999,
            max_strategy_proposal_calls=99999,
            max_lua_generation_calls=99999,
            max_lua_repair_calls=99999,
            max_comparative_learning_calls=99999,
            max_skill_author_calls=99999,
            max_wall_clock_seconds=0,
            per_generation_timeout_seconds=3600,
            per_candidate_timeout_seconds=600,
        )

    def _poll_worker(
        self,
        service: ProductionEvolutionCampaignService,
        worker_id: str,
        timeout_seconds: int = 3600,
    ) -> bool:
        """轮询 worker 直到完成或超时"""
        deadline = time.monotonic() + timeout_seconds
        store = service._services[self.campaign_id]._load if hasattr(service._services.get(self.campaign_id), "_load") else None

        while time.monotonic() < deadline:
            if self._stop_event.is_set():
                return False
            try:
                store = CampaignStore(self.project_root / "runs" / "evolution" / self.campaign_id)
                worker = store.get_worker(worker_id)
                if worker is not None and worker.status in {"completed", "failed", "cancelled"}:
                    return worker.status == "completed"
            except Exception as exc:
                logger.debug("poll_worker: %s", exc)
            time.sleep(5)
        return False

    def _get_campaign_state(self, store: CampaignStore) -> dict[str, Any] | None:
        """从 CampaignStore 读取 campaign 状态元数据"""
        try:
            meta_path = self.project_root / "runs" / "evolution" / self.campaign_id / ".campaign-meta.json"
            if meta_path.exists():
                return json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return None

    def _read_phase6_scores(self, generation: int) -> dict[str, int]:
        """读取代数分数快照（用于进度展示）"""
        gen_root = self._output_root / "generations" / f"generation_{generation:03d}" / "phase6"
        if not gen_root.exists():
            return {}
        scores: dict[str, int] = {}
        for candidate_dir in gen_root.iterdir():
            outcome_file = candidate_dir / "candidate_outcome.json"
            if outcome_file.exists():
                try:
                    data = json.loads(outcome_file.read_text(encoding="utf-8"))
                    cid = data.get("candidate_id", candidate_dir.name)
                    scores[candidate_dir.name] = data.get("native_score", 0)
                except Exception:
                    pass
        return scores

    def _read_lineage(self) -> list[dict[str, Any]]:
        lineage_file = self._output_root / "lineage.jsonl"
        if not lineage_file.exists():
            return []
        entries = []
        for line in lineage_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    entries.append(json.loads(line))
                except Exception:
                    pass
        return entries[-10:]  # 最近 10 代

    def _count_experiences(self) -> int:
        try:
            store = ExperienceStore(self.project_root / "data" / "experiences")
            return len(list(store._records_dir.glob("exp_*.json")))
        except Exception:
            return 0

    def _load_state(self) -> OrchestratorState:
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text(encoding="utf-8"))
                return OrchestratorState(**{k: v for k, v in data.items()
                                           if k in OrchestratorState.__dataclass_fields__})
            except Exception:
                pass
        return OrchestratorState(campaign_id=self.campaign_id)

    def _save_state(self, state: OrchestratorState) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(
            json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _save_error(self, generation: int, phase: str, error: str) -> None:
        state = self._load_state()
        state.errors.append({
            "generation": generation,
            "phase": phase,
            "error": error,
            "at": datetime.now(UTC).isoformat(),
        })
        self._save_state(state)

    def _build_final_result(
        self,
        lineage: list[dict[str, Any]],
        total_exp: int,
    ) -> dict[str, Any]:
        rolling = lineage[-1]["best_score"] if lineage else 0
        global_best = max((e["best_score"] for e in lineage), default=0)
        return {
            "campaign_id": self.campaign_id,
            "total_experiences": total_exp,
            "experience_goal": self.experience_goal,
            "goal_reached": total_exp >= self.experience_goal,
            "completed_generations": len(lineage),
            "rolling_score": rolling,
            "global_best_score": global_best,
            "lineage": lineage,
            "errors": self._load_state().errors,
            "campaign_root": str(self._output_root),
        }
