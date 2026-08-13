"""Training 后台进程的生产装配入口。

``TrainingProcessManager`` 以独立进程调用本模块；它装配 TrainingRunner 与唯一的
ProductionEvolutionCampaignService。此处不保存业务进度，所有可恢复事实均在
TrainingStore 和 Campaign Artifact 中，故进程重启不会依赖旧进程内存。
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
from time import sleep
from typing import Any

from cmo_lua_agent.agents.code_repair_agent import CodeRepairAgent
from cmo_lua_agent.agents.context_summary_agent import ContextSummaryAgent
from cmo_lua_agent.evolution.production_service import (
    create_production_evolution_campaign_service,
)
from cmo_lua_agent.llm.client import ClaudeClient
from cmo_lua_agent.llm.json_client import ClaudeJsonClient
from cmo_lua_agent.llm_config import load_config
from cmo_lua_agent.training.models import TrainingRequest
from cmo_lua_agent.training.models import TrainingAction, TrainingStatus
from cmo_lua_agent.training.runner import TrainingRunner
from cmo_lua_agent.training.store import TrainingStore
from cmo_lua_agent.training.repair import CodeRepairCoordinator
from cmo_lua_agent.training.fixture import FixtureCampaignDriver
from cmo_lua_agent.training.recovery import RecoveryRouter, make_unknown_diagnoser
from cmo_lua_agent.orchestration.events import AgentEvent, AgentEventType
from cmo_lua_agent.orchestration.context_manager import ContextManager


class ProductionCampaignDriver:
    """把 Training 调度动作翻译为正式 Campaign 门面调用。

它是 Training 与 evolution 两层的唯一桥接层：上游是 TrainingRunner，下游是
ProductionEvolutionCampaignService。它不读取 Campaign 私有字段，也不自行轮询
或重排候选，从而保证 Campaign 的状态机只有一份。
    """

    def __init__(self, service: Any) -> None:
        self._service = service

    def prepare(self, request: TrainingRequest) -> str:
        """将持久化训练请求转换为生产 Campaign，并返回稳定 Campaign ID。"""
        if request.generation_count is None:
            raise ValueError("fixed_generation_count_required")
        campaign_id = f"{request.workflow_id}-campaign"
        self._service.prepare_training_campaign(
            campaign_id=campaign_id,
            input_package_id=request.input_path,
            generation_objective=request.objective,
            generation_count=request.generation_count,
        )
        return campaign_id

    def preview(self, campaign_id: str, generation_index: int) -> None:
        """生成本代预览；仅对明确的可再生预览错误执行一次受控重建。

        ``preview_regeneration_required`` 是 Campaign 层公开的稳定恢复码。除该情况外，
        异常必须向上传回 Runner 统一分类，避免适配层吞掉真实的系统或业务失败。
        """
        arguments = {
            "campaign_id": campaign_id,
            "generation_index": generation_index,
        }
        try:
            self._service.preview_generation(**arguments)
        except ValueError as exc:
            if str(exc) != "preview_regeneration_required":
                raise
            self._service.preview_generation(**arguments, regenerate_preview=True)

    def execute(self, campaign_id: str, generation_index: int) -> None:
        """委托 Campaign 启动本代执行；实际 CMO Worker 生命周期由 Campaign 管理。"""
        self._service.execute_generation(
            campaign_id=campaign_id,
            generation_index=generation_index,
        )

    def inspect_generation(self, campaign_id: str, generation_index: int) -> dict[str, object]:
        """读取已持久化的本代状态，不从本地内存推断 Worker 是否完成。"""
        return self._service.inspect_generation(campaign_id, generation_index)

    def pause(self, campaign_id: str) -> None:
        self._service.pause_campaign(campaign_id)

    def resume(self, campaign_id: str) -> None:
        self._service.resume_campaign(campaign_id)

    def stop(self, campaign_id: str) -> None:
        self._service.stop_campaign(campaign_id)

    def reconcile(self, campaign_id: str) -> dict[str, object]:
        return self._service.reconcile_campaign(campaign_id)

    def run_phase8(
        self,
        campaign_id: str,
        completed_generations: tuple[int, ...],
    ) -> dict[str, object]:
        """在所有代完成后委托 Campaign 统一聚合本 Workflow 的经验。"""
        return self._service.run_training_phase8(
            workflow_id=campaign_id.removesuffix("-campaign"),
            campaign_id=campaign_id,
            completed_generations=completed_generations,
        )


def run_workflow(*, project_root: Path, workflow_id: str) -> TrainingStatus:
    """运行或恢复一个持久化 Workflow，直到终态或需要人工处理。

输入是磁盘上已经创建的 workflow_id；返回最终 TrainingStatus。函数会先对账，
再循环调用 Runner。CMO 等待和可重试端点失败均保留在 state.json 中，因此这里
只负责下一次唤醒，不把“等待”误判为失败或要求用户重复授权。
    """
    root = Path(project_root).resolve()
    store = TrainingStore(root, workflow_id)
    execution_mode = store.load_request().execution_mode if store.root.is_dir() else "PRODUCTION_CMO"
    if execution_mode == "FAKE_FIXTURE":
        driver = FixtureCampaignDriver()
        recovery_router = RecoveryRouter()
        repair_coordinator = None
    else:
        config = load_config()
        llm_client = ClaudeClient(config.llm)
        service = create_production_evolution_campaign_service(
            project_root=root,
            app_config=config,
            llm_client=llm_client,
        )
        driver = ProductionCampaignDriver(service)
        recovery_router = RecoveryRouter(
            unknown_diagnoser=make_unknown_diagnoser(ClaudeJsonClient(llm_client))
        )
        repair_agent = CodeRepairAgent(
            project_root=root,
            llm_client=llm_client,
            event_handler=lambda event: _append_repair_agent_event(store, event),
            context_manager=ContextManager(
                context_window_tokens=getattr(
                    config.llm, "context_window_tokens", 1_000_000
                ),
                summarizer=ContextSummaryAgent(ClaudeJsonClient(llm_client)),
            ),
        )
        repair_coordinator = CodeRepairCoordinator(
            project_root=root,
            system_repair_agent=repair_agent,
        )
    runner = TrainingRunner(
        store,
        driver,
        repair_coordinator=repair_coordinator,
        recovery_router=recovery_router,
    )
    runner.reconcile()
    while True:
        state = runner.run()
        if state.status is not TrainingStatus.RUNNING:
            return state.status
        # RUNNING 既可能是在等 CMO Worker，也可能是在等可重试的端点/进程失败退避。
        # 两者的下一步都由持久化 action 决定，后台进程不能因为没有即时结果而结束。
        sleep(retry_sleep_seconds(state))


def _append_repair_agent_event(store: TrainingStore, event: AgentEvent) -> None:
    """把修复轨迹压缩进现有 journal，不记录模型流式正文或完整工具输出。"""

    if event.type is AgentEventType.TEXT_DELTA:
        return
    data = event.data
    row: dict[str, object] = {
        "event": "code_repair_agent_event",
        "agent_event": event.type.value,
    }
    for key in (
        "turn",
        "turns",
        "tool_name",
        "duration_seconds",
        "error_type",
        "stop_reason",
        "estimated_tokens_before",
        "estimated_tokens_after",
        "context_window_tokens",
        "target_tokens",
        "retained_message_count",
        "strategy",
        "fallback_reason",
    ):
        if key in data:
            row[key] = data[key]
    arguments = data.get("arguments")
    if isinstance(arguments, dict):
        if isinstance(arguments.get("path"), str):
            row["target"] = arguments["path"]
        elif isinstance(arguments.get("argv"), list):
            row["target"] = arguments["argv"]
    store.append_event(row)


def retry_sleep_seconds(state: object) -> int:
    """读取持久化退避时间；没有 retry 时使用普通 Worker 轮询间隔。

    上限为 60 秒，保证暂停、停止等外部控制请求不会因一次端点退避而长时间失去响应。
    """
    runner = getattr(state, "runner", {})
    retry = runner.get("retry") if isinstance(runner, dict) else None
    next_retry_at = retry.get("next_retry_at") if isinstance(retry, dict) else None
    if not isinstance(next_retry_at, str):
        return 1
    try:
        target = datetime.fromisoformat(next_retry_at.replace("Z", "+00:00"))
    except ValueError:
        return 1
    if target.tzinfo is None:
        target = target.replace(tzinfo=UTC)
    remaining = int((target - datetime.now(UTC)).total_seconds())
    return max(1, min(remaining, 60))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one persistent CMO training workflow")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--project-root", required=True)
    run.add_argument("--workflow-id", required=True)
    args = parser.parse_args(argv)
    status = run_workflow(
        project_root=Path(args.project_root),
        workflow_id=str(args.workflow_id),
    )
    return 0 if status is TrainingStatus.COMPLETED else 1


if __name__ == "__main__":
    raise SystemExit(main())
