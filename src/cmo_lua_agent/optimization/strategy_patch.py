"""将候选策略 Patch 安全组装回完整 StrategySpec。

核心职责：

    baseline StrategySpec
        ↓
    找出真正允许修改的标量字段
        ↓
    给每个字段补充类型 / 最小值 / 最大值 / 可选值约束
        ↓
    LLM 提交 CandidatePatch
        ↓
    确定性校验并应用 Patch
        ↓
    重新构造 StrategySpec
        ↓
    再次计算真实 diff，确认没有偷偷改到其他字段

这里不让 LLM 直接修改完整策略对象，
目的是把修改范围严格限制在“系统明确允许且 Runtime 真正可执行”的字段上。
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from cmo_lua_agent.contract.strategy_models import ScenarioDefinition, StrategySpec, strategy_spec_from_dict
from cmo_lua_agent.optimization.candidate_set_validator import strategy_leaf_diff
from cmo_lua_agent.optimization.executable_patch_paths import (
    is_executable_patch_path,
    non_executable_patch_diagnostics,
)
from cmo_lua_agent.optimization.tactical_capability_registry import TacticalCapabilityRegistry
from cmo_lua_agent.optimization.proposal_models import AssembledStrategyPatch, CandidatePatch, JsonScalar, ProposalContractError, MAX_EFFECTIVE_PATCH_LEAVES, MIN_EFFECTIVE_PATCH_LEAVES


# 这些字段属于策略/场景的稳定身份字段，禁止候选 Patch 修改。
#
# 例如：
# scenario_id、attack_id、weapon_dbid
#
# 一旦允许 LLM 修改这些字段，就不再是“调战术参数”，
# 而是在改变场景事实或对象身份。
_STABLE_FIELD_NAMES = {"scenario_id", "attack_id", "sortie_id", "shooter_id", "aircraft_id", "base_unit_id", "weapon_dbid"}


@dataclass(frozen=True, slots=True)
class PatchableLeaf:
    """一个真正允许候选策略修改的叶子字段。"""

    # StrategySpec 中的完整 JSON Pointer 路径
    path: str

    # baseline 当前值
    current_value: JsonScalar

    # 当前值类型，用于防止 int 被改成 str 等类型漂移
    value_type: str

    # 数值下界
    minimum: int | float | None = None

    # 数值上界
    maximum: int | float | None = None

    # 枚举类字段允许使用的固定值集合
    allowed_values: tuple[JsonScalar, ...] = ()

    def to_prompt_dict(self) -> dict[str, Any]:
        """转换成可以安全提供给 LLM 的字段约束描述。

        LLM 不需要看到完整 StrategySpec，
        只需要知道：

            path
            当前值
            类型
            合法范围/合法候选值
        """

        payload: dict[str, Any] = {
            "path": self.path,
            "current_value": self.current_value,
            "value_type": self.value_type,
        }

        if self.minimum is not None:
            payload["minimum"] = self.minimum

        if self.maximum is not None:
            payload["maximum"] = self.maximum

        if self.allowed_values:
            payload["allowed_values"] = list(self.allowed_values)

        return payload


def build_patchable_leaf_catalog(*, baseline: StrategySpec, scenario: ScenarioDefinition, allowed_paths: tuple[str, ...]) -> tuple[PatchableLeaf, ...]:
    """建立候选生成阶段真正允许修改的字段目录。

    这里会同时检查：

        路径是否真的可执行；
        是否误碰稳定ID字段；
        字段是不是标量；
        该字段允许的值范围是什么。

    最终得到的 catalog 才能交给 LLM 生成 Patch。
    """

    # baseline 必须属于当前场景，防止拿错策略做候选生成
    if baseline.scenario_id != scenario.scenario_id:
        raise ProposalContractError("scenario_baseline_mismatch")

    # 允许修改路径本身不能重复
    if len(set(allowed_paths)) != len(allowed_paths):
        raise ProposalContractError("duplicate_allowed_patch_path")

    payload = baseline.to_dict()
    units = scenario.unit_by_id()
    catalog: list[PatchableLeaf] = []

    # allowed_paths 还要再经过一次“Runtime 是否真的能执行”的过滤。
    #
    # StrategySpec 里存在某个字段，
    # 不代表生成出的 Lua / Runtime 一定会使用它。
    executable_paths = tuple(
        path for path in sorted(set(allowed_paths)) if is_executable_patch_path(path)
    )

    for path in executable_paths:
        tokens = _tokens(path)

        # 禁止修改稳定身份字段
        if not tokens or tokens[-1] in _STABLE_FIELD_NAMES:
            raise ProposalContractError("stable_field_not_patchable")

        # 从 baseline 中取得这个字段当前值
        value = _get(payload, tokens)

        # 候选 Patch 只允许修改叶子标量，
        # 不允许整体替换 dict/list 等复杂结构。
        if type(value) not in (str, int, float, bool):
            raise ProposalContractError("patch_path_not_scalar")

        # 根据字段性质补充合法范围
        catalog.append(_leaf_constraint(path, value, payload, units))

    return tuple(catalog)


class StrategyPatchAssembler:
    """把受限 CandidatePatch 安全应用到 baseline，并构造新的 StrategySpec。"""

    def __init__(self, *, baseline: StrategySpec, catalog: tuple[PatchableLeaf, ...]) -> None:
        self._baseline = baseline

        # path → PatchableLeaf，方便 Patch 应用时 O(1) 查找
        self._catalog = {leaf.path: leaf for leaf in catalog}

    @property
    def catalog(self) -> tuple[PatchableLeaf, ...]:
        """返回稳定排序后的可修改字段目录。"""

        return tuple(self._catalog[path] for path in sorted(self._catalog))

    def assemble(self, patch: CandidatePatch) -> AssembledStrategyPatch:
        """校验并真正应用候选 Patch。"""

        # 第一层：路径必须属于 Runtime 真正支持的可执行字段
        validate_patch_paths_executable(patch)

        # 防止候选什么都不改，或者一次修改太多失去可解释性
        if not MIN_EFFECTIVE_PATCH_LEAVES <= len(patch.changes) <= MAX_EFFECTIVE_PATCH_LEAVES:
            raise ProposalContractError("candidate_change_count_out_of_bounds")

        # 深拷贝 baseline，
        # 后续修改只发生在副本上，不污染原始策略。
        payload = deepcopy(self._baseline.to_dict())

        validated: list[tuple[Any, PatchableLeaf]] = []

        # 记录“虽然提交了Patch，但值其实和baseline一样”的无效修改
        no_effective_changes: list[dict[str, JsonScalar | str]] = []

        for operation in patch.changes:
            # Patch 只能修改 catalog 中明确登记过的字段
            leaf = self._catalog.get(operation.path)

            if leaf is None:
                raise ProposalContractError("path_not_catalogued")

            # 类型必须完全一致。
            #
            # 例如 baseline 是 int，
            # 就不能让 LLM 提交 "100" 这种 str。
            if type(operation.value) is not type(leaf.current_value):
                raise ProposalContractError("scalar_type_mismatch")

            # 检查范围 / 枚举值是否合法
            self._validate_value(leaf, operation.value)

            validated.append((operation, leaf))

            # 新值与旧值相同，不算真正的候选变化
            if operation.value == leaf.current_value:
                no_effective_changes.append({
                    "path": operation.path,
                    "baseline_value": leaf.current_value,
                    "proposed_value": operation.value,
                })

        # 不允许 LLM 用“没改任何东西”的假 Patch 占一个候选名额
        if no_effective_changes:
            first = no_effective_changes[0]

            raise ProposalContractError(
                "no_effective_change",
                diagnostics={
                    **first,
                    "no_effective_changes": no_effective_changes,
                },
            )

        expected_paths: list[str] = []

        # 真正把经过校验的 Patch 写入策略副本
        for operation, leaf in validated:
            _set(payload, _tokens(operation.path), operation.value)
            expected_paths.append(operation.path)

        try:
            # Patch 应用完成后重新经过正式 StrategySpec 构造器。
            #
            # 这样可以再次利用 StrategySpec 自己的结构/业务校验，
            # 而不是把一个随便修改过的 dict 直接当成合法策略。
            strategy = strategy_spec_from_dict(payload)

        except (KeyError, TypeError, ValueError) as error:
            raise ProposalContractError("strategy_rebuild_failed", str(error)) from error

        # 重新从 baseline 和最终 strategy 计算真实 diff。
        #
        # 不能只相信 LLM 声称“我改了这些路径”，
        # 必须让系统自己算实际发生了什么。
        actual_paths = strategy_leaf_diff(self._baseline, strategy, tuple(self._catalog))

        # 如果实际变化和提交 Patch 不一致，
        # 说明组装过程出现了额外副作用，立即拒绝。
        if tuple(sorted(expected_paths)) != actual_paths:
            raise ProposalContractError("actual_diff_mismatch")

        return AssembledStrategyPatch(strategy=strategy, changed_paths=actual_paths)

    @staticmethod
    def _validate_value(leaf: PatchableLeaf, value: JsonScalar) -> None:
        """检查候选值是否符合该字段的确定性约束。"""

        # 枚举字段只能从允许集合中选择
        if leaf.allowed_values and value not in leaf.allowed_values:
            raise ProposalContractError("value_not_allowed")

        # 数值不能低于合法下限
        if leaf.minimum is not None and value < leaf.minimum:  # type: ignore[operator]
            raise ProposalContractError("value_below_minimum")

        # 数值不能超过合法上限
        if leaf.maximum is not None and value > leaf.maximum:  # type: ignore[operator]
            raise ProposalContractError("value_above_maximum")


def validate_patch_paths_executable(patch: CandidatePatch) -> None:
    """在真正应用 Patch 前，再检查所有路径是否可以被 Runtime 执行。

    这是为了防止出现：

        StrategySpec 改成功了
        ↓
        但 Lua 根本不会使用这个字段

    这种“看起来形成了新候选，实际上仿真行为没变化”的假候选。
    """

    for change in patch.changes:
        diagnostics = non_executable_patch_diagnostics(
            path=change.path, candidate_id=patch.candidate_id
        )

        if diagnostics is not None:
            raise ProposalContractError(
                "patch_path_not_executable", diagnostics=diagnostics
            )


def _leaf_constraint(path: str, value: JsonScalar, payload: dict[str, Any], units: dict[str, Any]) -> PatchableLeaf:
    """根据字段类型生成对应的合法取值范围。"""

    # 优先查看 TacticalCapabilityRegistry。
    #
    # 注册表是正式战术参数的权威来源，
    # 例如 attack_range_nm 的合法范围由 Registry 决定。
    capability = TacticalCapabilityRegistry.default().capability_for_path(path)

    if capability is not None:
        return PatchableLeaf(
            path, value, type(value).__name__, capability.minimum, capability.maximum
        )

    tokens = _tokens(path)

    # 经纬度使用现实合法范围
    if tokens[-1] in {"latitude", "longitude"}:
        return PatchableLeaf(path, value, type(value).__name__, -90 if tokens[-1] == "latitude" else -180, 90 if tokens[-1] == "latitude" else 180)

    # 时间类参数统一限制在 0~24小时
    if tokens[-1] in {"delay_seconds", "fire_delay_seconds", "return_delay_seconds"}:
        return PatchableLeaf(path, value, type(value).__name__, 0, 86400)

    # 发射数量 / 预留数量不能超过平台实际库存
    if tokens[-1] in {"fire_quantity", "reserve_quantity"}:
        maximum = _quantity_maximum(tokens, payload, units)
        return PatchableLeaf(path, value, type(value).__name__, 0, maximum)

    # 目标字段不能填任意字符串，
    # 只能从当前场景真实存在的敌方单位中选择。
    if tokens[-1] in {"target_id"} or "target_ids" in tokens:
        allowed = _enemy_targets(tokens, payload, units)
        return PatchableLeaf(path, value, type(value).__name__, allowed_values=allowed)

    # 普通数值字段给一个保守通用范围
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return PatchableLeaf(path, value, type(value).__name__, 0, 86400)

    return PatchableLeaf(path, value, type(value).__name__)


def _quantity_maximum(tokens: list[str], payload: dict[str, Any], units: dict[str, Any]) -> int:
    """根据真实武器库存计算 fire_quantity / reserve_quantity 的最大合法值。"""

    try:
        # 从路径中确定当前 attack 的数组下标
        index = int(tokens[1])

        attack = payload["attacks"][index]

        # 找到执行此次攻击的平台
        unit = units[attack["shooter_id"]]

        if attack.get("weapon_selection", "explicit") == "auto":
            # 自动选武器时没有固定 weapon_dbid。
            #
            # 如果平台只有一种武器，可以安全使用这份库存作为上限；
            # 如果有多种武器，则无法确定最终选哪一个，
            # 因此退回 baseline 当前数量作为保守上限。
            if len(unit.weapon_inventory) == 1:
                inventory = unit.weapon_inventory[0]
            else:
                return int(attack["fire_quantity"])
        else:
            # 显式指定武器时，
            # 根据 weapon_dbid 找到对应库存。
            inventory = next(
                item
                for item in unit.weapon_inventory
                if item.weapon_dbid == attack["weapon_dbid"]
            )

        # fire_quantity 最大不能吃掉 reserve_quantity
        if tokens[-1] == "fire_quantity":
            return inventory.max_quantity - attack["reserve_quantity"]

        # reserve_quantity 最大不能吃掉已经决定发射的数量
        return inventory.max_quantity - attack["fire_quantity"]

    except (IndexError, KeyError, StopIteration, ValueError):
        # 无法可靠获得库存约束时宁愿拒绝，
        # 不猜一个最大值。
        raise ProposalContractError("inventory_constraint_unavailable") from None


def _enemy_targets(tokens: list[str], payload: dict[str, Any], units: dict[str, Any]) -> tuple[str, ...]:
    """计算当前攻击平台真正允许选择的敌方目标集合。"""

    try:
        # 水面攻击由 shooter_id 决定所属阵营
        if tokens[0] == "attacks":
            owner_id = payload["attacks"][int(tokens[1])]["shooter_id"]

        # 飞机 sortie 由 aircraft_id 决定所属阵营
        else:
            owner_id = payload["sorties"][int(tokens[1])]["aircraft_id"]

        owner_side = units[owner_id].side_id

    except (IndexError, KeyError, ValueError):
        raise ProposalContractError("target_constraint_unavailable") from None

    # 只允许选择与攻击平台不同阵营的单位。
    #
    # 这样 LLM 无法把己方单位误设成攻击目标。
    return tuple(sorted(unit_id for unit_id, unit in units.items() if unit.side_id != owner_side))


def _tokens(path: str) -> list[str]:
    """把 JSON Pointer 路径拆成逐级访问 token。

    例如：

        /attacks/0/fire_quantity

    →

        ["attacks", "0", "fire_quantity"]
    """

    if not isinstance(path, str) or not path.startswith("/") or path == "/":
        raise ProposalContractError("invalid_patch_pointer")

    # 处理 JSON Pointer 标准转义：
    # ~1 → /
    # ~0 → ~
    return [token.replace("~1", "/").replace("~0", "~") for token in path[1:].split("/")]


def _get(payload: Any, tokens: list[str]) -> Any:
    """根据 token 路径安全读取嵌套 dict/list 中的值。"""

    current = payload

    for token in tokens:
        if isinstance(current, list):
            # list 必须使用数字下标
            if not token.isdecimal():
                raise ProposalContractError("invalid_array_index")

            try:
                current = current[int(token)]
            except IndexError as error:
                raise ProposalContractError("patch_path_out_of_bounds") from error

        elif isinstance(current, dict):
            if token not in current:
                raise ProposalContractError("patch_path_out_of_bounds")

            current = current[token]

        else:
            # 中间节点已经不是容器，
            # 说明路径本身不合法。
            raise ProposalContractError("patch_path_out_of_bounds")

    return current


def _set(payload: Any, tokens: list[str], value: JsonScalar) -> None:
    """根据 JSON Pointer 路径安全替换一个已经存在的叶子字段。

    注意这里只支持“替换已有字段”，
    不允许新增字段或扩展数组。
    """

    # 先找到目标字段的父节点
    parent = _get(payload, tokens[:-1])
    token = tokens[-1]

    if isinstance(parent, list):
        if not token.isdecimal() or int(token) >= len(parent):
            raise ProposalContractError("patch_path_out_of_bounds")

        parent[int(token)] = value

    elif isinstance(parent, dict):
        # 字段必须已经存在，
        # Patch 不能临时创造新的 StrategySpec 结构。
        if token not in parent:
            raise ProposalContractError("patch_path_out_of_bounds")

        parent[token] = value

    else:
        raise ProposalContractError("patch_path_out_of_bounds")