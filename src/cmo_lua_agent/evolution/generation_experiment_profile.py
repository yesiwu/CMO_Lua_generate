"""
单代演化预览所用、固定且确定的实验约束配置。

本模块职责边界清晰：**不参与基线选取、分数解析、策略规格生成、因果学习**。
滚动基线的选择逻辑归属 EvolutionCampaignWorkflow；本 Profile 仅负责约束、收窄已经规范化的参数修改空间。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cmo_lua_agent.generation.runtime_models import canonical_sha256


@dataclass(frozen=True, slots=True)
class GenerationExperimentProfile:
    """
    一代演化实验静态约束快照（不可变结构）
    frozen：实例创建后禁止修改；slots：优化内存占用
    """
    generation_index: int          # 当前演化代数编号
    objective: str                 # 本代优化目标标识
    roles: dict[str, dict[str, Any]]  # 各个候选个体对应的角色、假设、可修改参数约束

    @property
    def checksum(self) -> str:
        """计算当前配置的标准SHA256校验和，用于版本一致性校验"""
        return canonical_sha256(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典，用于持久化、哈希校验、日志落盘"""
        return {
            "generation_index": self.generation_index,
            "objective": self.objective,
            "roles": self.roles,
        }


class GenerationExperimentProfileBuilder:
    """
    实验约束配置构建器
    只生成系统预设的角色约束规则，**不负责填充具体策略参数值**
    """

    # 本代统一优化目标：维持打击成功率，同时降低歼15战损
    _OBJECTIVE = "retain_strike_success_and_reduce_j15_losses"

    def build(self, *, generation_index: int) -> GenerationExperimentProfile:
        """
        根据代数生成完整一代实验约束配置
        :param generation_index: 目标演化代数
        :return: 不可变的实验约束对象 GenerationExperimentProfile
        """
        if generation_index < 0:
            raise ValueError("generation_index_invalid")

        # 定义4路候选个体的角色、探索假设、参数修改权限约束
        roles = {
            "candidate_00": {
                "role": "exploit",  # 局部择优利用角色
                "hypothesis": "降低突防高度有望维持打击成功率，并减少J-15损失。",
                "allowed_capabilities": ["air_tactics.ingress_altitude_m"],  # 允许修改的战术参数
                "required_capabilities": ["air_tactics.ingress_altitude_m"],  # 必须修改的参数
            },
            "candidate_01": {
                "role": "robust_repair",  # 稳健修复型探索角色
                "hypothesis": "跃升距离与攻击距离调整可以缩短战机暴露时间。",
                "allowed_capabilities": ["air_tactics.popup_range_nm", "air_tactics.attack_range_nm"],
                "required_capabilities": ["air_tactics.popup_range_nm"],
            },
            "candidate_02": {
                "role": "coordinated_explore",  # 协同探索角色
                "hypothesis": "发射延时调整可以优化舰机出动时序协同。",
                "allowed_capabilities": ["air_tactics.launch_delay_seconds"],
                "required_capabilities": ["air_tactics.launch_delay_seconds"],
            },
            "candidate_03": {
                "role": "conservative_control",  # 保守对照角色，测试参数交互效应
                "hypothesis": "有界高度与时序组合，用于验证多个参数之间的耦合影响。",
                "allowed_capabilities": ["air_tactics.ingress_altitude_m", "air_tactics.launch_delay_seconds"],
                "required_capabilities": [],
                "max_changed_capabilities": 2,  # 最多同时修改2个参数
            },
        }
        return GenerationExperimentProfile(generation_index, self._OBJECTIVE, roles)
