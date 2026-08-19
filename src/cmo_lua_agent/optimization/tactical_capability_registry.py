"""可执行战术参数的唯一注册表。

这里注册的是“允许修改的战术参数”，不是 Lua 代码本身。

只有当某个参数：
1. 在正式 ExecutionPlan 中存在；
2. Runtime/执行器能够真正支持；
3. 在这里被明确注册；

它才允许进入候选策略生成或自动修复。

这样设计是为了避免 LLM 提出“看起来合理，但实际 Runtime 根本不会执行”的参数。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TacticalCapability:
    # 参数的稳定唯一标识，例如 air_tactics.attack_range_nm
    capability_id: str
    # StrategySpec 中 air_tactics 下的字段名
    path_suffix: str
    # 这个参数属于哪个战术语义维度
    semantic_dimension: str
    # 参数允许的最小值
    minimum: int
    # 参数允许的最大值
    maximum: int
    # 默认值
    default: int
    # 哪些候选角色允许修改这个参数
    allowed_roles: tuple[str, ...]
    # Lua模板/执行器中对应的字段名
    template_slot_field: str

    def concrete_path(self, sortie_index: int) -> str:
        # 把抽象参数转换成某个具体 sortie 的 StrategySpec 路径
        # 例如：
        # sortie_index=0
        # launch_delay_seconds
        # →
        # /sorties/0/air_tactics/launch_delay_seconds
        return f"/sorties/{sortie_index}/air_tactics/{self.path_suffix}"


class TacticalCapabilityRegistry:
    """受限空中战术参数注册表。

    它规定：
    哪些 air_tactics 参数真的存在、可以执行、允许被哪些候选角色修改。

    候选生成器不能自己发明新参数，只能从这里选择。
    """

    # 当前正式注册的空中战术参数
    _AIR_TACTICS = (
        # 起飞延迟：控制飞机什么时候起飞
        # 允许 coordinated_explore / conservative_control 调整
        TacticalCapability("air_tactics.launch_delay_seconds", "launch_delay_seconds", "air_launch_timing", 0, 120, 5, ("coordinated_explore", "conservative_control"), "launch_delay_seconds"),
        # 进入任务区域高度：控制飞机低空/高空进入
        # exploit / conservative_control 可以调整
        TacticalCapability("air_tactics.ingress_altitude_m", "ingress_altitude_m", "air_ingress_altitude", 100, 2000, 200, ("exploit", "conservative_control"), "ingress_altitude_m"),
        # Popup高度：飞机攻击前爬升到的高度
        # 当前 allowed_roles 为空，说明虽然 Runtime 支持，但暂时不开放给候选修改
        TacticalCapability("air_tactics.popup_altitude_m", "popup_altitude_m", "air_popup_profile", 3000, 12000, 9500, (), "popup_altitude_m"),
        # Popup距离：距离目标多远开始爬升/进入攻击姿态
        # 主要开放给 robust_repair，用于修复攻击距离相关问题
        TacticalCapability("air_tactics.popup_range_nm", "popup_range_nm", "air_attack_range", 30, 140, 95, ("robust_repair",), "popup_range_nm"),
        # 实际攻击距离
        # 主要开放给 robust_repair，用于修复距离过远/过近等执行问题
        TacticalCapability("air_tactics.attack_range_nm", "attack_range_nm", "air_attack_range", 30, 140, 80, ("robust_repair",), "attack_range_nm"),
    )

    @classmethod
    def default(cls) -> "TacticalCapabilityRegistry":
        # 返回系统默认战术能力注册表
        return cls()

    @property
    def capabilities(self) -> tuple[TacticalCapability, ...]:
        # 对外提供当前所有正式注册参数
        return self._AIR_TACTICS

    def capability_for_path(self, path: str) -> TacticalCapability | None:
        # 根据具体 StrategySpec 路径反查它对应哪个 TacticalCapability
        # 找不到说明这个字段没有被注册为正式可修改战术参数
        for capability in self._AIR_TACTICS:
            if path.endswith("/air_tactics/" + capability.path_suffix):
                return capability
        return None

    def paths_for_role(self, *, role: str, sortie_count: int) -> tuple[str, ...]:
        # 根据候选角色生成它真正允许修改的字段路径集合
        #
        # 例如：
        # role = robust_repair
        # sortie_count = 2
        #
        # 会生成类似：
        # /sorties/0/air_tactics/popup_range_nm
        # /sorties/1/air_tactics/popup_range_nm
        # /sorties/0/air_tactics/attack_range_nm
        # /sorties/1/air_tactics/attack_range_nm
        return tuple(
            capability.concrete_path(index)
            for capability in self._AIR_TACTICS
            if role in capability.allowed_roles
            for index in range(sortie_count)
        )