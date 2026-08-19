"""Phase 9C 执行阶段：冻结候选集加载消费逻辑"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cmo_lua_agent.contract.strategy_models import strategy_spec_from_dict
from cmo_lua_agent.evolution.production_models import FrozenCandidateSet


class FrozenCandidateSetProvider:
    """
    加载并校验已冻结候选集，**不依赖任何策略生成（Proposal）链路组件**
    职责：解析冻结快照、完整性校验、基线与候选策略反序列化、ID合规校验
    """

    def __init__(
        self,
        *,
        strategy_parser: Callable[[dict[str, Any]], Any] = strategy_spec_from_dict,
        verify_checksum_metadata: bool = True,
    ) -> None:
        """
        :param strategy_parser: 策略字典转为策略规格对象的解析器
        :param verify_checksum_metadata: 是否启用候选集元数据校验和完整性校验
        """
        self._strategy_parser = strategy_parser
        self._verify_checksum_metadata = verify_checksum_metadata

    def load(self, frozen: FrozenCandidateSet) -> tuple[Any, tuple[tuple[str, Any], ...]]:
        """
        载入冻结候选集，执行校验并反序列化基线与全部候选策略
        :param frozen: 原始FrozenCandidateSet冻结实例
        :return: (基线策略实例, ((candidate_id, 候选策略实例),...))
        :raises ValueError: 候选ID序列不符合规范时抛出异常
        """
        # 使用内置校验方法重建候选集，按需校验内部所有checksum
        verified = FrozenCandidateSet.from_dict(
            frozen.to_dict(),
            verify_checksums=self._verify_checksum_metadata,
        )
        # 反序列化基线策略
        baseline = self._strategy_parser(dict(verified.baseline))
        # 遍历所有候选，解析策略并绑定候选ID
        candidates = tuple(
            (str(item["candidate_id"]), self._strategy_parser(dict(item["strategy"])))
            for item in verified.candidates
        )
        # 强制校验候选ID必须为 candidate_00 ~ candidate_03 固定序列
        if [item[0] for item in candidates] != [f"candidate_{index:02d}" for index in range(4)]:
            raise ValueError("frozen_candidate_ids_invalid")
        return baseline, candidates