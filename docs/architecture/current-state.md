# 当前实现状态

更新日期：2026-07-27。本文件只记录已接入、可验证的正式路径；草稿、计划文件和未接入模块不代表可用功能。

## 主链路

```text
Chat / run CLI
  -> ScenarioWorkflow
  -> JSON 校验 -> Scenario IR -> 数据库解析
  -> CMOLua-main -> Lua 预检 -> original.lua

execute_cmo
  -> CmoRunner -> CmoBatchRunner
  -> Results / runner.log / 运行产物
```

`ScenarioWorkflow` 默认只完成 JSON 到 Lua。CMO 执行是独立、需审批的工具调用。

## 已实现

- Phase 1：`ScenarioDefinition`、`InitialStrategyHint`、`StrategySpec` 与已验证 Baseline。场景事实、库存和策略参数已分离。
- Phase 2：`ExecutionPlanCompiler`、`CapabilityValidator`、确定性 `LuaRenderer`、Runtime Primitive/Helper 分层及 6v4 Golden。
- Phase 3：CMO 原生计分编译、评分插桩、`Phase3EvaluationService` 与结果证据产物。正式最终分数唯一来自 `execution-summary.json#/official_score/final`；SQLite、CSV 和日志只作为辅助证据。
- Phase 4：受控 `LuaSynthesisAgent` 与单次 `LuaRepairAgent`。LLM 只能生成结构化策略或受限补丁，不能生成自由 Lua。
- Phase 5：单候选 `CandidateEvaluationWorkflow`，支持受限 Strategy Patch 和唯一 Runtime Patch `retry_missing_contact_once`。
- Phase 6：`OptimizationGenerationWorkflow`，固定 Bootstrap Skill、Baseline 加四候选的串行评估、正式 Candidate Comparator 与确定性排行榜。
- Phase 7：`src/cmo_lua_agent/learning/` 提供只读 Learning View、Bundle、Proposal 型对比分析、经验键归一化、幂等 Experience Store、Retriever 和 Experience Card。

## Phase 6 与评分状态

正式 CandidateOutcome 记录 `execution_success`、`native_score`、`scoreable`、`semantic_valid`、`rank` 和 `score_source`。语义无效不会覆盖已验证的原生分数，但不会参与排名。

历史 `candidate_03` 的摘要可验证为：`0 -> -20 -> -40 -> 35`，最终分数为 `35`。新鲜正式候选如无计分事件，摘要中的 `final=0` 是运行事实，不得由旧 SQLite、CSV 或最低中间分数伪造替换。

## Phase 7 边界

Phase 7 只消费已落盘的正式 Phase 6 产物，不重新执行 CMO、不修改评分、Outcome、排行榜或同一代候选。经验默认状态为 `candidate`，只影响后续优化轮；Retriever 强制排除当前 `optimization_id`。

正式 Phase 7 LLM Agent 位于 `src/cmo_lua_agent/agents/comparative_learning_agent.py`。它只接收 `GenerationLearningBundle`，并仅返回受限的 `ComparativeAnalysis` 与 `ExperienceProposal`；事实字段仍由确定性学习链路补充。

`src/cmo_lua_agent/memory/experience_store.py` 与 `src/cmo_lua_agent/memory/experience_retriever.py` 是 legacy/unwired 代码。它们使用旧 SQLite 或完整 Lua 经验模型，禁止被正式 Phase 7 路径导入。

Phase 7 已对 `runs/phase6_score_summary_20260725_b` 完成一次真实 LLM 离线验收。该轮五个正式 Outcome 缺少 `execution-summary.json` 且均未通过语义/计分门控，因此保守地产生零条 ExperienceCandidate；没有生成战术正向经验。正式官方得分只接受 `execution-summary.json#/official_score/final`，不回退 Outcome、SQLite、CSV 或中间分数。验收入口为 `scripts/run_phase7_learning.py`，其第二次回放复用已保存的 LLM 响应以验证 Store 幂等，不会再次调用模型或启动 CMO。

## 未实现

- Phase 8：经验跨运行聚合、Skill 晋升策略、SkillAuthorAgent。
- 向量数据库、多代自动优化、Chat/Auto 默认接入。
- Research Reward、因果归因、自动战术解释。
- 对所有历史 Results 的自动重放或 CMO 并行执行。

## 健康检查

建议使用：

```powershell
$env:PYTHONPATH="$PWD\src"
python -m compileall src\cmo_lua_agent
python -m pytest src\cmo_lua_agent\tests -q
git diff --check
```

真实 CMO 集成测试必须显式启用对应的 `CMO_*` 环境变量，普通回归测试不依赖本机 CMO。
