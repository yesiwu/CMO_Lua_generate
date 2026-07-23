# 当前实现状态

> 盘点日期：2026-07-22。本文只记录已接入、可验证的代码路径；规划文件和未接入模块不等同于可用功能。

## 1. 当前主链路

项目当前有两条可用但尚未闭环的确定性链路：

```text
Chat / run CLI
  -> ScenarioWorkflow
  -> JsonLoader -> Schema / Semantic -> IR -> DatabaseResolver
  -> ScenarioDefinition + InitialStrategyHint
  -> ManifestBuilder -> CMOLua-main -> Preflight -> original.lua

execute_cmo Tool
  -> CmoRunner -> CmoJobConfig + CmoProcessRunner
  -> BatchRunner runner.log / cmo_output.txt / result.json
```

`ScenarioWorkflow` 在 Lua 生成成功后结束，不会自动执行 CMO。`execute_cmo` 保持独立、人工审批的工具调用。因此“Lua 已生成”和“CMO 推演成功”仍是两件独立的事，执行结果尚未回流为统一战果、评分或候选结果。

## 2. 已实现模块

| 区域 | 状态 | 说明 |
| --- | --- | --- |
| `ingest` / `contract` | 已实现 | JSON 读取、结构/语义校验、IR、数据库解析、Manifest 构建。平台歧义返回 `NEEDS_USER_INPUT`。 |
| Phase 1 策略契约 | 已实现 | `ScenarioDefinition` 保存单位、DBID、基地、Loadout 与武器最大库存；`InitialStrategyHint` 保存旧 JSON 的计划；`StrategySpec` 是唯一正式策略表达。 |
| Phase 1 Baseline | 已实现 | `baseline/6v4/baseline_strategy.json` 是人工维护的已验证基线，包装同一个 `StrategySpec` 和来源元数据；不做 Lua 反向解析。 |
| `generation` | 已实现 | 旧链路中的 `LuaGenerationService` 继续调用 `CMOLua-main`；Phase 2 并行增加 `ExecutionPlanCompiler`、`CapabilityValidator`、`LuaRuntimeProfile`、分层 Runtime Primitive/Helper、确定性 `LuaRenderer` 和 `Phase2GoldenBaselineService`。 |
| `execution` | 已实现 | `CmoRunner`、`CmoProcessRunner`、进度解析、超时、批次汇总、结果保存均在正式链路中。无引用且语法无效的 `cmo_executor.py` 已移除。 |
| `tools` / `cli` | 已实现 | Chat 支持文件、Skill、数据库、JSON→Lua 和 CMO 工具；Rich 终端支持流式文本、审批和工具进度。 |
| `artifacts` | 已实现 | 每次 JSON→Lua Workflow 保存输入、校验、IR、Manifest、Lua 及 Phase 1 派生产物；Phase 2 Golden 另保存 plan、renderer manifest、source map 和 Golden Manifest。 |

## 3. Phase 1 数据边界

```text
旧 JSON
  -> ScenarioIR（兼容旧链路，仍含 strikePlan）
  -> ScenarioDefinition（仅事实）
  -> InitialStrategyHint（旧 JSON 中的初始计划）

显式 baseline_path
  -> BaselineStrategy（已验证 StrategySpec）
  -> initial_hint_vs_baseline.json
```

`weaponLoad` 的边界固定如下：武器名称、DBID 与最大库存进入 `ScenarioDefinition`；本次使用武器、发射量、目标分配、延迟、航路和保留量进入 `StrategySpec`。`StrategyValidator` 的正式公开输入是 `StrategySpec + ScenarioDefinition`，不依赖旧 `ScenarioContract`。

普通生产 JSON 只保存：

```text
contract/scenario_definition.json
strategy/initial_strategy_hint.json
validation/strategy_report.json
```

只有显式配置且 `scenario_id` 匹配的已验证 Baseline 才保存：

```text
strategy/baseline_strategy.json
strategy/initial_hint_vs_baseline.json
```

## 4. Phase 2 确定性 Golden 链路

```text
ScenarioDefinition + StrategySpec
  -> ExecutionPlanCompiler
  -> ExecutionPlan
  -> CapabilityValidator
  -> LuaRuntimeProfile + registered Plan Primitives
  -> deterministic LuaRenderer
  -> rendered_baseline.lua
```

当前只覆盖已验证的 6v4 海空协同反舰 Baseline，作为并行验证入口，不替换 Chat 默认生成路径、`ScenarioWorkflow`、`generate_cmo_lua` 或 Auto 模式。Runtime Helper（例如 `lookup_unit`、`schedule_lua`、`checked_cmo_call`）只在 Primitive 内部使用，不会成为独立 Operation。Golden Manifest 记录输入、运行时、编译器/渲染器版本、checksum、CMO 结果目录和验证状态；CMO 版本未从运行产物可靠取得时标记为 unavailable/unknown。

## 5. Agent、Workflow 与尚未实现对象

已接入：`AgentLoop`、`ScenarioWorkflow`、`CmoRunner`、`ScenarioInput`、`ScenarioIR`、`ScenarioContract`、`ResolvedScenarioManifest`、Phase 1 策略模型。

文件存在但未进入生产主链路：`agents/strategy_proposal_agent.py`、`lua_synthesis_agent.py`、`lua_repair_agent.py`、`comparative_learning_agent.py`、`skill_author_agent.py`，以及旧 `generation/strategy_generator.py` / `candidate_generator.py`。

尚未实现：`RuntimeTelemetry`、`CmoNativeSnapshot`、`CombatEvidenceBundle`、`EvidenceReconciler`、正式闭环 `SemanticValidator`、`CombatMetrics`、`CombatScorer`、`CandidateOutcome` 和 `CandidateEvaluationWorkflow`。项目不宣称已具备战果评分、候选优化或经验进化。

## 6. ToolRegistry 与权限

唯一生产注册入口是：

```text
src/cmo_lua_agent/tools/tool_base/factory.py
-> build_tool_registry(...)
```

`execute_cmo`、`create_file`、`create_json_copy`、`edit_file` 需要审批；文件、目录、Skill 与受限数据库查询为只读工具，不需要审批。正式 Skill 路径是 `list_skills -> load_skill`；旧 CMO 专用读取/搜索工具保留模块与测试，但不作为正式入口注册。

## 7. 重复和旧路径

- `CMOLua-main/tools/json_to_lua.py` 仍含自身 JSON 解释、武器兜底和 Lua 模板逻辑，与 `contract` / `generation` 局部重叠；它目前是稳定生成器来源，不应删除。
- 当前兼容 JSON 的 `weaponLoad`、`strikePlan` 混合事实与策略；Phase 1 以并行派生产物隔离二者，未改变旧输入格式。
- `ScenarioWorkflow` 顶部历史说明仍描述完整执行/修复流程，但实际代码只运行到 Lua 生成；后续引入候选评估工作流时应一并清理该旧文案。

## 8. 测试与健康检查

根目录 `pytest.ini` 固定：

```ini
testpaths = src/cmo_lua_agent/tests
pythonpath = src
addopts = --import-mode=importlib
```

这解决了同名测试模块的收集冲突，并将旧顶层导入修正为稳定包路径。

2026-07-22 Phase 2 收口验证结果：

```text
全量测试：449 passed, 2 skipped（pytest cache 权限警告不影响结果）。
```

`compileall` 曾发现无引用的 `execution/cmo_executor.py` 语法无效；该文件已删除。下一次健康检查应使用：

```powershell
python -m compileall src\cmo_lua_agent
python -m pytest src\cmo_lua_agent\tests -q
```

## 9. 当前结论

项目已具备稳定的 JSON→Lua 与单 Lua→CMO 执行能力，并已完成 Phase 1 的“场景事实 / 初始计划 / 已验证基线”分离，以及 Phase 2 6v4 确定性 Golden 生成和真实 CMO 验证。该新链路仍是并行入口；尚未具备 RuntimeTelemetry、CMO 原生快照、证据协调、战果指标/评分、候选比较、自动修复或优化闭环能力。
