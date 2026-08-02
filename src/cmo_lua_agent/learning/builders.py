"""
由第6阶段制品生成确定性投影，产出安全可用于学习的输入数据。
核心约束：仅提取客观事实，不做任何战术效能推断，防止引入主观偏差。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import CandidateLearningView, GenerationLearningBundle


def _read(path: Path) -> dict[str, Any]:
    """
    读取指定路径JSON文件并校验根节点为字典对象
    :param path: JSON文件路径
    :return: 解析后的字典
    :raises ValueError: JSON根不是Object（数组/基础类型）时报错
    """
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


class CandidateLearningViewBuilder:
    """
    候选方案学习视图构建器
    设计原则：只萃取客观事实数据；绝不主动推断战术效能，避免引入主观预判。
    """
    def build(
        self,
        *,
        candidate_dir: Path,
        is_baseline: bool,
        strategy_diff: tuple[str, ...] = (),
        candidate_quality: dict[str, Any] | None = None,
    ) -> CandidateLearningView:
        """
        加载单条候选方案所有仿真制品，组装标准化学习视图
        :param candidate_dir: 当前候选方案根目录
        :param is_baseline: 是否为基线对照方案
        :param strategy_diff: 相对基线的策略差异描述元组
        :return: 结构化候选学习视图 CandidateLearningView
        """
        root = Path(candidate_dir)
        # 读取候选方案元数据与得分结果
        outcome = _read(root / "candidate_outcome.json")
        attempt = root / "attempts" / "attempt_00"

        # 查找执行摘要文件（全局搜索，取第一个匹配文件）
        summary_path = attempt / "execution-summary.json"
        if not summary_path.is_file():
            summary_path = next(iter(attempt.rglob("execution-summary.json")), None)
        summary = _read(summary_path) if summary_path else {}

        # 提取官方得分区块，不存在则为空字典
        official = summary.get("official_score") if isinstance(summary.get("official_score"), dict) else {}
        # 提取证据完整性校验信息
        integrity = summary.get("evidence_integrity") if isinstance(summary.get("evidence_integrity"), dict) else {}

        # 查找时序事件文件
        timeline = next(iter(attempt.rglob("execution-timeline.jsonl")), None)
        # 判断时序文件是否可用：存在且文件大小大于0
        timeline_usable = bool(timeline and timeline.is_file() and timeline.stat().st_size > 0)
        # 是否具备有效计分条件：允许计分标识为真 + 存在摘要文件
        final_score = official.get("final")
        scoreable = (
            bool(outcome.get("scoreable"))
            and bool(summary_path)
            and isinstance(final_score, int)
        )

        diagnostic_path = attempt / "execution-diagnostic.json"
        diagnostic = _read(diagnostic_path) if diagnostic_path.is_file() else {}
        analysis_path = next(iter(attempt.rglob("llm-analysis.json")), None)
        auxiliary_execution_analysis = self._load_auxiliary_execution_analysis(analysis_path)

        # 计划vs实际执行状态初始值
        planned = {
            "attacker": "unknown",
            "target": "unknown",
            "fire_quantity": "unknown",
            "sorties": "unknown",
            "unexpected_activity": "unknown"
        }
        fidelity = "unknown"

        # 如果有时序文件，执行保真度标记为 partial（部分可用）
        if timeline_usable:
            planned["attacker"] = planned["target"] = planned["fire_quantity"] = planned["sorties"] = "partial"
            fidelity = "partial"
        # Execution fidelity is independent from score-event completeness.  A
        # completed real CMO run with a result summary is verified even when
        # score evidence is reconstructed later.
        if outcome.get("execution_success") and diagnostic.get("cmo_started") and diagnostic.get("cmo_success") and summary_path:
            fidelity = "verified"
        elif outcome.get("execution_success") and summary_path:
            fidelity = "partial"
        elif not summary_path:
            fidelity = "failed"

        # 收集有效证据文件相对路径（用于溯源）
        refs = tuple(
            str(p.relative_to(root))
            for p in (summary_path, timeline, diagnostic_path, analysis_path)
            if p and p.is_file()
        )

        # 加载最终策略文件，不存在则为空字典
        strategy = _read(root / "strategy" / "final_strategy.json") if (root / "strategy" / "final_strategy.json").is_file() else {}
        # 加载生成清单文件
        manifest = _read(attempt / "generation_manifest.json") if (attempt / "generation_manifest.json").is_file() else {}

        return CandidateLearningView(
            candidate_id=str(outcome.get("candidate_id", "baseline" if is_baseline else "unknown")),
            is_baseline=is_baseline,
            # 策略概要：攻击方案数量、出动架次数量
            strategy_summary={
                "attack_count": len(strategy.get("attacks", [])),
                "sortie_count": len(strategy.get("sorties", []))
            },
            strategy_diff=tuple(strategy_diff),
            planned_vs_actual=planned,
            # 优先取摘要内最终官方得分，兜底使用原生仿真得分
            official_score=final_score if isinstance(final_score, int) else None,
            score_source="execution-summary.json#/official_score/final" if summary_path else None,
            scoreable=scoreable,
            semantic_valid=bool(outcome.get("semantic_valid")),
            execution_success=bool(outcome.get("execution_success")),
            losses=summary.get("losses", {}),
            target_damage=summary.get("target_damage", []),
            weapon_expenditures=summary.get("weapon_expenditures", []),
            timing_summary={"timeline_available": timeline_usable},
            execution_fidelity=fidelity,
            evidence_integrity=integrity,
            # 运行环境版本信息，缺失填充unknown
            environment={k: str(manifest.get(k, "unknown")) for k in ("runtime_version", "renderer_version", "score_spec_checksum")},
            evidence_refs=refs,
            scoring_evidence_status=str(summary.get("scoring_evidence_status", "MISSING")),
            candidate_quality=dict(candidate_quality or {}),
            auxiliary_execution_analysis=auxiliary_execution_analysis,
        )

    @staticmethod
    def _load_auxiliary_execution_analysis(path: Path | None) -> dict[str, Any]:
        """Project selected event facts from BatchRunner's auxiliary analysis.

        This deliberately keeps official score, losses, and damage sourced from
        ``execution-summary.json``.  The selected event/engagement aggregates
        help the learning model compare execution behaviour without exposing a
        full AAR, SQLite database, or raw timeline.
        """
        if path is None or not path.is_file():
            return {"available": False}
        try:
            value = _read(path)
        except (OSError, ValueError, json.JSONDecodeError):
            return {"available": False, "status": "unreadable"}

        def selected(items: object, fields: tuple[str, ...], limit: int) -> list[dict[str, Any]]:
            if not isinstance(items, list):
                return []
            return [
                {field: item.get(field) for field in fields if field in item}
                for item in items[:limit]
                if isinstance(item, dict)
            ]

        return {
            "available": True,
            "source": "llm-analysis.json",
            "key_events": selected(
                value.get("KeyEvents"),
                ("SimTime", "Category", "SideId", "TargetId", "Target", "Result"),
                20,
            ),
            "weapon_engagements": selected(
                value.get("WeaponEngagements"),
                ("SideId", "PlatformId", "WeaponId", "TargetId", "Fired", "Hits", "Kills", "Misses", "Unresolved"),
                20,
            ),
        }


class GenerationLearningBundleBuilder:
    """
    学习数据包构建器
    聚合基线方案 + 全部候选视图，组装统一输入包供给Phase7对比学习Agent
    """
    def build(
        self,
        *,
        optimization_dir: Path,
        views: tuple[CandidateLearningView, ...]
    ) -> GenerationLearningBundle:
        """
        构建一代优化任务完整学习数据包
        :param optimization_dir: 当前优化任务根目录
        :param views: 本代所有候选方案学习视图集合
        :return: 可输入对比智能体 GenerationLearningBundle
        """
        root = Path(optimization_dir)
        result = _read(root / "generation_result.json")
        leaderboard = json.loads((root / "leaderboard.json").read_text(encoding="utf-8"))

        # 分离基线方案与普通候选方案
        baseline = next(item for item in views if item.is_baseline)
        candidates = tuple(item for item in views if not item.is_baseline)

        # 契约环境：以基线环境版本作为统一运行契约
        contract = {k: v for k, v in baseline.environment.items() if k in {"runtime_version", "renderer_version", "score_spec_checksum"}}

        # 筛选有效候选：执行成功、可计分、语义合法、执行保真度为 verified
        valid = tuple(
            item.candidate_id
            for item in candidates
            if item.execution_success and item.scoreable and item.semantic_valid
            and item.execution_fidelity == "verified"
            and item.scoring_evidence_status in {"COMPLETE", "DERIVED"}
        )
        # 无效候选 = 全部候选剔除有效候选
        invalid = tuple(item.candidate_id for item in candidates if item.candidate_id not in valid)

        return GenerationLearningBundle(
            str(result["optimization_id"]),
            (),
            contract,
            baseline,
            candidates,
            tuple(leaderboard),
            # key:candidate_id, value:策略差异列表
            {item.candidate_id: item.strategy_diff for item in candidates},
            valid,
            invalid,
            # 汇总所有候选的证据溯源路径
            tuple(ref for item in views for ref in item.evidence_refs)
        )
