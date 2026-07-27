"""
仅用于pytest测试的独立、确定性Phase8经验测试样本工厂。
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


class Phase8ExperienceFixtureFactory:
    """仅构造测试用经验记录，不读写正式生产存储。"""

    artifact_provenance = "test_fixture"
    store_mode = "test"

    @classmethod
    def promotable_records(cls) -> tuple[dict[str, Any], ...]:
        """返回同一兼容分组内5条支持证据、1条矛盾证据。"""
        return tuple(
            cls.record(index=index, stance=("support" if index <= 5 else "contradict"))
            for index in range(1, 7)
        )

    @classmethod
    def record(cls, *, index: int, stance: str = "support") -> dict[str, Any]:
        optimization_id = f"opt_fixture_{index:03d}"
        return {
            "schema_version": "2",
            "experience_id": f"exp_fixture_{index:03d}",
            "experience_key": "naval_air_anti_surface.target_deconfliction",
            "experience_type": "tactical_positive",
            "evidence_stance": stance,
            "status": "candidate",
            "consumer": "StrategyProposalAgent",
            "source_optimization_id": optimization_id,
            "artifact_provenance": cls.artifact_provenance,
            "store_mode": cls.store_mode,
            "hypothesis": "舰艇与舰载机进行目标去冲突分配，能够提升多目标打击覆盖率。",
            "applicable_conditions": ["海上空对面作战场景", "存在多个水面目标"],
            "recommended_pattern": {"summary": "对目标分配方案执行去冲突处理"},
            "counter_conditions": ["仅有单个有效目标"],
            "observed_effect": {
                "supporting_candidate_ids": [f"candidate_fixture_{index:02d}"],
                "score_delta_vs_baseline": 25,
            },
            "environment": {
                "mission_type": "naval_air_anti_surface",
                "scenario_id": f"scenario_fixture_{(index - 1) % 3 + 1}",
                "score_spec_version": "1.0.0",
                "score_spec_checksum": "fixture-score-spec-v1",
                "runtime_version": "2.0.0",
                "renderer_version": "2.0.0",
                "scenario_schema_version": "1.0",
                "score_source": "execution_summary",
            },
            "evidence_refs": [
                f"tests/fixtures/phase8/{optimization_id}/execution-summary.json"
            ],
            "evidence_quality": 0.9,
            "model_confidence": 0.8,
            "execution_success": True,
            "scoreable": True,
            "semantic_valid": True,
            "execution_fidelity": "verified",
        }

    @classmethod
    def duplicate_evidence(cls) -> dict[str, Any]:
        """生成一条重复经验样本（用于重复数据测试）"""
        value = deepcopy(cls.record(index=1))
        value["experience_id"] = "exp_fixture_001_duplicate"
        value["observed_effect"]["supporting_candidate_ids"] = [
            "candidate_fixture_duplicate"
        ]
        return value

    @classmethod
    def different_cohort(cls) -> dict[str, Any]:
        """生成一条属于不同兼容分组的经验（用于跨分组隔离测试）"""
        value = deepcopy(cls.record(index=7))
        value["environment"]["runtime_version"] = "3.0.0"
        return value