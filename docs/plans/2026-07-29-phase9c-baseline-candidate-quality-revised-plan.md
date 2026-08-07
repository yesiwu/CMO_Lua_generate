# Phase 9C Baseline、候选质量与 Campaign 完整性改进计划（修订版）

> **状态基线：** Phase 3 读取端已完成严格化改造；当前计划不再包含“从旧 Results 修补官方分数”的任务。后续只接受新版 BatchRunner 产生的、满足完整评分契约的 `execution-summary.json`。

## 目标

在不破坏正式链路的前提下，完成四件事：

1. 验证新版 BatchRunner 能稳定产出 Phase 3 所要求的正式评分摘要；
2. 将 `6v4ScenarioIR.json` 建立为 6v4 场景事实和 Baseline 任务的唯一正式来源；
3. 区分策略差异、Lua 渲染、Dynamic Job、场景运行时长和评分采集对结果的影响；
4. 扩大受控候选搜索空间，同时保证不完整 Generation 不会进入排行榜、Phase 7、Phase 8 或 Champion 选择。

正式策略链保持：

```text
ScenarioIR
→ Derived Baseline StrategySpec
→ Candidate Intent
→ Bounded StrategyPatch
→ StrategySpec
→ ExecutionPlanCompiler
→ ScoredLuaAssemblyService
→ DynamicBatchJob
→ CMO
→ execution-summary.json
→ Phase 3
→ Comparator
```

禁止恢复：

```text
LLM 直接输出完整 Lua
LLM 修改 ScoreSpec / Runtime / Stable ID
Phase 3 从 SQLite、CSV、显示名或旧摘要猜测分数
外部参考 Lua 参与正式排行榜
```

---

# 一、当前已完成事实

## 1. Phase 3 读取端已严格化

当前 Phase 3 只接受新版 `execution-summary.json`，必须同时满足：

```text
stable_side_id == "red"
cmo_side_id == "red"
official_score.status == "VALID"
score_event_chain_status == "VALID"
evidence_integrity.status == "VALID"
```

并校验：

```text
initial + sum(score_events.delta) == final
```

每个计分事件必须包含：

```text
稳定规则 ID：native_score/...
原始规则名
delta
证据引用
```

`display_name` 仅要求存在，不参与分方匹配。

已删除：

```text
SQLite 回填
旧摘要修改
红方/蓝方显示名猜测
最低分替代最终分
旧 Results 自动修补
```

已覆盖：

```text
35 / 60 / 260 最终分数链
-40 最低分不替代 official final
UNSCORABLE 摘要保持不可评分
```

验证状态：

```text
compileall：通过
全量测试：649 passed, 3 skipped
git diff --check：通过
```

## 2. 当前剩余评分阻塞在生产端

Phase 3 消费契约已经完成，但仍需新版 BatchRunner 实际生成包含下列字段的 Results：

```text
stable_side_id
cmo_side_id
official_score.status
official_score.initial
official_score.final
score_events
score_event_chain_status
evidence_integrity
```

因此下一步不是再次修改 Phase 3，而是验证：

```text
新版 BatchRunner Producer
→ 新版 execution-summary.json
→ 当前 Phase 3 Consumer
```

旧 Results 不再具有正式评分资格。

---

# 二、实施原则

## 1. 分阶段实施

本计划拆为三个里程碑，禁止评分、Baseline 和候选生成同时大改。

### Milestone A：结果正确性和执行路径隔离

解决：

```text
新版 BatchRunner 摘要契约
Dynamic Job 是否改变 CMO 行为
Lua 是否完整执行
不完整 Generation 控制流
审批过期后的同代恢复
```

### Milestone B：Baseline 单一来源

解决：

```text
ScenarioIR → ScenarioDefinition
ScenarioIR → Derived Baseline StrategySpec
auto weapon selection 保真
Preview 冻结派生身份
Baseline 正式 Golden
```

### Milestone C：候选质量

解决：

```text
历史舰机协同策略正式化
多 operation 候选模板
战术上下文增强
候选质量报告
完整五项真实 Campaign
```

## 2. 必须保留的边界

```text
独立 scenario.scen 副本
独立 Lua
独立 Dynamic Job
独立 Results
官方 execution-summary 分数
CMO Instance Lock
Operation Ledger
Frozen Candidate Set
审批 slot 白名单
不允许修改稳定 ID、DBID、Loadout、评分和 Runtime
```

## 3. 可以简化的边界

```text
不重复维护多套 per-candidate 预算权威
Approval 可收紧 Campaign hard ceiling
审批过期不直接报废整个 Generation
候选质量不只用 changed leaf 数衡量
```

---

# Milestone A：正确性和执行路径隔离

## Task A1：冻结新版评分 Producer/Consumer 契约

**目标：** 确认新版 BatchRunner 能生成当前 Phase 3 唯一接受的摘要。

**新增：**

```text
src/cmo_lua_agent/tests/integration/test_batchrunner_execution_summary_contract.py
docs/architecture/execution-summary-v2-contract.md
```

**验收字段：**

```json
{
  "official_score": {
    "status": "VALID",
    "stable_side_id": "red",
    "cmo_side_id": "red",
    "display_name": "红方",
    "initial": 0,
    "final": -40
  },
  "score_events": [],
  "score_event_chain_status": "VALID",
  "evidence_integrity": {
    "status": "VALID"
  }
}
```

**要求：**

- `stable_side_id` 和 `cmo_side_id` 必须来自 CMO 稳定分方身份；
- `display_name` 只展示，不参与匹配；
- `official_score.final` 是唯一最终分；
- `score_events` 必须能重建 final；
- 合法 `0 → 0` 且无事件可以评分；
- 非零 final 缺事件链时必须 `UNSCORABLE`；
- Producer 不输出模糊、翻译或 fallback side identity。

**测试：**

1. `red=-40`、`红方=0` 同时存在，正式摘要必须指向 `red`；
2. `35 / 60 / 260` 可由事件链重建；
3. 最低分不替代最终分；
4. 缺 stable side ID 时 Producer 标记不可评分；
5. Phase 3 只读消费，不修改摘要。

**完成条件：**

```text
新版 BatchRunner 产生至少一份真实 execution-summary v2
→ 当前 Phase 3 可直接读取
→ 不需要任何迁移或补丁
```

---

## Task A2：增加 Runtime 完整执行证据

**目标：** 区分“CMO 进程成功退出”和“全部策略操作确实执行完成”。

**摘要新增：**

```text
simulation_start_time
simulation_end_time
simulation_elapsed_seconds
stop_reason
last_runtime_event_time
last_scheduled_operation_time
scheduled_operation_count
started_operation_count
completed_operation_count
pending_operation_count
lua_bootstrap_seen
score_fragment_registered
execution_fidelity
```

**规则：**

```text
pending_operation_count > 0
或 simulation_end_time < last_scheduled_operation_time
→ execution_fidelity = partial
```

```text
所有计划操作完成
→ execution_fidelity = complete
```

`execution_success=true` 不能自动代表 `execution_fidelity=complete`。

**重点验证：**

- 180 秒以后调度的攻击是否真的发生；
- `stopWhenScenarioEnds` 是否导致后续操作未执行；
- Dynamic Job 的仿真时长是否覆盖最后计划操作；
- Lua bootstrap 和计分片段是否实际注册。

---

## Task A3：建立 Lua / Job / 场景隔离诊断矩阵

**目标：** 在扩大候选空间前，先定位历史分差与当前同分的真正来源。

### 实验 A：固定 Lua，只替换 Job

```text
同一份 formal renderer Lua
+ 同一份源 .scen
```

对比：

```text
历史 tot-three 配置方式
当前 DynamicBatchJobBuilder
```

比较：

```text
scenario path/checksum
script checksum
outputDirectory
simulation.enabled
pulseSeconds
stopWhenScenarioEnds
wallTimeoutSeconds
simulation elapsed seconds
stop reason
攻击事件数
score event chain
official_score.final
execution_fidelity
```

### 实验 B：固定 Dynamic Job，只替换 Lua

```text
当前 Derived Baseline Lua
vs
历史 formal_rendered coordinated candidate Lua
```

历史 Lua只作为诊断输入，不进入正式排行榜。

### 实验 C：固定 StrategySpec，比较 Renderer

同一个 StrategySpec 分别用：

```text
历史正式 Renderer
当前 Compiler + Renderer
```

比较：

```text
ExecutionPlan operation sequence
Runtime Helper checksum
Native Score Fragment checksum
schedule_lua
单位初始化
攻击参数
J-15 起飞/航路/攻击/返航
Lua 行为指纹
```

### 推荐顺序

```text
Producer/Consumer 摘要契约
→ 同 Lua 不同 Job
→ 同 Job 不同 Lua
→ 同 StrategySpec 不同 Renderer
```

任何真实 A/B 实验必须使用独立 Results，不能覆盖正式 Campaign 结果。

---

## Task A4：增加 Generation Completion Gate

**目标：** 不完整 Generation 不得排名、学习或选择 Champion。

**新增：**

```text
src/cmo_lua_agent/evolution/generation_completion_gate.py
src/cmo_lua_agent/tests/evolution/test_generation_completion_gate.py
```

**预期执行对象：**

```text
baseline
candidate_00
candidate_01
candidate_02
candidate_03
```

**终态：**

```text
completed
semantic_invalid
unscoreable
execution_failed
runtime_defect
repair_budget_exhausted
cancelled_after_start
```

**非终态：**

```text
not_started
awaiting_approval
approval_expired_before_start
running
```

**规则：**

```text
五项全部进入明确终态
→ 允许 Comparator
→ 允许后续阶段
```

```text
存在未启动或等待审批对象
→ 不生成 leaderboard
→ 不运行 Phase 7
→ 不运行 Phase 8
→ 不运行 ChampionPolicy
```

**产物：**

```text
generation-incomplete.json
awaiting-approval.json
```

---

## Task A5：审批过期后支持同代续批

**目标：** candidate_03 尚未启动时，不浪费已经完成的 Baseline 和三个候选。

**流程：**

```text
Approval 过期
→ 当前未启动对象保持 pending
→ 保存已有 Outcome
→ 释放 CMO Lock
→ Campaign status=awaiting_approval
```

重新审批时：

```text
只批准剩余 slot
例如 g000:cmo:candidate_03:a00
```

不得重新执行：

```text
Baseline
candidate_00
candidate_01
candidate_02
Proposal LLM
```

仅当以下情况发生时，才不能继续原 Generation：

```text
FrozenCandidateSet checksum 改变
Scenario checksum 改变
Runtime / ScoreSpec / code contract 改变
用户明确 Stop
```

---

# Milestone B：Baseline 单一来源

## Task B1：正式表达 auto weapon selection

**模型：**

```python
WeaponSelectionMode = Literal["auto", "explicit"]
```

```python
AttackDirective:
    weapon_selection: WeaponSelectionMode
    weapon_dbid: int | None
```

**规则：**

```text
auto
→ weapon_dbid=None
→ ExecutionPlan 保留 auto
→ Renderer 输出 CMO 自动选弹模式
```

```text
explicit
→ weapon_dbid 为正整数
→ Renderer 输出指定 DBID
```

**安全边界：**

Candidate Patch 不允许修改：

```text
weapon_selection
weapon_dbid
```

除非未来单独建立经过审计的武器选择策略空间。

---

## Task B2：补齐 ScenarioIR Baseline 语义

`6v4ScenarioIR.json` 必须显式表达：

```text
mission ID
unit ID
target ID
weaponSelection
weaponDbid
fireQuantity
delaySeconds
reserveQuantity
sortie route
altitude
throttle
fire delay
return delay
```

### reserveQuantity 规则

不允许 Builder 临时猜测：

```text
inventory - fireQuantity
```

优先方案：

```text
ScenarioIR 显式写 reserveQuantity
```

暂时缺失时：

```text
使用 schema 明确默认值 0
并在 derivation manifest 记录 defaulted_reserve_quantity
```

默认规则必须写入 schema 和测试，不允许隐藏在 Builder 内部。

---

## Task B3：实现 ScenarioIR → Derived Baseline

**新增：**

```text
src/cmo_lua_agent/contract/baseline_strategy_builder.py
src/cmo_lua_agent/contract/baseline_derivation.py
src/cmo_lua_agent/tests/contract/test_baseline_strategy_builder.py
```

**输出：**

```text
DerivedBaseline.strategy
BaselineDerivationManifest
```

Manifest 至少包含：

```text
schema_version
builder_version
ScenarioIR checksum
ScenarioDefinition checksum
Derived Baseline checksum
mapping checksum
defaulted fields
```

**映射要求：**

- 五条 attack；
- 两条 sortie；
- stable IDs 不变；
- auto weapon selection 保真；
- target、delay、quantity、reserve、route 一致；
- 相同输入产生稳定 checksum；
- 未知 unit/target、重复 ID、非法 route、库存违规被拒绝。

---

## Task B4：Controlled Input Package 切换到派生 Baseline

新 Preview 数据流：

```text
加载 ScenarioIR
→ ScenarioDefinitionBuilder
→ BaselineStrategyBuilder
→ Derived Baseline
→ Preview
```

Preview 必须保存：

```text
derived-baseline-strategy.json
baseline-derivation-manifest.json
frozen-candidate-set.json
strategy-diff.json
knowledge-snapshot.json
proposal-trace.json
```

冻结身份必须包含：

```text
ScenarioIR checksum
ScenarioDefinition checksum
Baseline builder version
Derived Baseline checksum
Runtime checksum/version
ScoreSpec checksum
Bootstrap Skill checksum
CandidateSet checksum
```

旧 Preview 不允许静默吸收新 Baseline。

错误码：

```text
baseline_derivation_identity_mismatch
```

---

## Task B5：Baseline Golden 分为两层

### 离线 Golden

必须严格确定：

```text
ScenarioIR missions
→ Derived StrategySpec
→ ExecutionPlan
→ Lua
```

行为指纹一致，包括：

```text
operation ID
target
delay
quantity
reserve
route
weapon selection
score fragment checksum
```

### 真实 CMO Golden

第一次不直接把 `-40` 设为唯一硬值。

必须先验证：

```text
execution_success=true
scoreable=true
official_score.stable_side_id=red
official_score.cmo_side_id=red
score chain VALID
evidence integrity VALID
execution_fidelity=complete
```

连续运行 2–3 次后再判断：

```text
是否稳定为 -40
是否存在随机区间
是否需要固定随机种子
```

只有确认完全稳定后，才建立精确分数 Golden。

---

## Task B6：保留旧 Baseline 作为只读历史证据

不直接删除：

```text
baseline/6v4/baseline_strategy.json
```

迁移为：

```text
baseline/6v4/legacy/baseline_strategy.pre-scenario-ir.json
```

附加 Manifest：

```json
{
  "status": "legacy_read_only",
  "production_eligible": false,
  "deprecated_reason": "replaced_by_scenario_ir_derivation",
  "checksum": "...",
  "last_compatible_code_revision": "..."
}
```

生产 Loader 必须拒绝使用 legacy Baseline。

---

# Milestone C：候选质量

## Task C1：建立 coordinated strike 正式 Fixture

不要称为 `high_score_strategy_fixture`。

建议命名：

```text
coordinated_strike_strategy_fixture
```

目标是证明正式链能够表达历史多平台舰机协同策略，而不是预设它一定高分。

**受控差异示例：**

```text
055 → DDG-113-1
052D-1 → CVN-70
052D-2 → CG-59
三舰攻击时序错开
J-15-1 → CVN-70
J-15-2 → DDG-113-2
调整既有 route / fire delay
```

全部通过：

```text
StrategyPatch
→ StrategySpec
→ Validator
→ Compiler
→ Scored Renderer
→ Dynamic Job
```

不执行外部 Lua 作为正式候选。

真实验收先要求：

```text
攻击行为与 Baseline 可解释地不同
执行完整
分数可审计
```

连续运行后再决定是否建立分数区间。

---

## Task C2：采用受控 operation template

不要只依赖自由 LLM Patch。

系统先为候选选择模板：

```text
surface_retargeting
surface_timing_deconfliction
surface_air_coordination
fire_reserve_rebalance
single_variable_control
```

LLM只在模板允许的 operation 和 leaf 范围内选择具体值。

这样可以同时保证：

```text
差异足够大
结构仍受控
不会再次出现角色/Novelty 契约冲突
```

---

## Task C3：调整四类候选角色

### candidate_00：exploit

```text
3–5 个叶子
至少 2 个 operation
至少 2 个语义维度
高价值目标利用或去冲突
```

### candidate_01：repair

```text
3–5 个叶子
至少 2 个 operation
必须覆盖 BaselineFailureProfile
是否需要 surface + air 由失败画像决定
```

不得无条件强迫 repair 修改飞机。

### candidate_02：coordinated_explore

```text
5–8 个叶子
至少 3 个 operation
至少 3 个语义维度
必须同时涉及 surface attack 和 sortie
```

### candidate_03：conservative_control

```text
1–2 个叶子
1 个 operation
1 个语义维度
作为近单变量控制组
```

仍禁止：

```text
新增/删除/reorder attack 或 sortie
修改 stable ID
修改 DBID / Loadout
修改评分和 Runtime
```

---

## Task C4：增强受限战术上下文

新增：

```text
src/cmo_lua_agent/optimization/proposal_context_builder.py
```

Planner 可以接收：

```text
红蓝单位角色摘要
Baseline attack/sortie 分配
库存与允许值
评分目标摘要
Baseline 官方分数
Baseline 损失和未完成目标
operation catalog
coupling groups
failure profile
```

Patch Generator 可以接收：

```text
path → operation_id
attacker / target / timing / quantity
surface operations
air sorties
same-target operations
角色 min_operations / min_dimensions
已接受候选覆盖摘要
```

禁止发送：

```text
评分 Lua
Points Trigger/Action/Event 实现
完整 SQLite
完整 AALog
未经压缩的原始日志
模型预测分
完整 StrategySpec 输出要求
```

---

## Task C5：增加 Candidate Quality Report

不能只看 changed leaf 数。

每个候选至少记录：

```text
changed_leaf_count
changed_operation_ids
changed_platform_ids
semantic_dimensions
surface_operation_count
sortie_operation_count
target_assignment_changes
timing_changes
fire_quantity_changes
baseline_distance
role_conformance
```

批次增加 Pairwise Matrix：

```text
path_jaccard
operation_jaccard
value_difference_count
semantic_dimensions_equal
strategy_checksum_equal
```

如果 `candidate_00/01/02` 仍集中修改同一 operation，即使 checksum 不同，也应拒绝人工授权。

---

## Task C6：生成新 Preview

前置条件：

```text
Milestone A 完成
Milestone B 完成
Baseline Golden 通过
```

新 Preview 必须输出：

```text
derived-baseline-strategy.json
baseline-derivation-manifest.json
candidate-intents.json
candidate-patches.json
strategy-diff.json
candidate-quality-report.json
frozen-candidate-set.json
knowledge-snapshot.json
proposal-trace.json
```

人工检查：

- candidate_00/01/02 是否覆盖不同 operation；
- candidate_01 是否真实响应 failure profile；
- candidate_02 是否实现舰机协同；
- candidate_03 是否保持近单变量；
- Pairwise Matrix 是否显示实质差异；
- 所有 checksum 是否一致。

未通过质量审查时不得签发 Approval。

---

## Task C7：完整 Phase 9C 真实验收

执行：

```text
Derived Baseline
→ candidate_00
→ candidate_01
→ candidate_02
→ candidate_03
```

全部串行。

每次 Attempt 检查：

```text
独立 scenario.scen
独立 candidate.lua
独立 batch-job.json
独立 batch-results
scenario checksum 一致
runtime checksum 一致
score spec checksum 一致
execution-summary v2
exact stable_side_id=red
execution_fidelity=complete
CMO lock 正常
```

Generation 完整前不得：

```text
排名
Phase 7
Phase 8
Champion
```

最终验收：

1. 五项均进入明确终态；
2. 所有可评分结果来自新版 `execution-summary.json`；
3. 不存在显示名 Side fallback；
4. 至少两个候选在 operation 行为或分数上与 Baseline 可解释地不同；
5. 即使同分，也能证明 Strategy、Plan、Lua 和实际行为是否不同；
6. Comparator 只排名可信结果；
7. Leaderboard、Generation Result、Optimization Summary 正确落盘；
8. 审批、Ledger、Results 和 CMO Lock 一致；
9. Phase 7/8 在本计划验收期间保持禁用。

---

# 三、推荐提交顺序

```text
A1 BatchRunner execution-summary v2 producer contract
A2 Runtime execution fidelity
A3 Lua/Job diagnostic matrix
A4 Generation Completion Gate
A5 approval-expired same-generation resume

B1 auto weapon selection
B2 ScenarioIR reserve semantics
B3 BaselineStrategyBuilder
B4 Preview derived baseline identity
B5 Baseline offline/CMO Golden
B6 legacy baseline migration

C1 coordinated strike fixture
C2 operation templates
C3 candidate role expansion
C4 tactical context
C5 candidate quality report
C6 new Preview
C7 full CMO Campaign
```

每个任务：

```text
先写失败测试
→ 最小实现
→ 专项测试
→ 相关回归
→ git diff --check
→ 单独提交
```

禁止：

```text
git add .
git add -A
一次性提交整个计划
```

---

# 四、验证命令

```powershell
$env:PYTHONPATH="$PWD\src"

python -m compileall src\cmo_lua_agent

python -m pytest src\cmo_lua_agent\tests\evaluation -q
python -m pytest src\cmo_lua_agent\tests\contract -q
python -m pytest src\cmo_lua_agent\tests\generation -q
python -m pytest src\cmo_lua_agent\tests\optimization -q
python -m pytest src\cmo_lua_agent\tests\evolution -q
python -m pytest src\cmo_lua_agent\tests -q

git diff --check
```

真实 CMO 集成测试必须显式开启：

```powershell
$env:CMO_INTEGRATION="1"

python -m pytest `
  src\cmo_lua_agent\tests\integration\test_batchrunner_execution_summary_contract.py `
  src\cmo_lua_agent\tests\integration\test_phase9c_baseline_golden.py `
  src\cmo_lua_agent\tests\integration\test_phase9c_coordinated_strike_fixture.py `
  -v -m cmo_integration
```

---

# 五、停止条件

必须停止后续任务并先修复：

```text
新版 BatchRunner 无法生成 execution-summary v2
Phase 3 仍需要 fallback 才能读取分数
execution_fidelity=partial
Derived Baseline 无法通过 StrategyValidator
auto weapon selection 在 Plan 或 Lua 中丢失
Baseline 正式 CMO 行为与 ScenarioIR 不一致
旧手工 Baseline 仍被生产 Loader 使用
不完整 Generation 仍进入排行榜
候选可以修改 stable ID / ScoreSpec / Runtime
```

可以记录为单候选终态并继续完整性判断：

```text
CapabilityGap
Lua/CMO execution_failed
semantic_invalid
result_integrity_failed
unscoreable
repair_budget_exhausted
```

前提是该对象已经进入明确终态，而不是未启动或等待审批。

---

# 六、最终完成定义

本计划完成必须同时满足：

```text
1. 新版 BatchRunner 稳定生成 execution-summary v2
2. Phase 3 只读消费新版摘要，无任何旧格式 fallback
3. Runtime 能证明计划操作完整执行
4. Lua/Job/Renderer 差异已通过隔离实验定位
5. 不完整 Generation 不排名
6. 审批过期后可同代续批剩余候选
7. ScenarioIR 成为唯一正式 Baseline 来源
8. auto weapon selection 全链保真
9. 旧 baseline_strategy 仅保留为 legacy_read_only
10. Baseline Offline Golden 与真实 CMO Golden 通过
11. 正式链可表达 coordinated strike 策略
12. 四候选具备可审计的 operation/semantic 差异
13. 新 Preview 通过人工质量审查
14. 完整五项 CMO Campaign 通过
15. 全量测试、compileall、git diff --check 通过
```

完成后，才重新开启 Phase 7：

```text
完整且可信的五个 CandidateOutcome
→ CandidateLearningView
→ ComparativeLearningAgent
→ ExperienceCandidate
```

在此之前，不允许把当前旧摘要、同分结果或不完整 Generation 写入经验库。
