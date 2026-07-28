"""
仅固化世代生成前、种群内兼容的知识输入快照
保证同一世代内所有候选策略共享完全一致的知识库素材，避免种群内信息不一致
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, Protocol


class ExperienceCardRetriever(Protocol):
    """经验案例检索器协议，外部注入实现"""
    def retrieve(self, **kwargs: object) -> tuple[dict[str, object], ...]: ...


@dataclass(frozen=True, slots=True)
class KnowledgeSnapshot:
    """
    知识快照：世代启动前固化的静态知识库视图
    一旦生成，整个世代生命周期内不可变更；用于约束LLM策略生成的统一输入素材
    """
    campaign_id: str                          # 推演任务ID
    generation_index: int                     # 所属世代编号
    bootstrap_checksum: str                   # 初始化基线知识包哈希
    active_skills: tuple[dict[str, object], ...] # 当前可用战术技能集合
    experience_cards: tuple[dict[str, object], ...] # 检索得到的历史经验案例卡片
    experience_store_revision: str            # 经验库版本号
    experience_index_checksum: str            # 经验索引哈希
    selected_experience_ids: tuple[str, ...]  # 本次选中生效的经验ID清单
    retrieval_query_checksum: str             # 检索条件哈希
    contract: dict[str, str]                  # 当前推演契约摘要
    parent_strategy_checksum: str             # 父代基线策略哈希
    checksum: str                             # 快照整体完整性哈希

    def to_dict(self) -> dict[str, object]:
        """序列化为字典用于持久化存储"""
        return asdict(self)


class KnowledgeSnapshotService:
    """知识快照管理服务，负责生成、加载、原子持久化快照"""
    def __init__(self, *, retriever: ExperienceCardRetriever) -> None:
        self._retriever = retriever  # 经验检索实现注入

    def freeze(self, *, path: Path, campaign_id: str, generation_index: int, bootstrap_checksum: str,
               active_skills: tuple[dict[str, object], ...], experience_store_revision: str,
               experience_index_checksum: str, retrieval_query: dict[str, object],
               contract: dict[str, str], parent_strategy_checksum: str) -> KnowledgeSnapshot:
        """
        冻结一份世代知识快照；文件已存在则直接加载，不重复检索
        :param path: 快照持久化文件路径
        :param campaign_id: 推演任务ID
        :param generation_index: 当前世代编号
        :param bootstrap_checksum: 初始基线知识哈希
        :param active_skills: 生效战术技能
        :param experience_store_revision: 经验库版本
        :param experience_index_checksum: 经验索引哈希
        :param retrieval_query: 经验检索查询条件
        :param contract: 推演契约信息
        :param parent_strategy_checksum: 父代基线策略哈希
        :return: 不可变知识快照实例
        """
        path = Path(path)
        # 文件已存在，直接加载已有快照，避免重复查询知识库
        if path.is_file():
            return self._from_dict(json.loads(path.read_text(encoding="utf-8")))

        # 计算检索条件哈希，用于校验检索条件未发生变更
        query_checksum = self._checksum(retrieval_query)
        # 调用检索器拉取经验卡片
        cards = self._retriever.retrieve(query=dict(retrieval_query), current_generation=generation_index)
        # 过滤规则：只允许使用【诞生于更早世代】的历史经验，禁止使用本代尚未完成的结果
        visible = tuple(
            dict(card) for card in cards
            if int(card.get("source_generation_index", -1)) < generation_index
        )
        # 提取生效经验ID列表
        selected = tuple(str(card["experience_id"]) for card in visible if "experience_id" in card)

        # 组装快照完整载荷
        body = {
            "campaign_id": campaign_id, "generation_index": generation_index,
            "bootstrap_checksum": bootstrap_checksum, "active_skills": active_skills,
            "experience_cards": visible, "experience_store_revision": experience_store_revision,
            "experience_index_checksum": experience_index_checksum, "selected_experience_ids": selected,
            "retrieval_query_checksum": query_checksum, "contract": dict(contract),
            "parent_strategy_checksum": parent_strategy_checksum,
        }
        # 生成快照总哈希，构造不可变快照对象
        snapshot = KnowledgeSnapshot(**body, checksum=self._checksum(body))
        # 原子写入磁盘，防止文件损坏
        self._write_atomic(path, snapshot.to_dict())
        return snapshot

    @staticmethod
    def _checksum(value: object) -> str:
        """对对象序列化后计算sha256哈希，用于完整性校验"""
        return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    @staticmethod
    def _write_atomic(path: Path, value: dict[str, object]) -> None:
        """原子写入JSON：先写临时文件，成功后替换目标文件，避免半写损坏"""
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8", newline="\n")
        os.replace(temporary, path)

    @staticmethod
    def _from_dict(value: dict[str, Any]) -> KnowledgeSnapshot:
        """字典反序列化为强类型快照对象"""
        return KnowledgeSnapshot(
            campaign_id=value["campaign_id"], generation_index=int(value["generation_index"]),
            bootstrap_checksum=value["bootstrap_checksum"], active_skills=tuple(dict(item) for item in value["active_skills"]),
            experience_cards=tuple(dict(item) for item in value["experience_cards"]), experience_store_revision=value["experience_store_revision"],
            experience_index_checksum=value["experience_index_checksum"], selected_experience_ids=tuple(value["selected_experience_ids"]),
            retrieval_query_checksum=value["retrieval_query_checksum"], contract=dict(value["contract"]),
            parent_strategy_checksum=value["parent_strategy_checksum"], checksum=value["checksum"],
        )