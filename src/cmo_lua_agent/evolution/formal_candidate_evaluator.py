"""Phase 9C 冻结策略 → Phase 5 评估器适配层"""
from __future__ import annotations

import json
from pathlib import Path

from cmo_lua_agent.agents.lua_repair_agent import LuaRepairAgent
from cmo_lua_agent.evolution.authorized_candidate_runner import (
    CampaignAuthorizedCandidateRunner,
)
from cmo_lua_agent.optimization.candidate_evaluation_workflow import (
    CandidateEvaluationWorkflow,
)
from cmo_lua_agent.optimization.candidate_models import CandidateRequest
from cmo_lua_agent.generation.manual_template_assembly import (
    ManualTemplateAssemblyService,
)


class FormalCandidateEvaluator:
    """
    正式候选评估适配器：将已冻结策略输入对接至 Phase 6/CMO 推演评估链路
    职责范围：管理候选Lua修复配额、采集推演运行证据；
    不参与Champion选拔、不负责演化世代推进，上述逻辑归属CampaignPolicy与TrainingRunner。
    """
    def __init__(
        self,
        *,
        json_client,
        cmo_runner_path: Path,
        cmo_executable_path: Path,
        runner_factory=None,
    ) -> None:
        """
        :param json_client: LLM JSON交互客户端，供给Lua修复Agent使用
        :param cmo_runner_path: CMO批量推演执行器路径
        :param cmo_executable_path: CMO主程序可执行文件路径
        :param runner_factory: 自定义Runner工厂，用于依赖注入与单元测试
        """
        self._json_client = json_client
        self._runner_path = Path(cmo_runner_path)
        self._command_path = Path(cmo_executable_path)
        self._runner_factory = runner_factory

    def preflight(self) -> dict[str, str]:
        """前置预检：校验CMO推演依赖文件是否存在，返回运行环境信息"""
        if not self._runner_path.is_file():
            raise ValueError("cmo_batch_runner_missing")
        if not self._command_path.is_file():
            raise ValueError("cmo_executable_missing")
        return {
            "cmo_batch_runner": str(self._runner_path.resolve()),
            "cmo_executable": str(self._command_path.resolve()),
        }

    def __call__(
        self,
        *,
        candidate_id,
        strategy,
        candidate_dir,
        generation_index,
        context,
        package,
    ) -> dict[str, object]:
        """
        执行单个候选策略完整推演评估流程
        :param candidate_id: 候选唯一标识
        :param strategy: 待评估冻结策略对象
        :param candidate_dir: 当前候选独立工作目录
        :param generation_index: 当前演化代数
        :param context: 任务运行上下文（含暂停/终止控制、预算约束）
        :param package: ControlledCampaignInputPackage，承载想定资产、基线、约束等全局输入
        :return: 附带溯源信息的候选评估结果字典
        :raises ValueError: 评估结束未生成输出文件时抛出异常
        """
        # 构建授权推演运行器，隔离单候选推演环境
        runner = CampaignAuthorizedCandidateRunner(
            candidate_id=candidate_id,
            generation_index=generation_index,
            worker_context=context,
            scenario_asset=package.scenario_asset,
            cmo_runner_path=self._runner_path,
            cmo_executable_path=self._command_path,
            runner_factory=self._runner_factory,
        )
        # 可选：手动Lua模板装配服务，存在模板根路径时启用
        assembler = (
            ManualTemplateAssemblyService(
                template_root=package.manual_template_root,
                baseline_strategy=package.baseline.strategy,
            )
            if getattr(package, "manual_template_root", None) is not None
            else None
        )
        # 组装完整评估工作流：推演执行 + Lua脚本自动修复
        workflow = CandidateEvaluationWorkflow(
            cmo_runner=runner,
            repair_agent=LuaRepairAgent(self._json_client),
            # 外部中断信号回调
            is_cancelled=lambda: context.control_action() in {"pause", "stop"},
            assembler=assembler,
        )
        # 构造候选评估请求，固化本轮预算、权限、运行约束
        request = CandidateRequest(
            candidate_id=candidate_id,
            generation_index=generation_index,
            scenario=package.scenario,
            strategy=strategy,
            runtime=package.runtime,
            native_score_compilation=package.native_score_compilation,
            max_repairs=context.spec.budget.max_repair_attempts_per_candidate,
            timeout_seconds=context.spec.budget.per_candidate_timeout_seconds,
            candidate_dir=Path(candidate_dir),
            allowed_strategy_paths=package.allowed_strategy_paths,
            reuse_existing_artifacts=True,
            official_score_only=True,
        )
        # 启动推演与打分流程
        workflow.evaluate(request)
        # 读取评估产出文件
        outcome_path = Path(candidate_dir) / "candidate_outcome.json"
        if not outcome_path.is_file():
            raise ValueError("candidate_outcome_missing")
        value = json.loads(outcome_path.read_text(encoding="utf-8"))

        # 追加溯源标记，用于上层校验
        value["artifact_provenance"] = "formal_renderer"
        value["scenario_reset"] = {
            "scenario_reset_verified": True,
            "scenario_asset_id": package.scenario_asset.asset_id,
            "scenario_checksum": package.scenario_asset.sha256,
        }
        return value