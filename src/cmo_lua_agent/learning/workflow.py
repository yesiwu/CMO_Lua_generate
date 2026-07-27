"""
Phase7 显式离线学习工作流。本流程仅执行事后分析，**绝不调用CMO仿真引擎或Phase6评估器**。
运行时机：一代仿真全部完成后，基于已产出的仿真制品离线完成对比学习、经验提取与持久化。
"""
from __future__ import annotations
import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from cmo_lua_agent.agents.comparative_learning_agent import ComparativeLearningAgent
from .builders import CandidateLearningViewBuilder, GenerationLearningBundleBuilder
from .models import (
    ComparativeAnalysis,
    EvidenceStance,
    ExperienceCandidate,
    ExperienceProposal,
    GenerationLearningBundle,
)
from .store import ExperienceKeyNormalizer, ExperienceStore


class ExperienceCandidateAssembler:
    """
    经验候选组装器
    将LLM输出的原始ExperienceProposal（假设提案），结合仿真事实校验规则，
    转换为可持久化、具备完整元数据的ExperienceCandidate实体。
    核心作用：过滤低可信度提案、修正经验类型、计算证据质量、提取溯源信息与策略维度。
    """
    # 战术类经验合法类型集合
    _tactical = {"tactical_positive", "tactical_negative"}

    def __init__(self, normalizer: ExperienceKeyNormalizer | None = None) -> None:
        # 注入经验键归一化器，未传入则新建实例
        self._normalizer = normalizer or ExperienceKeyNormalizer()

    def assemble(
        self,
        *,
        bundle: GenerationLearningBundle,
        proposals: tuple[ExperienceProposal, ...]
    ) -> tuple[ExperienceCandidate, ...]:
        """
        批量将LLM提案转换为标准化经验候选实体
        :param bundle: 当前代完整学习数据包
        :param proposals: LLM产出的原始经验提案列表
        :return: 可持久化的ExperienceCandidate元组
        """
        # 构建候选ID -> CandidateLearningView 映射，方便快速查找案例事实
        views = {x.candidate_id: x for x in (bundle.baseline_view, *bundle.candidate_views)}
        result = []

        for index, p in enumerate(proposals, 1):
            supporting_ids = tuple(dict.fromkeys(p.supporting_candidate_ids))
            contradicting_ids = tuple(dict.fromkeys(p.contradicting_candidate_ids))
            referenced_ids = set(supporting_ids) | set(contradicting_ids)
            unknown_ids = referenced_ids - set(views)
            if unknown_ids:
                raise ValueError(
                    f"proposal references unknown candidate: {sorted(unknown_ids)[0]}"
                )
            if set(supporting_ids) & set(contradicting_ids):
                raise ValueError("supporting and contradicting candidates overlap")
            if (
                supporting_ids != p.supporting_candidate_ids
                or contradicting_ids != p.contradicting_candidate_ids
            ):
                raise ValueError("proposal candidate references contain duplicates")

            # 取出支撑该提案的候选视图
            support = [views[x] for x in supporting_ids]
            contradict = [views[x] for x in contradicting_ids]
            trusted_support = [x for x in support if self._trusted(x)]
            trusted_contradict = [x for x in contradict if self._trusted(x)]
            if p.evidence_stance is EvidenceStance.SUPPORT and not trusted_support:
                raise ValueError("support stance requires trusted supporting evidence")
            if (
                p.evidence_stance is EvidenceStance.CONTRADICT
                and not trusted_contradict
            ):
                raise ValueError(
                    "contradict stance requires trusted contradicting evidence"
                )
            if p.evidence_stance is EvidenceStance.QUALIFY:
                if not (trusted_support or trusted_contradict):
                    raise ValueError("qualify stance requires trusted evidence")
                if not p.counter_conditions:
                    raise ValueError("qualify stance requires counter conditions")

            # 校验支撑案例是否全部满足可信条件：执行成功、可计分、语义合法、仿真证据完整
            tactical_ok = bool(trusted_support) and len(trusted_support) == len(support)

            # 初始化经验类型，只允许系统预设合法类型
            kind = p.experience_type if p.experience_type in {
                "tactical_positive", "tactical_negative", "counterexample",
                "execution_failure", "runtime_diagnostic", "evidence_limitation"
            } else "evidence_limitation"

            # 规则1：标记为战术类，但支撑案例不满足可信条件 → 降级为证据局限类
            if kind in self._tactical and not tactical_ok:
                kind = "evidence_limitation"

            # 标准化经验唯一键
            key = self._normalizer.normalize(p.experience_key)

            # 规则2：键无法归类（unclassified）但试图作为战术经验 → 降级
            if key == "unclassified" and kind in self._tactical:
                kind = "evidence_limitation"

            # 证据质量得分：有效可信支撑案例 / 全部支撑案例数量，保留两位小数
            relevant = (
                support
                if p.evidence_stance is EvidenceStance.SUPPORT
                else contradict
                if p.evidence_stance is EvidenceStance.CONTRADICT
                else [*support, *contradict]
            )
            valid_relevant_count = sum(1 for x in relevant if self._trusted(x))
            quality = round(
                valid_relevant_count / max(1, len(relevant)),
                2,
            )

            # 汇总所有支撑案例的证据文件路径，去重并排序
            refs = tuple(sorted({
                ref for x in relevant for ref in x.evidence_refs
            }))

            # 提取策略维度：从strategy_diff中解析 /xxx/dimension 格式的维度标识
            dims = tuple(sorted({
                d.split("/")[1]
                for x in relevant
                for d in x.strategy_diff
                if d.startswith("/") and len(d.split("/")) > 1
            }))

            # 构造唯一经验ID：exp_优化轮ID_序号（001、002...）
            exp_id = f"exp_{bundle.optimization_id}_{index:03d}"
            result.append(ExperienceCandidate(
                experience_id=exp_id,
                experience_key=key,
                experience_type=kind,
                evidence_stance=p.evidence_stance,
                status="candidate",
                consumer="StrategyProposalAgent",
                source_optimization_id=bundle.optimization_id,
                hypothesis=p.hypothesis,
                applicable_conditions=p.applicable_conditions,
                recommended_pattern=p.recommended_pattern,
                counter_conditions=p.counter_conditions,
                observed_effect={
                    "supporting_candidate_ids": list(supporting_ids),
                    "contradicting_candidate_ids": list(contradicting_ids),
                    "scores": {x.candidate_id: x.official_score for x in support}
                },
                environment={**bundle.comparison_contract},
                evidence_refs=refs,
                created_from=("generation-learning-bundle.json", "comparative-analysis.json"),
                evidence_quality=quality,
                model_confidence=p.model_confidence,
                strategy_dimensions=dims
            ))
        return tuple(result)

    @staticmethod
    def _trusted(view: object) -> bool:
        return bool(
            view.execution_success
            and view.scoreable
            and view.semantic_valid
            and view.execution_fidelity == "verified"
        )


class GenerationLearningWorkflow:
    """
    一代仿真离线学习主工作流
    完整链路：加载仿真制品 → 构建候选视图 → 组装学习数据包 → LLM对比分析 → 生成经验提案 → 组装经验实体 → 本地持久化归档 + 存入经验库
    运行约束：纯离线后处理，不启动新一轮仿真评估
    """
    def __init__(self, *, agent: ComparativeLearningAgent, store: ExperienceStore) -> None:
        self._agent = agent                  # Phase7对比学习智能体
        self._store = store                  # 经验持久存储
        self._views = CandidateLearningViewBuilder()    # 候选视图构建器
        self._bundles = GenerationLearningBundleBuilder()# 学习数据包构建器
        self._assembler = ExperienceCandidateAssembler()# 经验实体组装器

    def run(
        self,
        optimization_dir: Path,
        *,
        reuse_saved_response: bool = False,
    ) -> tuple[GenerationLearningBundle, tuple[ExperienceCandidate, ...]]:
        """
        执行单代优化任务完整离线学习流程
        :param optimization_dir: 当前优化任务根目录
        :return: (学习数据包, 生成的全部经验候选实体)
        """
        root = Path(optimization_dir)
        # 读取一代汇总结果、策略差异文件
        generation_result = json.loads((root / "generation_result.json").read_text(encoding="utf-8"))
        strategy_diffs = json.loads((root / "strategy_diff.json").read_text(encoding="utf-8"))

        # 定位基线方案目录、所有候选方案目录
        baseline_dir = Path(generation_result["baseline_outcome_path"]).parent
        candidate_dirs = [Path(path).parent for path in generation_result["candidate_outcome_paths"]]

        # 批量构建所有候选学习视图（基线+全部普通候选）
        views = (
            self._views.build(candidate_dir=baseline_dir, is_baseline=True, strategy_diff=()),
        ) + tuple(
            self._views.build(
                candidate_dir=p,
                is_baseline=False,
                strategy_diff=tuple(strategy_diffs.get(p.name, ()))
            )
            for p in candidate_dirs
        )

        # 组装标准化学习数据包
        bundle = self._bundles.build(optimization_dir=root, views=views)
        learning_dir = root / "learning"
        if reuse_saved_response:
            analysis, proposals = self._load_saved_response(learning_dir)
        else:
            # 调用LLM执行对比分析，产出观测结论 + 原始经验提案
            analysis, proposals = self._agent.analyze(bundle)
        # 将提案加工为可持久化经验候选
        experiences = self._assembler.assemble(bundle=bundle, proposals=proposals)

        # 将所有中间产物写入learning目录归档（审计用途）
        self._write(learning_dir / "candidate-learning-views.json", [x.to_dict() for x in views])
        self._write(learning_dir / "generation-learning-bundle.json", bundle.to_dict())
        self._write(learning_dir / "comparative-analysis.json", asdict(analysis))
        self._write(learning_dir / "experience-proposals.json", [asdict(x) for x in proposals])
        self._write(learning_dir / "experience-candidates.json", [x.to_dict() for x in experiences])

        # 写入全局经验持久库
        self._store.save(experiences)
        return bundle, experiences

    @staticmethod
    def _load_saved_response(
        learning_dir: Path,
    ) -> tuple[ComparativeAnalysis, tuple[ExperienceProposal, ...]]:
        analysis_path = learning_dir / "comparative-analysis.json"
        proposals_path = learning_dir / "experience-proposals.json"
        if not analysis_path.is_file() or not proposals_path.is_file():
            raise ValueError("saved Phase 7 response is unavailable")
        analysis_data = json.loads(analysis_path.read_text(encoding="utf-8"))
        proposals_data = json.loads(proposals_path.read_text(encoding="utf-8"))
        fields = (
            "observed_strategy_differences",
            "observed_execution_differences",
            "observed_outcome_differences",
            "evidence_limitations",
            "possible_random_factors",
            "next_testable_hypotheses",
        )
        if not isinstance(analysis_data, dict) or set(analysis_data) != set(fields):
            raise ValueError("saved comparative analysis is invalid")
        if not isinstance(proposals_data, list):
            raise ValueError("saved experience proposals are invalid")
        analysis = ComparativeAnalysis(
            *(tuple(str(item) for item in analysis_data[field]) for field in fields)
        )
        proposals: list[ExperienceProposal] = []
        for item in proposals_data:
            if not isinstance(item, dict):
                raise ValueError("saved experience proposal is invalid")
            proposals.append(ExperienceProposal(
                experience_key=str(item["experience_key"]),
                experience_type=str(item["experience_type"]),
                evidence_stance=EvidenceStance(str(item["evidence_stance"])),
                hypothesis=str(item["hypothesis"]),
                applicable_conditions=tuple(map(str, item["applicable_conditions"])),
                recommended_pattern=dict(item["recommended_pattern"]),
                counter_conditions=tuple(map(str, item["counter_conditions"])),
                supporting_candidate_ids=tuple(map(str, item["supporting_candidate_ids"])),
                contradicting_candidate_ids=tuple(map(str, item["contradicting_candidate_ids"])),
                model_confidence=float(item["model_confidence"]),
            ))
        return analysis, tuple(proposals)

    @staticmethod
    def _write(path: Path, value: object) -> None:
        """
        原子写入JSON归档文件
        有序序列化保证文本确定性；临时文件替换方式防止文件损坏
        """
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            default=str
        ) + "\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent) as f:
            f.write(payload)
            tmp_path = f.name
        os.replace(tmp_path, path)
