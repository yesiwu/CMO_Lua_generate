# 当前实现状态

更新日期：2026-07-27。

本文只记录已经接入并可通过测试验证的正式路径。草稿、计划文件、
运行产物和 legacy 模块不代表可用能力。

## 主链路

```text
Chat / run CLI
  -> ScenarioWorkflow
  -> JSON 校验
  -> Scenario IR / Contract
  -> 数据库解析
  -> CMOLua-main
  -> Lua 预检

execute_cmo
  -> CmoRunner
  -> CmoBatchRunner
  -> Results / runner.log / 运行产物
```

`ScenarioWorkflow` 的默认职责仍是 JSON 到 Lua。CMO 执行是独立、
需要审批的工具调用。

## 已实现阶段

- Phase 1：`ScenarioDefinition`、`InitialStrategyHint`、`StrategySpec`
  与已验证 Baseline。场景事实、库存上限和策略参数已经分离。
- Phase 2：`ExecutionPlanCompiler`、`CapabilityValidator`、确定性
  `LuaRenderer`、Runtime Primitive/Helper 分层及 6v4 Golden。
- Phase 3：CMO 原生计分编译、评分 instrumentation、
  `Phase3EvaluationService` 和结果证据产物。正式最终分数只接受
  `execution-summary.json#/official_score/final`。
- Phase 4：受控 `LuaSynthesisAgent` 与单次 `LuaRepairAgent`。
  Agent 只能生成结构化策略或受限补丁，不能生成自由 Lua。
- Phase 5：单候选 `CandidateEvaluationWorkflow`，支持受限
  Strategy Patch 和唯一 Runtime Patch `retry_missing_contact_once`。
- Phase 6：`OptimizationGenerationWorkflow`，支持 Bootstrap Skill、
  Baseline 加四候选串行评估、正式 Comparator 与确定性排行榜。
- Phase 7：只读 Learning View、Bundle、受控对比分析、
  `ExperienceCandidate`、幂等 Experience Store、Retriever 和
  Experience Card。
- Phase 8：经验聚合、Cohort 隔离、确定性资格验证、晋升决策、
  Pending Skill 组装、三类静态回归、人工审批和 Active Skill 加载
  的工程链已经实现。
- Phase 9：已新增受控 Campaign 的基础编排层：不可变 Campaign 契约、
  CMO/LLM 预算、操作账本、知识快照、四角色生成上下文、候选新颖性门控、
  Champion/Stop 策略、Fake 三代端到端测试及全局 CMO 锁。Fake 产物固定标记
  `phase9_fake_fixture`，不会写入正式 Experience Store 或触发真实 Skill 晋升。
  本阶段未启动真实 CMO，也未产生真实多代经验、Pending/Curated Skill 或
  CMO effectiveness validation。

## 评分边界

正式 `CandidateOutcome` 分别保存：

```text
execution_success
native_score
scoreable
semantic_valid
rank
score_source
```

语义无效不会覆盖已经验证的 CMO 原生最终分数，但该候选不能排名。
SQLite、CSV、日志、最低分和中间累计分只作为辅助证据，不能替代
`execution-summary.json` 的官方最终分数。

## Phase 7 边界

正式对比学习 Agent 位于：

```text
src/cmo_lua_agent/agents/comparative_learning_agent.py
```

它只接收 `GenerationLearningBundle`，输出
`ComparativeAnalysis` 和 `ExperienceProposal`。正式 Proposal 与
Candidate 必须显式携带：

```text
evidence_stance = support | contradict | qualify
```

事实字段由确定性 Assembler 补充。Phase 7 不重跑 CMO，不修改
Outcome、排行榜或同一代候选。Retriever 强制排除当前
`optimization_id`。

以下模块属于 legacy/unwired，不得导入正式 Phase 7/8 路径：

```text
src/cmo_lua_agent/memory/experience_store.py
src/cmo_lua_agent/memory/experience_retriever.py
```

## Phase 8 安全边界

Bootstrap Skill 位于源码目录并保持只读：

```text
src/cmo_lua_agent/skills/bootstrap/
```

运行时可变资产只能位于：

```text
data/skills/
```

生产 Store 固定为项目根目录的 `data/skills`。测试必须显式使用
`SkillStoreMode.TEST` 和 pytest 临时目录，产物标记
`provenance=test_fixture`；Fixture 永远不能进入生产 Curated Store。

Phase 8 只按显式 `evidence_stance` 聚合。缺失或非法 stance 的旧记录
会以 `missing_or_invalid_evidence_stance` 排除，不根据
`experience_type` 推断。

Pending 包绑定不可变 `PromotionDecision`。人工批准时必须重新验证：

- 决策可晋升且 action 合法；
- validated experience、Family、Cohort、版本和 provenance 一致；
- 三类回归检查全部通过；
- 实际磁盘包、metadata、回归报告和人工提供的 checksum 完全一致。

`compute_skill_package_checksum()` 覆盖全部受保护文件。任何受保护内容
被修改后，审批和 Active Skill 加载都会失败。`current.json` 只能由
成功的 `approve()` 更新。

回归报告明确区分：

```text
static_validation_passed
traceability_validation_passed
proposal_regression_passed
cmo_effectiveness_validation = not_run
```

## Phase 8 当前真实状态

- Phase 8 工程链已实现。
- 当前真实 Experience Store 没有可用于晋升的聚合经验。
- 尚未产生真实 Pending Skill。
- 尚未产生真实 Curated Skill。
- 测试 Fixture 仅用于 pytest 临时目录，标记为
  `artifact_provenance=test_fixture`、`store_mode=test`；它只验证聚合、
  晋升、Pending、回归和审批隔离工程链，不属于真实 CMO 经验或真实 Skill。
- `cmo_effectiveness_validation=not_run`，没有宣称通过真实 CMO
  验证 Skill 的战斗效果。

## 尚未实现

- 自动审批或自动激活 Skill；
- 真实 CMO Skill 效果回归；
- 通用跨领域 Skill 进化；
- 多代自动优化和向量经验数据库；
- Chat/Auto 默认接入 Phase 7/8；
- Research Reward、因果归因和自动战术解释。

## Phase 9B Chat Campaign Control Plane

- The campaign Chat profile exposes exactly six high-level tools:
  `prepare_evolution_campaign`, `preview_evolution_generation`,
  `execute_evolution_generation`, `inspect_evolution_campaign`,
  `inspect_evolution_generation`, and `control_evolution_campaign`.
  It does not expose `execute_cmo` or Phase 6/7/8 implementation tools.
- Campaign state, previews, approvals, checkpoints, worker state, and the
  operation ledger are persisted below `runs/evolution/<campaign_id>/`.
  Chat history is not a source of campaign state.
- Preview is idempotent by generation/revision. Regeneration invalidates prior
  approvals. Strategy-proposal LLM budget is consumed only for a new preview.
- `execute_evolution_generation` is asynchronous: it returns a worker
  operation ID. The Worker checks persistent pause/stop requests at safe
  boundaries. A cancelled incomplete generation skips ranking, Phase 7/8
  learning, and champion selection.
- PermissionHook creates a trusted in-process approval receipt. The Campaign
  Permission Broker validates the matching approval, preview, contract,
  budget, control request, worker state, and CMO lock before each attempt.
- Phase 9B was validated only with Fake workers. No real CMO Chat smoke ran.

## 健康检查

```powershell
$env:PYTHONPATH="$PWD\src"
python -m compileall src\cmo_lua_agent
python -m pytest src\cmo_lua_agent\tests -q
git diff --check
```

真实 CMO 集成测试必须通过对应 `CMO_*` 环境变量显式启用。普通回归
测试不依赖本机 CMO。
