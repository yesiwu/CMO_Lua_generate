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
| Phase 3.1 原生计分 | 已实现但未接入渲染 | `UnitRoleCatalog`、`ScoreProfile`、`ScenarioObjectives`、`ScenarioScoreSpec` 与 `CmoNativeScoreCompiler` 可确定性生成 CMO `UnitDestroyed → Points → Event` 片段。评分片段是系统级 instrumentation，尚未插入 Renderer，也未执行 CMO 或解析结果。 |
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

尚未实现：Phase 3.2 的评分片段 Renderer 接入、`RuntimeTelemetry`、`CmoNativeSnapshot`、`ResultArtifactPaths`、`CombatEvidenceBundle`、`EvidenceReconciler`、正式闭环 `SemanticValidator`、`CombatMetrics`、`CombatScorer`、`CandidateOutcome` 和 `CandidateEvaluationWorkflow`。CMO 原生计分结果尚未经过真实执行或结果解析；项目不宣称已具备战果评分、候选优化或经验进化。

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

2026-07-23 Phase 3.1 验证结果：

```text
全量测试：461 passed, 2 skipped（pytest cache 权限警告不影响结果）。
```

`compileall` 曾发现无引用的 `execution/cmo_executor.py` 语法无效；该文件已删除。下一次健康检查应使用：

```powershell
python -m compileall src\cmo_lua_agent
python -m pytest src\cmo_lua_agent\tests -q
```

## 9. 当前结论

项目已具备稳定的 JSON→Lua 与单 Lua→CMO 执行能力，已完成 Phase 1 场景事实/策略分离、Phase 2 6v4 确定性 Golden，以及完整 Phase 3 的 CMO 原生计分与最小执行反馈闭环。当前可对 scored 6v4 自动定位本轮 Results、核验原生分数并生成可审计的评分产物；尚未具备 Candidate 比较、Research Reward、自动修复或优化闭环能力。

## 10. Phase 3.2 原生计分组装

已实现并行的 scored Golden 链路，且不改变 Chat 默认生成路径或 Phase 2 Golden：

```text
ScenarioDefinition + StrategySpec -> ExecutionPlanCompiler
ScenarioDefinition + UnitRoleCatalog + ScoreProfile + ScenarioObjectives
  -> CmoNativeScoreCompiler
ExecutionPlan + LuaRuntimeProfile + NativeScoreCompilation
  -> ScoredLuaAssemblyService -> LuaRenderer
  -> baseline/6v4/scored/rendered_scored_baseline.lua
```

`SystemInstrumentationBundle` 只接受系统生成的 `NativeScoreCompilation`，并校验场景、评分契约、片段、Runtime 和 Renderer 版本。评分片段固定插入在单位与舰载机配置之后、第一条攻击之前；它不是 ExecutionPlan Operation。scored Runtime 使用 `cmo_naval_air_anti_surface_scored@2.0.0`，但仍复用唯一的 Runtime Helper 与 `LuaRenderer` 实现。

2026-07-23 的真实 CMO Golden run 为 `phase32_scored_6v4_cdrive_2`，结果目录 `C:\CMO\CmoBatchRunner\Results\20260723-102542`：Batch 成功 1、失败 0；十条 CMO 原生计分规则均完成注册；两架 J-15 被毁后红方原生分数为 `-40`，与 `carrier_fighter` 的每架 `-20` 规则一致。该信息只作为 Golden 审计记录；项目仍未实现 Results 目录定位、SQLite/CSV 解析、EvidenceReconciler、CombatMetrics 或 Research Reward。

## 12. Phase 4 受控 Agent

Phase 4 已实现两个未接入 Chat 或 Auto 默认路径的受控 Agent：

```text
LuaSynthesisAgent
  CREATE: StructuredStrategyClient -> 完整 StrategySpec
  REVISE: StructuredStrategyClient -> RestrictedStrategyPatch
  -> StrategyChangeGuard -> StrategyValidator
  -> ExecutionPlanCompiler -> CapabilityValidator
  -> LuaRenderer / ScoredLuaAssemblyService -> ArtifactWriter

LuaRepairAgent
  Structured CmoError -> RepairErrorRouter
  -> StrategyPatch | RuntimePatchProposal | RuntimeDefectReport
```

`LuaSynthesisAgent` 不生成自由 Lua，也不执行 CMO。CREATE 模式只接收完整严格的 `StrategySpec`；REVISE 模式仅支持现有叶子字段的 `replace`，数组项必须以 `attack_id` 或 `sortie_id` 核验。`StrategyChangeGuard` 会拒绝未授权路径、祖先/后代路径、字段缺失、数组重排和稳定 ID 不匹配，并输出系统验证的 `verified_changed_paths`。Lua 与 manifest 在全部校验、编译和渲染成功后才由 `ArtifactWriter` 原子写入；文件身份包含场景、策略、Runtime、Renderer、评分片段和 Compiler 的稳定 checksum。

`LuaRepairAgent` 每次最多调用一次结构化 JSON 客户端，不执行、不重试、不修改场景事实或 CMO 原生计分。`RepairErrorRouter` 决定 `retry_eligible`，模型自报的 `agent_confidence` 仅用于展示。`RuntimePatchProposal` 不含 Lua 文本，必须经 `RuntimePatchRegistry` 验证已注册类型、Operation、Runtime 兼容性和评分区域隔离；未注册或不适用的提案会转为 `RuntimeDefectReport`。Phase 4 尚未实现执行循环、修复预算、CMO 自动重跑、候选比较、排行榜、经验系统或 Chat/Auto 默认路径接入。

## 13. Phase 5 单候选评估

`CandidateEvaluationWorkflow` 已提供单个 scored 候选的策略校验、计划编译、确定性 Lua 渲染、CMO 调用、Phase 3 直接评估和统一 `CandidateOutcome` 落盘。它支持受限 `StrategyPatch`，以及唯一已注册的 Runtime Patch `retry_missing_contact_once`：该补丁只复制并更新 `prepare_target_contact` Operation，不修改 Strategy、评分片段或原 Plan。`Phase3RepairSignalMapper` 仅消费 Phase 3 已解析的结构化攻击证据，将 `missing_contact` 回流到受控 Runtime Patch；未支持的动态错误不会扩展为自由 Lua 修复。

Phase 5 仍不生成四候选、不提供 CandidateComparator/排行榜，也未接入 Chat、Auto、Experience 或 Skill。当前普通回归为 `491 passed, 2 skipped`；真实 scored 6v4 Candidate Workflow CMO 验收尚需在具备足够执行窗口时单独运行并记录 run_id、Results 与 Outcome。

## 11. Phase 3 最小执行反馈闭环

已实现 `Phase3EvaluationService` 与 `Phase3EvaluationHook` 的最小闭环。scored 执行可将 Hook 交给 `CmoRunner`，在 `CmoRunResult` 和运行产物落盘后自动评估，且 Hook 失败只写入 `unscorable` 产物，不改变原始 CMO 执行结论。结果定位只接受 `CmoRunResult` 显式给出的 `batch_result_dir`，不扫描或选择历史最新 Results；仅在唯一 `001_*` job 的 `events.sqlite` 中核验本轮 Lua 脚本名，SQLite 不可用时才读取同 job 的 `combat-summary.csv`。解析器只读取 `side_scores`、场景单位毁伤、计划相关 `weapon_events`、`run_info` 与本 job 的 `lua-output.log`，不会解析完整 AALog 或保留原始事件流。

产物固定为 `combat_evidence.json`、`semantic_validation.json`、`combat_metrics.json` 和 `reward_breakdown.json`。`EvidenceReconciliation` 只输出 `valid`、`unscorable`、`result_integrity_failed`；未知场景单位、脚本不匹配或评分规则毁伤与 CMO 原生分数不一致时拒绝评分。CMO 武器对象的自毁记录不作为场景单位毁伤。`AttackEpisode` 仅来自 ExecutionPlan 中的攻击操作，并在数据可得时聚合发射、命中和拦截；普通轮询和重复成功日志不会进入 `key_events`。

最新自动端到端验证为 `phase3_gate_6v4_cdrive_5`，Results 位于 `C:\CMO\CmoBatchRunner\Results\20260723-152951`：Batch 成功 1、失败 0，任务配置恢复成功；红方原生分数差为 `-40`，`red_j15_1` 与 `red_j15_2` 各生成一个 `-20` 毁伤计分项，四份 JSON 自动写入 `runs/phase3_gate_6v4_cdrive_5/phase3/`。这不是 Research Reward、CandidateOutcome 或 CandidateEvaluationWorkflow；后续阶段仍须保持这些边界。
