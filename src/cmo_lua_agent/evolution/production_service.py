"""
Phase 9C 生产环境推演进化任务组装模块，同时提供完全隔离的测试变体。
职责：
1) 对外门面(Facade)，为每一轮推演进化任务（campaign）构建一套不可变更、绑定输入包的核心服务实例
2) 区分正式生产实例与测试Fixture实例，测试环境允许依赖注入替换组件，正式环境禁止外部覆盖依赖
3) 封装任务初始化、预校验、构造规格对象、存储任务清单、代理下层EvolutionCampaignService全部操作
4) 内置测试用的空适配器、Fixture冠军选择策略，单元测试可以不依赖真实CMO、Phase7/Phase8链路
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

# 进化模块：冠军策略（选出每代最优候选策略）
from cmo_lua_agent.evolution.champion_selection import ChampionSelectionPolicy
# 任务持久化存储，负责写入清单、快照、执行记录
from cmo_lua_agent.evolution.campaign_store import CampaignStore
# 核心业务服务：进化推演任务的真正实现逻辑
from cmo_lua_agent.evolution.control_plane import EvolutionCampaignService
# 受管控的输入包加载器：加载场景、基线策略、各类校验哈希、git版本信息
from cmo_lua_agent.evolution.controlled_input_package import (
    ControlledCampaignInputPackageLoader,
)
# 正式候选评估器：调用CMO仿真、执行全套Phase3‑6校验（语义校验、checksum审计、打分）
from cmo_lua_agent.evolution.formal_candidate_evaluator import FormalCandidateEvaluator
# 数据模型：任务预算、执行模式、任务完整规格定义
from cmo_lua_agent.evolution.models import (
    CampaignBudget,
    CampaignExecutionMode,
    EvolutionCampaignSpec,
)
# 新颖度校验：防止生成和历史高度重复的候选方案
from cmo_lua_agent.evolution.novelty import CandidateNoveltyValidator
# 生产环境代际执行器：驱动完整一代的生成‑评估‑对比‑学习闭环
from cmo_lua_agent.evolution.production_executor import ProductionGenerationExecutor
# 知识快照提供器：读取Phase8沉淀下来的Skill/经验库快照给生成环节使用
from cmo_lua_agent.evolution.production_knowledge import (
    ProductionKnowledgeSnapshotProvider,
)
# 预览构建器：预览模式，不跑真实CMO，只做规划渲染预览，用于调试
from cmo_lua_agent.evolution.production_preview_builder import ProductionPreviewBuilder
from cmo_lua_agent.evolution.rolling_baseline import (
    RollingBaselineResolver,
    apply_rolling_baseline,
)
# Phase7/Phase8生产适配器：把外部契约对接进进化任务工作流
from cmo_lua_agent.evolution.production_phase_adapters import (
    ProductionPhase7Adapter,
    ProductionPhase8Adapter,
)
# 停止策略：判断进化任务何时终止（达到预算、不再提升、最大代数）
from cmo_lua_agent.evolution.stop_policy import StopPolicy
# LLM JSON客户端，强制输出JSON，做格式校验
from cmo_lua_agent.llm.json_client import ClaudeJsonClient
from cmo_lua_agent.llm.agent_loop_json_client import AgentLoopJsonClient
from cmo_lua_agent.learning.skill_evolution.curated_skill_registry import CuratedSkillRegistry
from cmo_lua_agent.tools.list_curated_skills_tool import ListCuratedSkillsTool
from cmo_lua_agent.tools.view_curated_skill_tool import ViewCuratedSkillTool
from cmo_lua_agent.tools.tool_base.registry import ToolRegistry
# 策略提案Agent：基于经验库生成新的策略候选StrategySpec
from cmo_lua_agent.optimization.strategy_proposal_agent import StrategyProposalAgent


@dataclass(frozen=True, slots=True)
class ProductionDependencyOverrides:
    """
    仅用于测试Fixture工厂的依赖覆盖对象。
    生产环境**严禁使用本类**；单元测试可以替换任意组件，绕开真实CMO、真实LLM、真实Phase7‑8。
    """
    test_mode: bool                              # 是否开启测试模式开关
    artifact_provenance: str                     # 制品来源标记：test_fixture / formal_renderer
    package_loader: object | None = None         # 可替换输入包加载器
    proposal_agent: object | None = None         # 可替换策略生成Agent
    candidate_evaluator: object | None = None    # 可替换评估器（mock，不调用CMO）
    phase7_adapter: object | None = None         # 可替换Phase7对比学习适配器
    phase8_adapter: object | None = None         # 可替换Phase8技能演化适配器
    champion_policy: object | None = None        # 可替换冠军选择策略
    stop_policy: object | None = None            # 可替换任务停止条件
    synchronous_fake_workers: bool = True        # 测试用：使用同步假worker，不走异步并发
    knowledge_snapshot_provider: object | None = None  # 可替换知识快照


class _UnavailableAdapter:
    """
    测试占位适配器。
    如果单元测试没有注入Phase7/Phase8适配器，一旦调用run就抛出明确异常，防止静默错误。
    """
    def __init__(self, phase: str) -> None:
        self._phase = phase

    def run(self, **_: object) -> dict[str, object]:
        raise RuntimeError(f"{self._phase}_production_adapter_not_configured")


class _FixtureChampionPolicy:
    """
    仅单元测试使用的冠军选择器（mock）。
    不会把Fixture测试证据升级为正式证据；只简单过滤合法候选，按分数取最高分。
    过滤条件：执行成功、可打分、语义校验通过、存在官方分数。
    """

    def select(self, *, rolling_baseline, candidates):
        # 筛选全部合法候选
        ranked = [
            item
            for item in candidates
            if item.execution_success
            and item.scoreable
            and item.semantic_valid
            and item.official_score is not None
        ]
        # 优先分数；分数相同按candidate_id字典序；无合法候选则沿用基线
        best = max(
            ranked,
            key=lambda item: (item.official_score, item.candidate_id),
            default=rolling_baseline,
        )
        # 返回简单命名空间对象，对齐正式ChampionPolicy输出接口
        return SimpleNamespace(
            best_candidate_id=best.candidate_id,
            selected_champion_id=best.candidate_id,
            selected_score=best.official_score,
            improved=best.candidate_id != rolling_baseline.candidate_id,
            exclusion_reasons={},
        )


class ProductionEvolutionCampaignService:
    """
    对外门面类Facade。
    每一个推演进化campaign任务，都会创建一套独立、不可修改、绑定输入包的核心服务实例。
    职责：
    - 管理多个campaign实例缓存 _services
    - prepare_campaign_request：初始化任务规格、加载输入包、预校验、写入任务清单
    - _build_core：组装真正的EvolutionCampaignService内核（预览构建器 + 代际执行器）
    - 代理全部上层API：preview / repair / resume / execute / 查看状态 / 暂停/恢复/停止 / 权限留存
    """

    def __init__(
        self,
        *,
        project_root: Path,                     # 项目根目录
        package_loader: object,                 # 输入包加载器
        proposal_agent: object,                 # 策略提案Agent
        candidate_evaluator: object,            # 候选评估器（CMO仿真+全套校验）
        phase7_adapter: object,                 # Phase7对比学习适配器
        phase8_adapter: object,                 # Phase8技能演化适配器
        champion_policy: object | None,         # 冠军选择策略，None则使用默认正式策略
        stop_policy: object,                    # 任务停止判断策略
        synchronous_fake_workers: bool,         # 是否同步假worker，测试为True；生产False
        artifact_provenance: str,               # 制品来源标记 formal_renderer / test_fixture
        knowledge_snapshot_provider: object | None = None,  # Phase8知识快照
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self._campaigns_root = self.project_root / "runs" / "evolution"  # 所有campaign持久化根目录
        self._package_loader = package_loader
        self._proposal_agent = proposal_agent
        self._candidate_evaluator = candidate_evaluator
        self._phase7 = phase7_adapter
        self._phase8 = phase8_adapter
        self._champion = champion_policy
        self._stop = stop_policy
        self._synchronous = synchronous_fake_workers
        self.artifact_provenance = artifact_provenance
        self._knowledge = knowledge_snapshot_provider
        self._services: dict[str, EvolutionCampaignService] = {}  # 缓存已初始化campaign服务

    def prepare_campaign_request(
        self,
        *,
        campaign_id: str,
        input_package_id: str,
        generation_objective: str,
        budget: dict[str, object],
        minimum_improvement_delta: int,
        no_improvement_patience: int,
    ) -> dict[str, Any]:
        """
        初始化一个进化推演任务：
        1. 加载输入包（场景、基线、各种合约checksum、git信息）
        2. 执行评估器前置预检查preflight
        3. 构造完整 EvolutionCampaignSpec 任务规格对象
        4. 根据制品来源标记选择运行模式：FAKE_FIXTURE测试 / PRODUCTION_CMO真实仿真
        5. 构建内核EvolutionCampaignService实例并缓存
        6. 将输入包完整清单写入磁盘，用于审计溯源
        返回：下层service.prepare_campaign的结果
        """
        # 加载受管控输入包：场景定义、基线策略、全套哈希、git提交信息
        package = self._package_loader.load(input_package_id)
        # 执行评估器前置检查；测试fixture没有preflight属性就返回测试标记
        runtime_preflight = (
            self._candidate_evaluator.preflight()
            if hasattr(self._candidate_evaluator, "preflight")
            else {"status": "test_fixture"}
        )
        campaign_budget = CampaignBudget(**budget)
        # 组装任务完整规格契约，保存全部哈希，保证可复现、可审计
        spec = EvolutionCampaignSpec(
            campaign_id=campaign_id,
            scenario_id=package.scenario.scenario_id,
            scenario_ref=input_package_id,
            scenario_checksum=package.checksums["scenario_definition_derived"],
            initial_strategy_ref=f"{input_package_id}#derived-baseline",
            runtime_contract_checksum=package.checksums["runtime"],
            renderer_contract_checksum=package.checksums["renderer"],
            score_contract_checksum=package.checksums["score_spec_compiled"],
            semantic_contract_checksum=package.package_checksum,
            code_revision=package.git_commit,
            allowed_strategy_paths=package.allowed_strategy_paths,
            generation_objective=generation_objective,
            budget=campaign_budget,
            # 区分测试fixture模式与正式CMO仿真模式
            execution_mode=(
                CampaignExecutionMode.FAKE_FIXTURE
                if self.artifact_provenance == "test_fixture"
                else CampaignExecutionMode.PRODUCTION_CMO
            ),
            minimum_improvement_delta=minimum_improvement_delta,
            no_improvement_patience=no_improvement_patience,
        )
        # 构建内核业务服务实例
        service = self._build_core(spec, package)
        self._services[campaign_id] = service
        result = service.prepare_campaign(spec)
        # 写入输入包审计清单：全部版本、哈希、dirty标记、制品来源，事后可以复现任务
        CampaignStore(self._campaigns_root / campaign_id).write_input_package_manifest(
            {
                "package_id": package.package_id,
                "package_checksum": package.package_checksum,
                "git_commit": package.git_commit,
                "working_tree_dirty": package.working_tree_dirty,
                "diff_checksum": package.diff_checksum,
                "artifact_provenance": self.artifact_provenance,
                "scenario_asset": package.scenario_asset.to_dict(),
                "runtime_preflight": runtime_preflight,
            }
        )
        return result

    def _build_core(self, spec: EvolutionCampaignSpec, package: object) -> EvolutionCampaignService:
        """
        组装真正的核心业务对象：
        ProductionPreviewBuilder 预览构建器 + ProductionGenerationExecutor代际执行器
        返回可执行任务的EvolutionCampaignService实例
        """
        root_for = lambda campaign_id: self._campaigns_root / campaign_id
        preview = ProductionPreviewBuilder(
            package=package,
            proposal_agent=self._proposal_agent,
            novelty_validator=CandidateNoveltyValidator(),
            campaign_root_provider=root_for,
            knowledge_snapshot_provider=self._knowledge,
            proposal_provider=(
                "fake" if self.artifact_provenance == "test_fixture" else "configured_json_client"
            ),
            production_execution_eligible=self.artifact_provenance != "test_fixture",
        )
        executor = ProductionGenerationExecutor(
            package=package,
            candidate_evaluator=self._candidate_evaluator,
            phase7_adapter=self._phase7,
            phase8_adapter=self._phase8,
            # 如果外部未传入champion_policy，则实例化正式的冠军选择策略
            champion_policy=(
                self._champion
                or ChampionSelectionPolicy(
                    minimum_improvement_delta=spec.minimum_improvement_delta
                )
            ),
            stop_policy=self._stop,
            artifact_provenance=self.artifact_provenance,
        )
        return EvolutionCampaignService(
            campaigns_root=self._campaigns_root,
            preview_builder=preview,
            generation_executor=executor,
            synchronous_fake_workers=self._synchronous,
        )

    def _service(self, campaign_id: str) -> EvolutionCampaignService:
        """Return a cached core service, rehydrating persisted Campaigns on demand."""
        service = self._services.get(campaign_id)
        if service is None:
            service = self.load_campaign(campaign_id)
        return service

    def load_campaign(self, campaign_id: str) -> EvolutionCampaignService:
        """Recreate a Campaign core from its persisted specification and input package."""
        root = self._campaigns_root / campaign_id
        spec = EvolutionCampaignService.load_spec(root)
        package = self._package_loader.load(spec.scenario_ref)
        service = self._build_core(spec, package)
        self._services[campaign_id] = service
        return service

    def preview_generation(self, **kwargs: Any):
        """预览模式：不跑真实CMO，仅做策略生成、Lua渲染预览"""
        self._bind_generation_core(
            campaign_id=str(kwargs["campaign_id"]),
            generation_index=int(kwargs["generation_index"]),
        )
        return self._service(str(kwargs["campaign_id"])).preview_generation(**kwargs)

    def repair_preview_candidate(self, **kwargs: Any):
        """修复预览模式下失败的候选方案"""
        self._bind_generation_core(
            campaign_id=str(kwargs["campaign_id"]),
            generation_index=int(kwargs["generation_index"]),
        )
        return self._service(str(kwargs["campaign_id"])).repair_preview_candidate(**kwargs)

    def resume_preview_from_candidate(self, **kwargs: Any):
        """从某个已有候选恢复预览推演流程"""
        self._bind_generation_core(
            campaign_id=str(kwargs["campaign_id"]),
            generation_index=int(kwargs["generation_index"]),
        )
        return self._service(str(kwargs["campaign_id"])).resume_preview_from_candidate(**kwargs)

    def execute_generation(self,** kwargs: Any):
        """正式执行一代：生成候选 → CMO仿真 → Phase3‑6校验打分 → Phase7‑8学习"""
        self._bind_generation_core(
            campaign_id=str(kwargs["campaign_id"]),
            generation_index=int(kwargs["generation_index"]),
        )
        return self._service(str(kwargs["campaign_id"])).execute_generation(**kwargs)

    def _bind_generation_core(self, *, campaign_id: str, generation_index: int) -> None:
        """Use the persisted Champion as the next generation's baseline."""
        root = self._campaigns_root / campaign_id
        spec = EvolutionCampaignService.load_spec(root)
        package = self._package_loader.load(spec.scenario_ref)
        if generation_index > 0:
            package = apply_rolling_baseline(
                package,
                RollingBaselineResolver(root).resolve_for_generation(generation_index),
            )
        self._services[campaign_id] = self._build_core(spec, package)

    def inspect_campaign(self, campaign_id: str):
        """查询整个进化任务总体状态"""
        return self._service(campaign_id).inspect_campaign(campaign_id)

    def inspect_generation(self, campaign_id: str, generation_index: int):
        """查询指定某一代的详细结果"""
        return self._service(campaign_id).inspect_generation(campaign_id, generation_index)

    def reconcile_campaign(self, campaign_id: str) -> dict[str, Any]:
        """Reconcile the persisted generation currently owned by a restarted runner."""
        service = self._service(campaign_id)
        campaign = service.inspect_campaign(campaign_id)
        generation_index = int(campaign["current_generation"])
        return service.reconcile_generation(campaign_id, generation_index)

    def pause_campaign(self, campaign_id: str):
        """暂停进化任务"""
        return self._service(campaign_id).pause_campaign(campaign_id)

    def resume_campaign(self, campaign_id: str):
        """恢复已暂停任务"""
        return self._service(campaign_id).resume_campaign(campaign_id)

    def stop_campaign(self, campaign_id: str):
        """终止任务，不再继续生成下一代"""
        return self._service(campaign_id).stop_campaign(campaign_id)

    def persist_permission_grant(self, receipt: object, context: dict[str, Any]) -> str:
        """持久化权限审批记录，用于审计：人工审批/自动审批留痕"""
        campaign_id = str(context["arguments"]["campaign_id"])
        return self._service(campaign_id).persist_permission_grant(receipt, context)


def create_production_evolution_campaign_service(
    *,
    project_root: Path,
    app_config: Any,
    llm_client: Any,
) -> ProductionEvolutionCampaignService:
    """
    创建**唯一正式生产环境**服务实例。
    故意不接受任何依赖覆盖，所有组件硬编码为正式实现，防止测试组件泄漏进生产。
    Phase 9C‑1改动：不再要求git工作树必须干净；允许带修改的可追踪工作树直接预览。
    """

    json_client = ClaudeJsonClient(llm_client)
    curated_skill_registry = ToolRegistry()
    curated_skills = CuratedSkillRegistry(project_root / "data" / "skills")
    curated_skill_registry.register(ListCuratedSkillsTool(registry=curated_skills))
    curated_skill_registry.register(ViewCuratedSkillTool(registry=curated_skills))
    intent_client = AgentLoopJsonClient(
        client=llm_client,
        tool_registry=curated_skill_registry,
        max_turns=6,
    )
    phase7 = ProductionPhase7Adapter(
        project_root=project_root,
        json_client=json_client,
    )
    phase8 = ProductionPhase8Adapter(
        project_root=project_root,
        json_client=json_client,
        experience_store=phase7.experience_store,
    )
    return ProductionEvolutionCampaignService(
        project_root=project_root,
        package_loader=ControlledCampaignInputPackageLoader(
            project_root=project_root,
            # Phase 9C‑1：冻结当前版本与工作树指纹写入输入包，不再拒绝带修改的预览
        ),
        proposal_agent=StrategyProposalAgent(json_client, intent_client=intent_client),
        candidate_evaluator=FormalCandidateEvaluator(
            json_client=json_client,
            cmo_runner_path=Path(r"C:\CMO\CmoBatchRunner\CmoBatchRunner.exe"),
            cmo_executable_path=Path(r"C:\CMO\Command\bin\Debug\Command.exe"),
        ),
        phase7_adapter=phase7,
        phase8_adapter=phase8,
        champion_policy=None,
        stop_policy=StopPolicy(),
        synchronous_fake_workers=False,   # 生产环境关闭同步假worker，走真实并发
        artifact_provenance="formal_renderer",
        knowledge_snapshot_provider=ProductionKnowledgeSnapshotProvider(
            project_root=project_root,
            experience_store=phase7.experience_store,
        ),
    )


def create_test_evolution_campaign_service(
    *,
    project_root: Path,
    overrides: ProductionDependencyOverrides,
) -> ProductionEvolutionCampaignService:
    """
    创建单元测试专用服务实例。
    强制校验：必须打开test_mode，制品来源必须是test_fixture，必须注入关键mock依赖。
    缺失的适配器自动填充 _UnavailableAdapter；缺失冠军策略自动填充Fixture测试版。
    """
    if not overrides.test_mode or overrides.artifact_provenance != "test_fixture":
        raise ValueError("test_dependency_overrides_required")
    if overrides.package_loader is None or overrides.proposal_agent is None:
        raise ValueError("test_dependency_overrides_incomplete")
    return ProductionEvolutionCampaignService(
        project_root=project_root,
        package_loader=overrides.package_loader,
        proposal_agent=overrides.proposal_agent,
        candidate_evaluator=overrides.candidate_evaluator or (lambda **_: {}),
        phase7_adapter=overrides.phase7_adapter or _UnavailableAdapter("phase7"),
        phase8_adapter=overrides.phase8_adapter or _UnavailableAdapter("phase8"),
        champion_policy=overrides.champion_policy or _FixtureChampionPolicy(),
        stop_policy=overrides.stop_policy or StopPolicy(),
        synchronous_fake_workers=overrides.synchronous_fake_workers,
        artifact_provenance="test_fixture",
        knowledge_snapshot_provider=overrides.knowledge_snapshot_provider,
    )
