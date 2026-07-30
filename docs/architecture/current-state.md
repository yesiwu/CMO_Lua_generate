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

## Phase 9C-0 生产接线

Phase 9C-0 已建立唯一生产装配路径：

```text
chat --profile campaign
→ ProductionEvolutionServiceFactory
→ ProductionPreviewBuilder
→ FrozenCandidateSet
→ GenerationApprovalGrant
→ ProductionGenerationExecutor
→ Phase 6 → Phase 7 → Phase 8
```

当前实现边界：

- `standard` Chat 不注册 Evolution Tool；`campaign` Chat 只注册六个高层
  Campaign Tool，且不暴露 `execute_cmo` 或底层 Phase 6/7/8 Tool。
- Preview 是唯一 Strategy Proposal LLM 阶段。同一 revision 重复读取冻结
  Snapshot 和 Candidate Set；执行阶段只通过
  `FrozenCandidateSetProvider` 解析、校验冻结策略，不再次调用 Proposal
  LLM。
- Production Knowledge Snapshot 复用正式 `KnowledgeSnapshotService`，
  固化 Experience Store revision、index checksum、检索条件、选中经验、
  Bootstrap checksum 和精确 Cohort 的 Active Curated Skill。Pending Skill
  不进入 Snapshot。
- `PermissionHook` 的可信回执由本机 OS 用户归因：
  `actor_source=local_os_user`，
  `identity_strength=local_os_attribution`。Tool 不能接收或自行构造
  approval ID。
- `campaign-control-state.json` 是 ApprovalUsage、Campaign Budget、
  Attempt Slot 和 Operation 状态的事务权威；`operation-ledger.jsonl`
  是确定性审计投影。`started/unknown` 不会在 Resume 时自动重跑。
- 每个 CMO Attempt 在授权后复制独立 `.scen` 和 `candidate.lua`，生成
  独立 `batch-job.json` 与 Results 目录；Attempt 前后校验受控源
  `.scen` checksum，不读取 `tot-three.json` 或 `all1v1.lua`。
- Pause 在 Candidate 安全收口后生效并撤销现有审批；Resume 只对账并回到
  `awaiting_approval`。Stop 产生 `cancelled_incomplete` 时不排行、不执行
  Phase 7/8、不选择 Champion。
- 生产 prepare 默认要求 clean working tree、人工 VerificationRecord、
  `.scen` checksum 一致，以及 `CmoBatchRunner.exe` 和 `Command.exe`
  preflight 通过。
- Fake 生产装配测试资产统一标记 `test_fixture`，不能成为正式评分、
  Experience 或 Skill 证据。

Phase 9C-0 尚未完成的真实验收：

- 未运行真实 Chat 单代 CMO Smoke；
- 本机 `.scen` 尚需操作员通过 `scripts/manage_cmo_assets.py verify`
  明确确认；
- `process_restart_recovery=not_validated`，当前 Worker 只支持同进程后台
  线程；
- 未执行真实多代 Campaign；
- Campaign 不会自动 approve/reject Pending Skill；
- `cmo_effectiveness_validation=not_run`。

Phase 9C-0 Fake 生产装配验收（2026-07-28）：

```text
compileall: passed
evolution: 46 passed
optimization: 10 passed, 1 cmo_integration skipped
learning: 74 passed
full suite: 621 passed, 3 cmo_integration skipped
git diff --check: passed
```

上述结果只证明生产接线、冻结候选、审批事务、动态 Job、场景副本、
Pause/Stop、恢复规则和 Phase 6/7/8 调用边界的 Fake 工程验收，不代表
真实 Chat 单代 CMO Smoke 已完成。

## Phase 9C Two-Stage Strategy Proposal

- The formal proposal implementation remains
  `optimization/strategy_proposal_agent.py`; the untracked agent draft is not
  imported or registered.
- Preview uses one constrained intent-planning JSON call, then one scalar Patch
  request for each fixed candidate in order. Each candidate may make one local
  structured repair request, so a preview consumes 5 to 9 proposal calls.
- Complete StrategySpec objects are assembled deterministically from the
  baseline. The LLM cannot replace objects or arrays, stable IDs, scenario IDs,
  or weapon DBIDs. `StrategyCandidate.intended_difference` is derived from the
  validated Patch diff, not a model-provided summary.
- Preview reserves the worst-case nine proposal calls before starting. Frozen
  previews remain the only execution input and idempotent preview reads use no
  additional proposal calls.
- This change does not invoke CMO or a production LLM endpoint.

## Phase 9C Candidate Role Constraints

- Formal Phase 9C previews use four system-owned role contracts before any
  proposal LLM call: `exploit` (3-5 leaves, 2 operations, 2 dimensions),
  `robust_repair` (3-5, 2, 2), `coordinated_explore` (5-8, 3, 3 with both
  surface and sortie coverage), and `conservative_control` (1-2 leaves in
  exactly one operation and one semantic dimension).
- `StrategyProposalAgent` performs deterministic catalog feasibility checks
  before invoking the Intent Planner or Patch Generator. An insufficient
  catalog returns `candidate_role_not_feasible` with operation, dimension,
  surface, and sortie counts, and consumes zero proposal calls.
- Candidate intent constraints are system-owned. The LLM supplies only an
  objective and preferred dimensions; conformance derives actual leaves,
  operations, dimensions, platform coverage, and optional frozen failure
  profile coverage from the assembled Patch.
- A missing failure profile leaves `candidate_01` as generic `robust_repair`;
  no failure evidence is invented. When a frozen profile is supplied, its
  operation IDs or semantic dimensions must be touched.
- This milestone changes no CMO, approval, scoring, or Candidate Quality
  Report behavior.

## Phase 9C Proposal Tactical Context

- `ProposalTacticalContextBuilder` deterministically projects the Derived
  Baseline, ScenarioDefinition, executable Patch Catalog, C2 role contract,
  optional frozen Failure Profile, and accepted candidate summaries into a
  canonical JSON context with a checksum.
- The context contains only scenario/unit summaries, operation-level target,
  timing, quantity, reserve, route, and patchable-path facts; target and
  platform coupling groups; role requirements; and accepted coverage facts.
- Planner and Patch Generator prompts receive this compact context. They do
  not receive a complete StrategySpec, candidate Lua, Runtime Lua, native
  score implementation, SQLite, AALog, execution timeline, legacy Baseline,
  or score prediction.
- Production Preview persists `proposal-context.json` and records its checksum,
  baseline-operation count, patchable-path count, and Failure Profile
  availability in `proposal-trace.json`.
- C3 does not modify C2 role thresholds, Patch validation, CMO execution,
  scoring, approvals, or Candidate Quality Report behavior.

## Phase 9C Candidate Quality Gate

- `CandidateQualityEvaluator` runs only after `CandidateSetValidator` and
  `CandidateNoveltyValidator`, and before a `FrozenCandidateSet` is written.
  It consumes assembled strategies, system-owned role constraints, actual
  baseline diffs, and the frozen tactical context; it does not use an LLM
  quality assertion or predict a CMO score.
- `candidate-quality-report.json` is canonical and deterministic. It records
  per-candidate leaf, operation, platform, dimension, surface/sortie, role,
  and baseline-distance facts, plus all six pairwise Jaccard/value comparisons.
- The batch gate requires unique strategy checksums, at least four operations,
  three semantic dimensions, two platform types, one surface-plus-sortie
  candidate, distinct operation sets across candidates 00/01/02, and the C2
  conservative-control scope for candidate 03.
- Same changed paths with different scalar values are reported in Pairwise
  data and are not rejected solely for sharing a path. A failed quality gate
  writes the report and trace checksum, sets Preview to
  `awaiting_operator_action`, and never freezes candidates, calls an extra
  LLM, creates an Approval, or starts CMO.

## Phase 9C Fake Preview Acceptance

- The formal bounded preview chain has a deterministic Fake JSON acceptance
  test: ScenarioIR-derived Baseline, tactical context, one Intent Planner call,
  four Patch Generator calls, assembly, all validators, quality gate, and
  FrozenCandidateSet. No CMO, Approval, Phase 7, or Phase 8 is invoked.
- Preview now persists `candidate-intents.json` and `candidate-patches.json`
  from the bounded proposal trace. A FrozenCandidateSet also binds the
  ScenarioIR, derived Baseline, tactical-context, knowledge-snapshot, and
  candidate-quality checksums in addition to its four strategy checksums.
- Fake previews are explicitly marked `proposal_provider="fake"` and
  `production_execution_eligible=false`; they cannot be confused with an
  execution-eligible production preview. Replaying an already frozen revision
  reads the same artifacts and consumes zero additional proposal calls.
- C5 includes role-conformance, post-proposal batch-quality, and deferred
  `fire_delay_seconds` failure cases. These failure paths never freeze a
  candidate set or start CMO.

## Phase 9C Baseline Derivation

- `json_data/6v4ScenarioIR.json` is the only production 6v4 Baseline input.
  `BaselineStrategyBuilder` derives the Baseline deterministically for every
  new Campaign.
- `baseline/6v4/generated/` is Golden and audit output only, never a
  production input.
- `baseline/6v4/legacy/` is read-only historical material. New Campaigns
  reject it rather than using a fallback.
- A real Baseline CMO Golden still waits for deployment of the updated
  BatchRunner.

## 健康检查

```powershell
$env:PYTHONPATH="$PWD\src"
python -m compileall src\cmo_lua_agent
python -m pytest src\cmo_lua_agent\tests -q
git diff --check
```

真实 CMO 集成测试必须通过对应 `CMO_*` 环境变量显式启用。普通回归
测试不依赖本机 CMO。
