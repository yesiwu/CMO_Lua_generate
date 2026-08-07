"""Phase 4：LLM 只产生策略结构，Lua 始终由确定性链路渲染。
核心约束：大模型仅输出标准化 StrategySpec 结构化策略，绝不直接生成Lua；
Lua生成、校验、编译、渲染全部走固定确定性管线，保证输出可复现。
两大模式：CREATE（全新生成）就是用户提一个需求，然后生成一套完整 StrategySpec，REVISE就是根据方案生成skill生成的几个来微调参数。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

# 产物写入工具
from cmo_lua_agent.agents.artifact_writer import ArtifactWriter
# 策略补丁安全校验：限制只能修改允许的字段
from cmo_lua_agent.agents.strategy_change_guard import RestrictedStrategyPatch, StrategyChangeGuard
# LLM结构化输出客户端，强制返回标准JSON策略
from cmo_lua_agent.agents.structured_strategy_client import StructuredJsonClient, StructuredStrategyClient
# Phase1 基础契约：场景、基线、策略校验器
from cmo_lua_agent.contract import BaselineStrategy, ScenarioDefinition, StrategyValidator
from cmo_lua_agent.contract.models import ValidationResult
# 标准策略模型、字典转策略解析工具
from cmo_lua_agent.contract.strategy_models import StrategySpec, strategy_spec_from_dict
# Phase2 编译、渲染、运行时相关
from cmo_lua_agent.generation.capability_validator import CapabilityValidator
from cmo_lua_agent.generation.execution_plan_compiler import ExecutionPlanCompiler
from cmo_lua_agent.generation.lua_renderer import LuaRenderer
from cmo_lua_agent.generation.runtime_models import CapabilityGap, ExecutionPlan, LuaRuntimeProfile, canonical_sha256
from cmo_lua_agent.generation.runtime_primitives import runtime_primitive_registry_for
# Phase3 计分编译产物
from cmo_lua_agent.generation.scored_lua_assembly import ScoredLuaAssemblyService
from cmo_lua_agent.scoring.native_score_compiler import CmoNativeScoreCompilation


# 合成模式：新建策略 / 修改已有策略
class LuaSynthesisMode(str, Enum):
    CREATE = "create"    # 从零生成全新StrategySpec
    REVISE = "revise"    # 基于现有策略打补丁修改


# 策略合成入参：单次生成/修订的全部上下文
@dataclass(frozen=True, slots=True)
class LuaSynthesisRequest:
    mode: LuaSynthesisMode                                  # 创建/修订模式
    scenario: ScenarioDefinition                            # 全局固定场景事实
    user_requirement: str                                   # 用户自然语言需求
    runtime: LuaRuntimeProfile                              # 运行时能力包版本
    output_dir: Path                                        # 产物输出目录
    allowed_strategy_paths: tuple[str, ...]                 # 允许修改的策略JSON路径（安全限制）
    baseline_strategy: BaselineStrategy | None = None      # 黄金基线策略（参考用）
    current_strategy: StrategySpec | None = None           # REVISE模式必填：当前待修改策略
    related_skills: tuple[str, ...] = ()                   # 相关战术Skill参考
    native_score_compilation: CmoNativeScoreCompilation | None = None # 计分插件（带计分Lua才传）


# 策略合成统一输出结果：包含全链路校验、中间产物、失败原因
@dataclass(frozen=True, slots=True)
class LuaSynthesisResult:
    success: bool                                   # 整体流程是否成功
    strategy: StrategySpec | None                   # LLM输出/补丁后的标准策略
    strategy_validation: ValidationResult | None    # Phase1策略校验报告
    execution_plan: ExecutionPlan | None            # Phase2编译后的执行步骤计划
    generation_manifest: dict[str, Any] | None       # 全链路哈希溯源清单
    rendered_lua_path: Path | None                  # 生成Lua文件路径
    generation_manifest_path: Path | None           # 溯源清单文件路径
    change_summary: tuple[str, ...]                 # 策略变更文字摘要
    verified_changed_paths: tuple[str, ...]         # 实际被修改的合法字段路径
    capability_gap: CapabilityGap | None            # 运行时不支持的能力缺口
    failure_reason: str | None                      # 失败中文原因


# 底层确定性合成服务：不接触LLM，只做校验→编译→渲染→落盘
class LuaSynthesisService:
    def __init__(self) -> None:
        self._validator = StrategyValidator()                  # Phase1策略合法性校验
        self._compiler = ExecutionPlanCompiler()               # Phase2 策略转执行计划
        self._renderer = LuaRenderer()                         # Phase2 Lua渲染器
        self._writer = ArtifactWriter()                        # 文件持久化工具

    def synthesize(self, *, request: LuaSynthesisRequest, strategy: StrategySpec, summary: tuple[str, ...], changed: tuple[str, ...]) -> LuaSynthesisResult:
        # 1. 校验策略是否符合场景约束（弹药、单位、敌我等）
        validation = self._validator.validate(strategy=strategy, scenario_definition=request.scenario)
        if not validation.valid:
            return LuaSynthesisResult(
                False, strategy, validation, None, None, None, None, summary, changed, None, "策略字段校验失败"
            )
        # 2. 策略编译为分步执行计划ExecutionPlan
        compiled = self._compiler.compile(scenario=request.scenario, strategy=strategy, runtime=request.runtime)
        if compiled.plan is None:
            return LuaSynthesisResult(
                False, strategy, validation, None, None, None, None, summary, changed, compiled.capability_gaps[0], "存在运行时不支持的作战能力缺口"
            )
        # 3. 校验执行计划使用的原语是否在当前Runtime支持列表
        capability = CapabilityValidator(runtime_primitive_registry_for(request.runtime.runtime_id, request.runtime.runtime_version)).validate(plan=compiled.plan, runtime=request.runtime)
        if not capability.is_valid:
            return LuaSynthesisResult(
                False, strategy, validation, compiled.plan, None, None, None, summary, changed, None, "执行计划运行时原语校验不通过"
            )
        # 4. 判断是否需要注入计分插桩
        score_checksum = "none"
        if request.native_score_compilation is None:
            # 无计分：直接渲染基础作战Lua
            compiled_plan = compiled.plan
            rendered = self._renderer.render(plan=compiled.plan, runtime=request.runtime)
            base_manifest = rendered.to_manifest_dict()
        else:
            # 带计分：调用Phase3组装服务，融合计分Lua片段
            assembled = ScoredLuaAssemblyService().render(
                scenario=request.scenario, strategy=strategy, plan=compiled.plan, runtime=request.runtime,
                native_score_compilation=request.native_score_compilation,
            )
            compiled_plan, rendered, base_manifest = assembled.plan, assembled.rendered, assembled.generation_manifest
            score_checksum = request.native_score_compilation.fragment_checksum
        # 5. 计算全局唯一构建指纹，保证确定性
        identity = canonical_sha256({
            "scenario": canonical_sha256(request.scenario.to_dict()),
            "strategy": canonical_sha256(strategy.to_dict()),
            "runtime": request.runtime.to_dict(),
            "renderer_version": rendered.metadata["renderer_version"],
            "score_fragment_checksum": score_checksum,
            "compiler_version": compiled_plan.compiler_version,
        })
        # 6 组装完整溯源清单
        manifest = {**base_manifest,
            "build_identity": identity,
            "scenario_checksum": canonical_sha256(request.scenario.to_dict()),
            "strategy_checksum": canonical_sha256(strategy.to_dict()),
            "score_fragment_checksum": score_checksum
        }
        # 7 写入lua与清单文件
        lua_path, manifest_path = self._writer.write(output_dir=Path(request.output_dir), stem=f"candidate_{identity[:16]}", lua=rendered.content, manifest=manifest)
        # 全部流程正常，返回成功结果
        return LuaSynthesisResult(
            True, strategy, validation, compiled_plan, manifest, lua_path, manifest_path, summary, changed, None, None
        )


# Phase4 对外门面Agent：负责调用LLM生成结构化策略，然后调用底层确定性合成服务
class LuaSynthesisAgent:
    """公开 Facade：仅组织结构化提案、确定性校验和渲染。
    LLM只输出标准策略JSON，不允许生成自由Lua代码
    """
    def __init__(self, client: StructuredJsonClient, *, service: LuaSynthesisService | None = None, guard: StrategyChangeGuard | None = None) -> None:
        self._client = StructuredStrategyClient(client)  # LLM结构化输出客户端，强制JSON格式
        self._service = service or LuaSynthesisService()  # 底层Lua合成管线
        self._guard = guard or StrategyChangeGuard()      # 策略修改安全拦截器

    def synthesize(self, request: LuaSynthesisRequest) -> LuaSynthesisResult:
        try:
            # 组装给LLM的上下文Prompt
            payload = self._client.complete(mode=request.mode.value, prompt=self._prompt(request))
            if request.mode is LuaSynthesisMode.CREATE:
                # 新建模式：LLM只能返回 strategy + 修改摘要
                if request.current_strategy is not None or set(payload) != {"strategy", "change_summary"}:
                    raise ValueError("CREATE模式仅允许返回strategy与change_summary两个字段")
                strategy = _strict_strategy(payload["strategy"])
                changed: tuple[str, ...] = ()
            else:
                # 修订模式：基于现有策略打补丁
                if request.current_strategy is None or set(payload) != {"patches", "change_summary"}:
                    raise ValueError("REVISE模式需要传入当前策略，且仅允许返回patches、change_summary字段")
                patches = tuple(_patch(item) for item in payload["patches"])
                # 安全应用补丁，仅修改allowed_paths内字段
                strategy, changed = self._guard.apply(current=request.current_strategy, patches=patches, allowed_paths=request.allowed_strategy_paths)
            summary = tuple(str(item) for item in payload["change_summary"])
            # 交付底层确定性管线生成Lua
            return self._service.synthesize(request=request, strategy=strategy, summary=summary, changed=changed)
        except (KeyError, TypeError, ValueError) as exc:
            # LLM输出格式错误、补丁非法、字段不匹配统一捕获返回失败结果
            return LuaSynthesisResult(False, None, None, None, None, None, None, (), (), None, str(exc))

    @staticmethod
    def _prompt(request: LuaSynthesisRequest) -> str:
        # 构造传给LLM的上下文：需求、场景、基线/当前策略、可修改字段、参考技能
        base = request.current_strategy or (request.baseline_strategy.strategy if request.baseline_strategy else None)
        return (
            f"用户需求={request.user_requirement}\n"
            f"场景定义={request.scenario.to_dict()}\n"
            f"基线/当前策略={base.to_dict() if base else None}\n"
            f"允许修改的策略路径={request.allowed_strategy_paths}\n"
            f"参考战术Skill={request.related_skills}"
        )


# LLM输出策略JSON强校验，不符合标准直接抛异常
def _strict_strategy(value: object) -> StrategySpec:
    if not isinstance(value, dict) or set(value) != {"scenario_id", "attacks", "sorties"}:
        raise ValueError("StrategySpec顶层必须仅包含 scenario_id、attacks、sorties 三个字段")
    if not isinstance(value["attacks"], list) or not isinstance(value["sorties"], list):
        raise ValueError("attacks、sorties 必须为数组格式")
    # 舰艇攻击指令固定字段
    attack_fields = {
        "attack_id", "shooter_id", "target_ids", "weapon_dbid", "fire_quantity",
        "delay_seconds", "reserve_quantity",
    }
    # 舰载机出击指令固定字段
    sortie_fields = {
        "sortie_id", "aircraft_id", "target_id", "base_unit_id", "route",
        "altitude_meters", "throttle", "fire_delay_seconds", "return_delay_seconds",
    }
    # 校验所有攻击结构字段完整
    if not all(isinstance(item, dict) and set(item) == attack_fields for item in value["attacks"]):
        raise ValueError("每条攻击指令字段不完整或存在多余字段")
    # 校验所有出击结构字段完整
    allowed_sortie_fields = sortie_fields | {"air_tactics"}
    if not all(isinstance(item, dict) and set(item) in {frozenset(sortie_fields), frozenset(allowed_sortie_fields)} for item in value["sorties"]):
        raise ValueError("每条舰载机出击指令字段不完整或存在多余字段")
    # 校验航路点格式
    for sortie in value["sorties"]:
        if "air_tactics" in sortie and (
            not isinstance(sortie["air_tactics"], dict)
            or set(sortie["air_tactics"]) != {"launch_delay_seconds", "ingress_altitude_m", "popup_altitude_m", "popup_range_nm", "attack_range_nm"}
        ):
            raise ValueError("air_tactics fields are invalid")
        if not isinstance(sortie["route"], list) or not all(
            isinstance(point, dict) and set(point) == {"latitude", "longitude"}
            for point in sortie["route"]
        ):
            raise ValueError("航路点仅允许 latitude、longitude 两个字段")
    return strategy_spec_from_dict(value)


# 校验单条修改补丁格式，仅允许标量修改，禁止批量改数组/对象
def _patch(value: object) -> RestrictedStrategyPatch:
    if not isinstance(value, dict) or set(value) != {"op", "path", "expected_object_id", "value"}:
        raise ValueError("策略补丁格式非法，必须包含op/path/expected_object_id/value")
    if isinstance(value["value"], (dict, list)):
        raise ValueError("补丁仅支持修改标量值，不允许批量修改对象/数组")
    return RestrictedStrategyPatch(**value)
