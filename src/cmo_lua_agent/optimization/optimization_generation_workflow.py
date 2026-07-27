"""Phase 6 orchestration over the existing single-candidate evaluator.
Phase6 一代优化调度主流程
上层总控制器，统筹「策略生成→候选集合校验→基线+4条候选依次调用Phase5仿真评估→结果排行→生成本轮优化结论」；
整套流程目录隔离、所有中间产物落地存档，成功/失败状态持久化，异常兜底返回标准化结果。
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Protocol

# 全局哈希工具
from cmo_lua_agent.generation.runtime_models import canonical_sha256
# 技能加载器（战术经验Skill）
from cmo_lua_agent.optimization.bootstrap_skill_loader import BootstrapSkillLoader
# 候选排行榜对比工具
from cmo_lua_agent.optimization.candidate_comparator import CandidateComparator
# Phase5 候选输出结果、候选评估入参
from cmo_lua_agent.optimization.candidate_models import CandidateOutcome, CandidateRequest
# 候选批次校验器、策略差异对比工具
from cmo_lua_agent.optimization.candidate_set_validator import CandidateSetValidator, strategy_leaf_diff
# Phase6 数据契约：评估标识、本轮优化结果、顶层规划请求、单条候选、策略生成上下文
from cmo_lua_agent.optimization.phase6_models import (
    EvaluationIdentity, GenerationResult, PlanningRequest, StrategyCandidate,
    StrategyProposalContext,
)
# 策略生成Agent，用于产出4条候选策略
from cmo_lua_agent.optimization.strategy_proposal_agent import StrategyProposalAgent


# 单候选评估器协议：对接Phase5 CandidateEvaluationWorkflow
class SingleCandidateEvaluator(Protocol):
    def evaluate(self, request: CandidateRequest) -> CandidateOutcome: ...


# Phase6 单轮优化主工作流
class OptimizationGenerationWorkflow:
    def __init__(self, *, project_root: Path, proposal_agent: StrategyProposalAgent,
                 candidate_evaluator: SingleCandidateEvaluator) -> None:
        # 项目根目录
        self._root = Path(project_root).resolve()
        # 策略生成Agent：产出4条候选策略
        self._proposal_agent = proposal_agent
        # Phase5单候选评估执行器（协议注入，解耦）
        self._candidate_evaluator = candidate_evaluator
        # 战术Skill加载工具
        self._skill_loader = BootstrapSkillLoader(self._root)
        # 候选批次合法性校验器
        self._set_validator = CandidateSetValidator()
        # 候选结果排行榜排序工具
        self._comparator = CandidateComparator()

    def run(self, request: PlanningRequest) -> GenerationResult:
        """单轮优化完整入口
        输入顶层规划请求，执行一轮：生成候选→预检→基线+候选仿真→排行→输出本轮结果
        """
        # 创建本轮优化独立根目录沙箱
        root = self._create_root(request)
        paths: dict[str, str] = {"optimization_dir": str(root)}
        # 写入初始清单，标记运行中
        self._write_json(root / "generation_manifest.json", {"optimization_id": request.optimization_id, "status": "in_progress"})

        try:
            # 加载参考战术Skill，落地快照存档
            snapshot = self._skill_loader.load(request.bootstrap_skill_path)
            self._write_text(root / "bootstrap_skill_snapshot.md", snapshot.content)
            self._write_json(root / "bootstrap_skill_manifest.json", snapshot.to_dict())
            # 持久化入参、基线策略，方便复现实验
            self._write_json(root / "planning_request.json", request.to_dict())
            self._write_json(root / "baseline_strategy.json", request.baseline.to_dict())

            # 组装策略生成上下文，交给Agent生成4条候选
            context = StrategyProposalContext(
                request.scenario, request.baseline.strategy, request.user_objective,
                request.allowed_strategy_paths, request.diversity_dimensions,
                request.runtime.runtime_id, request.runtime.runtime_version, snapshot,
            )
            candidates = self._proposal_agent.propose(context)

            # Phase6前置强校验：4条候选数量、ID、结构、多样性、无重复策略
            candidate_set = self._set_validator.validate(
                scenario=request.scenario, baseline=request.baseline.strategy, candidates=candidates,
                allowed_paths=request.allowed_strategy_paths, diversity_dimensions=request.diversity_dimensions,
            )
            # 存档候选列表与多样性校验报告
            self._write_json(root / "strategy_candidates.json", [candidate.to_dict() for candidate in candidates])
            self._write_json(root / "diversity_report.json", candidate_set.diversity_report.to_dict())

            # 批次非法直接终止，不启动仿真
            if not candidate_set.diversity_report.valid:
                raise ValueError("candidate_set_invalid: " + ",".join(candidate_set.diversity_report.violations))

            # 计算每条候选相对基线的改动字段并存档
            diffs = {
                candidate.candidate_id: list(strategy_leaf_diff(request.baseline.strategy, candidate.strategy_spec, request.allowed_strategy_paths))
                for candidate in candidates
            }
            self._write_json(root / "strategy_diff.json", diffs)

            # 生成本轮评估唯一标识：保证所有候选使用同一套场景、计分规则、运行时，禁止跨组对比
            identity = EvaluationIdentity(
                canonical_sha256(request.scenario.to_dict()),
                request.native_score_compilation.score_spec_checksum,
                request.native_score_compilation.fragment_checksum,
                request.runtime.runtime_version,
                request.native_score_compilation.score_spec.rules[0].score_side_id,
            )

            evaluated: list[tuple[CandidateOutcome, EvaluationIdentity, bool]] = []
            # 先运行基线策略仿真评估
            baseline_outcome = self._evaluate(
                request, request.baseline.strategy, "baseline", root / "baseline" / "candidate_baseline"
            )
            evaluated.append((baseline_outcome, identity, True))

            # 依次串行执行4条候选，调用Phase5流水线仿真
            for candidate in candidates:
                outcome = self._evaluate(
                    request, candidate.strategy_spec, candidate.candidate_id,
                    root / "generation_00" / candidate.candidate_id
                )
                evaluated.append((outcome, identity, False))

            # 批量对比所有结果，生成排行榜（自动分类+打分排序）
            leaderboard = self._comparator.compare(outcomes=evaluated)
            ranks = {entry.candidate_id: entry.rank for entry in leaderboard}
            # CandidateOutcome is the durable per-candidate view; persist its final rank as well.
            for outcome, _, _ in evaluated:
                outcome_dir = Path(outcome.candidate_dir).resolve()
                if outcome_dir.is_relative_to(root):
                    self._write_json(
                        outcome_dir / "candidate_outcome.json",
                        asdict(replace(outcome, rank=ranks.get(outcome.candidate_id))),
                    )
            self._write_json(root / "leaderboard.json", [entry.to_dict() for entry in leaderboard])
            self._write_json(root / "optimization_summary.json", self._summary(
                optimization_id=request.optimization_id,
                leaderboard=leaderboard,
                baseline_strategy=request.baseline.strategy,
                strategy_diffs=diffs,
                leaderboard_path=root / "leaderboard.json",
            ))

            # 组装本轮最终输出结果
            result = GenerationResult(
                request.optimization_id,
                True,
                # 是否存在优于基线的有效候选
                any(entry.category == "ranked_success" and not entry.is_baseline for entry in leaderboard),
                # 基线本身是否成功有效、可以参与排名
                next(entry.category == "ranked_success" for entry in leaderboard if entry.is_baseline),
                str(root / "baseline" / "candidate_baseline" / "candidate_outcome.json"),
                tuple(str(root / "generation_00" / candidate.candidate_id / "candidate_outcome.json") for candidate in candidates),
                leaderboard,
                snapshot.skill_id,
                snapshot.version,
                snapshot.checksum,
                paths,
            )
            # 写入最终结果，更新状态为完成
            self._write_json(root / "generation_result.json", result.to_dict())
            self._write_json(root / "generation_manifest.json", {
                "optimization_id": request.optimization_id,
                "status": "completed",
                "bootstrap_skill_checksum": snapshot.checksum
            })
            return result

        except (KeyboardInterrupt, SystemExit):
            # 用户主动中断，直接上抛
            raise
        except Exception as exc:
            # 任意异常兜底：标记本轮失败，写入失败日志与空结果
            self._write_json(root / "generation_manifest.json", {
                "optimization_id": request.optimization_id,
                "status": "failed",
                "failure_reason": str(exc)
            })
            failed_result = GenerationResult(
                request.optimization_id, False, False, False,
                None, (), (), "unknown", "unknown", "unknown", paths, str(exc)
            )
            self._write_json(root / "generation_result.json", failed_result.to_dict())
            return failed_result

    def _evaluate(self, request: PlanningRequest, strategy, candidate_id: str, candidate_dir: Path) -> CandidateOutcome:
        """封装：构造Phase5入参，调用单候选评估流水线"""
        candidate_request = CandidateRequest(
            candidate_id=candidate_id,
            generation_index=0,
            scenario=request.scenario,
            strategy=strategy,
            runtime=request.runtime,
            native_score_compilation=request.native_score_compilation,
            max_repairs=request.max_repairs,
            timeout_seconds=request.timeout_seconds,
            candidate_dir=candidate_dir,
            allowed_strategy_paths=request.allowed_strategy_paths,
        )
        return self._candidate_evaluator.evaluate(candidate_request)

    @staticmethod
    def _create_root(request: PlanningRequest) -> Path:
        """创建本轮优化顶层沙箱目录，禁止覆盖已有实验目录，保证隔离"""
        root = Path(request.optimization_dir).resolve()
        if root.name != request.optimization_id:
            raise ValueError("optimization_dir name must equal optimization_id")
        root.parent.mkdir(parents=True, exist_ok=True)
        try:
            # exist_ok=False 目录已存在直接报错，防止覆盖旧实验
            root.mkdir(exist_ok=False)
        except FileExistsError as exc:
            raise ValueError("optimization_dir already exists") from exc
        return root

    @staticmethod
    def _write_text(path: Path, content: str) -> None:
        """原子写入文本：临时文件中转再重命名，避免程序崩溃产生损坏文件"""
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", delete=False, dir=path.parent) as handle:
            handle.write(content)
            temp_path = handle.name
        os.replace(temp_path, path)

    @classmethod
    def _write_json(cls, path: Path, value: object) -> None:
        """序列化JSON，调用原子文本写入；sort_keys=True保证每次输出顺序一致，确定性存档"""
        json_text = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=str) + "\n"
        cls._write_text(path, json_text)

    @staticmethod
    def _summary(*, optimization_id, leaderboard, baseline_strategy, strategy_diffs, leaderboard_path):
        baseline = next(entry for entry in leaderboard if entry.is_baseline)
        ranked = [entry for entry in leaderboard if entry.category == "ranked_success" and not entry.is_baseline]
        best = min(ranked, key=lambda entry: entry.rank) if ranked else None
        if baseline.category != "ranked_success":
            status = "baseline_unavailable"
        elif best is None:
            status = "no_scoreable_candidate"
        elif best.raw_score > baseline.raw_score:
            status = "candidate_improved_over_baseline"
        else:
            status = "baseline_remains_best"
        return {
            "optimization_id": optimization_id,
            "baseline_available": baseline.category == "ranked_success",
            "baseline_score": baseline.raw_score,
            "ranked_candidate_count": len(ranked),
            "failed_candidate_count": sum(1 for entry in leaderboard if not entry.is_baseline and entry.category != "ranked_success"),
            "best_candidate_id": best.candidate_id if best else ("baseline" if baseline.category == "ranked_success" else None),
            "best_candidate_score": best.raw_score if best else baseline.raw_score,
            "score_delta_vs_baseline": (best.raw_score - baseline.raw_score) if best and baseline.raw_score is not None else None,
            "best_candidate_strategy_diff": strategy_diffs.get(best.candidate_id, []) if best else [],
            "leaderboard_path": str(leaderboard_path),
            "conclusion_status": status,
        }
