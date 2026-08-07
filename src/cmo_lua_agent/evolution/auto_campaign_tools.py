"""
一键自动化推演工具（Phase9C 全自动运行封装）

封装 prepare → preview → execute × N代 的完整自动化链路：
- 幂等：已完成的 candidate_outcome.json 直接跳过重评
- 经验目标退出：积累够 target_experiences 条经验后优雅终止
- 进度推送：通过 ToolProgressReporter 实时输出到终端
- 可中断：StopEvolutionCampaignTool 发送信号后，当前代完成后退出循环

使用方式（终端对话）：
  → 启动自动化推演，场景 red_blue_6v4_liaoning，积累 100 条经验
  → 用测试模式启动自动化推演，积累 20 条经验
  → 停止当前自动化推演
  → 查看自动化推演进度
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, UTC
from pathlib import Path
from threading import Event
from typing import Any

from cmo_lua_agent.evolution.campaign_store import CampaignStore
from cmo_lua_agent.evolution.controlled_input_package import ControlledCampaignInputPackageLoader
from cmo_lua_agent.evolution.formal_adapters import FormalPhase6Adapter
from cmo_lua_agent.evolution.formal_candidate_evaluator import FormalCandidateEvaluator
from cmo_lua_agent.evolution.production_knowledge import ProductionKnowledgeSnapshotProvider
from cmo_lua_agent.evolution.models import CampaignBudget, CampaignExecutionMode, EvolutionCampaignSpec
from cmo_lua_agent.evolution.production_phase_adapters import ProductionPhase7Adapter, ProductionPhase8Adapter
from cmo_lua_agent.evolution.production_service import ProductionEvolutionCampaignService
from cmo_lua_agent.evolution.stop_policy import StopPolicy
from cmo_lua_agent.llm.json_client import ClaudeJsonClient
from cmo_lua_agent.llm_config import load_config
from cmo_lua_agent.learning.store import ExperienceStore
from cmo_lua_agent.tools.tool_base.base import BaseTool, ToolResult
from cmo_lua_agent.tools.tool_base.context import ToolContext

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 全局停止信号（跨工具共享）
# ─────────────────────────────────────────────────────────────────────────────
_AUTO_STOP_EVENTS: dict[str, Event] = {}  # campaign_id → stop event


def _stop_event(campaign_id: str) -> Event:
    if campaign_id not in _AUTO_STOP_EVENTS:
        _AUTO_STOP_EVENTS[campaign_id] = Event()
    return _AUTO_STOP_EVENTS[campaign_id]


# ─────────────────────────────────────────────────────────────────────────────
# 工具：启动自动化推演
# ─────────────────────────────────────────────────────────────────────────────
class StartAutoEvolutionCampaignTool(BaseTool):
    """
    一键启动自动化推演：prepare → preview → execute × N代 → 经验积累退出。

    幂等保证：
      - 首次运行：创建 campaign，执行所有代数
      - 中断后重跑：从最后一个完成代数继续（candidate_outcome.json 已存在的跳过）
      - 经验目标达成：优雅退出，不跑更多代数
    """
    name = "start_auto_evolution_campaign"
    toolset = "campaign"

    description = """
一键启动完整自动化推演链路：prepare → preview → execute × N代 → 经验积累退出。
幂等可恢复。参数 target_experiences=100 表示积累 100 条经验后自动停止。
可用 execution_mode=FAKE_FIXTURE 做快速冒烟测试（不调用真实 CMO）。
    """.strip()

    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "campaign_id": {
                "type": "string",
                "description": "唯一推演任务 ID，用于幂等恢复。如已存在则续跑。",
            },
            "scenario_package_id": {
                "type": "string",
                "enum": ["red_blue_6v4_liaoning_v1"],
                "description": "输入场景包 ID",
            },
            "generation_objective": {
                "type": "string",
                "default": "Improve red-side score through multi-candidate generation, experience accumulation, and skill evolution.",
                "description": "推演目标描述",
            },
            "target_experiences": {
                "type": "integer",
                "default": 100,
                "minimum": 1,
                "description": "积累够此数量的经验后自动停止",
            },
            "max_generations": {
                "type": "integer",
                "default": 20,
                "minimum": 1,
                "description": "最大代数上限（防止经验目标一直达不到时无限跑）",
            },
            "max_cmo_runs": {
                "type": "integer",
                "default": 200,
                "minimum": 1,
                "description": "全局 CMO 仿真次数上限",
            },
            "max_repair_attempts": {
                "type": "integer",
                "default": 3,
                "minimum": 1,
                "description": "单条候选 Lua 修复最大重试次数",
            },
            "execution_mode": {
                "type": "string",
                "enum": ["PRODUCTION_CMO", "FAKE_FIXTURE"],
                "default": "FAKE_FIXTURE",
                "description": "PRODUCTION_CMO=真实 CMO 仿真；FAKE_FIXTURE=测试冒烟（快速验证流程）",
            },
            "minimum_improvement_delta": {
                "type": "integer",
                "default": 1,
                "description": "分数提升低于此值触发 patience",
            },
            "no_improvement_patience": {
                "type": "integer",
                "default": 3,
                "description": "连续几代无提升后退出",
            },
        },
        "required": ["campaign_id", "scenario_package_id"],
        "additionalProperties": False,
    }

    def execute(self, arguments: dict[str, Any], context: ToolContext | None = None) -> ToolResult:
        campaign_id = str(arguments["campaign_id"])
        scenario_package_id = str(arguments["scenario_package_id"])
        target_experiences = int(arguments.get("target_experiences", 100))
        max_generations = int(arguments.get("max_generations", 20))
        max_cmo_runs = int(arguments.get("max_cmo_runs", 200))
        max_repair_attempts = int(arguments.get("max_repair_attempts", 3))
        execution_mode = str(arguments.get("execution_mode", "FAKE_FIXTURE"))
        generation_objective = str(arguments.get(
            "generation_objective",
            "Improve red-side score through multi-candidate generation, experience accumulation, and skill evolution.",
        ))
        minimum_improvement_delta = int(arguments.get("minimum_improvement_delta", 1))
        no_improvement_patience = int(arguments.get("no_improvement_patience", 3))

        project_root = Path(__file__).parents[3]  # src/cmo_lua_agent/evolution → 项目根
        stop_evt = _stop_event(campaign_id)
        stop_evt.clear()

        def report(msg: str) -> None:
            if context is not None:
                context.progress.tool_progress(msg)
            logger.info("[%s] %s", campaign_id, msg)

        try:
            result = _run_auto_campaign(
                project_root=project_root,
                campaign_id=campaign_id,
                scenario_package_id=scenario_package_id,
                generation_objective=generation_objective,
                target_experiences=target_experiences,
                max_generations=max_generations,
                max_cmo_runs=max_cmo_runs,
                max_repair_attempts=max_repair_attempts,
                execution_mode=execution_mode,
                minimum_improvement_delta=minimum_improvement_delta,
                no_improvement_patience=no_improvement_patience,
                stop_event=stop_evt,
                progress_callback=report,
            )
            return ToolResult(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        except Exception as exc:
            logger.exception("自动化推演出错: %s", exc)
            return ToolResult(
                json.dumps({"error": "auto_campaign_failed", "message": str(exc)}, ensure_ascii=False, indent=2),
                is_error=True,
            )


# ─────────────────────────────────────────────────────────────────────────────
# 工具：停止自动化推演
# ─────────────────────────────────────────────────────────────────────────────
class StopAutoEvolutionCampaignTool(BaseTool):
    name = "stop_auto_evolution_campaign"
    toolset = "campaign"

    description = "向运行中的自动化推演发送停止信号，当前代数完成后优雅退出。"

    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "campaign_id": {"type": "string", "description": "要停止的推演任务 ID"},
        },
        "required": ["campaign_id"],
        "additionalProperties": False,
    }

    def execute(self, arguments: dict[str, Any], context: ToolContext | None = None) -> ToolResult:
        campaign_id = str(arguments["campaign_id"])
        stop_evt = _stop_event(campaign_id)
        stop_evt.set()
        return ToolResult(json.dumps({
            "message": f"已向 {campaign_id} 发送停止信号，当前代数完成后退出",
            "campaign_id": campaign_id,
        }, ensure_ascii=False, indent=2))


# ─────────────────────────────────────────────────────────────────────────────
# 工具：查看自动化推演进度
# ─────────────────────────────────────────────────────────────────────────────
class StatusAutoEvolutionCampaignTool(BaseTool):
    name = "status_auto_evolution_campaign"
    toolset = "campaign"

    description = "查询自动化推演当前进度（不执行任何操作）。"

    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "campaign_id": {"type": "string", "description": "推演任务 ID"},
        },
        "required": ["campaign_id"],
        "additionalProperties": False,
    }

    def execute(self, arguments: dict[str, Any], context: ToolContext | None = None) -> ToolResult:
        campaign_id = str(arguments["campaign_id"])
        project_root = Path(__file__).parents[3]

        # 读 lineage
        lineage_file = project_root / "runs" / "evolution" / campaign_id / "lineage.jsonl"
        lineage: list[dict[str, Any]] = []
        if lineage_file.exists():
            for line in lineage_file.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        lineage.append(json.loads(line))
                    except Exception:
                        pass

        # 读 campaign-meta
        meta_file = project_root / "runs" / "evolution" / campaign_id / ".campaign-meta.json"
        meta: dict[str, Any] = {}
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        # 读经验数
        exp_count = _count_experiences(project_root)

        # 读 orchestrator-state
        state_file = project_root / "runs" / "evolution" / campaign_id / ".orchestrator-state.json"
        state: dict[str, Any] = {}
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        last_gen = lineage[-1] if lineage else {}
        status = meta.get("status", "unknown")
        return ToolResult(json.dumps({
            "campaign_id": campaign_id,
            "status": status,
            "last_generation": last_gen.get("generation_index") if last_gen else None,
            "last_best_score": last_gen.get("selected_score") if last_gen else None,
            "completed_generations": len(lineage),
            "total_experiences": exp_count,
            "lineage": lineage[-5:],  # 最近 5 代
            "errors": state.get("errors", []),
            "is_running": campaign_id in _AUTO_STOP_EVENTS and not _AUTO_STOP_EVENTS[campaign_id].is_set(),
        }, ensure_ascii=False, indent=2, default=str))


# ─────────────────────────────────────────────────────────────────────────────
# 核心运行函数（工具逻辑抽出来，方便直接调用）
# ─────────────────────────────────────────────────────────────────────────────
def _run_auto_campaign(
    *,
    project_root: Path,
    campaign_id: str,
    scenario_package_id: str,
    generation_objective: str,
    target_experiences: int,
    max_generations: int,
    max_cmo_runs: int,
    max_repair_attempts: int,
    execution_mode: str,
    minimum_improvement_delta: int,
    no_improvement_patience: int,
    stop_event: Event,
    progress_callback: callable,
) -> dict[str, Any]:

    config = load_config()
    json_client = ClaudeJsonClient(config.llm)

    # ── 构建服务 ────────────────────────────────────────────────────────────
    package_loader = ControlledCampaignInputPackageLoader(project_root=project_root)
    candidate_evaluator = FormalCandidateEvaluator(
        project_root=project_root,
        json_client=json_client,
    )
    knowledge_snapshot = ProductionKnowledgeSnapshotProvider(project_root=project_root)

    phase7_adapter = ProductionPhase7Adapter(
        project_root=project_root,
        json_client=json_client,
    )
    phase8_adapter = ProductionPhase8Adapter(
        project_root=project_root,
        json_client=json_client,
        experience_store=phase7_adapter.experience_store,
    )

    artifact_provenance = (
        "test_fixture" if execution_mode == "FAKE_FIXTURE" else "formal_renderer"
    )

    service = ProductionEvolutionCampaignService(
        project_root=project_root,
        package_loader=package_loader,
        proposal_agent=None,
        candidate_evaluator=candidate_evaluator,
        phase7_adapter=phase7_adapter,
        phase8_adapter=phase8_adapter,
        champion_policy=None,
        stop_policy=StopPolicy(),
        synchronous_fake_workers=(execution_mode == "FAKE_FIXTURE"),
        artifact_provenance=artifact_provenance,
        knowledge_snapshot_provider=knowledge_snapshot,
    )

    # ── 准备 campaign（幂等：已存在则跳过）─────────────────────────────────
    budget = CampaignBudget(
        max_generations=max_generations,
        max_cmo_runs=max_cmo_runs,
        max_cmo_attempts_per_candidate=max_repair_attempts + 1,
        max_cmo_attempts_for_baseline=3,
        max_repair_attempts_per_candidate=max_repair_attempts,
        max_failed_runs=max(1, max_cmo_runs // 10),
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

    try:
        service.prepare_campaign_request(
            campaign_id=campaign_id,
            input_package_id=scenario_package_id,
            generation_objective=generation_objective,
            budget=asdict(budget),
            minimum_improvement_delta=minimum_improvement_delta,
            no_improvement_patience=no_improvement_patience,
        )
        progress_callback(f"✅ Campaign {campaign_id} 初始化完成")
    except Exception as exc:
        # 已存在的 campaign prepare 会抛异常，继续执行
        progress_callback(f"ℹ️  Campaign {campaign_id} 已存在，继续执行: {exc}")

    svc_instance = service._services.get(campaign_id)
    if svc_instance is None:
        raise RuntimeError(f"Campaign {campaign_id} 创建失败，未在服务中找到")

    store = CampaignStore(project_root / "runs" / "evolution" / campaign_id)

    # ── 确定起始代数（断点续跑：从最后一个完成代数之后开始）─────────────────
    lineage_file = project_root / "runs" / "evolution" / campaign_id / "lineage.jsonl"
    start_generation = 0
    if lineage_file.exists():
        lines = [l for l in lineage_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        if lines:
            try:
                last_line = json.loads(lines[-1])
                start_generation = last_line.get("generation_index", 0) + 1
            except Exception:
                pass

    # ── 经验计数基准 ───────────────────────────────────────────────────────
    exp_before = _count_experiences(project_root)
    lineage_entries: list[dict[str, Any]] = []

    # ── 代际主循环 ─────────────────────────────────────────────────────────
    for gen in range(start_generation, max_generations):
        if stop_event.is_set():
            progress_callback(f"⏹️  收到停止信号，代数 {gen} 后退出")
            break

        progress_callback(f"🟡 代数 {gen}/{max_generations} 开始")

        # 启动工作节点
        try:
            worker = svc_instance.execute_generation(
                campaign_id=campaign_id,
                generation_index=gen,
            )
        except Exception as exc:
            progress_callback(f"❌ 代数 {gen} 启动失败: {exc}")
            break

        # 轮询等待完成
        done = _poll_worker(store, worker.operation_id, timeout_seconds=3600, stop_event=stop_event)
        if not done:
            progress_callback(f"❌ 代数 {gen} 执行超时或被中断")
            break

        # 读取本代分数
        phase6_scores = _read_phase6_scores(project_root, campaign_id, gen)
        best_score = max(phase6_scores.values()) if phase6_scores else 0
        progress_callback(f"  ✅ Phase6 完成，候选分数: {phase6_scores}，本代最优: {best_score}")

        # 读 lineage 最后一行（Phase7/8 结果）
        new_exp = 0
        if lineage_file.exists():
            lines = [l for l in lineage_file.read_text(encoding="utf-8").splitlines() if l.strip()]
            if lines:
                try:
                    last_line = json.loads(lines[-1])
                    if last_line.get("generation_index") == gen:
                        new_exp = max(0, _count_experiences(project_root) - exp_before)
                except Exception:
                    pass

        lineage_entries.append({
            "generation_index": gen,
            "best_score": best_score,
            "new_experiences": new_exp,
        })

        # 经验目标检查
        exp_now = _count_experiences(project_root)
        progress_callback(f"  📚 经验累计: {exp_now}/{target_experiences}")
        if exp_now >= target_experiences:
            progress_callback(f"🎉 经验目标达成！{exp_now}/{target_experiences}，优雅退出")
            break

    # ── 最终汇总 ──────────────────────────────────────────────────────────
    total_exp = _count_experiences(project_root)
    return {
        "campaign_id": campaign_id,
        "total_experiences": total_exp,
        "experience_goal": target_experiences,
        "goal_reached": total_exp >= target_experiences,
        "completed_generations": len(lineage_entries),
        "lineage": lineage_entries,
        "campaign_root": str(project_root / "runs" / "evolution" / campaign_id),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 工具工厂
# ─────────────────────────────────────────────────────────────────────────────
def auto_campaign_tools() -> tuple[BaseTool, ...]:
    return (
        StartAutoEvolutionCampaignTool(),
        StopAutoEvolutionCampaignTool(),
        StatusAutoEvolutionCampaignTool(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────────────────────────────────────────
def _poll_worker(
    store: CampaignStore,
    operation_id: str,
    timeout_seconds: int,
    stop_event: Event,
) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if stop_event.is_set():
            return False
        try:
            worker = store.get_worker(operation_id)
            if worker is not None and worker.status in {"completed", "failed", "cancelled"}:
                return worker.status == "completed"
        except Exception:
            pass
        time.sleep(5)
    return False


def _read_phase6_scores(project_root: Path, campaign_id: str, generation: int) -> dict[str, int]:
    gen_root = project_root / "runs" / "evolution" / campaign_id / "generations" / f"generation_{generation:03d}" / "phase6"
    if not gen_root.exists():
        return {}
    scores: dict[str, int] = {}
    for candidate_dir in gen_root.iterdir():
        if not candidate_dir.is_dir():
            continue
        outcome_file = candidate_dir / "candidate_outcome.json"
        if outcome_file.exists():
            try:
                data = json.loads(outcome_file.read_text(encoding="utf-8"))
                scores[candidate_dir.name] = data.get("native_score", 0)
            except Exception:
                pass
    return scores


def _count_experiences(project_root: Path) -> int:
    try:
        records_dir = project_root / "data" / "experiences" / "records"
        if records_dir.exists():
            return len(list(records_dir.glob("exp_*.json")))
    except Exception:
        pass
    return 0
