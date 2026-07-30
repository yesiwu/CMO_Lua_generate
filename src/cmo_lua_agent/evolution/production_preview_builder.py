"""
Phase 9C 正式预览组装模块；整个进化流水线中**唯一调用LLM做策略提案**的阶段。
职责：
1) 调用StrategyProposalAgent生成一代4份策略候选(candidate_00~03)；不调用CMO仿真，仅做预览校验。
2) 全套前置校验：候选集合合法性校验、新颖度校验、候选质量门禁Quality‑Gate。
3) 磁盘持久化：基线策略、知识快照、审计追踪trace、质量报告、冻结候选集frozen‑candidate‑set、变更diff。
4) 支持两种修复模式：
   - repair_candidate：针对「新颖度缺失」错误，单独重生成某一个候选，其余保留不变，生成新版本revision。
   - resume_from_candidate：针对LLM输出JSON解析失败，从失败点继续生成后面候选，不重新规划意图intent。
5) 幂等：如果对应revision目录下文件已全部存在，直接读取磁盘返回，不再重新调用LLM。
6) 失败审计：所有校验/LLM异常统一输出proposal‑failure.json，标记失败阶段、恢复动作、操作员等待状态。

输出产物：GenerationPreviewPayload，交给上层ProductionGenerationExecutor，决定是否送入真实CMO仿真。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# 预览载荷模型，预览完成后返回给执行器
from cmo_lua_agent.evolution.control_plane import GenerationPreviewPayload
# 演化模型：冻结候选集、全局哈希工具
from cmo_lua_agent.evolution.production_models import (
    FrozenCandidateSet,
    canonical_checksum,
)
# 新颖度校验异常：候选不能和历史/基线过度重复
from cmo_lua_agent.evolution.novelty import CandidateNoveltyError
# 候选质量评估：C4质量门禁，检查策略改动是否符合战术意图、维度覆盖率
from cmo_lua_agent.optimization.candidate_quality import (
    CandidateBatchQualityError,
    CandidateQualityEvaluator,
)
# Phase6候选集合校验器：数量、白名单路径、多样性校验
from cmo_lua_agent.optimization.candidate_set_validator import CandidateSetValidator
# 意图一致性异常：生成策略与预设战术意图不匹配（缺少要求的语义维度）
from cmo_lua_agent.optimization.candidate_intent_conformance import (
    CandidateIntentConformanceError,
)
# Phase6模型：策略提案上下文对象，传给LLM的全部输入上下文
from cmo_lua_agent.optimization.phase6_models import StrategyProposalContext
# 提案契约模型：候选摘要、意图、补丁、操作、角色规格
from cmo_lua_agent.optimization.proposal_models import (
    AcceptedCandidateSummary,
    CandidateIntent,
    CandidatePatch,
    ProposalContractError,
    StrategyPatchOperation,
    candidate_role_specs,
)
# 战术上下文构建器：组装给Agent的约束、角色、可修改叶子节点目录
from cmo_lua_agent.optimization.proposal_context_builder import (
    ProposalTacticalContextBuilder,
)
# 策略补丁组装：把LLM输出的改动path‑value补丁，合并到基线策略得到完整StrategySpec
from cmo_lua_agent.optimization.strategy_patch import (
    StrategyPatchAssembler,
    build_patchable_leaf_catalog,
)
# 语义维度工具：提取一份策略改动覆盖了哪些战术语义维度
from cmo_lua_agent.optimization.strategy_dimensions import semantic_dimensions


class ProductionPreviewBuilder:
    """
    Phase9C预览构建器，唯一执行LLM策略提案的组件。
    工作目录结构 runs/evolution/{campaign_id}/previews/generation_XXX/revision_XXX/
    核心文件：
        frozen‑candidate‑set.json    冻结后的4份候选集合（审计哈希）
        knowledge‑snapshot.json      Phase7/8知识快照：经验卡片、生效Skill
        strategy‑diff.json           每个候选相对基线的改动路径
        proposal‑trace.json          LLM全链路审计追踪：意图、补丁尝试、调用记录
        candidate‑quality‑report.json C4质量门禁报告
        proposal‑failure.json        失败时生成，记录错误码、阶段、恢复方式
    """
    def __init__(
        self,
        *,
        package,                              # 输入包：场景、基线策略、合约哈希、bootstrap
        proposal_agent,                        # StrategyProposalAgent，真正调用LLM生成候选
        novelty_validator,                     # 新颖度校验器，防止重复策略
        campaign_root_provider,                # lambda(campaign_id) -> Path，生成任务磁盘根路径
        generation_context_builder=None,       # 代际上下文构建器；None使用默认上下文
        knowledge_snapshot_provider=None,      # Phase8知识快照提供器，输出active_skills、experience_cards
        proposal_provider: str = "configured_json_client", # 标记提案来源，写入审计
        production_execution_eligible: bool = True, # 是否允许本预览结果送入正式CMO执行
    ) -> None:
        self._package = package
        self._proposal_agent = proposal_agent
        self._novelty = novelty_validator
        self._root_for = campaign_root_provider
        self._context_builder = generation_context_builder
        self._knowledge = knowledge_snapshot_provider
        self._proposal_provider = proposal_provider
        self._production_execution_eligible = production_execution_eligible
        self.proposal_calls = 0   # 统计本次预览一共发起多少次LLM调用

    def build(self, *, spec, generation_index: int, preview_revision: int) -> GenerationPreviewPayload:
        """
        构建一代预览；幂等接口。
        :param spec: 进化任务完整规格EvolutionCampaignSpec
        :param generation_index: 代序号（000,001…）
        :param preview_revision: 预览修订版本号；修复错误时revision递增
        :return GenerationPreviewPayload：预览结果，给代际执行器
        逻辑：
        1）检查磁盘：三份关键文件全部存在，直接加载返回，不再跑生成
        2）创建revision预览目录，写出基线策略
        3）生成/冻结知识快照（有Phase8就输出Skill与经验卡片；无则空快照）
        4）组装StrategyProposalContext，传给proposal_agent.propose()生成4候选
        5）依次执行三层校验：CandidateSetValidator → NoveltyValidator → QualityGate(C4)
        6）全部校验通过，写出frozen‑candidate‑set、diff、快照；返回payload
        7）任何异常：写出proposal‑failure.json审计，向上抛出异常
        """
        root = Path(self._root_for(spec.campaign_id)).resolve()
        preview_root = (
            root
            / "previews"
            / f"generation_{generation_index:03d}"
            / f"revision_{preview_revision:03d}"
        )
        # 幂等判断：文件全部存在直接读取磁盘结果，不再调用LLM
        frozen_path = preview_root / "frozen-candidate-set.json"
        diff_path = preview_root / "strategy-diff.json"
        snapshot_path = preview_root / "knowledge-snapshot.json"
        if frozen_path.is_file() and diff_path.is_file() and snapshot_path.is_file():
            frozen = FrozenCandidateSet.from_dict(
                json.loads(frozen_path.read_text(encoding="utf-8"))
            )
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            diffs = json.loads(diff_path.read_text(encoding="utf-8"))
            return self._payload(frozen, snapshot, diffs, frozen_path, diff_path, 0)

        # 目录不允许已存在，防止覆盖旧revision
        preview_root.mkdir(parents=True, exist_ok=False)

        # 输出基线策略文件
        self._atomic_json(
            preview_root / "derived-baseline-strategy.json",
            self._package.baseline.strategy.to_dict(),
        )
        # 如果输入包携带基线衍生清单，持久化，用于溯源IR转换
        derivation_manifest = getattr(self._package, "baseline_derivation_manifest", None)
        if derivation_manifest is not None:
            self._atomic_json(
                preview_root / "baseline-derivation-manifest.json",
                dict(derivation_manifest),
            )

        # 组装代际运行上下文；外部builder不为空就使用外部，否则使用默认上下文
        context_value = (
            dict(self._context_builder(generation_index))
            if self._context_builder is not None
            else self._default_generation_context(generation_index)
        )

        # 构造知识快照：有Phase8快照提供器则调用freeze；否则构造空快照
        if self._knowledge is None:
            snapshot_body = {
                "campaign_id": spec.campaign_id,
                "generation_index": generation_index,
                "bootstrap_checksum": self._package.bootstrap.checksum,
                "active_skills": [],
                "experience_cards": [],
                "contract": self._package.checksums,
                "parent_strategy_checksum": canonical_checksum(
                    self._package.baseline.strategy.to_dict()
                ),
            }
            snapshot = {
                **snapshot_body,
                "checksum": canonical_checksum(snapshot_body),
            }
        else:
            snapshot = self._knowledge.freeze(
                path=snapshot_path,
                spec=spec,
                package=self._package,
                generation_index=generation_index,
            )

        # 组装完整提案上下文，喂给LLM Agent
        context = StrategyProposalContext(
            scenario=self._package.scenario,
            baseline=self._package.baseline.strategy,
            user_objective=spec.generation_objective,
            allowed_strategy_paths=self._package.allowed_strategy_paths,
            diversity_dimensions=self._package.diversity_dimensions,
            runtime_id=self._package.runtime.runtime_id,
            runtime_version=self._package.runtime.runtime_version,
            bootstrap=self._package.bootstrap,
            retrieved_experience_cards=tuple(
                dict(item) for item in snapshot.get("experience_cards", ())
            ),
            active_curated_skill=(
                dict(snapshot["active_skills"][0])
                if snapshot.get("active_skills")
                else None
            ),
            generation_context=context_value,
        )

        try:
            # LLM调用入口：生成4份候选策略
            candidates = self._proposal_agent.propose(context)
        except Exception as error:
            # LLM生成失败：写出上下文、审计追踪、失败报告，再抛异常
            self._write_proposal_context(preview_root)
            trace = getattr(self._proposal_agent, "last_audit", {})
            if trace:
                self._atomic_json(preview_root / "proposal-trace.json", trace)
                self._write_proposal_records(preview_root, trace)
            self._atomic_json(
                preview_root / "proposal-failure.json",
                self.failure_audit(error=error, proposal_agent=self._proposal_agent),
            )
            raise
        finally:
            # 无论成功失败，记录LLM调用总次数
            usage = getattr(self._proposal_agent, "last_usage", None)
            self.proposal_calls = int(getattr(usage, "total_calls", 0))

        # 生成成功：持久化审计trace
        trace = getattr(self._proposal_agent, "last_audit", {})
        self._write_proposal_context(preview_root)
        if trace:
            self._atomic_json(preview_root / "proposal-trace.json", trace)
            self._write_proposal_records(preview_root, trace)

        try:
            # 校验1：候选集合校验（数量4个、路径白名单、多样性）
            candidate_set = CandidateSetValidator().validate(
                scenario=self._package.scenario,
                baseline=self._package.baseline.strategy,
                candidates=candidates,
                allowed_paths=self._package.allowed_strategy_paths,
                diversity_dimensions=self._package.diversity_dimensions,
            )
            if not candidate_set.diversity_report.valid:
                raise ValueError("candidate_set_invalid")

            # 校验2：新颖度校验，不能与基线/历史高度重合
            self._novelty.validate(
                baseline=self._package.baseline.strategy,
                candidates=candidates,
                generation_context=context_value,
            )

            # 校验3：C4质量门禁，检查意图‑策略一致性、维度覆盖率
            quality_report = self._quality_gate(
                preview_root=preview_root,
                baseline=self._package.baseline.strategy,
                candidates=candidates,
                context_value=context_value,
                trace=trace,
            )
        except Exception as error:
            # 任意校验失败，写出失败审计文件再抛出
            self._atomic_json(
                preview_root / "proposal-failure.json",
                self.failure_audit(error=error, proposal_agent=self._proposal_agent),
            )
            raise

        # 全部校验通过：构造冻结不可修改候选集，写入磁盘
        frozen = FrozenCandidateSet.create(
            campaign_id=spec.campaign_id,
            generation_index=generation_index,
            preview_revision=preview_revision,
            baseline=self._package.baseline.strategy.to_dict(),
            candidates=tuple(candidate.to_dict() for candidate in candidates),
            source_proposal_operation_id=f"g{generation_index:03d}:strategy_proposal:r{preview_revision:03d}",
            **self._frozen_identity(
                snapshot=snapshot,
                trace=trace,
                quality_report=quality_report,
            ),
        )
        # 收集每个候选相对基线改动的配置路径
        diffs = [
            {
                "candidate_id": candidate.candidate_id,
                "changed_paths": list(
                    candidate_set.diversity_report.candidate_diffs[candidate.candidate_id]
                ),
            }
            for candidate in candidates
        ]
        if not snapshot_path.is_file():
            self._atomic_json(snapshot_path, snapshot)
        self._atomic_json(frozen_path, frozen.to_dict())
        self._atomic_json(diff_path, diffs)
        return self._payload(frozen, snapshot, diffs, frozen_path, diff_path, self.proposal_calls)

    def _default_generation_context(self, generation_index: int) -> dict[str, object]:
        """
        默认代际上下文，当没有外部context_builder时使用。
        定义4个候选固定角色：exploit / robust_repair / coordinated_explore / conservative_control
        携带上一代失败特征、允许改动路径、单次最多改动叶子节点约束。
        """
        profile = getattr(self._package, "baseline_failure_profile", None)
        return {
            "generation_index": generation_index,
            "candidate_roles": {
                "candidate_00": "exploit",
                "candidate_01": "robust_repair",
                "candidate_02": "coordinated_explore",
                "candidate_03": "conservative_control",
            },
            "allowed_strategy_paths": list(self._package.allowed_strategy_paths),
            "history_fingerprints": [],
            "previous_generation_failures": (
                list(profile.failure_indicators) if profile is not None else []
            ),
            # 当前版本还没有完整冻结的操作/维度契约，不编造C2失败配置
            "failure_profile_available": False,
            "conservative_max_changed_leaves": 1,
        }

    @staticmethod
    def _payload(frozen, snapshot, diffs, frozen_path, diff_path, calls):
        """组装返回给上层的预览载荷对象"""
        return GenerationPreviewPayload(
            knowledge_snapshot_checksum=snapshot["checksum"],
            candidate_set_checksum=frozen.candidate_set_checksum,
            strategy_diffs=tuple(diffs),
            proposal_llm_calls=calls,
            baseline_checksum=frozen.baseline_checksum,
            frozen_candidate_set_ref=str(frozen_path),
            strategy_diff_ref=str(diff_path),
            candidate_quality_index_ref=str(frozen_path.parent / "candidate-quality-index.json"),
        )

    @staticmethod
    def failure_audit(*, error: Exception, proposal_agent) -> dict[str, object]:
        """
        统一失败审计转换器：把各种异常实例转为可持久化JSON结构proposal‑failure.json。
        识别错误类型，标记failure_stage、preview_status、campaign_status、recovery_action。
        恢复动作两种：
            awaiting_operator_action：等待人工干预
            resume_preview_from_candidate：可以调用resume_from_candidate接口继续生成
            terminal_failed：不可修复，任务终止
        """
        error_code = getattr(error, "code", None) or str(error) or type(error).__name__
        if isinstance(error, CandidateBatchQualityError):
            stage = "candidate_quality_validation"
        elif error_code.startswith("novelty_"):
            stage = "novelty_validation"
        elif error_code == "candidate_set_invalid":
            stage = "candidate_set_validation"
        else:
            stage = getattr(error, "stage", "intent_or_patch")
        is_json_failure = error_code == "proposal_json_invalid"
        return {
            "candidate_id": getattr(error, "candidate_id", None),
            "failed_candidate_id": getattr(error, "candidate_id", None),
            "failed_candidate_ids": list(getattr(error, "failed_candidate_ids", ())),
            "error_code": error_code,
            "failure_code": "proposal_json_invalid" if is_json_failure else error_code,
            "failure_stage": stage,
            "failed_stage": stage if is_json_failure else None,
            "message": str(error),
            "proposal_llm_calls": int(
                getattr(getattr(proposal_agent, "last_usage", None), "total_calls", 0)
            ),
            "validator_violations": list(getattr(error, "violations", ())),
            "changed_paths": list(getattr(error, "changed_paths", ())),
            "required_dimensions": list(getattr(error, "required_dimensions", ())),
            "actual_dimensions": list(getattr(error, "actual_dimensions", ())),
            "related_changed_paths": list(getattr(error, "related_changed_paths", ())),
            "failed_rules": list(getattr(error, "failed_rules", ())),
            "covered_operation_ids": list(getattr(error, "covered_operation_ids", ())),
            "covered_dimensions": list(getattr(error, "covered_dimensions", ())),
            "covered_platform_types": list(getattr(error, "covered_platform_types", ())),
            "candidate_quality_report_checksum": getattr(
                getattr(error, "report", None), "report_checksum", None
            ),
            "json_diagnostics": dict(getattr(error, "diagnostics", {})),
            "preview_status": (
                "novelty_repair_required"
                if error_code == "novelty_explore_dimension_missing"
                else "awaiting_operator_action"
                if error_code == "candidate_batch_quality_failed"
                else "awaiting_operator_action"
                if is_json_failure
                else "terminal_failed"
            ),
            "campaign_status": "awaiting_operator_action" if is_json_failure else None,
            "recovery_action": "resume_preview_from_candidate" if is_json_failure else None,
        }

    def repair_candidate(
        self,
        *,
        spec,
        generation_index: int,
        source_revision: int,
        preview_revision: int,
        candidate_id: str,
    ) -> GenerationPreviewPayload:
        """
        修复单个候选，生成子修订版本；**仅用于novelty_explore_dimension_missing新颖度缺失错误**。
        逻辑：读取上一版revision的trace快照，保留另外3个候选不变，只让Agent重新repair_candidate生成出错那一个。
        :param source_revision: 出错的原始修订号
        :param preview_revision: 新建的修订号
        :param candidate_id: 需要重生成的候选ID
        返回新预览载荷，写入新revision目录。
        """
        root = Path(self._root_for(spec.campaign_id)).resolve()
        source_root = root / "previews" / f"generation_{generation_index:03d}" / f"revision_{source_revision:03d}"
        trace_path = source_root / "proposal-trace.json"
        failure_path = source_root / "proposal-failure.json"
        if not trace_path.is_file() or not failure_path.is_file():
            raise ValueError("awaiting_operator_action")
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        failure = json.loads(failure_path.read_text(encoding="utf-8"))
        failed_ids = tuple(failure.get("failed_candidate_ids", ()))
        # 本接口只允许处理【新颖度维度缺失】这一类错误
        if failure.get("error_code") != "novelty_explore_dimension_missing" or failed_ids != (candidate_id,):
            raise ValueError("awaiting_operator_action")

        target_intent = _intent_from_trace(trace, candidate_id)
        context_value = self._default_generation_context(generation_index)
        snapshot = json.loads((source_root / "knowledge-snapshot.json").read_text(encoding="utf-8"))
        context = self._proposal_context(spec=spec, snapshot=snapshot, generation_context=context_value)

        # 从trace恢复已有候选，把待修复项排除在accepted之外
        existing = _candidates_from_trace(trace, context)
        accepted = tuple(
            AcceptedCandidateSummary(item.candidate_id, item.strategy_checksum, item.intended_difference, ())
            for item in existing if item.candidate_id != candidate_id
        )
        current = next(item for item in existing if item.candidate_id == candidate_id)
        actual_dimensions = semantic_dimensions(current.intended_difference)
        # 把上一轮的错误传给Agent，作为修复提示
        prior = CandidateIntentConformanceError(
            code="candidate_intent_dimension_missing",
            required_dimensions=tuple(target_intent.strategy_dimensions),
            actual_dimensions=actual_dimensions,
            changed_paths=current.intended_difference,
        )

        preview_root = root / "previews" / f"generation_{generation_index:03d}" / f"revision_{preview_revision:03d}"
        preview_root.mkdir(parents=True, exist_ok=False)
        try:
            # 调用Agent的repair_candidate接口，仅重生成这一个候选
            replacement = self._proposal_agent.repair_candidate(
                context, intent=target_intent, accepted=accepted, prior_error=prior
            )
        except Exception as error:
            self.proposal_calls = int(getattr(self._proposal_agent.last_usage, "total_calls", 0))
            failed_trace = dict(trace)
            failed_trace["parent_revision"] = source_revision
            failed_trace["targeted_repair"] = getattr(self._proposal_agent, "last_audit", {})
            self._atomic_json(preview_root / "proposal-trace.json", failed_trace)
            self._atomic_json(preview_root / "knowledge-snapshot.json", snapshot)
            self._atomic_json(
                preview_root / "proposal-failure.json",
                self.failure_audit(error=error, proposal_agent=self._proposal_agent),
            )
            raise

        self.proposal_calls = int(getattr(self._proposal_agent.last_usage, "total_calls", 0))
        # 替换目标候选，其余保持不变
        candidates = tuple(replacement if item.candidate_id == candidate_id else item for item in existing)

        # 重新跑全套校验流程
        candidate_set = CandidateSetValidator().validate(
            scenario=self._package.scenario, baseline=self._package.baseline.strategy,
            candidates=candidates, allowed_paths=self._package.allowed_strategy_paths,
            diversity_dimensions=self._package.diversity_dimensions,
        )
        if not candidate_set.diversity_report.valid:
            raise ValueError("candidate_set_invalid")
        self._novelty.validate(baseline=self._package.baseline.strategy, candidates=candidates, generation_context=context_value)
        merged_trace = dict(trace)
        quality_report = self._quality_gate(
            preview_root=preview_root,
            baseline=self._package.baseline.strategy,
            candidates=candidates,
            context_value=context_value,
            trace=merged_trace,
        )
        merged_trace["parent_revision"] = source_revision
        merged_trace["targeted_repair"] = self._proposal_agent.last_audit
        self._atomic_json(preview_root / "proposal-trace.json", merged_trace)
        self._atomic_json(preview_root / "knowledge-snapshot.json", snapshot)

        frozen = FrozenCandidateSet.create(
            campaign_id=spec.campaign_id, generation_index=generation_index,
            preview_revision=preview_revision, baseline=self._package.baseline.strategy.to_dict(),
            candidates=tuple(item.to_dict() for item in candidates),
            source_proposal_operation_id=f"g{generation_index:03d}:strategy_candidate_repair:r{preview_revision:03d}",
            **self._frozen_identity(
                snapshot=snapshot,
                trace=merged_trace,
                quality_report=quality_report,
            ),
        )
        diffs = [{"candidate_id": item.candidate_id, "changed_paths": list(item.intended_difference)} for item in candidates]
        self._atomic_json(preview_root / "frozen-candidate-set.json", frozen.to_dict())
        self._atomic_json(preview_root / "strategy-diff.json", diffs)
        return self._payload(frozen, snapshot, diffs, preview_root / "frozen-candidate-set.json", preview_root / "strategy-diff.json", self.proposal_calls)

    def resume_from_candidate(
        self,
        *,
        spec,
        generation_index: int,
        source_revision: int,
        preview_revision: int,
        candidate_id: str,
    ) -> GenerationPreviewPayload:
        """
        从JSON解析失败点继续生成，不重新生成全部意图intent。
        适用场景：LLM输出JSON格式错误，前面若干候选已经生成成功，某一个patch解析失败。
        逻辑：恢复已经成功的前面N个候选，复用原始intent，从失败的candidate_id往后逐个generate_candidate。
        不会重新调用propose()完整生成全部4个。
        """
        root = Path(self._root_for(spec.campaign_id)).resolve()
        source_root = root / "previews" / f"generation_{generation_index:03d}" / f"revision_{source_revision:03d}"
        trace_path = source_root / "proposal-trace.json"
        failure_path = source_root / "proposal-failure.json"
        if not trace_path.is_file() or not failure_path.is_file():
            raise ValueError("awaiting_operator_action")
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        failure = json.loads(failure_path.read_text(encoding="utf-8"))
        # 定位JSON失败发生在哪一个候选、哪一个阶段
        failure_candidate, failure_stage = _json_failure_location(trace, failure)
        if (
            failure_candidate != candidate_id
            or failure_stage not in {"patch_generation", "patch_repair"}
        ):
            raise ValueError("awaiting_operator_action")

        snapshot_path = source_root / "knowledge-snapshot.json"
        if not snapshot_path.is_file():
            raise ValueError("awaiting_operator_action")
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        context_value = self._default_generation_context(generation_index)
        context = self._proposal_context(spec=spec, snapshot=snapshot, generation_context=context_value)

        intents = tuple(_intent_from_trace(trace, item) for item in _candidate_ids_from_trace(trace))
        target_index = _candidate_ids_from_trace(trace).index(candidate_id)
        # 恢复已经成功生成的前缀候选（失败点之前的）
        existing = _accepted_prefix_from_trace(trace, context, stop_before=candidate_id)
        accepted = [
            AcceptedCandidateSummary(item.candidate_id, item.strategy_checksum, item.intended_difference, semantic_dimensions(item.intended_difference))
            for item in existing
        ]

        preview_root = root / "previews" / f"generation_{generation_index:03d}" / f"revision_{preview_revision:03d}"
        preview_root.mkdir(parents=True, exist_ok=False)
        calls = 0
        merged_trace = dict(trace)
        merged_trace["parent_revision"] = source_revision
        resumed_attempts: list[object] = []
        candidates = list(existing)
        try:
            # 从失败下标开始，逐个生成剩余候选，复用原始intent
            for intent in intents[target_index:]:
                candidate = self._proposal_agent.generate_candidate(
                    context, intent=intent, accepted=tuple(accepted)
                )
                calls += int(getattr(self._proposal_agent.last_usage, "total_calls", 0))
                candidates.append(candidate)
                dimensions = semantic_dimensions(candidate.intended_difference)
                accepted.append(AcceptedCandidateSummary(candidate.candidate_id, candidate.strategy_checksum, candidate.intended_difference, dimensions))
                resumed_attempts.append(getattr(self._proposal_agent, "last_audit", {}))
        except Exception as error:
            calls += int(getattr(self._proposal_agent.last_usage, "total_calls", 0))
            self.proposal_calls = calls
            merged_trace["parent_revision"] = source_revision
            merged_trace["resumed_candidate_attempts"] = resumed_attempts
            self._atomic_json(preview_root / "proposal-trace.json", merged_trace)
            self._atomic_json(preview_root / "knowledge-snapshot.json", snapshot)
            self._atomic_json(preview_root / "proposal-failure.json", self.failure_audit(error=error, proposal_agent=self._proposal_agent))
            raise

        self.proposal_calls = calls
        merged_trace["parent_revision"] = source_revision
        merged_trace["resumed_candidate_attempts"] = resumed_attempts
        self._atomic_json(preview_root / "proposal-trace.json", merged_trace)
        self._atomic_json(preview_root / "knowledge-snapshot.json", snapshot)
        candidate_tuple = tuple(candidates)

        # 重新全套校验
        candidate_set = CandidateSetValidator().validate(
            scenario=self._package.scenario, baseline=self._package.baseline.strategy,
            candidates=candidate_tuple, allowed_paths=self._package.allowed_strategy_paths,
            diversity_dimensions=self._package.diversity_dimensions,
        )
        if not candidate_set.diversity_report.valid:
            raise ValueError("candidate_set_invalid")
        try:
            self._novelty.validate(
                baseline=self._package.baseline.strategy,
                candidates=candidate_tuple,
                generation_context=context_value,
            )
            quality_report = self._quality_gate(
                preview_root=preview_root,
                baseline=self._package.baseline.strategy,
                candidates=candidate_tuple,
                context_value=context_value,
                trace=merged_trace,
            )
        except Exception as error:
            self._atomic_json(preview_root / "proposal-failure.json", self.failure_audit(error=error, proposal_agent=self._proposal_agent))
            raise

        frozen = FrozenCandidateSet.create(
            campaign_id=spec.campaign_id, generation_index=generation_index,
            preview_revision=preview_revision, baseline=self._package.baseline.strategy.to_dict(),
            candidates=tuple(item.to_dict() for item in candidate_tuple),
            source_proposal_operation_id=f"g{generation_index:03d}:strategy_proposal_resume:r{preview_revision:03d}",
            **self._frozen_identity(
                snapshot=snapshot,
                trace=merged_trace,
                quality_report=quality_report,
            ),
        )
        diffs = [{"candidate_id": item.candidate_id, "changed_paths": list(item.intended_difference)} for item in candidate_tuple]
        self._atomic_json(preview_root / "frozen-candidate-set.json", frozen.to_dict())
        self._atomic_json(preview_root / "strategy-diff.json", diffs)
        return self._payload(frozen, snapshot, diffs, preview_root / "frozen-candidate-set.json", preview_root / "strategy-diff.json", calls)

    def _proposal_context(self, *, spec, snapshot, generation_context):
        """复用已有快照，重建StrategyProposalContext对象，用于修复/恢复流程"""
        return StrategyProposalContext(
            scenario=self._package.scenario, baseline=self._package.baseline.strategy,
            user_objective=spec.generation_objective, allowed_strategy_paths=self._package.allowed_strategy_paths,
            diversity_dimensions=self._package.diversity_dimensions,
            runtime_id=self._package.runtime.runtime_id, runtime_version=self._package.runtime.runtime_version,
            bootstrap=self._package.bootstrap,
            retrieved_experience_cards=tuple(dict(item) for item in snapshot.get("experience_cards", ())),
            active_curated_skill=(dict(snapshot["active_skills"][0]) if snapshot.get("active_skills") else None),
            generation_context=generation_context,
        )

    @staticmethod
    def _atomic_json(path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        """
        原子写JSON：先写.tmp临时文件，再os.replace原子重命名。
        防止进程崩溃产生半截损坏的JSON文件。
        """
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)

    def _write_proposal_context(self, preview_root: Path) -> None:
        """持久化传给Agent的战术上下文proposal‑context.json，带上下文哈希用于审计"""
        tactical = getattr(self._proposal_agent, "last_tactical_context", None)
        if tactical is not None:
            payload = dict(tactical)
            audit = getattr(self._proposal_agent, "last_audit", {})
            checksum = audit.get("proposal_context_checksum") if isinstance(audit, dict) else None
            if isinstance(checksum, str):
                payload["context_checksum"] = checksum
            self._atomic_json(preview_root / "proposal-context.json", payload)

    def _quality_gate(
        self,
        *,
        preview_root: Path,
        baseline,
        candidates,
        context_value: dict[str, object],
        trace: dict[str, object],
    ):
        """
        C4候选质量门禁。
        校验：意图与实际策略改动一致性、语义维度覆盖率、操作覆盖率。
        输出candidate‑quality‑report.json；报告不通过直接抛异常阻断流程。
        把报告哈希、统计指标回填进proposal‑trace审计文件。
        """
        tactical = getattr(self._proposal_agent, "last_tactical_context", None)
        if not isinstance(tactical, dict):
            catalog = build_patchable_leaf_catalog(
                baseline=baseline,
                scenario=self._package.scenario,
                allowed_paths=self._package.allowed_strategy_paths,
            )
            tactical = ProposalTacticalContextBuilder().build(
                scenario=self._package.scenario,
                baseline=baseline,
                patch_catalog=catalog,
                role_specs=candidate_role_specs(context_value),
                accepted_candidates=(),
            ).to_dict()
        try:
            intents = tuple(
                _intent_from_trace(trace, candidate.candidate_id)
                for candidate in candidates
            )
        except (KeyError, TypeError, ValueError):
            # Fixture测试Agent可能不保存正式intent审计，直接使用角色规格
            intents = candidate_role_specs(context_value)

        report = CandidateQualityEvaluator().evaluate(
            baseline=baseline,
            candidates=tuple(candidates),
            intents=intents,
            proposal_context=tactical,
            repair_summaries=_repair_summaries(trace),
        )
        self._atomic_json(preview_root / "candidate-quality-report.json", report.to_dict())
        index_rows = []
        for item in report.candidate_reports:
            candidate_root = preview_root / "candidates" / item.candidate_id
            self._atomic_json(candidate_root / "candidate-quality-report.json", item.to_dict())
            self._atomic_json(candidate_root / "strategy-diff.json", {
                "candidate_id": item.candidate_id,
                "strategy_checksum": item.strategy_checksum,
                "changed_paths": list(item.changed_paths),
            })
            index_rows.append({
                "candidate_id": item.candidate_id,
                "strategy_diff_ref": f"candidates/{item.candidate_id}/strategy-diff.json",
                "candidate_quality_report_ref": f"candidates/{item.candidate_id}/candidate-quality-report.json",
                "candidate_quality_report_checksum": item.report_checksum,
            })
        quality_index_body = {
            "schema_version": "1.0",
            "candidates": index_rows,
            "batch_warnings": list(report.warnings),
        }
        quality_index = {**quality_index_body, "index_checksum": canonical_checksum(quality_index_body)}
        self._atomic_json(preview_root / "candidate-quality-index.json", quality_index)
        updated_trace = dict(trace)
        updated_trace.update(
            {
                "candidate_quality_status": report.status,
                "candidate_quality_report_checksum": report.report_checksum,
                "candidate_quality_index_checksum": quality_index["index_checksum"],
                "batch_operation_count": len(report.batch_coverage["operation_ids"]),
                "batch_dimension_count": len(report.batch_coverage["semantic_dimensions"]),
                "batch_platform_type_count": len(report.batch_coverage["platform_types"]),
            }
        )
        trace.clear()
        trace.update(updated_trace)
        self._atomic_json(preview_root / "proposal-trace.json", trace)
        # 质量报告不通过抛出异常阻断预览流程
        report.require_passed()
        return report

    def _frozen_identity(self, *, snapshot, trace, quality_report) -> dict[str, object]:
        """组装FrozenCandidateSet需要的审计身份字段：各类哈希、来源标记、是否允许生产执行"""
        manifest = getattr(self._package, "baseline_derivation_manifest", None)
        if not isinstance(manifest, dict):
            manifest = {}
        return {
            "scenario_ir_checksum": manifest.get(
                "scenario_ir_checksum", getattr(self._package, "scenario_ir_checksum", None)
            ),
            "derived_baseline_checksum": manifest.get("baseline_strategy_checksum"),
            "proposal_context_checksum": trace.get("proposal_context_checksum"),
            "knowledge_snapshot_checksum": snapshot.get("checksum"),
            "candidate_quality_report_checksum": quality_report.report_checksum,
            "candidate_quality_index_checksum": self._quality_index_checksum(quality_report),
            "proposal_provider": self._proposal_provider,
            "production_execution_eligible": self._production_execution_eligible,
        }

    def _write_proposal_records(self, preview_root: Path, trace: dict[str, object]) -> None:
        """输出两份审计文件：candidate‑intents.json、candidate‑patches.json"""
        self._atomic_json(preview_root / "candidate-intents.json", trace.get("intents", []))
        self._atomic_json(preview_root / "candidate-patches.json", trace.get("patch_attempts", []))

    @staticmethod
    def _quality_index_checksum(quality_report) -> str:
        body = {
            "schema_version": "1.0",
            "candidates": [
                {
                    "candidate_id": item.candidate_id,
                    "strategy_diff_ref": f"candidates/{item.candidate_id}/strategy-diff.json",
                    "candidate_quality_report_ref": f"candidates/{item.candidate_id}/candidate-quality-report.json",
                    "candidate_quality_report_checksum": item.report_checksum,
                }
                for item in quality_report.candidate_reports
            ],
            "batch_warnings": list(quality_report.warnings),
        }
        return canonical_checksum(body)


# ------------------------------ 模块内部辅助函数：从trace审计json恢复对象模型 ------------------------------
def _repair_summaries(trace: dict[str, object]) -> dict[str, dict[str, object]]:
    attempts = trace.get("patch_attempts", [])
    result: dict[str, dict[str, object]] = {}
    if not isinstance(attempts, list):
        return result
    for candidate_id in ("candidate_00", "candidate_01", "candidate_02", "candidate_03"):
        rows = [row for row in attempts if isinstance(row, dict) and row.get("candidate_id") == candidate_id]
        repair_rows = [row for row in rows if row.get("phase") == "repair"]
        result[candidate_id] = {
            "attempted": bool(repair_rows),
            "initial_error_code": next((row.get("error_code") for row in rows if row.get("phase") == "initial_failed"), None),
            "final_patch_phase": repair_rows[-1].get("phase") if repair_rows else "initial",
        }
    return result


def _intent_from_trace(trace: dict[str, object], candidate_id: str) -> CandidateIntent:
    """从trace的intents数组，根据candidate_id反序列化出CandidateIntent对象"""
    for row in trace.get("intents", []):
        if isinstance(row, dict) and row.get("candidate_id") == candidate_id:
            return CandidateIntent(
                candidate_id,
                str(row["role"]),
                str(row["objective"]),
                tuple(row["strategy_dimensions"]),
                int(row["min_changes"]),
                int(row["max_changes"]),
                tuple(row.get("required_dimensions", ())),
                min_operations=int(row.get("min_operations", 1)),
                min_dimensions=int(row.get("min_dimensions", 1)),
                require_surface=bool(row.get("require_surface", False)),
                require_sortie=bool(row.get("require_sortie", False)),
                max_operations=(
                    None if row.get("max_operations") is None else int(row["max_operations"])
                ),
                max_dimensions=(
                    None if row.get("max_dimensions") is None else int(row["max_dimensions"])
                ),
                failure_profile_mode=str(row.get("failure_profile_mode", "unavailable")),
                failure_operation_ids=tuple(row.get("failure_operation_ids", ())),
                failure_semantic_dimensions=tuple(row.get("failure_semantic_dimensions", ())),
                failure_profile_source_checksum=row.get("failure_profile_source_checksum"),
            )
    raise ValueError("awaiting_operator_action")


def _candidate_ids_from_trace(trace: dict[str, object]) -> tuple[str, ...]:
    """从trace读取候选ID列表，强制校验必须是固定4个ID顺序candidate_00‑03，否则抛出等待操作员异常"""
    values = []
    for row in trace.get("intents", []):
        if not isinstance(row, dict) or not isinstance(row.get("candidate_id"), str):
            raise ValueError("awaiting_operator_action")
        values.append(row["candidate_id"])
    if values != ["candidate_00", "candidate_01", "candidate_02", "candidate_03"]:
        raise ValueError("awaiting_operator_action")
    return tuple(values)


def _json_failure_location(trace: dict[str, object], failure: dict[str, object]) -> tuple[str | None, str | None]:
    """
    解析失败报告与trace，定位JSON解析失败发生在哪一个候选、哪一个阶段。
    返回：(candidate_id | None, stage: patch_generation / patch_repair | None)
    兼容新旧版本审计字段；旧版本trace没有失败标记时通过accepted/patch_attempts推导。
    """
    if failure.get("failure_code") == "proposal_json_invalid":
        return (
            failure.get("failed_candidate_id") if isinstance(failure.get("failed_candidate_id"), str) else None,
            failure.get("failed_stage") if isinstance(failure.get("failed_stage"), str) else None,
        )
    if failure.get("error_code") != "JSON completion is invalid":
        return None, None
    accepted = {
        row.get("candidate_id")
        for row in trace.get("accepted_candidates", [])
        if isinstance(row, dict) and isinstance(row.get("candidate_id"), str)
    }
    pending = next((item for item in _candidate_ids_from_trace(trace) if item not in accepted), None)
    if pending is None:
        return None, None
    attempts = [
        row for row in trace.get("patch_attempts", [])
        if isinstance(row, dict) and row.get("candidate_id") == pending
    ]
    return pending, "patch_repair" if attempts else "patch_generation"


def _accepted_prefix_from_trace(trace: dict[str, object], context: StrategyProposalContext, *, stop_before: str):
    """
    从trace恢复【已经成功生成的前缀候选】。
    stop_before：到此ID为止停止，不包含该ID，用于resume_from_candidate。
    """
    candidate_ids = _candidate_ids_from_trace(trace)
    prefix = candidate_ids[:candidate_ids.index(stop_before)]
    candidates = _candidates_from_trace(trace, context, candidate_ids=prefix)
    if tuple(item.candidate_id for item in candidates) != prefix:
        raise ValueError("awaiting_operator_action")
    return candidates


def _candidates_from_trace(
    trace: dict[str, object], context: StrategyProposalContext, *, candidate_ids: tuple[str, ...] | None = None
):
    """
    从完整trace审计JSON，反序列化恢复StrategyCandidate对象列表。
    逻辑：读取patch_attempts/resumed_candidate_attempts补丁记录，调用StrategyPatchAssembler把补丁合并到基线策略。
    用于修复/恢复流程，不用再次调用LLM，直接复现当时生成的策略。
    """
    catalog = build_patchable_leaf_catalog(baseline=context.baseline, scenario=context.scenario, allowed_paths=context.allowed_strategy_paths)
    assembler = StrategyPatchAssembler(baseline=context.baseline, catalog=catalog)
    final_patch: dict[str, dict[str, object]] = {}
    # 收集原始补丁尝试
    for row in trace.get("patch_attempts", []):
        if isinstance(row, dict) and isinstance(row.get("candidate_id"), str):
            final_patch[row["candidate_id"]] = row
    # 收集resume恢复流程追加的补丁尝试
    for audit in trace.get("resumed_candidate_attempts", []):
        if not isinstance(audit, dict):
            continue
        generated = audit.get("candidate_generation")
        if not isinstance(generated, dict):
            continue
        for row in generated.get("patch_attempts", []):
            if isinstance(row, dict) and isinstance(row.get("candidate_id"), str):
                final_patch[row["candidate_id"]] = row
    candidates = []
    wanted = candidate_ids or _candidate_ids_from_trace(trace)
    for candidate_id in wanted:
        intent_row = next(
            (row for row in trace.get("intents", []) if isinstance(row, dict) and row.get("candidate_id") == candidate_id),
            None,
        )
        if not isinstance(intent_row, dict):
            raise ValueError("awaiting_operator_action")
        patch_row = final_patch.get(candidate_id)
        if patch_row is None:
            raise ValueError("awaiting_operator_action")
        patch = CandidatePatch(candidate_id, str(patch_row["proposal_summary"]), tuple(StrategyPatchOperation(str(change["path"]), change["value"]) for change in patch_row["changes"]))
        assembled = assembler.assemble(patch)
        from cmo_lua_agent.optimization.phase6_models import StrategyCandidate
        candidates.append(StrategyCandidate(candidate_id, assembled.strategy, patch.proposal_summary, assembled.changed_paths))
    return tuple(candidates)
