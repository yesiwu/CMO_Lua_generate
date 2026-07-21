"""由标准化JSON构建确定性中间表示(IR)

定位
前面 JsonLoader→Schema 校验→语义校验标准化，本段 IRBuilder 是流水线倒数第二步，专门把扁平 JSON 重组成方便 Lua 脚本生成器读取的专用中间数据结构。
核心改造逻辑
单位扁平化全局索引 unitById
原来单位分散嵌套在 red.units/blue.units 里，查找目标 / 射手要循环两层；
IR 统一把所有单位放到顶层 unitById，通过单位 ID 一步直达，不用循环遍历。
同时给每个单位新增 sideKey 标记所属红蓝阵营，后续敌我判断直接读取。
重构阵营结构，删除嵌套 units 大数组
原结构：sides.red.units = [一堆单位对象]
IR 改造后：sides.red.unitIds = [单位ID字符串列表]，不再存完整单位，只存 ID；
需要单位详情时去顶层 unitById 查表，大幅减少重复数据，结构更清爽。
统一约束，确保输入格式固定
强制校验所有攻击计划只能用 shooters 数组，不能有旧格式 shooter 单字符串，避免下游写两套兼容代码。
兼容扩展字段，不丢用户自定义数据
白名单只定义标准业务字段，用户新增的自定义顶层 key 会原样拷贝进 IR，不会丢失。
全程深拷贝隔离
所有数据都复制副本，修改 IR 不会污染上游原始标准化 JSON。
输出 IR 对比原始 JSON 的优势
查找单位 O (1)，不用嵌套循环；
阵营结构轻量化，只存 ID 列表，冗余数据少；
全局自带阵营标记，不用反复判断单位归属；
结构完全固定、格式唯一，Lua 生成器只需要写一套解析逻辑。
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from cmo_lua_agent.contract.models import ScenarioIR

# IR格式版本标记，用于后续版本兼容判断
_IR_VERSION = "scenario-ir-v1"
# 固定两大阵营标识
_SIDE_KEYS = ("red", "blue")
# 顶层标准字段白名单，区分业务内置字段与用户自定义扩展字段
_KNOWN_TOP_LEVEL_FIELDS = {
    "scenario",
    "sides",
    "strikePlan",
    "missileSummary",
    "notes",
}


class IRBuilder:
    """将经过语义标准化的场景JSON转换为统一的中间表示 ScenarioIR"""

    def build(self, normalized: Mapping[str, Any]) -> ScenarioIR:
        """IR构建入口主函数
        :param normalized: 语义校验器输出的标准化完整场景字典
        :return: 结构化中间表示实例 ScenarioIR
        """
        if not isinstance(normalized, Mapping):
            raise TypeError("normalized 必须为字典/映射类型")

        # 深拷贝标准化数据，所有操作仅操作副本，不污染原始输入
        source = deepcopy(dict(normalized))
        # 强制校验攻击计划已完成标准化（仅保留shooters数组，无单独shooter字段）
        self._require_normalized_strikes(source)

        # 重构后的阵营容器：key=red/blue，value=重构后的阵营信息
        sides: dict[str, dict[str, Any]] = {}
        # 全局单位索引：key=单位id，value=完整单位数据（附加所属阵营标记sideKey）
        unit_by_id: dict[str, dict[str, Any]] = {}

        # 遍历红蓝两大阵营，重构数据结构
        for side_key in _SIDE_KEYS:
            side_source = source["sides"][side_key]
            units = side_source["units"]

            # 拷贝阵营基础信息，剔除units、key、unitIds、unitCount等需要重新生成的字段
            side_data = {
                key: deepcopy(value)
                for key, value in side_source.items()
                if key not in {"units", "key", "unitIds", "unitCount"}
            }
            # 存放当前阵营所有单位ID列表
            unit_ids: list[str] = []

            # 遍历阵营下所有单位，构建全局单位索引
            for unit in units:
                unit_data = deepcopy(unit)
                unit_id = unit_data["id"]
                # 给单位附加所属阵营标记，方便后续逻辑快速判断敌我
                unit_data["sideKey"] = side_key
                unit_ids.append(unit_id)
                unit_by_id[unit_id] = unit_data

            # 组装重构后的阵营结构：
            # 1. 固定key标识阵营名称
            # 2. 保留原有基础字段
            # 3. 重新计算单位总数unitCount
            # 4. 存入本阵营全部单位ID清单unitIds
            sides[side_key] = {
                "key": side_key,
                **side_data,
                "unitCount": len(unit_ids),
                "unitIds": unit_ids,
            }

        # 组装顶层IR核心结构
        ir_data: dict[str, Any] = {
            "irVersion": _IR_VERSION,          # IR版本号
            "scenario": deepcopy(source["scenario"]),  # 场景基础信息
            "sides": sides,                    # 重构后的阵营数据（无嵌套units数组）
            "unitById": unit_by_id,            # 全局单位ID索引，全量单位扁平化存放
            "strikePlan": deepcopy(source["strikePlan"]),  # 标准化攻击计划数组
        }

        # 拷贝可选顶层字段：导弹汇总、备注
        for field in ("missileSummary", "notes"):
            if field in source:
                ir_data[field] = deepcopy(source[field])

        # 处理用户自定义扩展顶层字段（不在标准白名单内的字段全部保留，实现向前兼容）
        # 排除IR内置字段irVersion、unitById，避免键冲突覆盖
        for field in sorted(set(source) - _KNOWN_TOP_LEVEL_FIELDS):
            if field == "irVersion" or field == "unitById":
                continue
            ir_data[field] = deepcopy(source[field])

        # 封装为IR模型实例返回，作为Lua代码生成器的统一输入
        return ScenarioIR(data=ir_data)

    @staticmethod
    def _require_normalized_strikes(source: Mapping[str, Any]) -> None:
        """静态校验工具：强制攻击计划已经完成语义层标准化
        规则：每条打击条目只能存在shooters数组，不能残留单独shooter字段
        防止下游IR、Lua生成逻辑出现分支兼容问题
        """
        for strike in source["strikePlan"]:
            if "shooter" in strike or "shooters" not in strike:
                raise ValueError(
                    "strikePlan 必须使用标准化后的 shooters 数组格式，禁止遗留 shooter 单字段"
                )