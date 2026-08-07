# Lua 生成实际链路

本文基于当前仓库代码核对 JSON 到 Lua 的实际主链路。它描述的是
`ScenarioWorkflow` / `generate_cmo_lua` 当前调用的确定性流程，不把 Phase 2
的 `ExecutionPlan -> LuaRenderer` 路径、Phase 5/6 的候选评测路径或 CMO 执行
路径混入其中。

## 结论

原说明的总体分层是合理的：输入 JSON 经过校验、IR、数据库解析和 Manifest
后交给生成器，随后进行 Lua 预检并保存产物。

但有五处需要修正：

1. 当前正式输入并不是泛化的 `sides[] / units[] / missions[] / terrain`。
   当前 Schema 至少要求根对象中的 `scenario`、`sides` 和 `strikePlan`；
   `sides` 是包含 `red`、`blue` 的对象，每一方内部才有 `units` 数组。
2. 外部 `CMOLua-main/tools/json_to_lua.py` 接收的是本项目已解析完成的
   `resolved_manifest.json`，而不是直接接收用户原始 JSON。
3. 成功 Lua 的当前路径是
   `runs/<run_id>/generation/original.lua`，不是
   `runs/<run_id>/original.lua`。
4. `generate_cmo_lua` 主链不调用 `LuaRenderer`，也不执行 CMO 或 Lua 自动修复。
   它使用 `CmoLuaGeneratorAdapter` 调用外部确定性生成器，再做预检。
5. `LuaRenderer` 是 Phase 2 及后续受控策略链的另一条生成路径；它没有替代
   现有 `ScenarioWorkflow` 的默认 JSON 到 Lua 路径。

## 入口与输入

有两个等价入口会进入同一条工作流：

```text
CLI: python -m cmo_lua_agent.main run <SCENARIO_JSON>
Chat Tool: generate_cmo_lua(json_path=..., runs_root=..., run_id=...)
                                  |
                                  v
                         ScenarioWorkflow.run(...)
```

`GenerateCmoLuaTool` 位于
`src/cmo_lua_agent/tools/generate_cmo_lua_tool.py`。它只校验工作区路径，
调用 `ScenarioWorkflow`，并返回结构化结果；该工具明确不启动 CMO。

当前 JSON 的最小结构边界由
`src/cmo_lua_agent/contract/scenario_schema_validator.py` 定义：

```json
{
  "scenario": {
    "id": "stable_scenario_id",
    "name": "显示名称"
  },
  "sides": {
    "red": {"name": "红方", "units": []},
    "blue": {"name": "蓝方", "units": []}
  },
  "strikePlan": []
}
```

单位结构还会经过字段和语义校验；数据库中的平台、武器和 Loadout 事实不是由
模型猜测，而是由后续 `DatabaseResolver` 使用 CMO 数据库补齐。若平台类别或
DBID 有歧义，工作流返回 `platform_resolution_required`，必须由用户提供
`platform_resolutions` 后重新运行。

## 默认 JSON 到 Lua 数据流

```text
source JSON
  |
  v
JsonLoader -> ScenarioInput
  |
  v
ScenarioSchemaValidator -> schema validation report
  |
  v
ScenarioSemanticValidator -> normalized mapping + semantic report
  |
  v
IRBuilder -> ScenarioIR -> IRValidator
  |
  v
DatabaseResolver(CmoDatabaseRepository) -> resolved ScenarioIR
  |
  +--> ScenarioDefinitionBuilder -> ScenarioDefinition + InitialStrategyHint
  |                                  (side artifacts; not Lua input)
  v
ManifestBuilder -> ScenarioContract + ResolvedScenarioManifest
  |
  v
CmoLuaGeneratorAdapter -> CMOLua-main/tools/json_to_lua.py::generate_cmo_lua
  |
  v
LuaPreflightValidator -> LuaGenerationResult
  |
  v
RunArtifactStore -> generation/original.lua + workflow_result.json
```

`ScenarioWorkflow` 位于
`src/cmo_lua_agent/orchestration/scenario_workflow.py`，依赖图由
`src/cmo_lua_agent/bootstrap/app_factory.py::create_application()` 组装。

## 阶段、对象和调用文件

| 阶段 | 主要文件 | 输入 | 输出 | 是否改变用户原始 JSON |
|---|---|---|---|---|
| 文件读取 | `ingest/json_loader.py` | JSON 文件路径 | `ScenarioInput` | 否 |
| 结构校验 | `contract/scenario_schema_validator.py` | `ScenarioInput` | `ValidationResult` | 否 |
| 语义标准化 | `contract/scenario_semantic_validator.py` | `ScenarioInput` | 标准化 mapping、`ValidationResult` | 不修改原始对象；处理副本 |
| IR | `contract/ir_builder.py`、`contract/ir_validator.py` | 标准化 mapping | `ScenarioIR`、校验报告 | 否 |
| 数据库解析 | `contract/database_resolver.py`、`integrations/cmolua/database_repository.py` | `ScenarioIR` | 补全 DBID 的 `ScenarioIR`、解析报告 | 否 |
| Phase 1 派生产物 | `contract/scenario_definition_builder.py` | 已解析 IR | `ScenarioDefinition`、`InitialStrategyHint` | 否 |
| Manifest | `contract/manifest_builder.py` | 已解析 IR | `ScenarioContract`、`ResolvedScenarioManifest` | 否 |
| 外部生成 | `generation/lua_generation_service.py`、`integrations/cmolua/generator_adapter.py` | Manifest 文件 | Lua 文本、生成器警告 | 否 |
| 预检 | `generation/lua_preflight_validator.py` | Lua 文本、Manifest、Contract | 预检结果 | 否 |
| 产物写入 | `artifacts/run_artifact_store.py`、`orchestration/workflow_context.py` | 各阶段对象 | Run 目录文件 | 不写回输入 |

外部生成器路径和数据库路径由
`src/cmo_lua_agent/integrations/cmolua/config.py` 配置；默认情况下它们指向：

```text
CMOLua-main/tools/json_to_lua.py
CMOLua-main/mcp/db/DB3K_504.db3
```

环境变量 `CMO_LUA_GENERATOR_PATH`、`CMO_DATABASE_PATH` 等可以覆盖这些默认
路径。`CmoLuaGeneratorAdapter` 采用延迟加载，在真正生成时才导入外部模块。

## 成功运行的产物

一次成功的默认工作流写入：

```text
runs/<run_id>/
├── input/source.json
├── validation/
│   ├── schema_report.json
│   ├── semantic_report.json
│   ├── ir_report.json
│   ├── database_report.json
│   ├── manifest_report.json
│   ├── strategy_report.json
│   └── lua_preflight_report.json
├── contract/
│   ├── scenario_ir.json
│   ├── scenario_contract.json
│   ├── resolved_manifest.json
│   └── scenario_definition.json
├── strategy/
│   └── initial_strategy_hint.json
├── generation/original.lua
└── result/workflow_result.json
```

配置了已验证 Baseline 时，`strategy/` 还会包含
`baseline_strategy.json` 和 `initial_hint_vs_baseline.json`。若预检失败，
Lua 文本会保存为 `generation/rejected.lua`，而不会作为正式可执行 Lua 返回。

## 不属于这条主链的内容

### CMO 执行

CMO 执行是独立的 `execute_cmo` 工具，底层为
`execution/cmo_runner.py` 和 `execution/cmo_process_runner.py`。它需要人工审批，
并在已经存在 Lua 文件后运行。`generate_cmo_lua` 不会隐式调用它。

### Phase 2 及后续的受控策略链

下面这条链用于 Baseline、候选策略和优化，不是普通场景 JSON 的默认生成器：

```text
ScenarioDefinition + StrategySpec
  -> ExecutionPlanCompiler
  -> CapabilityValidator
  -> LuaRenderer / ScoredLuaAssemblyService
  -> deterministic rendered Lua
```

相关模块包括：

```text
generation/execution_plan_compiler.py
generation/capability_validator.py
generation/lua_renderer.py
generation/scored_lua_assembly.py
optimization/candidate_evaluation_workflow.py
```

这条路径支持 Runtime Primitive、Source Map、评分 instrumentation 和候选评测。
它不能被描述成 `ScenarioWorkflow` 在外部生成器之后必然执行的下一步。

### LLM 与修复

默认 `ScenarioWorkflow` 中没有 Claude 调用，也没有自动 Lua 修复循环。LLM 只在
更上层的受控 Agent 中出现，例如 `LuaSynthesisAgent`、`LuaRepairAgent` 和
`StrategyProposalAgent`。这些 Agent 生成或修改的是 `StrategySpec`/受限 Patch，
然后进入受控的 Compiler/Renderer 链，而不是自由拼接 Lua。

## 推荐的简化表述

对外说明当前默认能力时，建议使用以下版本：

> 系统接收符合 CMO 场景 Schema 的 JSON。它依次完成文件读取、结构与语义校验、
> IR 构建、CMO 数据库解析、Manifest 构建，再调用 `CMOLua-main` 的确定性
> `generate_cmo_lua()` 生成 Lua，最后执行静态预检。成功产物保存在
> `runs/<run_id>/generation/original.lua`，并同时保存 IR、Manifest、校验报告和
> `workflow_result.json`。此默认流程不调用 LLM，也不执行 CMO；CMO 执行和 Phase 2+
> 的策略编译/候选优化是独立链路。
