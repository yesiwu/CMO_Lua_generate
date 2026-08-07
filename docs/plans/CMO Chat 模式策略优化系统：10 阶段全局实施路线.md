# CMO Chat 模式策略优化系统：10 阶段全局实施路线

> 本计划只规划 Chat 模式，不包含 Auto、无人值守授权、自动恢复和后台调度。
>
> 本计划的粒度是“全局架构与阶段验收”，不替 Codex 预先决定每个类、函数和文件。每个 Phase 开始前，Codex 必须先检查当前代码，再提交该 Phase 的文件改动清单、接口设计和测试方案；通过评审后才能编码。

## 一、当前起点

当前项目已有两条相邻但尚未闭环的可用链路：

```text
JSON
→ ScenarioWorkflow
→ 校验 / IR / 数据库解析 / Manifest
→ CMOLua-main
→ original.lua
```

以及：

```text
Lua
→ execute_cmo Tool
→ CmoRunner
→ BatchRunner
→ runner.log / cmo_output.txt / result.json
```

当前缺口不是“再增加几个 Agent”，而是把这两条链路连接成：

```text
场景事实
→ 可比较策略
→ 稳定 Lua
→ CMO 推演
→ 可信战果
→ 确定性评分
→ 候选比较
→ 经验积累
→ Skill 反馈
```

现有五个 Agent 文件尚未进入正式主链路。ExecutionPlan、RuntimeProfile、CombatMetrics、CombatScorer、CandidateOutcome 和 CandidateEvaluationWorkflow 等关键闭环对象也尚不存在。

## 二、全局开发原则

### 1. 本计划固定什么

每个 Phase 固定：

- 阶段目标；
- 上一阶段输入；
- 必须产生的能力和领域对象；
- 与已有模块的边界；
- 关键失败路径；
- 阶段输出；
- 验收标准；
- 下一阶段如何消费这些输出；
- 明确不做的内容。

### 2. 让 Codex 决定什么

每个 Phase 开始时，Codex根据真实仓库决定：

- 修改哪些现有文件；
- 是否需要创建新文件；
- 类和函数放在哪个现有包最合理；
- 如何复用已有数据模型、ArtifactStore、Hook 和 Tool；
- 具体测试文件和实现细节。

Codex不得直接开始大规模编码。每个 Phase 先提交：

```text
1. 当前代码复用分析
2. 文件改动清单
3. 关键接口
4. 测试列表
5. 风险和兼容策略
```

评审确认后再编码。

### 3. 不提前固定所有目录

只固定跨阶段必须稳定的领域边界：

```text
ScenarioDefinition
InitialStrategyHint
StrategySpec
ExecutionPlan
LuaRuntimeProfile
CombatEvidence
CombatMetrics
RewardBreakdown
CandidateOutcome
ExperienceCandidate
ValidatedExperience
```

具体放在哪个现有目录，由 Codex根据当前结构提案。不得平行创建第二套重复模块。

### 4. 旧链路先保留

新链路通过真实 CMO Baseline 验证前：

- 不删除 ScenarioWorkflow；
- 不删除 CMOLua-main 适配；
- 不破坏 generate_cmo_lua；
- 不破坏 execute_cmo；
- 不一次性重命名全部 Agent；
- 不宣称尚未接入的 Agent 已经可用。

### 5. 测试前置但不单独设 Phase 0

当前全量测试因两个同名测试模块发生 import mismatch。开始 Phase 1 前先修复测试收集，或统一使用项目确认的 importlib 导入模式。该动作属于开发前预检，不构成业务 Phase。

---

# Phase 1：ScenarioDefinition / InitialStrategyHint / StrategySpec

## 目标

把当前混合了“场景事实”和“作战方案”的 JSON 拆成稳定的两层：

```text
ScenarioDefinition
= 不随候选变化的客观场景

InitialStrategyHint / BaselineStrategy
= 输入 JSON 中已有的初始打法

StrategySpec
= 后续所有候选统一使用的策略表达
```

## 为什么先做

单位、阵营、位置、DBID、Loadout、武器库存属于事实；目标分配、发射数量、攻击时间、航路属于策略。不拆开就无法证明多个候选在同一场景中公平比较，也无法阻止修复过程偷偷修改场景。

## 输入

- 当前 ScenarioInput / ScenarioIR；
- ScenarioContract；
- ResolvedScenarioManifest；
- 当前成功 JSON；
- 当前成功 Lua 中实际采用的 Baseline 打法。
（存在的问题，有成功json，但是lua需要自己生成而且验证哦）

## 必须完成

### ScenarioDefinition

至少表达：

```text
场景标识
阵营及敌对关系
单位及平台类型
DBID / Loadout
初始位置、航向、速度
武器库存
基地归属
不可变约束
```

### InitialStrategyHint

从旧 JSON 中提取：

```text
攻击方
目标
武器
发射数量
延迟
航路
高度与油门
起飞/返航参数
```

### StrategySpec

第一版只覆盖当前海空协同反舰：

```text
目标优先级
攻击单元与目标分配
舰艇攻击波次
舰载机出动与航路
发射数量
攻击触发时间或条件
返航策略
弹药保留策略
风险偏好
```

### 确定性校验

必须校验：

- 单位、目标和武器引用存在；
- 敌我关系合法；
- 发射量不超过库存；
- 飞机基地和 Loadout 合法；
- 坐标、时间、距离和数量合法；
- StrategySpec 不得修改 ScenarioDefinition。

## 输出

```text
scenario_definition.json  
initial_strategy_hint.json  用户给的初始作战意图
baseline_strategy.json  已验证成功的基线方案，它来源于成功运行的 Lua。可以作为比较基准的方案
StrategySpec schema/model   规定策略格式，好让plan agent  llm填写，不同的策略，格式与baseline_strategy.json一样
StrategyValidationReport  StrategyValidationReport 是把某个 StrategySpec 拿去检查后得到的报告。
```

BaselineStrategy 第一版允许人工根据成功 Lua 整理，不做任意 Lua 反向解析。

## 验收

1. 当前标准 JSON 稳定拆成 ScenarioDefinition 和 InitialStrategyHint。
2. BaselineStrategy 通过同一 StrategySpec 校验器。
3. 修改策略不会改变场景事实。
4. 非法单位、超量弹药、错误目标关系被明确拒绝。
5. 原 JSON→Lua 链路仍可工作。

## 与下一阶段衔接

Phase 2 只接受：

```text
ScenarioDefinition + 已校验 StrategySpec
```

## 本阶段不做

- 不生成多个候选；
- 不执行 CMO；
- 不评分；
- 不实现经验；
- 不让 LLM 直接输出完整 Lua。

---

# Phase 2：LuaRuntimeProfile 与确定性 LuaRenderer

## 目标

建立：

```text
ScenarioDefinition  场景里有什么
+ StrategySpec      这次的打击策略（plan 会生成多个打击策略）描述“想做什么”
→ ExecutionPlan      具体要按什么顺序做？ 描述“按什么步骤做”
→ LuaRuntimeProfile     调用哪些可靠的cmo能力，描述“每一步在 CMO 中怎么可靠实现”
→ LuaRenderer     组装成完成lua
→ candidate.lua
```

虽然标题保留 RuntimeProfile 与 Renderer，但必须增加 ExecutionPlan，避免 StrategySpec 直接拼 Lua。

## ExecutionPlan

把策略转换成有顺序和依赖的操作：

```text
确保阵营存在
确保单位存在
设置态势与 EMCON
确保舰载机挂载
补充舰艇弹药
建立目标 Contact
调度舰艇攻击
请求舰载机起飞
等待进入飞行状态
设置航路
等待进入攻击距离
发起攻击
返航
收集结束状态
```

每个操作至少包含：

```text
operation_id
primitive_type
parameters
depends_on
source_strategy_path
```

## LuaRuntimeProfile

从当前成功 Lua 和 CMOLua-main 中提取已验证能力：

- 阵营与单位初始化；
- 舰艇和舰载机装载；
- CMO 调用结果检查；
- Contact 解析；
- 延时事件；
- 舰艇反舰；
- 舰载机起飞轮询；
- 航路与攻击距离轮询；
- 攻击与返航；
- 标准化 Telemetry；
- 最终状态采集入口。

## CapabilityGap  能力缺口 ，描述RuntimeProfile 不支持的cmo  lua语法

当前 Runtime 不支持的能力必须返回结构化 CapabilityGap，不得静默忽略、降级或回退到 LLM 自由 Lua。

## LuaRenderer

只消费已验证 ExecutionPlan 与版本化 RuntimeProfile。相同输入和版本必须生成相同 Lua。

## 输入

- Phase 1 输出；
- 当前已成功运行 Lua；
- CMOLua-main 已验证逻辑；
- 现有 LuaGenerationDiagnostics。

## 输出

```text
execution_plan.json
runtime_profile_version
rendered_baseline.lua
lua_generation_manifest.json
CapabilityGap
```

## 验收

1. BaselineStrategy 编译为 ExecutionPlan。
2. ExecutionPlan 只使用已注册 Primitive。
3. Baseline 渲染成单个完整 Lua。
4. 新 Lua 经现有 CmoRunner 在真实 CMO 成功执行。
5. 单位、挂载、攻击目标、发射量、起飞、攻击和返航与 Baseline 一致。
6. 相同输入重复渲染结果一致。
7. 不支持能力返回 CapabilityGap。

## 与下一阶段衔接

Phase 3 依赖 Runtime 提供版本化 Telemetry 和最终状态采集。真实 CMO Baseline 未通过，不进入 Phase 3。

## 本阶段不做

- 不生成四候选；
- 不做正式评分；
- 不做 LLM 修复；
- 不建设万能 Runtime。

---

# Phase 3：战斗结果解析、语义验证与确定性评分

## 目标

把“CMO 运行了”转化为可信、可解释、可复现的结果：

```text
BatchRunnerEvidence
+ RuntimeTelemetry
+ CmoNativeSnapshot
→ EvidenceReconciler
→ CombatMetrics
→ SemanticValidation
→ CombatScorer
→ RewardBreakdown
```

## 三类证据

### CmoNativeSnapshot

最高战果权威：

```text
单位最终状态
是否被毁
损伤比例
剩余武器
仿真时间
最终位置
可获得的原生计分
```

### RuntimeTelemetry

只描述 Runtime 行为：

```text
Primitive 次序
攻击命令
攻击方与目标
波次
起飞、进入射程、攻击和返航
事件 ID
诊断信息
```

不得自报正式击毁数或 reward。

### BatchRunnerEvidence

描述外部执行：

```text
退出码
超时
Lua 异常
CMO API 异常
配置恢复
原始 stdout/stderr
```

## EvidenceReconciler

字段权威：

```text
最终存活、损伤、剩余武器 → NativeSnapshot
命令、Primitive、事件关联 → RuntimeTelemetry
进程、超时、异常 → BatchRunnerEvidence
```

关键冲突标记 `result_integrity_failed`；关键字段缺失标记 `unscorable`。

## 语义验证

比较：

```text
ScenarioDefinition
StrategySpec
ExecutionPlan
RuntimeTelemetry
最终结果
```

检查场景事实未变、资源未越权、实际攻击未严重偏离、发射量合法、无作弊行为、修复后仍符合策略。

## CombatMetrics

至少包含：

```text
任务完成度
敌方毁伤
己方损失
武器发射和剩余量
命中/拦截（可得时）
作战持续时间
执行成功性
修复次数
结果完整性
```

## CombatScorer

确定性、版本化，只消费协调后的 CombatMetrics。

## 输出

```text
batch_runner_evidence.json
runtime_telemetry.jsonl
cmo_native_snapshot.json
combat_evidence_bundle.json
evidence_reconciliation.json
semantic_validation.json
combat_metrics.json
reward_breakdown.json
```

## 验收

1. 录制证据可重复解析。
2. 相同 Metrics 重复评分一致。
3. 关键冲突不可正常评分。
4. 缺失关键字段明确不可评分。
5. Agent 无法覆盖 reward。
6. Baseline 产出完整 Metrics 和 RewardBreakdown。
7. 每项加减分可解释。

## 与下一阶段衔接

Phase 4 Agent 消费结构化错误、语义报告和证据摘要，不再依靠自由文本日志猜测。

---

# Phase 4：LuaSynthesisAgent 与单次 LuaRepairAgent

## 目标

在 Chat 中加入两个受控 Agent，但不让它们接管确定性主链。

## LuaSynthesisAgent 定位

它是 Chat 的智能编排外壳：

```text
理解用户策略要求
→ 选择相关 Skill
→ 生成或修订 StrategySpec
→ 调用确定性 Compiler/Renderer
→ 解释生成结果
```

它不应成为第二套自由 Lua 生成路径。

## 单次 LuaRepairAgent 定位

每次只处理一个结构化错误，输出一次修复建议或受控 Patch。它不负责：

- 反复执行 CMO；
- 决定最大重试次数；
- 无限循环；
- 计算分数；
- 改写场景事实。

优先级：

```text
StrategySpec 参数错误 → 修订 StrategySpec 后重编译
Runtime/Renderer 缺陷 → 返回系统缺陷报告
CMO 动态兼容问题 → 明确边界内给出单次修复建议
基础设施错误 → 不调用 Agent
```

## 输入

```text
StrategySpec
ExecutionPlan
LuaGenerationManifest
结构化 CmoError
SemanticValidation
相关 Skill
修复历史
```

## 输出

```text
LuaSynthesisResult
LuaRepairProposal / StrategyPatch
change_summary
semantic_impact
confidence
```

## 验收

1. SynthesisAgent 不绕过 ScenarioDefinition/StrategySpec。
2. RepairAgent 一次调用只返回一次结果。
3. RepairAgent 不拥有执行循环。
4. 修复建议可追踪到错误证据。
5. 修复后重新走编译、执行和语义验证。
6. Chat 显示修复原因和修改摘要。
7. Baseline 不依赖 Agent 也能成功执行。

## 与下一阶段衔接

CandidateEvaluationWorkflow 决定何时调用、调用几次和何时终止。

---

# Phase 5：CandidateEvaluationWorkflow

## 目标

建立一份候选策略的一次标准实验：

```text
CandidateRequest
→ 策略校验
→ 编译
→ Lua 渲染
→ CMO 执行
→ 证据协调
→ 条件修复
→ 语义验证
→ Metrics
→ Score
→ CandidateOutcome
```

## 为什么独立存在

它不是 Agent，而是保证候选公平、隔离、可审计的标准流水线。单个候选失败不污染其他候选，也不阻断后续候选。

## 状态与 reason

状态：

```text
CREATED
STRATEGY_VALIDATED
PLAN_COMPILED
LUA_RENDERED
CMO_EXECUTED
EVIDENCE_RECONCILED
REPAIRED
SEMANTIC_VALIDATED
METRICS_EXTRACTED
SCORED
COMPLETED
FAILED
```

reason：

```text
completed
strategy_invalid
capability_gap
render_failed
lua_syntax_error
lua_runtime_error
cmo_timeout
infrastructure_failure
repairable_error
repair_budget_exhausted
evidence_missing
evidence_conflict
semantic_drift
result_parse_failed
cancelled
```

## 修复闭环

Workflow 决定：

```text
是否可修复
使用哪种路径
最多几次
是否重新编译
何时停止
```

Chat 可以在每轮真实执行前要求人工确认。

不进入 Agent 修复：

```text
CapabilityGap
基础设施错误
配置恢复失败
证据冲突
Renderer 系统缺陷
```

## 输出

```text
CandidateOutcome
candidate trajectory
全部候选产物
```

## 验收

覆盖一次成功、可修复后成功、预算耗尽、CapabilityGap、超时、基础设施错误、证据缺失、证据冲突、语义漂移、解析失败。

所有分支返回统一 CandidateOutcome，不用散乱异常字符串作为业务结果。

## 与下一阶段衔接

Phase 6 只循环调用该 Workflow，不再了解 Lua 修复和 CMO 细节。

---

# Phase 6：StrategyProposalAgent 与一代四候选

## 目标

同一 ScenarioDefinition 下生成四个真正有差异的 StrategySpec，并经同一个 CandidateEvaluationWorkflow 得到排行榜。

## 输入

```text
ScenarioContext
BaselineStrategy
用户目标
允许的策略空间
相关 Skills
候选数量 4
多样性约束
```

## 多样性维度

至少两个维度存在实质差异：

```text
目标优先级
兵力分配
攻击时机
波次
发射数量
飞机航路
弹药保留
风险偏好
```

## 第一版流程

```text
Baseline
+ Generation 0 四候选
→ 串行评估
→ CandidateComparator
→ leaderboard
```

## 排行规则

区分：

```text
可评分成功
执行成功但不可评分
语义无效
执行失败
```

只有完整、可信、语义有效的候选参与战术排名。

## Chat 体验

用户可以查看四个策略摘要、选择全部或部分执行、逐次审批真实 CMO、查看进度、失败原因和排行榜。

## 输出

```text
planning_request.json
strategy_candidates.json
CandidateOutcome × 4
leaderboard.json
strategy_diff.json
```

## 验收

1. 一次生成四个有效 StrategySpec。
2. 候选有实质差异。
3. Baseline 与候选使用同一评分管线。
4. 单个失败不阻断其他候选。
5. 排行榜只使用可信结果。
6. Chat 展示策略差异和执行结果。

## 与下一阶段衔接

Phase 7 消费完整候选组，不只看最高分。

---

# Phase 7：ComparativeLearningAgent 与经验存储

## 目标

从同场景受控实验中提出可验证经验，并可供下一次规划检索。

## 输入

```text
ScenarioDefinition
Baseline Strategy/Outcome
四个 Strategy/Outcome
StrategyDiff
RewardBreakdown
SemanticValidation
修复历史
Runtime 与评分版本
```

## 输出

### ComparativeAnalysis

解释策略差异与结果差异、弹药浪费、目标覆盖、偶然因素和下一轮假设。

### ExperienceCandidate

至少包含：

```text
hypothesis
applicable_conditions
recommended_pattern
counter_conditions
supporting_candidates
contradicting_candidates
evidence_refs
confidence
status
```

一个场景只能形成候选经验，不能直接变成 Skill。

## ExperienceStore

保存场景特征、策略摘要、证据引用、评分版本、Runtime 版本、成功失败案例和经验状态。

## ExperienceRetriever

下一次规划只检索：

```text
Top 3 正向经验
Top 2 失败/反例经验
```

## 验收

1. 每条经验有证据引用。
2. 单次高分不直接变成确定结论。
3. 失败候选产生反例经验。
4. 经验能被后续 StrategyProposalAgent 检索。
5. 不把完整历史全部塞入 Prompt。
6. Runtime/评分版本可追踪。

## 与下一阶段衔接

Phase 8 只处理积累多次证据的 ExperienceCandidate。

---

# Phase 8：Skill 晋升

## 目标

把跨场景反复成立的经验转化为可加载 Skill。

## 链路

```text
ExperienceCandidate
→ EvidenceAggregator
→ ValidatedExperience
→ SkillPromotionPolicy
→ SkillAuthorAgent
→ 回归测试
→ Active Skill
```

## EvidenceAggregator

统计独立场景数、支持证据、反例、平均提升、执行成功率、语义有效率、证据完整率和版本信息。

## SkillPromotionPolicy

第一版门槛可配置，但必须显式，例如：

```text
至少 3 个独立场景/初始态
至少 5 条支持证据
平均奖励提升达阈值
执行成功率达阈值
无严重语义违规
无显著反例
```

## SkillAuthorAgent

只负责写：

```text
适用条件
推荐策略
禁用条件
反例
证据摘要
版本
相关 Runtime 能力
```

不负责决定是否晋升。

## 输出

```text
validated_experience.json
skill_candidate.md
skill_metadata.json
skill_regression_report.json
active skill version
```

## 验收

1. 单一场景经验不能晋升。
2. Skill 有适用/禁用条件。
3. Skill 有版本且不覆盖旧版本。
4. 回归失败不得激活。
5. Chat 可查看来源和证据。

## 与下一阶段衔接

Phase 9 把前述能力整合进统一 Chat。

---

# Phase 9：Chat 模式产品化整合

## 目标

将前八个 Phase 接入现有 Chat，不建立第二套 CLI。

## Chat 主链路

```text
用户选择 JSON
→ 准备 ScenarioContext
→ 展示 Baseline
→ 生成候选
→ 展示差异
→ 用户审批执行
→ CandidateEvaluationWorkflow
→ 展示 Metrics 和排行榜
→ ComparativeLearningAgent
→ 保存经验
→ 展示可晋升 Skill
```

## 必须复用

```text
AgentLoop
ToolRegistry 工厂
HookManager
PermissionHook
TerminalDisplay
ToolProgressReporter
generate_cmo_lua
execute_cmo
Skill Tool
数据库 Tool
ArtifactStore
```

## Chat 能力范围

具体 Tool 名称由 Codex决定，但应覆盖：

```text
准备场景
查看 Baseline
生成候选
比较策略
评估单个候选
评估候选组
查看排行榜
查看证据和评分
检索经验
查看 Skill 来源
```

## 审批边界

以下继续要求人工确认：

```text
真实 CMO 执行
写入/编辑关键文件
激活新 Skill
```

## 终端展示

```text
当前阶段
当前候选
CMO 关键进度
修复轮次
证据完整性
得分分解
排行榜
经验摘要
```

完整日志只保存在运行目录。

## 验收

1. 旧 JSON→Lua Chat 不回归。
2. 用户通过对话完成 Baseline + 四候选实验。
3. 每次 CMO 有明确审批。
4. 失败被准确解释。
5. 不伪称未执行的 CMO 成功。
6. Run 目录可定位全部产物。
7. 新旧 Tool 不重复注册。

## 与下一阶段衔接

Phase 10 只在一代四候选上增加下一代，不改变 CandidateEvaluationWorkflow。

---

# Phase 10：多代经验进化

## 目标

让上一代可信结果和经验影响下一代策略。

## 第一版流程

```text
Generation 0
→ 四候选
→ 评估
→ 排行
→ 对比学习
→ 本轮经验
→ 选择 Elite
→ Generation 1
→ 四个新候选
```

## 下一代输入

```text
原 ScenarioContext
Baseline
上一代 Elite
上一代失败模式
本轮经验
历史 Top-K 经验
用户追加约束
```

## EliteSelector

确定性选择，综合：

```text
最终奖励
任务完成度
己方损失
语义有效性
执行稳定性
策略多样性
```

## 避免候选坍缩

- 不得复制 Elite；
- 保留探索候选；
- 同时包含利用与探索；
- 对连续低收益模式降低权重；
- Baseline 始终作为对照。

## 收敛条件

```text
达到用户指定代数
连续若干代提升不足
候选奖励差异过低
全部候选失败
用户主动停止
```

## 输出

```text
generation_00/
generation_01/
generation_summary.json
elite_history.json
learning_history.json
convergence_report.json
```

## 验收

1. Generation 1 明确使用 Generation 0 结果。
2. 新候选不是简单复制。
3. 可比较无经验和有经验效果。
4. 每代可独立回放。
5. Chat 可暂停、调整和继续。
6. Baseline 始终保留。
7. 多代不改变评分规则。

## 本阶段不做

- 不做 SFT；
- 不做 GRPO；
- 不更新模型权重；
- 不做 Auto；
- 不实现 CMO 并发。

---

# 三、阶段依赖总图

```text
Phase 1  场景事实与策略分离
    ↓
Phase 2  StrategySpec 稳定落地为 Lua
    ↓
Phase 3  Lua 执行结果变成可信评分
    ↓
Phase 4  Chat 中加入受控生成与单次修复 Agent
    ↓
Phase 5  单候选标准实验单元
    ↓
Phase 6  一代四候选与排行榜
    ↓
Phase 7  可检索候选经验
    ↓
Phase 8  经证据验证的 Skill
    ↓
Phase 9  完整 Chat 使用体验
    ↓
Phase 10 多代策略进化
```

任何 Phase 未通过验收，不进入下一 Phase。

---

# 四、每个 Phase 交给 Codex 的固定指令模板

```text
请只执行 Phase X，不实施后续 Phase。

开始编码前，请先检查当前仓库并提交：
1. 本 Phase 将复用哪些已有实现；
2. 计划修改和新增的文件；
3. 关键接口与数据流；
4. 测试清单；
5. 对旧 Chat / generate_cmo_lua / execute_cmo 的兼容影响；
6. 本 Phase 的风险。

我确认设计后再编码。

编码要求：
- 使用 TDD；
- 不顺手重构无关模块；
- 不平行创建已有能力的第二套实现；
- 完成后给出修改文件、测试命令、测试结果、真实 CMO 验证结果和剩余风险；
- 未通过本 Phase 验收，不开始下一 Phase。
```

---

# 五、当前开发起点

现在只开始 Phase 1。

开始前完成短预检：

```text
1. 修复或绕过 pytest import mismatch，使目标测试可执行；
2. 确认现有 ScenarioIR / ScenarioContract / Manifest 的实际字段；
3. 确认当前成功 JSON 与成功 Lua 作为 Baseline；
4. 不修改现有 Chat 外部行为。
```

Phase 1 完成后应看到：

```text
同一份旧 JSON
→ ScenarioDefinition
+ InitialStrategyHint
+ BaselineStrategy
```

而不是继续新增 Agent或扩展旧 Lua 正则校验。
