"""构建供策略候选 Agent 使用的紧凑、确定性战术上下文。

这个模块不是直接生成候选策略，而是先把完整系统状态“压缩”为：

    场景摘要
    baseline 当前作战操作
    当前目标分配
    操作之间的耦合关系
    4个候选角色要求
    已经接受的候选摘要
    历史失败画像

然后再交给候选策略 LLM。

为什么要这样设计：

    不直接把完整 StrategySpec、Lua、评分逻辑、原始日志交给 LLM，
    而是只提供它真正需要的战术信息。

这样可以：

    1. 减少 Prompt 噪声；
    2. 避免 LLM 修改系统内部字段；
    3. 保证不同调用看到的是稳定、统一的上下文；
    4. 可以通过 checksum 判断上下文是否发生变化。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cmo_lua_agent.contract.strategy_models import ScenarioDefinition, StrategySpec
from cmo_lua_agent.generation.runtime_models import canonical_json, canonical_sha256
from cmo_lua_agent.optimization.proposal_models import (
    AcceptedCandidateSummary,
    CandidateRoleSpec,
)
from cmo_lua_agent.optimization.strategy_dimensions import semantic_dimension
from cmo_lua_agent.optimization.strategy_patch import PatchableLeaf


def _operation_key(path: str) -> str | None:
    """从 StrategySpec 字段路径中提取所属 operation。

    例如：

        /attacks/0/fire_quantity
            ↓
        attacks/0

        /sorties/1/air_tactics/attack_range_nm
            ↓
        sorties/1

    后面可以把 PatchableLeaf 归到对应攻击/出动任务。
    """

    tokens = path.strip("/").split("/")

    if len(tokens) >= 2 and tokens[0] in {"attacks", "sorties"} and tokens[1].isdecimal():
        return f"{tokens[0]}/{tokens[1]}"

    return None


@dataclass(frozen=True, slots=True)
class ProposalTacticalContext:
    """提供给策略 Agent 的紧凑战术上下文。

    注意：
    这里不是完整 Scenario / Strategy 的副本，
    而是专门为候选策略生成裁剪后的信息。
    """

    # 场景基本信息：
    # scenario_id、双方单位、平台类型等
    scenario_summary: dict[str, object]

    # baseline 当前有哪些攻击 / sortie，
    # 每个操作当前目标、参数以及允许修改哪些字段
    baseline_operations: tuple[dict[str, object], ...]

    # 当前蓝方目标分别被哪些攻击操作分配
    target_summary: tuple[dict[str, object], ...]

    # 操作之间的关联关系：
    # 同目标、同平台、水面攻击、空中出动等
    coupling_groups: dict[str, object]

    # 每个候选角色的系统硬约束
    role_requirements: tuple[dict[str, object], ...]

    # 已经接受的候选策略摘要
    #
    # 用于避免后面的候选继续生成高度重复的策略。
    accepted_candidate_summaries: tuple[dict[str, object], ...]

    # 上一轮失败操作 / 失败维度摘要
    #
    # 主要供 candidate_01 robust_repair 使用。
    failure_profile: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        """转换成稳定的普通字典，用于 Prompt / 持久化 / checksum。"""

        return {
            "scenario_summary": self.scenario_summary,
            "baseline_operations": list(self.baseline_operations),
            "target_summary": list(self.target_summary),
            "coupling_groups": self.coupling_groups,
            "role_requirements": list(self.role_requirements),
            "accepted_candidate_summaries": list(self.accepted_candidate_summaries),
            "failure_profile": self.failure_profile,
        }

    @property
    def canonical_json(self) -> str:
        """生成字段顺序稳定的规范 JSON。

        这样同样的战术上下文每次生成的文本都完全一致，
        方便 Prompt 缓存、审计和复现。
        """

        return canonical_json(self.to_dict())

    @property
    def checksum(self) -> str:
        """计算当前战术上下文的内容指纹。

        如果 checksum 没变，
        就说明提供给候选 Agent 的正式上下文没有变化。
        """

        return canonical_sha256(self.to_dict())


class ProposalTacticalContextBuilder:
    """构建策略候选 Agent 能看到的战术上下文。

    这是一个纯数据投影层：

        Scenario + Baseline + Patch Catalog
            ↓
        提取真正有用的战术信息
            ↓
        ProposalTacticalContext

    它不会暴露：

        完整 StrategySpec
        Lua代码
        评分实现
        原始日志/原始证据

    目的是把“Agent能看到什么”限制在明确边界内。
    """

    def build(
        self,
        *,
        scenario: ScenarioDefinition,
        baseline: StrategySpec,
        patch_catalog: tuple[PatchableLeaf, ...],
        role_specs: tuple[CandidateRoleSpec, ...],
        accepted_candidates: tuple[AcceptedCandidateSummary, ...],
    ) -> ProposalTacticalContext:
        """从正式系统对象构建候选生成上下文。"""

        # baseline 必须属于当前场景。
        #
        # 防止拿其他场景的策略生成候选。
        if scenario.scenario_id != baseline.scenario_id:
            raise ValueError("scenario_baseline_mismatch")

        # unit_id → Unit
        #
        # 后续构建 operation 时可以快速找到平台信息。
        units = scenario.unit_by_id()

        # -------------------------------------------------
        # 把可修改字段按照 operation 分组
        # -------------------------------------------------
        #
        # 例如：
        #
        # /attacks/0/fire_quantity
        # /attacks/0/delay_seconds
        #
        # 都会被放到：
        #
        # attacks/0
        paths_by_operation: dict[str, list[PatchableLeaf]] = {}

        for leaf in patch_catalog:
            operation = _operation_key(leaf.path)

            if operation is not None:
                paths_by_operation.setdefault(operation, []).append(leaf)

        operations: list[dict[str, object]] = []

        # 数组位置 → 稳定 operation_id
        #
        # 例如：
        # attacks/0 → surface_attack:attack_01
        #
        # 后面即使数组位置概念消失，
        # 也可以用稳定 operation_id 做追踪。
        stable_operation_ids: dict[str, str] = {}

        # -------------------------------------------------
        # 把 baseline 水面攻击转换成紧凑 operation 摘要
        # -------------------------------------------------
        for index, attack in enumerate(baseline.attacks):
            operation_key = f"attacks/{index}"

            stable_operation_ids[operation_key] = f"surface_attack:{attack.attack_id}"

            operations.append(
                self._surface_operation(
                    operation_key=operation_key,
                    operation_id=stable_operation_ids[operation_key],
                    platform=units[attack.shooter_id],
                    target_id=attack.target_ids[0],
                    delay_seconds=attack.delay_seconds,
                    fire_quantity=attack.fire_quantity,
                    reserve_quantity=attack.reserve_quantity,
                    weapon_selection=attack.weapon_selection,
                    leaves=paths_by_operation.get(operation_key, []),
                )
            )

        # -------------------------------------------------
        # 把 baseline 飞机 sortie 转换成紧凑 operation 摘要
        # -------------------------------------------------
        for index, sortie in enumerate(baseline.sorties):
            operation_key = f"sorties/{index}"

            stable_operation_ids[operation_key] = f"sortie:{sortie.sortie_id}"

            operations.append(
                self._sortie_operation(
                    operation_key=operation_key,
                    operation_id=stable_operation_ids[operation_key],
                    platform=units[sortie.aircraft_id],
                    target_id=sortie.target_id,
                    delay_seconds=sortie.fire_delay_seconds,
                    return_delay_seconds=sortie.return_delay_seconds,
                    leaves=paths_by_operation.get(operation_key, []),
                    route=sortie.route,
                )
            )

        # operation 使用稳定ID排序，
        # 保证每次生成上下文的顺序一致。
        operations.sort(key=lambda item: str(item["operation_id"]))

        # 根据当前 operation 统计目标分配情况
        target_summary = self._target_summary(scenario, operations)

        return ProposalTacticalContext(
            # 场景总体摘要
            scenario_summary=self._scenario_summary(scenario),

            # baseline 当前执行操作
            baseline_operations=tuple(operations),

            # 当前目标分配情况
            target_summary=target_summary,

            # operation 之间的协同/耦合关系
            coupling_groups=self._coupling_groups(operations),

            # 4个候选角色分别必须满足什么要求
            role_requirements=tuple(self._role_requirement(item) for item in role_specs),

            # 已经接受过哪些候选，避免重复生成
            accepted_candidate_summaries=tuple(
                self._accepted_summary(item, stable_operation_ids)
                for item in accepted_candidates
            ),

            # 如果有历史失败，则提供给 robust_repair 候选
            failure_profile=self._failure_profile(role_specs),
        )

    @staticmethod
    def _scenario_summary(scenario: ScenarioDefinition) -> dict[str, object]:
        """生成最精简的场景结构摘要。

        不把完整 Unit 对象交给 LLM，
        这里只告诉它：

            哪个阵营
            有哪些单位
            每个单位是什么平台类型
        """

        by_side: dict[str, list[dict[str, str]]] = {}

        for unit in sorted(scenario.units, key=lambda item: (item.side_id, item.unit_id)):
            by_side.setdefault(unit.side_id, []).append(
                {
                    "unit_id": unit.unit_id,
                    "platform_type": unit.platform_type,
                }
            )

        sides = sorted(by_side)

        return {
            "scenario_id": scenario.scenario_id,

            # 当前代码默认识别 red / blue 两个标准阵营ID
            "red_side_id": "red" if "red" in by_side else None,
            "blue_side_id": "blue" if "blue" in by_side else None,

            # 每个阵营有哪些平台
            "sides": {
                side: by_side[side]
                for side in sides
            },
        }

    @staticmethod
    def _surface_operation(**values: Any) -> dict[str, object]:
        """把一条水面攻击压缩成给 Agent 使用的战术摘要。"""

        leaves = values.pop("leaves")
        platform = values.pop("platform")

        return {
            # 稳定操作ID
            "operation_id": values["operation_id"],

            "operation_type": "surface_attack",

            # 哪个平台执行攻击
            "platform_id": platform.unit_id,
            "platform_type": platform.platform_type,

            # baseline 当前攻击哪个目标
            "current_target_id": values["target_id"],

            # baseline 当前攻击参数
            "delay_seconds": values["delay_seconds"],
            "fire_quantity": values["fire_quantity"],
            "reserve_quantity": values["reserve_quantity"],
            "weapon_selection": values["weapon_selection"],

            # 这个 operation 当前真正允许修改哪些战术维度
            #
            # 例如：
            # fire_quantity
            # attack_timing
            # target_assignment
            "patchable_dimensions": sorted({
                semantic_dimension(leaf.path)
                for leaf in leaves
            }),

            # 这个 operation 具体允许修改哪些字段路径
            "patchable_paths": sorted(
                leaf.path
                for leaf in leaves
            ),
        }

    @staticmethod
    def _sortie_operation(**values: Any) -> dict[str, object]:
        """把飞机 sortie 压缩成给 Agent 使用的战术摘要。"""

        leaves = values.pop("leaves")
        platform = values.pop("platform")
        route = values.pop("route")

        return {
            "operation_id": values["operation_id"],
            "operation_type": "sortie",

            # 执行这次 sortie 的飞机
            "platform_id": platform.unit_id,
            "platform_type": platform.platform_type,

            # baseline 当前攻击目标
            "current_target_id": values["target_id"],

            # 当前攻击时机
            "delay_seconds": values["delay_seconds"],

            # sortie 当前使用自动武器选择，
            # 因此这里没有固定 fire_quantity / reserve_quantity
            "fire_quantity": None,
            "reserve_quantity": None,
            "weapon_selection": "auto",

            # 不把完整航路所有航点都塞给 Agent，
            # 只提供一个紧凑摘要。
            "route_summary": {
                "waypoint_count": len(route),

                # 起始航点
                "first": {
                    "latitude": route[0].latitude,
                    "longitude": route[0].longitude,
                },

                # 最后航点
                "last": {
                    "latitude": route[-1].latitude,
                    "longitude": route[-1].longitude,
                },

                # 返航等待时间
                "return_delay_seconds": values["return_delay_seconds"],
            },

            # 当前 sortie 可以探索哪些战术维度
            "patchable_dimensions": sorted({
                semantic_dimension(leaf.path)
                for leaf in leaves
            }),

            # 当前 sortie 真正允许修改哪些字段
            "patchable_paths": sorted(
                leaf.path
                for leaf in leaves
            ),
        }

    @staticmethod
    def _target_summary(
        scenario: ScenarioDefinition,
        operations: list[dict[str, object]]
    ) -> tuple[dict[str, object], ...]:
        """统计当前每个目标被多少个 operation 分配。

        例如：

            blue_ship_01
                ← surface_attack:attack_01
                ← sortie:sortie_02

        这样候选 Agent 可以判断：

            某个目标是否被过度集中攻击；
            是否存在完全没有被分配的目标；
            是否应该重新进行目标分配。
        """

        assignments: dict[str, list[str]] = {}

        for operation in operations:
            assignments.setdefault(
                str(operation["current_target_id"]),
                []
            ).append(
                str(operation["operation_id"])
            )

        return tuple(
            {
                "target_id": unit.unit_id,
                "platform_type": unit.platform_type,

                # 当前有哪些 operation 攻击这个目标
                "current_assignment_operations": sorted(
                    assignments.get(unit.unit_id, [])
                ),

                # 当前这个目标被分配了多少次攻击
                "current_assignment_count": len(
                    assignments.get(unit.unit_id, [])
                ),
            }

            for unit in sorted(
                scenario.units,
                key=lambda item: item.unit_id
            )

            # 当前只把蓝方单位作为候选攻击目标摘要
            if unit.side_id == "blue"
        )

    @staticmethod
    def _coupling_groups(operations: list[dict[str, object]]) -> dict[str, object]:
        """整理 operation 之间的协同关系。

        主要告诉候选 Agent：

            哪些 operation 攻击同一个目标；
            哪些 operation 来自同一个平台；
            哪些是水面攻击；
            哪些是飞机 sortie。

        这样 candidate_02 coordinated_explore
        才有条件设计跨 operation 的协同策略。
        """

        # target_id → operation_ids
        by_target: dict[str, list[str]] = {}

        # platform_id → operation_ids
        by_platform: dict[str, list[str]] = {}

        surface: list[str] = []
        sortie: list[str] = []

        for operation in operations:
            operation_id = str(operation["operation_id"])

            by_target.setdefault(
                str(operation["current_target_id"]),
                []
            ).append(operation_id)

            by_platform.setdefault(
                str(operation["platform_id"]),
                []
            ).append(operation_id)

            # 分类记录水面攻击 / 空中 sortie
            (
                surface
                if operation["operation_type"] == "surface_attack"
                else sortie
            ).append(operation_id)

        return {
            # 哪些 operation 当前攻击同一个目标
            "same_target_operations": {
                target: sorted(values)
                for target, values in sorted(by_target.items())
            },

            # 哪些 operation 由同一个平台执行
            "same_platform_operations": {
                platform: sorted(values)
                for platform, values in sorted(by_platform.items())
            },

            # 所有水面攻击 operation
            "surface_operations": sorted(surface),

            # 所有空中 sortie operation
            "sortie_operations": sorted(sortie),
        }

    @staticmethod
    def _role_requirement(spec: CandidateRoleSpec) -> dict[str, object]:
        """把系统定义的候选角色硬约束提供给策略 Agent。

        LLM 可以决定具体怎么改，
        但不能自己降低这些约束。
        """

        return {
            "candidate_id": spec.candidate_id,
            "role": spec.role,

            # 最少 / 最多要修改多少叶子字段
            "min_changed_leaves": spec.min_changed_leaves,
            "max_changed_leaves": spec.max_changed_leaves,

            # 至少涉及多少个 operation
            "min_operations": spec.min_operations,

            # 至少覆盖多少种战术维度
            "min_dimensions": spec.min_dimensions,

            # 是否要求同时涉及水面 / 空中
            "require_surface": spec.require_surface,
            "require_sortie": spec.require_sortie,
        }

    @staticmethod
    def _accepted_summary(
        summary: AcceptedCandidateSummary,
        stable_operation_ids: dict[str, str]
    ) -> dict[str, object]:
        """把已经接受的候选压缩成摘要。

        后续候选 Agent 可以看到前面候选已经探索过什么，
        避免 candidate_01 / 02 / 03 继续生成高度重复方案。
        """

        return {
            "candidate_id": summary.candidate_id,

            # 把 attacks/0 / sorties/0
            # 转换成稳定 operation_id
            "changed_operation_ids": sorted(
                stable_operation_ids.get(value, value)
                for value in summary.changed_operation_ids
            ),

            # 这个候选已经探索过哪些战术维度
            "semantic_dimensions": sorted(
                summary.strategy_dimensions
            ),

            # 实际修改过哪些字段
            "changed_paths": sorted(
                summary.changed_paths
            ),

            # 如果修改过目标分配，
            # 这里保留目标调整摘要
            "target_assignment_summary": sorted(
                summary.target_assignment_summary
            ),
        }

    @staticmethod
    def _failure_profile(role_specs: tuple[CandidateRoleSpec, ...]) -> dict[str, object]:
        """提取上一轮失败画像，主要提供给 candidate_01 robust_repair。

        failure_profile 描述的是：

            哪些 operation 曾经出问题；
            哪些战术维度值得重点修复。

        它不是原始日志，而是已经整理好的结构化失败摘要。
        """

        # candidate_01 被固定定义为 robust_repair
        repair = next(
            item
            for item in role_specs
            if item.candidate_id == "candidate_01"
        )

        # 如果当前没有可用历史失败信息，
        # 明确告诉 Agent failure profile 不存在。
        if repair.failure_profile_mode != "required":
            return {
                "available": False,
                "source_checksum": None,
                "operation_ids": [],
                "semantic_dimensions": [],
            }

        # 有历史失败信息时，
        # 只暴露结构化摘要，不提供原始日志。
        return {
            "available": True,

            # 失败画像来源的 checksum，
            # 用于保证它对应的是正确那一轮历史证据。
            "source_checksum": repair.failure_profile_source_checksum,

            # 哪些 operation 曾经出问题
            "operation_ids": sorted(
                repair.failure_operation_ids
            ),

            # 哪些策略维度与失败相关
            "semantic_dimensions": sorted(
                repair.failure_semantic_dimensions
            ),
        }