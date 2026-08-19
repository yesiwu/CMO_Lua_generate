"""Phase 9C 候选冻结前的确定性批次质量检查。

这个模块不调用 LLM，也不生成新的策略。

它负责检查“已经生成好的候选策略”质量，例如：

    1. 每个候选相比 baseline 到底修改了什么；
    2. 修改涉及哪些作战操作、平台和策略维度；
    3. 候选是否符合预先定义的角色要求；
    4. 不同候选之间是不是过于相似；
    5. 整批候选的覆盖范围是否足够；
    6. 最终输出 passed / failed + warnings。

可以理解成：

    baseline
        ↓
    candidate_00
    candidate_01
    candidate_02
    ...
        ↓
    CandidateQualityEvaluator
        ↓
    候选质量报告
        ↓
    合格后才允许进入后续冻结 / 评测阶段
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Any, Mapping

from cmo_lua_agent.evolution.production_models import (
    canonical_checksum,
)
from cmo_lua_agent.optimization.candidate_set_validator import (
    strategy_leaf_diff,
)
from cmo_lua_agent.optimization.phase6_models import (
    StrategyCandidate,
    StrategySpec,
)
from cmo_lua_agent.optimization.strategy_dimensions import (
    semantic_dimensions,
)


def _operation_key(path: str) -> str | None:
    """从策略字段路径中提取它属于哪一个作战操作。

    例如：

        /attacks/0/fire_distance
            ↓
        attacks/0

        /sorties/2/launch_delay
            ↓
        sorties/2

    后面可以通过这个 key 找到：
        operation_id
        platform_id
        operation_type
    """

    tokens = path.strip("/").split("/")

    if (
        len(tokens) >= 2
        and tokens[0] in {"attacks", "sorties"}
        and tokens[1].isdecimal()
    ):
        return f"{tokens[0]}/{tokens[1]}"

    return None


def _pointer_value(
    payload: Any,
    path: str,
) -> Any:
    """按照类似 JSON Pointer 的路径读取策略字段值。

    例如：

        path = /attacks/0/fire_distance

    会依次访问：

        payload["attacks"][0]["fire_distance"]

    主要用于比较两个候选在同一个修改字段上的值是否真的不同。
    """

    current = payload

    for token in path.strip("/").split("/"):
        current = (
            current[int(token)]
            if isinstance(current, list)
            else current[token]
        )

    return current


def _jaccard(
    left: set[str],
    right: set[str],
) -> float:
    """计算两个集合的 Jaccard 相似度。

    例如：

        候选A修改：
            speed
            distance
            timeout

        候选B修改：
            speed
            distance
            altitude

    两者共同修改：
        speed
        distance

    Jaccard 越接近 1，
    说明两个候选改动位置越相似。

    如果大量候选 Jaccard 很高，
    说明所谓“多个候选”其实没有真正形成策略多样性。
    """

    union = left | right

    return (
        1.0
        if not union
        else len(left & right) / len(union)
    )


# ---------------------------------------------------------
# 单个候选的质量报告
# ---------------------------------------------------------
@dataclass(frozen=True, slots=True)
class CandidateQualityCandidateReport:
    """记录一个候选相比 baseline 实际发生了哪些变化。"""

    # 候选唯一 ID
    candidate_id: str

    # 这个候选预先承担的角色，例如：
    # conservative / aggressive / exploratory 等
    role: str

    # 策略内容的确定性 checksum。
    # 两个候选 checksum 相同，说明最终策略完全相同。
    strategy_checksum: str

    # 相比 baseline，一共修改了多少个最底层字段
    changed_leaf_count: int

    # 具体修改了哪些字段路径
    changed_paths: tuple[str, ...]

    # 改动涉及哪些作战 operation
    changed_operation_ids: tuple[str, ...]

    # 改动涉及哪些平台
    changed_platform_ids: tuple[str, ...]

    # 改动属于哪些战术语义维度
    # 例如 timing / range / salvo 等
    semantic_dimensions: tuple[str, ...]

    # 修改涉及多少个水面攻击操作
    surface_operation_count: int

    # 修改涉及多少个飞机 sortie 操作
    sortie_operation_count: int

    # 当前候选是否符合预先定义的角色要求
    role_conformance: Mapping[str, Any]

    # 当前候选距离 baseline 有多远
    baseline_distance: Mapping[str, int]

    # 如果候选经历过自动修复，
    # 这里可以附带修复摘要
    repair_summary: Mapping[str, Any] | None = None

    @property
    def report_checksum(self) -> str:
        """给当前候选质量报告计算确定性指纹。"""

        return canonical_checksum(
            self._body()
        )

    def _body(self) -> dict[str, Any]:
        """生成不包含 report_checksum 的主体内容。"""

        return {
            "schema_version": "1.0",

            "candidate_id": self.candidate_id,

            "role": self.role,

            "strategy_checksum": (
                self.strategy_checksum
            ),

            # 能进入这里，默认已经通过前面的硬校验
            "hard_validation": {
                "valid": True
            },

            # 实际改动情况
            "actual_changes": {
                "changed_leaf_count": (
                    self.changed_leaf_count
                ),
                "changed_paths": list(
                    self.changed_paths
                ),
                "changed_operation_ids": list(
                    self.changed_operation_ids
                ),
                "changed_platform_ids": list(
                    self.changed_platform_ids
                ),
                "semantic_dimensions": list(
                    self.semantic_dimensions
                ),
                "surface_operation_count": (
                    self.surface_operation_count
                ),
                "sortie_operation_count": (
                    self.sortie_operation_count
                ),
            },

            # 候选有没有按照预设角色去修改策略
            "role_quality": dict(
                self.role_conformance
            ),

            # 是否经历过 Repair
            "repair_summary": dict(
                self.repair_summary
                or {"attempted": False}
            ),

            # 这个候选的实验结果是否容易解释
            "interpretability": (
                _interpretability(
                    len(
                        self.changed_operation_ids
                    ),
                    len(
                        self.semantic_dimensions
                    ),
                )
            ),

            # 相比 baseline 改动范围有多大
            "baseline_distance": dict(
                self.baseline_distance
            ),
        }

    def to_dict(self) -> dict[str, Any]:
        """转换成最终可写 JSON 的格式，并附加报告 checksum。"""

        return {
            **self._body(),
            "report_checksum": (
                self.report_checksum
            ),
        }


# ---------------------------------------------------------
# 两个候选之间的相似度报告
# ---------------------------------------------------------
@dataclass(frozen=True, slots=True)
class CandidateQualityPairwiseReport:
    """比较两个候选是不是改得太像。"""

    left_candidate_id: str
    right_candidate_id: str

    # 两个候选修改字段路径的相似度
    path_jaccard: float

    # 两个候选修改 operation 的相似度
    operation_jaccard: float

    # 即使修改了相同字段，
    # 具体值真正不同的字段数量
    value_difference_count: int

    # 两份策略是否完全相同
    same_strategy_checksum: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "left_candidate_id": (
                self.left_candidate_id
            ),
            "right_candidate_id": (
                self.right_candidate_id
            ),
            "path_jaccard": (
                self.path_jaccard
            ),
            "operation_jaccard": (
                self.operation_jaccard
            ),
            "value_difference_count": (
                self.value_difference_count
            ),
            "same_strategy_checksum": (
                self.same_strategy_checksum
            ),
        }


# ---------------------------------------------------------
# 整批候选的最终质量报告
# ---------------------------------------------------------
@dataclass(frozen=True, slots=True)
class CandidateQualityReport:
    """整个候选集合的质量检查结果。"""

    # 每个候选自己的质量报告
    candidate_reports: tuple[
        CandidateQualityCandidateReport,
        ...
    ]

    # 每两个候选之间的比较结果
    pairwise_reports: tuple[
        CandidateQualityPairwiseReport,
        ...
    ]

    # 整批候选一共覆盖了哪些：
    # operation / semantic dimension / platform type
    batch_coverage: Mapping[
        str,
        tuple[str, ...],
    ]

    # 真正阻止批次继续的硬失败规则
    failed_rules: tuple[str, ...]

    # 整份报告的确定性 checksum
    report_checksum: str

    # 不阻止流程，但值得关注的问题
    warnings: tuple[str, ...] = ()

    schema_version: str = "1.0"

    @property
    def status(self) -> str:
        """只要存在 failed_rules，整批候选就算失败。"""

        return (
            "passed"
            if not self.failed_rules
            else "failed"
        )

    @classmethod
    def create(
        cls,
        *,
        candidate_reports: tuple[
            CandidateQualityCandidateReport,
            ...
        ],
        pairwise_reports: tuple[
            CandidateQualityPairwiseReport,
            ...
        ],
        batch_coverage: Mapping[
            str,
            tuple[str, ...],
        ],
        failed_rules: tuple[str, ...],
        warnings: tuple[str, ...] = (),
    ) -> "CandidateQualityReport":
        """统一创建整批质量报告，并计算 checksum。"""

        body = {
            "schema_version": "1.0",

            "status": (
                "passed"
                if not failed_rules
                else "failed"
            ),

            "candidate_reports": [
                item.to_dict()
                for item in candidate_reports
            ],

            "pairwise_reports": [
                item.to_dict()
                for item in pairwise_reports
            ],

            "batch_coverage": {
                key: list(value)
                for key, value
                in sorted(
                    batch_coverage.items()
                )
            },

            "failed_rules": list(
                failed_rules
            ),

            "warnings": list(warnings),
        }

        return cls(
            candidate_reports=(
                candidate_reports
            ),
            pairwise_reports=(
                pairwise_reports
            ),
            batch_coverage={
                key: tuple(value)
                for key, value
                in sorted(
                    batch_coverage.items()
                )
            },
            failed_rules=failed_rules,
            warnings=warnings,

            # 对整份报告计算内容指纹，
            # 后面可以判断报告是否被修改过。
            report_checksum=(
                canonical_checksum(body)
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """转成最终可序列化报告。"""

        return {
            "schema_version": (
                self.schema_version
            ),
            "status": self.status,

            "candidate_reports": [
                item.to_dict()
                for item
                in self.candidate_reports
            ],

            "pairwise_reports": [
                item.to_dict()
                for item
                in self.pairwise_reports
            ],

            "batch_coverage": {
                key: list(value)
                for key, value
                in sorted(
                    self.batch_coverage.items()
                )
            },

            "failed_rules": list(
                self.failed_rules
            ),

            "warnings": list(
                self.warnings
            ),

            "report_checksum": (
                self.report_checksum
            ),
        }

    def require_passed(self) -> None:
        """如果整批候选没有通过质量门槛，直接阻断后续流程。"""

        if self.failed_rules:
            raise CandidateBatchQualityError(
                self
            )


# ---------------------------------------------------------
# 批次质量不合格异常
# ---------------------------------------------------------
class CandidateBatchQualityError(
    ValueError
):
    """候选集合没有通过质量门槛。"""

    code = (
        "candidate_batch_quality_failed"
    )

    def __init__(
        self,
        report: CandidateQualityReport,
    ) -> None:

        # 保留完整报告，
        # 上层可以直接把失败原因返回给 Agent / CLI
        self.report = report

        self.failed_rules = (
            report.failed_rules
        )

        # 当前候选集合实际覆盖了哪些 operation
        self.covered_operation_ids = (
            report.batch_coverage[
                "operation_ids"
            ]
        )

        # 覆盖了哪些策略语义维度
        self.covered_dimensions = (
            report.batch_coverage[
                "semantic_dimensions"
            ]
        )

        # 覆盖了哪些平台类型
        self.covered_platform_types = (
            report.batch_coverage[
                "platform_types"
            ]
        )

        # 保存两两候选相似度摘要
        self.pairwise_summary = tuple(
            item.to_dict()
            for item
            in report.pairwise_reports
        )

        self.candidate_ids = tuple(
            item.candidate_id
            for item
            in report.candidate_reports
        )

        super().__init__(self.code)


# ---------------------------------------------------------
# 核心：候选质量评估器
# ---------------------------------------------------------
class CandidateQualityEvaluator:
    """对已经生成好的候选策略做纯确定性质量检查。

    它不会修改候选，
    也不会重新调用 LLM。

    主要检查：

        单候选改了什么
        ↓
        是否符合角色
        ↓
        候选之间是否过于相似
        ↓
        整批候选覆盖范围是否足够
    """

    def evaluate(
        self,
        *,
        baseline: StrategySpec,
        candidates: tuple[
            StrategyCandidate,
            ...
        ],
        intents: tuple[object, ...],
        proposal_context: Mapping[
            str,
            Any,
        ],
        repair_summaries: Mapping[
            str,
            Mapping[str, Any],
        ]
        | None = None,
    ) -> CandidateQualityReport:
        """生成整批候选质量报告。"""

        # candidate_id → 候选生成时对应的角色要求
        intent_by_id = {
            str(
                getattr(
                    item,
                    "candidate_id",
                )
            ): item
            for item in intents
        }

        # 建立：
        #
        # attacks/0
        #     →
        # operation_id
        # platform_id
        # platform_type
        #
        # sorties/0
        #     →
        # ...
        operation_metadata = (
            _operation_metadata(
                baseline,
                proposal_context,
            )
        )

        # 从冻结的 proposal_context 中读取：
        # 到底哪些字段允许候选修改。
        patchable_paths = (
            _patchable_paths(
                proposal_context
            )
        )

        # 先逐个候选生成质量报告
        reports = tuple(
            self._candidate_report(
                baseline=baseline,
                candidate=candidate,

                # 根据 candidate_id 找对应角色意图
                intent=intent_by_id.get(
                    candidate.candidate_id
                ),

                operation_metadata=(
                    operation_metadata
                ),

                patchable_paths=(
                    patchable_paths
                ),

                repair_summary=(
                    repair_summaries or {}
                ).get(
                    candidate.candidate_id
                ),
            )

            # candidate_id 排序保证输出确定性
            for candidate in sorted(
                candidates,
                key=lambda item: (
                    item.candidate_id
                ),
            )
        )

        # 再做所有候选两两比较
        pairwise = (
            self._pairwise_reports(
                candidates,
                reports,
            )
        )

        # operation_id → platform_type
        platform_types_by_operation = {
            str(
                value["operation_id"]
            ): str(
                value["platform_type"]
            )
            for value
            in operation_metadata.values()
        }

        # -------------------------------------------------
        # 统计整个候选集合的覆盖范围
        # -------------------------------------------------
        coverage = {
            # 所有候选一共改到了哪些 operation
            "operation_ids": tuple(
                sorted(
                    {
                        value
                        for item in reports
                        for value
                        in item.changed_operation_ids
                    }
                )
            ),

            # 一共覆盖多少种策略维度
            "semantic_dimensions": tuple(
                sorted(
                    {
                        value
                        for item in reports
                        for value
                        in item.semantic_dimensions
                    }
                )
            ),

            # 一共覆盖多少种平台类型
            "platform_types": tuple(
                sorted(
                    {
                        platform_types_by_operation[
                            value
                        ]
                        for item in reports
                        for value
                        in item.changed_operation_ids
                        if value
                        in platform_types_by_operation
                    }
                )
            ),
        }

        # 根据单候选报告 + 批次覆盖率 + 候选相似度，
        # 判断哪些属于失败，哪些只是警告。
        failed, warnings = (
            self._quality_messages(
                reports,
                coverage,
                pairwise,
            )
        )

        return CandidateQualityReport.create(
            candidate_reports=reports,
            pairwise_reports=pairwise,
            batch_coverage=coverage,
            failed_rules=tuple(
                sorted(failed)
            ),
            warnings=tuple(
                sorted(warnings)
            ),
        )

    @staticmethod
    def _candidate_report(
        *,
        baseline,
        candidate,
        intent,
        operation_metadata,
        patchable_paths,
        repair_summary=None,
    ):
        """生成单个候选自己的质量报告。"""

        # 找出：
        #
        # baseline
        #     VS
        # candidate
        #
        # 在允许修改的字段中，
        # 到底有哪些叶子字段真的发生了变化。
        paths = strategy_leaf_diff(
            baseline,
            candidate.strategy_spec,
            patchable_paths,
        )

        # 根据修改字段反推出：
        # 这些变化涉及哪些正式 operation_id。
        operation_ids = tuple(
            sorted(
                {
                    str(
                        operation_metadata[
                            key
                        ]["operation_id"]
                    )
                    for path in paths
                    if (
                        key := _operation_key(
                            path
                        )
                    )
                    is not None
                    and key
                    in operation_metadata
                }
            )
        )

        # 这些修改涉及哪些具体平台
        platform_ids = tuple(
            sorted(
                {
                    str(
                        operation_metadata[
                            key
                        ]["platform_id"]
                    )
                    for path in paths
                    if (
                        key := _operation_key(
                            path
                        )
                    )
                    is not None
                    and key
                    in operation_metadata
                }
            )
        )

        # 把底层字段变化映射成更高层的战术语义维度
        dimensions = semantic_dimensions(
            paths
        )

        # 保存候选实际修改过的局部 operation key
        local_operations = tuple(
            sorted(
                {
                    key
                    for path in paths
                    if (
                        key := _operation_key(
                            path
                        )
                    )
                    is not None
                }
            )
        )

        # 修改涉及多少个水面攻击
        surface = sum(
            operation_metadata[
                key
            ]["operation_type"]
            == "surface_attack"

            for key in {
                _operation_key(path)
                for path in paths
            }

            if key
            in operation_metadata
        )

        # 修改涉及多少个飞机 sortie
        sortie = sum(
            operation_metadata[
                key
            ]["operation_type"]
            == "sortie"

            for key in {
                _operation_key(path)
                for path in paths
            }

            if key
            in operation_metadata
        )

        # 检查这个候选是否真正符合
        # 当初给它设计的“角色”。
        role_conformance = (
            _role_conformance(
                candidate_id=(
                    candidate.candidate_id
                ),
                intent=intent,
                changed_leaf_count=len(
                    paths
                ),
                operation_count=len(
                    operation_ids
                ),
                local_operations=(
                    local_operations
                ),
                dimensions=dimensions,
                surface_count=surface,
                sortie_count=sortie,
            )
        )

        return CandidateQualityCandidateReport(
            candidate_id=(
                candidate.candidate_id
            ),

            role=str(
                getattr(
                    intent,
                    "role",
                    "unknown",
                )
            ),

            strategy_checksum=(
                candidate.strategy_checksum
            ),

            changed_leaf_count=len(
                paths
            ),

            changed_paths=paths,

            changed_operation_ids=(
                operation_ids
            ),

            changed_platform_ids=(
                platform_ids
            ),

            semantic_dimensions=(
                dimensions
            ),

            surface_operation_count=(
                surface
            ),

            sortie_operation_count=(
                sortie
            ),

            role_conformance=(
                role_conformance
            ),

            # 用三个角度描述这个候选
            # 距离 baseline 有多远。
            baseline_distance={
                "changed_leaf_count": (
                    len(paths)
                ),
                "changed_operation_count": (
                    len(operation_ids)
                ),
                "changed_dimension_count": (
                    len(dimensions)
                ),
            },

            repair_summary=repair_summary,
        )

    @staticmethod
    def _pairwise_reports(
        candidates,
        reports,
    ):
        """对所有候选做两两比较。

        目的不是判断谁更强，
        而是判断：

            candidate_00
            candidate_01
            candidate_02

        是不是真的不同，

        还是 LLM 实际生成了几份非常相似的策略。
        """

        candidate_by_id = {
            item.candidate_id: item
            for item in candidates
        }

        report_by_id = {
            item.candidate_id: item
            for item in reports
        }

        rows = []

        # combinations(..., 2)
        # 会生成所有候选两两组合。
        for (
            left_id,
            right_id,
        ) in combinations(
            sorted(candidate_by_id),
            2,
        ):
            left = candidate_by_id[
                left_id
            ]
            right = candidate_by_id[
                right_id
            ]

            left_report = report_by_id[
                left_id
            ]
            right_report = report_by_id[
                right_id
            ]

            # 两个候选共同修改过哪些字段
            shared = (
                set(
                    left_report.changed_paths
                )
                & set(
                    right_report.changed_paths
                )
            )

            left_payload = (
                left.strategy_spec.to_dict()
            )
            right_payload = (
                right.strategy_spec.to_dict()
            )

            rows.append(
                CandidateQualityPairwiseReport(
                    left_id,
                    right_id,

                    # 修改字段位置有多相似
                    _jaccard(
                        set(
                            left_report.changed_paths
                        ),
                        set(
                            right_report.changed_paths
                        ),
                    ),

                    # 修改 operation 有多相似
                    _jaccard(
                        set(
                            left_report.changed_operation_ids
                        ),
                        set(
                            right_report.changed_operation_ids
                        ),
                    ),

                    # 即使两个候选改的是同一字段，
                    # 也检查最终值是否真的不同。
                    sum(
                        _pointer_value(
                            left_payload,
                            path,
                        )
                        != _pointer_value(
                            right_payload,
                            path,
                        )
                        for path in shared
                    ),

                    # checksum 相同代表两份策略完全一样
                    (
                        left.strategy_checksum
                        == right.strategy_checksum
                    ),
                )
            )

        return tuple(rows)

    @staticmethod
    def _quality_messages(
        reports,
        coverage,
        pairwise,
    ):
        """根据质量规则生成：

        failed：
            会真正阻止候选集合进入下一阶段。

        warnings：
            不阻止流程，但提示候选质量可能不够好。
        """

        failed: list[str] = []
        warnings: list[str] = []

        # -------------------------------------------------
        # 单候选角色检查
        # -------------------------------------------------
        for item in reports:
            if (
                item.role_conformance[
                    "role_adherence"
                ]
                != "full"
            ):
                warnings.append(
                    f"{item.candidate_id}_role_"
                    f"{item.role_conformance['role_adherence']}"
                )

        # -------------------------------------------------
        # 硬规则：
        # 所有候选策略必须真正不同
        # -------------------------------------------------
        checksums = [
            item.strategy_checksum
            for item in reports
        ]

        if (
            len(checksums)
            != len(set(checksums))
        ):
            failed.append(
                "unique_strategy_checksums_required"
            )

        # -------------------------------------------------
        # 以下主要属于候选集合覆盖率警告
        # -------------------------------------------------

        # 整批候选最好至少覆盖 4 个不同 operation
        if (
            len(
                coverage["operation_ids"]
            )
            < 4
        ):
            warnings.append(
                "minimum_batch_operation_coverage"
            )

        # 最好覆盖至少 3 个策略语义维度
        if (
            len(
                coverage[
                    "semantic_dimensions"
                ]
            )
            < 3
        ):
            warnings.append(
                "minimum_batch_dimension_coverage"
            )

        # 最好覆盖至少两类平台
        # 例如 surface + aircraft
        if (
            len(
                coverage[
                    "platform_types"
                ]
            )
            < 2
        ):
            warnings.append(
                "minimum_batch_platform_type_coverage"
            )

        # 至少最好有一个候选同时涉及：
        # 水面攻击 + 飞机 sortie
        if not any(
            item.surface_operation_count
            and item.sortie_operation_count
            for item in reports
        ):
            warnings.append(
                "surface_sortie_candidate_required"
            )

        # 特别检查前三个候选是不是
        # 全部只修改了完全相同的一组 operation。
        first_three = [
            set(
                item.changed_operation_ids
            )
            for item in reports
            if item.candidate_id
            in {
                "candidate_00",
                "candidate_01",
                "candidate_02",
            }
        ]

        if (
            len(first_three) == 3
            and first_three[0]
            == first_three[1]
            == first_three[2]
        ):
            warnings.append(
                "candidate_00_01_02_same_operation_set"
            )

        # 如果任意两个候选修改字段的 Jaccard >= 0.8，
        # 说明两个候选改动位置非常相似。
        if any(
            item.path_jaccard >= 0.8
            for item in pairwise
        ):
            warnings.append(
                "pairwise_path_jaccard_high"
            )

        return failed, warnings


def _operation_metadata(
    baseline: StrategySpec,
    proposal_context: Mapping[
        str,
        Any,
    ],
) -> dict[str, dict[str, str]]:
    """建立策略数组位置与正式 operation 信息之间的映射。

    例如：

        attacks/0
            ↓
        {
            operation_id: surface_attack:attack_01
            platform_id: destroyer_01
            platform_type: surface
        }

    后面看到：

        /attacks/0/fire_distance

    就知道这个字段属于哪个正式作战操作。
    """

    # proposal_context 中的 baseline_operations
    # 本身已经带有正式 operation_id。
    context_by_id = {
        str(
            item.get("operation_id")
        ): item

        for item in proposal_context.get(
            "baseline_operations",
            (),
        )

        if (
            isinstance(
                item,
                Mapping,
            )
            and isinstance(
                item.get(
                    "operation_id"
                ),
                str,
            )
        )
    }

    result: dict[
        str,
        dict[str, str],
    ] = {}

    # -------------------------------------------------
    # 水面攻击
    # -------------------------------------------------
    for (
        index,
        attack,
    ) in enumerate(
        baseline.attacks
    ):
        operation_id = (
            f"surface_attack:"
            f"{attack.attack_id}"
        )

        item = context_by_id.get(
            operation_id,
            {},
        )

        result[
            f"attacks/{index}"
        ] = {
            "operation_id": (
                operation_id
            ),

            "operation_type": (
                "surface_attack"
            ),

            "platform_id": (
                attack.shooter_id
            ),

            # proposal_context 没有明确给出时，
            # 水面攻击默认视作 surface。
            "platform_type": str(
                item.get(
                    "platform_type",
                    "surface",
                )
            ),
        }

    # -------------------------------------------------
    # 飞机 sortie
    # -------------------------------------------------
    for (
        index,
        sortie,
    ) in enumerate(
        baseline.sorties
    ):
        operation_id = (
            f"sortie:"
            f"{sortie.sortie_id}"
        )

        item = context_by_id.get(
            operation_id,
            {},
        )

        result[
            f"sorties/{index}"
        ] = {
            "operation_id": (
                operation_id
            ),

            "operation_type": (
                "sortie"
            ),

            "platform_id": (
                sortie.aircraft_id
            ),

            "platform_type": str(
                item.get(
                    "platform_type",
                    "aircraft",
                )
            ),
        }

    return result


def _patchable_paths(
    proposal_context: Mapping[
        str,
        Any,
    ],
) -> tuple[str, ...]:
    """读取真正允许候选修改的字段白名单。

    这里绝不能相信 LLM 自己声称：

        “我只修改了这些字段”

    而是读取系统已经冻结好的：

        baseline_operations
            ↓
        patchable_paths

    这样质量检查基于系统事实，而不是 LLM 描述。
    """

    values = {
        str(path)

        for item
        in proposal_context.get(
            "baseline_operations",
            (),
        )

        if isinstance(
            item,
            Mapping,
        )

        for path in item.get(
            "patchable_paths",
            (),
        )

        if (
            isinstance(path, str)
            and path.startswith("/")
        )
    }

    # 如果 proposal_context 连字段白名单都没有，
    # 就无法可靠判断候选到底修改了什么。
    if not values:
        raise ValueError(
            "candidate_quality_context_missing_patchable_paths"
        )

    return tuple(
        sorted(values)
    )


def _role_conformance(
    *,
    candidate_id,
    intent,
    changed_leaf_count,
    operation_count,
    local_operations,
    dimensions,
    surface_count,
    sortie_count,
):
    """判断候选是否符合生成它时设定的角色要求。

    例如某个候选的 intent 可能要求：

        至少改 3 个字段
        最多改 6 个字段
        至少涉及 2 个 operation
        必须涉及 aircraft
        优先探索 timing 维度

    这里就是用实际 Candidate diff 去核对这些要求。
    """

    violations: list[str] = []

    # 连 intent 都不存在，
    # 就无法证明候选符合预定角色。
    if intent is None:
        violations.append(
            "intent_missing"
        )

        return {
            "role_adherence": "weak",
            "warnings": violations,
            "repair_recommended": True,
        }

    # -------------------------------------------------
    # 读取候选角色约束
    # -------------------------------------------------

    minimum = int(
        getattr(
            intent,
            "min_changed_leaves",
            getattr(
                intent,
                "min_changes",
                1,
            ),
        )
    )

    maximum = int(
        getattr(
            intent,
            "max_changed_leaves",
            getattr(
                intent,
                "max_changes",
                changed_leaf_count,
            ),
        )
    )

    min_operations = int(
        getattr(
            intent,
            "min_operations",
            1,
        )
    )

    min_dimensions = int(
        getattr(
            intent,
            "min_dimensions",
            1,
        )
    )

    max_operations = getattr(
        intent,
        "max_operations",
        None,
    )

    max_dimensions = getattr(
        intent,
        "max_dimensions",
        None,
    )

    # -------------------------------------------------
    # 检查实际改动字段数量
    # -------------------------------------------------
    if not (
        minimum
        <= changed_leaf_count
        <= maximum
    ):
        violations.append(
            "changed_leaf_count"
        )

    # -------------------------------------------------
    # 检查涉及 operation 数量
    # -------------------------------------------------
    if (
        operation_count
        < min_operations
        or (
            max_operations is not None
            and operation_count
            > int(max_operations)
        )
    ):
        violations.append(
            "operation_count"
        )

    # -------------------------------------------------
    # 检查覆盖策略维度数量
    # -------------------------------------------------
    if (
        len(dimensions)
        < min_dimensions
        or (
            max_dimensions is not None
            and len(dimensions)
            > int(max_dimensions)
        )
    ):
        violations.append(
            "dimension_count"
        )

    # -------------------------------------------------
    # 某些角色要求必须修改水面攻击
    # -------------------------------------------------
    if (
        bool(
            getattr(
                intent,
                "require_surface",
                False,
            )
        )
        and not surface_count
    ):
        violations.append(
            "surface_required"
        )

    # -------------------------------------------------
    # 某些角色要求必须修改飞机 sortie
    # -------------------------------------------------
    if (
        bool(
            getattr(
                intent,
                "require_sortie",
                False,
            )
        )
        and not sortie_count
    ):
        violations.append(
            "sortie_required"
        )

    # -------------------------------------------------
    # 检查候选有没有真正探索预期策略维度
    # -------------------------------------------------
    preferred = tuple(
        getattr(
            intent,
            "strategy_dimensions",
            (),
        )
    )

    if (
        preferred
        and not (
            set(dimensions)
            & set(preferred)
        )
    ):
        violations.append(
            "preferred_dimension_missing"
        )

    # -------------------------------------------------
    # 如果这个候选角色要求针对历史失败进行探索，
    # 那么它必须真的碰到相应 operation 或策略维度。
    # -------------------------------------------------
    if (
        getattr(
            intent,
            "failure_profile_mode",
            "unavailable",
        )
        == "required"
    ):
        failure_operations = set(
            getattr(
                intent,
                "failure_operation_ids",
                (),
            )
        )

        failure_dimensions = set(
            getattr(
                intent,
                "failure_semantic_dimensions",
                (),
            )
        )

        if not (
            failure_operations
            & set(local_operations)
            or failure_dimensions
            & set(dimensions)
        ):
            violations.append(
                "failure_profile_not_covered"
            )

    # -------------------------------------------------
    # 根据违规数量给角色符合度分级
    # -------------------------------------------------
    adherence = (
        "full"
        if not violations

        else "partial"
        if len(violations) == 1

        else "weak"
    )

    return {
        "role_adherence": adherence,

        "warnings": sorted(
            violations
        ),

        # 严重偏离角色时，
        # 可以建议上层重新修复/重新生成候选。
        "repair_recommended": (
            adherence == "weak"
        ),

        "candidate_id": (
            candidate_id
        ),
    }


def _interpretability(
    operation_count: int,
    dimension_count: int,
) -> dict[str, str]:
    """判断这个候选最终实验结果有多容易解释。

    原理很简单：

        改得越少
            ↓
        越容易知道“到底是什么改动导致结果变化”

    例如：

        只改一个 operation + 一个策略维度
            → 很容易做单因素解释

        一口气改多个 operation + 多个维度
            → 即使分数变好了，也很难判断原因
    """

    # 最容易解释：
    # 一个 operation + 一个维度
    if (
        operation_count == 1
        and dimension_count == 1
    ):
        return {
            "level": "high",
            "claim_scope": (
                "single_factor_hypothesis"
            ),
        }

    # 多个 operation，但都是同一个策略维度
    if (
        operation_count > 1
        and dimension_count == 1
    ):
        return {
            "level": "medium",
            "claim_scope": (
                "same_dimension_pattern"
            ),
        }

    # 一个 operation 内同时修改多个维度
    if operation_count == 1:
        return {
            "level": "medium",
            "claim_scope": (
                "combined_strategy_hypothesis"
            ),
        }

    # 多 operation + 多维度：
    # 只能说整体策略组合表现如何，
    # 很难把收益归因到单个因素。
    return {
        "level": "low",
        "claim_scope": (
            "combined_strategy_observation"
        ),
    }