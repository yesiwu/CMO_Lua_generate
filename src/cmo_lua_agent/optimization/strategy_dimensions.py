"""StrategySpec 字段路径 → 战术语义维度 的唯一映射表。

作用：

    具体字段路径
        ↓
    semantic_dimension()
        ↓
    更高层的战术维度

例如：

    /sorties/0/air_tactics/launch_delay_seconds
        ↓
    air_launch_timing

后面的候选质量评估不需要关心每一个具体字段名，
只需要知道：

    这个候选主要改了
    “起飞时机”
    “攻击距离”
    “航路”
    还是“目标分配”。

为什么要集中放在一个文件里：

    避免不同模块各自定义一套解释规则，
    导致同一个字段在不同地方被归到不同维度。
"""

from __future__ import annotations


def semantic_dimension(path: str) -> str:
    """把一个具体策略字段路径归类到一个战术语义维度。"""

    # 飞机起飞延迟
    #
    # 例如：
    # /sorties/0/air_tactics/launch_delay_seconds
    #
    # 统一归类为“空中起飞时机”
    if "/air_tactics/launch_delay_seconds" in path:
        return "air_launch_timing"

    # 飞机进入任务区域时的飞行高度
    #
    # 统一归类为“空中进入高度”
    if "/air_tactics/ingress_altitude_m" in path:
        return "air_ingress_altitude"

    # popup 相关参数以及攻击距离，
    # 都会影响飞机什么时候、在多远距离进入攻击状态。
    #
    # 因此统一归类为“空中攻击距离”
    if (
        "/air_tactics/popup_" in path
        or "/air_tactics/attack_range_nm" in path
    ):
        return "air_attack_range"

    # 修改攻击目标：
    #
    # target_id
    # target_ids
    # target_ids/0
    #
    # 都属于“目标分配”
    if (
        path.endswith("/target_id")
        or path.endswith("/target_ids")
        or "/target_ids/" in path
    ):
        return "target_assignment"

    # 一次攻击发射多少枚武器
    #
    # 属于“火力数量”
    if path.endswith("/fire_quantity"):
        return "fire_quantity"

    # 攻击延迟 / 开火延迟，
    # 本质上都在改变“什么时候攻击”
    if (
        path.endswith("/delay_seconds")
        or path.endswith("/fire_delay_seconds")
    ):
        return "attack_timing"

    # 只要修改的是 route 内部字段，
    # 都统一认为是在调整飞机航路。
    #
    # 例如：
    # /sorties/0/route/0/lat
    # /sorties/0/route/1/lon
    if "/route/" in path:
        return "air_route"

    # 预留多少弹药不使用
    #
    # 属于“弹药储备策略”
    if path.endswith("/reserve_quantity"):
        return "ammunition_reserve"

    # 返航等待时间会影响平台暴露时间和风险，
    # 因此统一归类到“风险策略”。
    if path.endswith("/return_delay_seconds"):
        return "risk_policy"

    # 没有被当前规则识别的字段，
    # 统一放进 other。
    #
    # 这样新字段出现时不会直接报错，
    # 但后续质量报告会暴露存在未分类策略维度。
    return "other"


def semantic_dimensions(
    paths: tuple[str, ...],
) -> tuple[str, ...]:
    """把多个修改字段汇总成“这个候选涉及哪些战术维度”。

    例如：

        paths = (
            "/sorties/0/air_tactics/launch_delay_seconds",
            "/sorties/0/air_tactics/attack_range_nm",
            "/attacks/0/fire_quantity",
        )

    最终得到：

        (
            "air_attack_range",
            "air_launch_timing",
            "fire_quantity",
        )

    使用 set 去重：
        同一个维度改了多个字段，也只统计一次。

    使用 sorted：
        保证输出顺序稳定，方便比较、保存和计算 checksum。
    """

    return tuple(
        sorted(
            {
                semantic_dimension(path)
                for path in paths
            }
        )
    )