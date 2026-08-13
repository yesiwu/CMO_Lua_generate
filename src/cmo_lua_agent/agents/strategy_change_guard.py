"""严格应用 StrategySpec 的受限 replace Patch。（替换补丁）
作用：安全给策略打补丁，强限制只能修改指定叶子标量字段，禁止增删条目、修改数组/子对象，防止LLM乱改作战结构，保证策略结构稳定可控。
二、触发替换补丁两大核心场景
    场景 1：用户主动修订现有策略（Chat 交互人工微调）
    场景 2：CMO 仿真报错，自动修复策略参数（自动化修复流水线）
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

# 标准策略模型 + 字典转回策略实例工具
from cmo_lua_agent.contract.strategy_models import StrategySpec, strategy_spec_from_dict


# 单条策略修改补丁：仅支持标量替换操作
@dataclass(frozen=True, slots=True)
class RestrictedStrategyPatch:
    """一条受限的标量替换补丁。

    ``expected_object_id`` 将数组位置与稳定对象身份绑定，防止候选策略在重排后仍按旧索引
    修改到错误目标；具体白名单判断与应用由 ``StrategyChangeGuard`` 完成。
    """
    op: str                  # 操作类型，仅允许 "replace"
    path: str                # JSON指针路径，格式如 /attacks/0/fire_quantity
    expected_object_id: str  # 目标条目唯一ID，防条目错位
    value: str | int | float | bool | None  # 要替换的标量新值


# 策略修改安全校验器：管控所有补丁合法性、执行替换
class StrategyChangeGuard:
    """限制策略 Patch 的可修改范围，保护 Scenario/稳定标识等不可变边界。

    上游 LLM 或修复 Agent 只能提出 Patch；本类对路径、对象身份与标量类型进行确定性
    校验后才返回新的 ``StrategySpec``，从不原地修改调用方传入的策略对象。
    """
    def apply(
        self, *,
        current: StrategySpec,                # 原始待修改策略
        patches: tuple[RestrictedStrategyPatch, ...], # LLM生成的补丁列表
        allowed_paths: tuple[str, ...]       # 白名单：允许修改的字段路径
    ) -> tuple[StrategySpec, tuple[str, ...]]:
        """应用白名单内的替换补丁，返回新策略及实际变更路径。

        任一补丁不满足安全约束即失败，不会部分提交此前补丁；调用方据此决定是否继续
        预检、渲染或将无效提案交回修复链路。
        """
        # 深度拷贝原始策略字典，不污染原对象
        payload = deepcopy(current.to_dict())
        # 记录本次实际修改过的路径，用于日志/差异对比
        changed: list[str] = []

        for patch in patches:
            # 校验1：操作只能是replace，且路径在白名单内
            if patch.op != "replace" or patch.path not in allowed_paths:
                raise ValueError("策略补丁仅允许白名单内的标量替换操作")

            # 拆分路径，过滤空分段（处理开头/）
            parts = [part for part in patch.path.split("/") if part]
            # 校验2：路径必须三层结构 根集合/索引/字段，只能是attacks或sorties下条目
            # 示例：["attacks", "0", "fire_quantity"]
            if len(parts) < 3 or parts[0] not in {"attacks", "sorties"} or not parts[1].isdigit():
                raise ValueError("策略补丁只能作用于attack或sortie下的叶子字段")

            collection = payload[parts[0]]  # 拿到攻击/出击数组
            index = int(parts[1])
            # 校验3：下标不能越界，路径必须刚好三层（集合+下标+字段）
            if index >= len(collection) or len(parts) != 3:
                raise ValueError("补丁指向的目标条目不存在")

            item = collection[index]
            # 校验4：条目ID匹配，防止数组顺序变动导致改错目标
            stable_field = "attack_id" if parts[0] == "sortie_id" else "attack_id"
            if item.get(stable_field) != patch.expected_object_id:
                raise ValueError("条目唯一ID不匹配，可能数组顺序发生变化，禁止修改")

            field = parts[2]
            # 校验5：目标字段必须存在，且只能是标量（禁止修改字典/数组）
            if field not in item or isinstance(item[field], (dict, list)):
                raise ValueError("仅允许替换已存在的标量字段，不支持数组/字典修改")

            # 合法：执行值替换
            item[field] = patch.value
            changed.append(patch.path)

        # 修改后的字典转回标准StrategySpec实例，同时返回所有变更路径
        return strategy_spec_from_dict(payload), tuple(changed)
