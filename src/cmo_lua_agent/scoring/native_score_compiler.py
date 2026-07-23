"""将固定评分契约确定性编译为 CMO 原生 Points 计分片段。
输入场景、单位角色、评分配置、目标清单，校验并生成可嵌入Lua的计分事件代码，
基于UnitDestroy触发器实现单位击毁自动加减分，全程强校验、可哈希溯源、输出标准化计分Lua片段
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

# 场景基础模型
from cmo_lua_agent.contract.strategy_models import ScenarioDefinition
# 全局稳定哈希工具
from cmo_lua_agent.generation.runtime_models import canonical_sha256
# 评分领域契约模型
from cmo_lua_agent.scoring.models import (
    NativeScoreFragment,
    NativeScoreRule,
    ScenarioObjectives,
    ScenarioScoreSpec,
    ScoreProfile,
    UnitRoleCatalog,
)

# 计分规则数据结构版本、编译工具版本（用于可复现溯源）
SCORE_SPEC_SCHEMA_VERSION = "1.0.0"
COMPILER_VERSION = "1.0.0"


class CmoNativeScoreCompileError(ValueError):
    """计分编译专属异常：输入数据不匹配、单位无角色、目标与计分单位不一致等校验失败抛出"""


@dataclass(frozen=True, slots=True)
class CmoNativeScoreCompilation:
    """计分编译完整输出产物，包含所有哈希指纹用于审计比对"""
    score_spec: ScenarioScoreSpec          # 标准化计分规则总契约
    fragment: NativeScoreFragment          # 最终生成Lua计分代码片段
    scenario_checksum: str                 # 场景哈希
    role_catalog_checksum: str              # 单位角色目录哈希
    score_profile_checksum: str            # 评分权重配置哈希
    objectives_checksum: str               # 击毁目标清单哈希
    score_spec_checksum: str               # 计分规则契约哈希
    fragment_checksum: str                 # 生成Lua代码哈希
    compiler_version: str                 # 当前编译工具版本


class CmoNativeScoreCompiler:
    """CMO原生计分规则编译器主类：校验输入→生成计分规则对象→渲染Lua代码片段"""
    def compile(
        self,
        *,
        scenario: ScenarioDefinition,        # 全局场景事实（所有单位）
        role_catalog: UnitRoleCatalog,        # 单位角色分配表（区分是否计分、角色类型）
        score_profile: ScoreProfile,          # 各角色击毁分值配置、计分阵营
        objectives: ScenarioObjectives,       # 需要监控击毁的目标单位清单
    ) -> CmoNativeScoreCompilation:
        # 第一步：校验所有输入绑定同一个场景ID，跨场景禁止混合
        self._validate_scenario_ids(scenario, role_catalog, objectives)
        # 构建单位ID索引、角色分配索引、目标ID索引
        units = scenario.unit_by_id()
        assignments = role_catalog.assignments_by_unit_id()
        objectives_by_unit = {obj.target_unit_id: obj for obj in objectives.objectives}
        role_scores = score_profile.role_scores()

        unknown_catalog_units = sorted(set(assignments) - set(units))
        if unknown_catalog_units:
            raise CmoNativeScoreCompileError(
                f"role catalog references unknown unit_id values: {unknown_catalog_units}"
            )

        rules: list[NativeScoreRule] = []
        # 筛选所有标记为需要计分的单位ID
        scored_unit_ids = {
            assign.unit_id
            for assign in role_catalog.assignments
            if assign.scoring_status == "scored"
        }

        # 校验1：所有目标单位必须分配计分角色，不能无角色/不计分
        for unit_id in sorted(objectives_by_unit):
            assign = assignments.get(unit_id)
            if assign is None:
                raise CmoNativeScoreCompileError(f"objective unit has no role assignment: {unit_id}")
            if assign.scoring_status == "unscored":
                raise CmoNativeScoreCompileError(f"objective references explicitly unscored unit: {unit_id}")
        # 校验2：计分单位集合 和 监控目标集合必须完全一致，不能多也不能少
        if set(objectives_by_unit) != scored_unit_ids:
            missing = sorted(scored_unit_ids - set(objectives_by_unit))
            extra = sorted(set(objectives_by_unit) - scored_unit_ids)
            raise CmoNativeScoreCompileError(
                f"objectives must cover exactly scored units; missing={missing}, extra={extra}"
            )

        # 遍历每个计分目标，逐条生成CMO计分触发规则
        for unit_id in sorted(objectives_by_unit):
            objective = objectives_by_unit[unit_id]
            assign = assignments.get(unit_id)
            unit = units.get(unit_id)
            # 校验单位存在于场景
            if unit is None:
                raise CmoNativeScoreCompileError(f"objective references unknown unit_id: {unit_id}")
            assert assign.role_kind is not None
            # 获取该角色对应的击毁分值配置
            role_score = role_scores.get(assign.role_kind)
            if role_score is None:
                raise CmoNativeScoreCompileError(
                    f"unrecognized scored role_kind: {assign.role_kind} for {unit_id}"
                )
            # 计算得分：己方击毁扣分，敌方击毁加分
            point_change = (
                -role_score.own_destroyed_points
                if unit.side_id == score_profile.score_side_id
                else role_score.enemy_destroyed_points
            )
            # 构造稳定唯一标识，生成固定哈希，保证事件名无随机、完全确定性
            identity = "|".join(
                (
                    scenario.scenario_id,
                    score_profile.profile_id,
                    score_profile.profile_version,
                    objective.objective_id,
                    unit_id,
                )
            )
            digest = sha256(identity.encode("utf-8")).hexdigest()[:16]
            # 单条计分规则封装：UnitDestroyed触发，配套固定事件/触发器/动作名称
            rules.append(
                NativeScoreRule(
                    rule_id=f"native_score/{unit_id}",
                    objective_id=objective.objective_id,
                    target_unit_id=unit_id,
                    target_side_id=unit.side_id,
                    target_unit_name=unit.name,
                    trigger_kind="unit_destroyed",
                    point_change=point_change,
                    event_name=f"p3score_evt_{digest}",
                    trigger_name=f"p3score_trg_{digest}",
                    action_name=f"p3score_act_{digest}",
                    score_side_id=score_profile.score_side_id,
                )
            )

        # 组装全局计分契约对象
        score_spec = ScenarioScoreSpec(
            schema_version=SCORE_SPEC_SCHEMA_VERSION,
            compiler_version=COMPILER_VERSION,
            scenario_id=scenario.scenario_id,
            catalog_id=role_catalog.catalog_id,
            catalog_version=role_catalog.catalog_version,
            profile_id=score_profile.profile_id,
            profile_version=score_profile.profile_version,
            objectives_version=objectives.objectives_version,
            rules=tuple(rules),
        )
        # 渲染完整可执行Lua计分代码片段
        fragment = NativeScoreFragment(
            compiler_version=COMPILER_VERSION,
            score_spec_checksum=score_spec.checksum,
            content=self._render_fragment(score_spec),
        )
        # 打包全部产物、各层哈希指纹返回
        return CmoNativeScoreCompilation(
            score_spec=score_spec,
            fragment=fragment,
            scenario_checksum=canonical_sha256(scenario.to_dict()),
            role_catalog_checksum=role_catalog.checksum,
            score_profile_checksum=score_profile.checksum,
            objectives_checksum=objectives.checksum,
            score_spec_checksum=score_spec.checksum,
            fragment_checksum=fragment.checksum,
            compiler_version=COMPILER_VERSION,
        )

    @staticmethod
    def _validate_scenario_ids(
        scenario: ScenarioDefinition,
        role_catalog: UnitRoleCatalog,
        objectives: ScenarioObjectives,
    ) -> None:
        """校验场景ID统一：所有输入资源必须归属同一个想定，禁止跨场景混合"""
        expected = scenario.scenario_id
        for label, actual in (("role_catalog", role_catalog.scenario_id), ("objectives", objectives.scenario_id)):
            if actual != expected:
                raise CmoNativeScoreCompileError(
                    f"{label}.scenario_id={actual!r} does not match scenario_id={expected!r}"
                )

    @staticmethod
    def _render_fragment(score_spec: ScenarioScoreSpec) -> str:
        """根据计分规则契约，渲染完整Lua计分代码片段
        包含：日志打印、错误捕获、清理旧计分事件、批量注册UnitDestroy计分触发器
        """
        # 将规则列表转为Lua字面量表
        lua_rules = _lua_value([rule.to_dict() for rule in score_spec.rules])
        return "\n".join(
            (
                "-- CMO native scoring instrumentation; generated deterministically.",
                f"-- score_spec_checksum: {score_spec.checksum}",
                f"local SCORE_RULES = {lua_rules}",
                "local function score_log(message)",
                "    print('[CMO-NATIVE-SCORE] ' .. tostring(message))",
                "end",
                "local function score_required(label, callback)",
                "    _errnum_ = 0",
                "    _errmsg_ = ''",
                "    local ok, result = pcall(callback)",
                "    local errnum = tonumber(_errnum_) or 0",
                "    if not ok or result == nil or result == false or errnum ~= 0 then",
                "        error('[CMO-NATIVE-SCORE] registration failed: ' .. label .. ' err=' .. tostring(_errmsg_ or ''))",
                "    end",
                "    score_log(label .. ' registered')",
                "end",
                "-- 先清理同单位旧计分事件，避免重复计分",
                "local function remove_previous(rule)",
                "    local event_name = rule.event_name",
                "    local trigger_name = rule.trigger_name",
                "    local action_name = rule.action_name",
                "    pcall(ScenEdit_SetEvent, event_name, {mode='remove'})",
                "    pcall(ScenEdit_SetAction, {mode='remove', type='Points', name=action_name})",
                "    pcall(ScenEdit_SetTrigger, {mode='remove', type='UnitDestroyed', name=trigger_name})",
                "    score_log('removed previous rule ' .. rule.rule_id)",
                "end",
                "-- 单条计分规则完整注册流程：触发器→计分动作→事件绑定→激活",
                "local function install_score_rule(rule)",
                "    remove_previous(rule)",
                "    local ok, unit = pcall(ScenEdit_GetUnit, {side=rule.target_side_id, name=rule.target_unit_name})",
                "    if not ok or not unit or not unit.guid then",
                "        error('[CMO-NATIVE-SCORE] unit lookup failed: ' .. rule.target_unit_id)",
                "    end",
                "    score_required('trigger ' .. rule.rule_id, function() return ScenEdit_SetTrigger({mode='add', type='UnitDestroyed', name=rule.trigger_name, TargetFilter={TargetSide=rule.target_side_id, SpecificUnitID=unit.guid}}) end)",
                "    score_required('action ' .. rule.rule_id, function() return ScenEdit_SetAction({mode='add', type='Points', name=rule.action_name, SideID=rule.score_side_id, PointChange=rule.point_change}) end)",
                "    score_required('event ' .. rule.rule_id, function() return ScenEdit_SetEvent(rule.event_name, {mode='add', IsActive=false, IsRepeatable=false}) end)",
                "    score_required('event trigger link ' .. rule.rule_id, function() return ScenEdit_SetEventTrigger(rule.event_name, {mode='add', name=rule.trigger_name}) end)",
                "    score_required('event action link ' .. rule.rule_id, function() return ScenEdit_SetEventAction(rule.event_name, {mode='add', name=rule.action_name}) end)",
                "    score_required('event activation ' .. rule.rule_id, function() return ScenEdit_SetEvent(rule.event_name, {IsActive=true}) end)",
                "end",
                "-- 批量安装所有计分规则",
                "for _, rule in ipairs(SCORE_RULES) do install_score_rule(rule) end",
                "score_log('installed native score rules=' .. tostring(#SCORE_RULES))",
                "",
            )
        )


def _lua_value(value: object) -> str:
    """通用Python值转合法Lua字面量，字典按键排序保证确定性输出"""
    if value is None:
        return "nil"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        # 转义Lua特殊字符：反斜杠、双引号、换行
        escaped = value.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n")
        return f'"{escaped}"'
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "{" + ",".join(_lua_value(item) for item in value) + "}"
    if isinstance(value, dict):
        # 字典key排序，消除遍历顺序差异，保证哈希稳定
        return "{" + ",".join(
            f"[{_lua_value(key)}]={_lua_value(value[key])}" for key in sorted(value)
        ) + "}"
    raise TypeError(f"unsupported Lua literal: {type(value).__name__}")
