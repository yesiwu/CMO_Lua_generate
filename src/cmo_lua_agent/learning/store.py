"""
基于确定性JSON记录实现经验持久化与检索模块。
提供经验键归一化、原子写入持久存储、索引构建、场景匹配经验检索整套能力。
"""
from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path
from .models import ExperienceCandidate, ExperienceCard


class ExperienceKeyNormalizer:
    """
    经验键归一化器
    统一不同命名别名，规范经验主键命名空间；无法匹配规范格式则归类为 unclassified（未分类）
    """
    # 别名映射：简写key → 完整带命名空间标准key
    _aliases = {
        "target_deconfliction": "naval_air_anti_surface.target_deconfliction",
        "salvo_timing": "naval_air_anti_surface.salvo_timing",
        "aircraft_early_loss": "naval_air_anti_surface.aircraft_early_loss"
    }

    def normalize(self, key: str) -> str:
        """
        标准化经验标识key
        :param key: 原始输入经验键
        :return: 归一化后标准key，非法格式返回 "unclassified"
        """
        # 小写清洗 + 别名替换
        raw = key.strip().lower()
        key = self._aliases.get(raw, raw)
        # 校验命名空间格式：naval_air_anti_surface.xxx，仅一个点，前后仅字母数字下划线
        if (key.startswith("naval_air_anti_surface.")
                and key.count(".") == 1
                and all(part.replace("_", "").isalnum() for part in key.split("."))):
            return key
        return "unclassified"


class ExperienceStore:
    """
    经验持久存储层
    职责：原子写入经验JSON记录、维护全局索引index.jsonl、防止经验ID冲突覆盖
    """
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.records = self.root / "records"    # 单条经验独立JSON文件存放目录
        self.index = self.root / "index.jsonl"   # 全局轻量索引（加速检索，避免遍历全部json）

    def save(self, candidates: tuple[ExperienceCandidate, ...]) -> None:
        """
        批量持久化经验候选实体，并重建索引文件
        :param candidates: 待保存经验候选集合
        :raises ValueError: 当存在同名ID但文件内容不一致（冲突修改）时报错
        """
        self.records.mkdir(parents=True, exist_ok=True)

        # 逐条写入经验记录
        for candidate in candidates:
            record_path = self.records / f"{candidate.experience_id}.json"
            # 生成确定性序列化文本（sort_keys保证相同对象文本唯一）
            payload = json.dumps(candidate.to_dict(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
            # 文件已存在并且内容不一致 → 冲突，禁止覆盖
            if record_path.exists():
                if record_path.read_text(encoding="utf-8") != payload:
                    raise ValueError(f"experience conflict: {candidate.experience_id}")
            else:
                # 新文件执行原子写入
                self._atomic(record_path, payload)

        # 重建索引：仅保留检索必需字段，减少索引体积
        index_rows = []
        for path in sorted(self.records.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            index_entry = {
                k: data[k]
                for k in (
                    "experience_id",
                    "schema_version",
                    "experience_key",
                    "experience_type",
                    "evidence_stance",
                    "status",
                    "source_optimization_id",
                    "evidence_quality",
                    "model_confidence",
                    "environment",
                    "strategy_dimensions"
                )
            }
            index_entry["record_path"] = str(path.relative_to(self.root))
            index_rows.append(index_entry)

        # 原子更新索引文件
        index_text = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in index_rows)
        self._atomic(self.index, index_text)

    @staticmethod
    def _atomic(path: Path, text: str) -> None:
        """
        原子写入文件：先写临时文件，成功后替换目标文件，避免断电/中断产生损坏文件
        :param path: 目标文件路径
        :param text: 需要写入的文本内容
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        # 在同目录创建临时文件，保证rename为原子操作
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent) as f:
            f.write(text)
            tmp_file_path = f.name
        os.replace(tmp_file_path, path)


class ExperienceRetriever:
    """
    经验检索器
    根据当前优化环境、允许策略维度，筛选匹配的历史经验，转换为轻量化ExperienceCard
    """
    def __init__(self, store: ExperienceStore) -> None:
        self.store = store

    def retrieve(
        self,
        *,
        current_optimization_id: str,
        environment: dict[str, str],
        allowed_dimensions: tuple[str, ...]
    ) -> tuple[tuple[ExperienceCard, ...], tuple[ExperienceCard, ...], tuple[ExperienceCard, ...]]:
        """
        检索可用历史经验，并按经验类型分组截断
        :param current_optimization_id: 当前正在执行的优化轮ID（排除本轮生成的经验，避免自引用）
        :param environment: 当前运行环境契约，必须与经验环境完全匹配
        :param allowed_dimensions: 当前优化关心的策略维度集合
        :return: (正向战术经验, 负向/反例经验, 诊断/证据局限类经验)
        """
        # 索引文件不存在 → 返回空集合
        if not self.store.index.is_file():
            return (), (), ()

        # 加载索引所有条目
        index_lines = self.store.index.read_text(encoding="utf-8").splitlines()
        rows = [json.loads(line) for line in index_lines if line.strip()]

        matched_items = []
        for row in rows:
            # 过滤规则1：排除本轮自身产出经验
            if row["source_optimization_id"] == current_optimization_id:
                continue
            # 过滤规则2：环境契约必须完全一致，任意版本不匹配直接丢弃
            env_match_ok = all(row["environment"].get(k) == v for k, v in environment.items())
            if not env_match_ok:
                continue

            # 读取完整经验记录
            full_data = json.loads((self.store.root / row["record_path"]).read_text(encoding="utf-8"))
            # 计算策略维度重叠数量，作为排序首要依据
            overlap_count = len(set(full_data["strategy_dimensions"]) & set(allowed_dimensions))
            matched_items.append((
                -overlap_count,
                -float(full_data["evidence_quality"]),
                -float(full_data["model_confidence"]),
                full_data
            ))

        # 排序优先级：维度重叠数降序 → 证据质量降序 → 模型置信度降序 → experience_id升序
        matched_items.sort()

        # 转换为轻量化经验卡片 ExperienceCard
        all_cards = []
        for item_tuple in matched_items:
            _, _, _, item = item_tuple
            card = ExperienceCard(
                experience_key=item["experience_key"],
                experience_type=item["experience_type"],
                source_optimization_id=item["source_optimization_id"],
                confidence=item["model_confidence"],
                evidence_quality=item["evidence_quality"],
                applicable_when=tuple(item["applicable_conditions"]),
                suggestion=item["hypothesis"],
                counter_conditions=tuple(item["counter_conditions"]),
                evidence_count=len(item["evidence_refs"]),
                status=item["status"]
            )
            all_cards.append(card)

        # 按类型分组并截断数量限制
        positive = tuple(c for c in all_cards if c.experience_type == "tactical_positive")[:3]
        negative = tuple(c for c in all_cards if c.experience_type in {"tactical_negative", "counterexample"})[:2]
        diagnostic = tuple(c for c in all_cards if c.experience_type in {"runtime_diagnostic", "evidence_limitation", "execution_failure"})
        return positive, negative, diagnostic
