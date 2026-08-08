# Codex 式训练 Loop Harness 总体设计

> 状态：已完成需求确认，作为后续实施计划的唯一设计依据。
>
> 目标：在不破坏现有 Campaign、CMO、Rolling Baseline、Phase 7 和手工训练入口的前提下，为系统增加一句话启动、后台持续运行、断点恢复、状态查询、上下文压缩和自动代码修复能力。

---

## 1. 产品目标

用户只需要提供一个与
`baseline/6v4/manual-template/6v4ScenarioIR_baseline_v3.json`
结构相近的 ScenarioIR 文件，并描述目标和训练代数，例如：

```text
读取 baseline/6v4/manual-template/6v4ScenarioIR_baseline_v3.json，
目标是提高红方官方得分、保持对蓝方高价值目标的毁伤并减少 J-15 损失，
连续优化 7 代。
```

系统应自动完成：

```text
理解用户请求
→ 校验并解析 ScenarioIR
→ 准备 Campaign Input Package
→ 创建 Training Workflow
→ 建立 Git 训练基线
→ 启动持久化 TrainingRunner
→ Prepare Campaign
→ Preview / Execute / Phase 7 × N 代
→ 每代读取正式 Artifact 并更新摘要
→ 发生临时错误时自行恢复
→ 发生系统代码错误时自行测试、修复、commit、push 并恢复训练
→ 所有代结束后冻结本 Workflow 的 Experience 集合
→ 统一执行一次 Phase 8
→ 生成训练报告和代码修改报告
```

用户在训练期间可以随时询问进度、暂停、恢复或停止。训练本身不依赖聊天窗口保持打开，也不依赖 LLM 记住之前执行到了哪里。

## 2. 已确认的产品规则

### 2.1 一次训练请求就是完整执行授权

用户明确要求“连续优化 7 代”后，系统不再逐代询问，也不再分别询问：

- 是否把 Curated Skill 摘要或正文发送给配置的 LLM；
- 是否启动本代五个初始 CMO 仿真；
- 是否把 LearningView 发送给 LLM 生成 Phase 7 经验；
- 是否进入下一代；
- 是否在所有代结束后执行 Phase 8。

新 Training Harness 路径不使用当前冗长的逐项终端授权。用户的 START 请求授权本 Workflow 完成其必要的 LLM、CMO、Phase 7 和最终 Phase 8 操作。

### 2.2 训练请求默认授权自动代码修复

训练过程中若确认是 Python 系统代码缺陷，系统可以自动：

```text
读取源码和日志
→ 编写回归测试
→ 修改源码
→ 运行测试
→ git diff --check
→ commit
→ push
→ 用新代码重启 TrainingRunner
→ 从失败节点继续
```

不逐次询问用户。最终报告必须列出故障、根因、修改文件、测试、commit、push 和恢复节点。

### 2.3 不使用固定执行次数预算

新 Harness 不以以下指标阻止任务继续：

- Agent 最大回合数；
- 最大 CMO 次数；
- 最大 LLM 总调用数；
- 最大策略生成调用数；
- 最大 Lua 生成或修复调用数；
- 最大 Phase 7 或 Phase 8 调用数；
- 固定工具调用次数。

训练代数只由用户要求决定。用户指定 7 代就运行 7 代；以后可以支持“持续训练直到我停止”。调用次数、CMO 次数和 Token 可记录为统计信息，但不是终止条件。

系统仍保留单次网络、CMO 子进程和 Worker 防卡死超时，以及无进展循环检测。这些是存活性机制，不是训练预算。

### 2.4 所有代结束后统一执行 Phase 8

新 Harness 路径不在每代执行 Phase 8。每代只完成 CMO、评分、Champion 和 Phase 7。全部代完成后，冻结本 Workflow 产生的 Experience 集合并统一执行一次离线 Phase 8。

旧手工训练入口第一阶段保持原行为，以避免破坏已有流程。

---

## 3. 设计原则

### 3.1 确定性代码维护执行真值

LLM 负责理解目标、分析未知错误和提出修复，不负责凭聊天历史判断任务是否完成。

正式完成状态必须来自：

- CampaignStore；
- Worker 状态；
- operation ledger；
- generation-result；
- candidate outcome；
- Phase 7 和 Phase 8 正式 Artifact。

### 3.2 Harness 不重写现有业务算法

Harness 不重新实现：

- Candidate Proposal；
- StrategySpec 校验；
- Lua 渲染和修复；
- CMO 执行；
- Candidate 评价；
- Leaderboard；
- ChampionSelectionPolicy；
- Rolling Baseline；
- Phase 7 Comparative Learning；
- Experience Aggregation；
- SkillAuthorAgent。

### 3.3 原始 Artifact 落盘，上下文只加载当前所需内容

完整 Lua、CMO stdout/stderr、Candidate JSON、Phase 7 原文和测试输出继续落盘。Main Agent 默认只读取当前状态、历史摘要、最近错误和必要路径。

### 3.4 先做最小架构收敛，不全面重写项目

只整理会阻碍 Harness 的冲突边界。现有正式训练流程必须持续可运行，legacy 模块在新 Runner 验证稳定前不立即删除。

---

## 4. 正式架构边界

### 4.1 保留的正式业务边界

以下组件继续作为正式实现：

- `ProductionEvolutionCampaignService`：生产业务门面；
- `EvolutionCampaignService`：Campaign 控制平面；
- `CampaignStore`：Campaign 状态、checkpoint、Worker 和 operation ledger；
- `ProductionGenerationExecutor`：执行一代冻结 Candidate；
- 现有 Candidate、CMO、Champion、Rolling Baseline 和 Phase 7 组件。

### 4.2 新增的 Harness 边界

```text
用户
↓
Codex 式 Main Agent
├── 理解 START / STATUS / PAUSE / RESUME / STOP
├── 创建 TrainingRequest
├── 查询 Workflow 并回复用户
└── 分析故障并执行代码修复
↓
持久化 TrainingRunner
├── Prepare
├── Preview / Execute / Phase 7 × N
├── 等待和对账 Worker
├── 生成状态、TODO、摘要和报告
└── 所有代结束后统一 Phase 8
↓
现有 Campaign 控制平面和正式业务 Artifact
```

Main Agent 和 TrainingRunner 职责必须分离。Main Agent 不使用 LLM 回合轮询数小时的 Worker；TrainingRunner 不依赖自然语言历史决定下一步。

### 4.3 Legacy orchestrator 处理

现有 `auto_campaign_tools.py` 和 `campaign_orchestrator.py` 暂时标记为 legacy：

1. 新 Harness 不再引用它们；
2. 提取其中仍有价值的测试和需求；
3. 新 TrainingRunner 覆盖其正式能力后，用 `rg` 确认无生产引用；
4. 最后单独删除 legacy 代码及专属测试。

不再新增第三套 Campaign 业务真值或 Candidate 执行逻辑。

---

## 5. Main Agent Runtime

### 5.1 AgentLoop 改为结果驱动

移除固定 `max_turns`。一次 Main Agent 请求持续执行，直到出现真实终止结果之一：

```text
用户请求已完成
长期任务已交给 TrainingRunner
明确需要用户提供信息
用户主动暂停或终止
出现无法自动恢复的错误
```

Main Agent 不因已经调用了多少次模型或工具而结束。

### 5.2 无进展循环检测

系统记录最近动作的签名：

```text
tool/action
arguments
result/error
相关状态revision
```

如果动作、参数、错误和状态完全相同，且没有新证据、新假设或新 Artifact，则不机械重复调用，而是进入诊断。诊断仍无进展时进入 WAITING_USER 或 FAILED。

### 5.3 用户意图

第一版支持：

- START：创建并启动 Training Workflow；
- STATUS：读取状态和摘要；
- PAUSE：阻止调度新动作，并在安全业务边界暂停；
- RESUME：对账后继续；
- STOP：在安全边界终止；
- ERROR EXPLANATION：读取 FailureRecord、日志和 Repair 记录；
- NORMAL CHAT：不影响后台训练。

---

## 6. TrainingRequest 与输入解析

### 6.1 TrainingRequest

```json
{
  "schema_version": "1.0",
  "workflow_id": "training_20260808_001",
  "session_id": "session-xxx",
  "input_path": "baseline/6v4/manual-template/6v4ScenarioIR_baseline_v3.json",
  "objective": "提高红方得分、保持蓝方目标毁伤并减少J-15损失",
  "generation_mode": "fixed_count",
  "generation_count": 7,
  "auto_code_repair": true,
  "phase8_mode": "after_all_generations",
  "authorized_by_request": true,
  "created_at": "..."
}
```

以后可增加：

```json
{
  "generation_mode": "until_stopped",
  "generation_count": null
}
```

### 6.2 ScenarioIR 输入

用户提供的 XX.json 与现有 6v4 ScenarioIR 基线相近。Main Agent 只负责提取路径、目标和代数；Python `ScenarioInputResolver` 负责：

1. 解析绝对或项目相对路径；
2. 校验 JSON 和 ScenarioIR；
3. 识别模板、基线策略、评分规则和运行时引用；
4. 构造或绑定 ControlledCampaignInputPackage；
5. 返回稳定的 input package reference 给 Campaign prepare。

用户不需要知道 `input_package_id` 或 `budget-file`。

### 6.3 budget-file 的处理

旧 `run_manual_campaign_generation.py prepare` 继续兼容旧 budget JSON。新 Training Harness 不要求用户提供 budget-file，也不生成固定 CMO/LLM 次数预算。

旧 Campaign Spec 中的历史预算字段继续可以反序列化，但新 Harness 不以这些字段作为终止理由。新运行只保留用户代数和单次操作防卡死超时。

---

## 7. TrainingRunner 生命周期

### 7.1 启动

```text
Main Agent解析请求
→ Python构造并校验TrainingRequest
→ 建立Git baseline commit并push
→ 创建runs/training/<workflow_id>
→ 启动独立TrainingRunner进程
→ Main Agent立即返回“训练已启动”
```

TrainingRunner 使用隐藏后台进程运行，stdout/stderr 重定向到 Workflow 日志。终端关闭不应删除状态或依赖聊天历史恢复。

### 7.2 代际循环

```text
Prepare Campaign
→ Preview generation N
→ Execute generation N
→ 等待Worker完成
→ 读取正式generation结果
→ 更新summary、journal和TODO
→ N + 1
```

不存在逐代用户审批。TrainingRunner 直接通过正式 Service API 推进，不通过面向终端的冗长 PermissionHook。

### 7.3 完成

```text
最后一代完成
→ 冻结本Workflow Experience列表
→ 启动离线Phase 8
→ 生成Skill报告
→ 生成Training报告
→ Workflow COMPLETED
```

### 7.4 单 Workflow 所有权

每个 Workflow 同时只能有一个 TrainingRunner。Runner 持有 workflow 级锁，并记录 PID、instance ID 和启动时间。启动和恢复前必须确认旧 Runner 是否仍存活，防止重复启动同一代或同一个 CMO Attempt。

生产模式继续服从现有 CMO 实例互斥机制。同一时刻不并行运行两个真实 CMO Workflow。

---

## 8. 状态真值与目录结构

### 8.1 目录

```text
runs/
├── evolution/
│   └── <campaign_id>/
│       ├── campaign-state.json
│       ├── campaign-spec.json
│       ├── operation-ledger.jsonl
│       ├── checkpoint.json
│       ├── workers/
│       ├── previews/
│       └── generations/
│
└── training/
    └── <workflow_id>/
        ├── request.json
        ├── state.json
        ├── journal.jsonl
        ├── TODO.md
        ├── summary.json
        ├── runner.log
        ├── failures/
        │   └── <failure_id>.json
        ├── repairs/
        │   ├── repair-log.jsonl
        │   └── code-repair-report.md
        ├── phase8/
        │   ├── state.json
        │   ├── experience-input.json
        │   └── skill-generation-report.md
        └── training-report.md
```

现有 `runs/evolution` 目录和 Artifact 不迁移、不复制。

### 8.2 state.json

`state.json` 是跨代调度投影，不是 Candidate/CMO 真值：

```json
{
  "schema_version": "1.0",
  "revision": 18,
  "workflow_id": "training_20260808_001",
  "campaign_id": "campaign_20260808_001",
  "status": "RUNNING",
  "stage": "EVOLUTION",
  "action": "WAIT_WORKER",
  "current_generation": 3,
  "completed_generations": [0, 1, 2],
  "worker_operation_id": "g003:phase6:...",
  "active_failure_id": null,
  "last_good_commit": "abc123",
  "runner": {
    "pid": 12345,
    "instance_id": "runner-xxx",
    "started_at": "..."
  },
  "phase8": {
    "status": "NOT_STARTED",
    "job_id": null
  },
  "updated_at": "..."
}
```

### 8.3 状态集合

```text
status:
CREATED
RUNNING
PAUSED
REPAIRING
WAITING_USER
COMPLETED
FAILED
STOPPED

stage:
PREPARE
EVOLUTION
PHASE8
REPORT

action:
VALIDATE_INPUT
PREPARE_CAMPAIGN
PREVIEW
EXECUTE
WAIT_WORKER
SUMMARIZE
RECONCILE
GENERATE_REPORT
IDLE
```

### 8.4 唯一真值

| 信息 | 唯一真值 |
|---|---|
| 用户要求、代数、目标 | Training `request.json` |
| 当前跨代调度位置 | Training `state.json` |
| Candidate 和 CMO 是否完成 | CampaignStore、Worker、operation ledger |
| 分数、Champion、Phase 7 | generation 正式 Artifact |
| 历史代际摘要 | Training `summary.json` |
| 用户聊天 | ChatSessionStore |
| 成功代码修复 | Git commit |
| Phase 8 输入 | `phase8/experience-input.json` |

`state.json` 和 `summary.json` 使用临时文件加原子替换。`TODO.md` 是派生视图，可以从 request、state 和 Campaign Artifact 重建。`journal.jsonl` 每条事件带递增序号。

---

## 9. 断点恢复和对账

### 9.1 Runner 重启

```text
读取request和state
→ 获取Workflow独占锁
→ 从campaign-spec重建ProductionEvolutionCampaignService
→ 读取CampaignStore、Worker和operation ledger
→ 检查正式Artifact
→ 对账当前generation/action
→ 推导next_action
→ 更新Training state
→ 继续运行
```

正式实现必须补齐公开的 Campaign rehydrate/load API，不能继续依赖只存在于进程内的 `_services` 缓存或脚本调用私有方法。

### 9.2 Worker 和 CMO 恢复

```text
Worker completed且generation-result完整
→ 本代完成

Worker failed
→ 错误分类

Worker标记running但旧Runner已不存在
→ 标记旧Worker需要对账
→ 检查已完成Candidate

CMO进程仍存在
→ 重新接管监控，不重复启动

CMO进程不存在且Artifact完整
→ 对账为完成

CMO进程不存在且Artifact不完整
→ 标记Attempt失败
→ 从对应Candidate继续
```

现有 `process_restart_recovery = not_validated` 必须在真实多代训练前解决。

### 9.3 安全业务边界

恢复粒度是 Prepare、Preview、Candidate、Leaderboard、generation-result、Phase 7 和 Phase 8，不尝试从任意 Python 代码行恢复。

---

## 10. Phase 8 最终聚合

### 10.1 新 Harness 路径

新 Harness 创建 Campaign 时禁用每代 Phase 8，但不全局删除旧执行器中的兼容路径。全部代完成后：

```text
筛选本Workflow产生的Experience
→ 记录Experience ID和路径
→ 写phase8/experience-input.json
→ Phase 8只读取该集合
→ 生成Pending Skill或NO_PROMOTABLE_EXPERIENCE
→ 写skill-generation-report.md
```

不需要复制或冻结整个 Experience 数据库，也不增加额外哈希体系。

### 10.2 兼容旧流程

- 旧手工入口暂时保持原有 Phase 8 行为；
- 新 Harness 保证只在末尾执行一次；
- 新 Harness 稳定后，再单独评估是否统一旧入口语义。

---

## 11. 错误恢复与自动代码修复

### 11.1 错误分类

```text
TRANSIENT
网络、LLM、文件暂时占用、CMO临时启动失败
→ 条件恢复后重试

BUSINESS
Candidate无有效变化、Lua执行失败、Phase 7无可学习结果
→ 使用现有业务Repair/Retry

INPUT
ScenarioIR错误、路径不存在、用户目标无法解析
→ WAITING_USER

CODE
Python traceback、状态机、解析、装配或Service代码缺陷
→ REPAIRING

UNKNOWN
→ Repair Agent先诊断
→ 能用回归测试证明代码错误才修改
→ 无法证明则WAITING_USER
```

### 11.2 Repair Agent 流程

```text
保存FailureRecord
→ 读取traceback、日志、源码和相关Artifact
→ 提出可验证的根因假设
→ 编写回归测试并观察预期失败
→ 修改最小必要代码
→ 运行专项测试
→ 运行受影响模块测试
→ 必要时完整测试
→ git diff --check
→ 记录修改日志
→ commit并push
→ 更新last_good_commit
→ 启动使用新代码的Replacement Runner
→ 旧Runner退出
→ 对账并恢复原失败节点
```

系统不能在原 Python 进程中假装使用了新代码继续运行，因为已导入模块仍是旧版本。

### 11.3 自动修复边界

可以自动修改：

- Python 源码；
- 测试；
- Harness 普通配置；
- 与代码缺陷直接相关的脚本。

不能自动修改：

- 用户 ScenarioIR；
- ScoreSpec 和评分语义；
- 用户训练目标；
- 已生成的正式训练结果；
- 不能由回归测试证明的问题。

### 11.4 Git 基线和无进展回退

训练开始前：

```text
运行基础测试
→ 建立baseline commit
→ push当前GitHub分支
→ 记录last_good_commit
```

不提交 `runs/`、CMO 输出、临时文件和 `.gitignore` 排除内容。训练期间用户不修改源码，Repair Agent 可以独占本地代码修改权。

不使用固定修复次数。只要出现新证据、新假设或新的测试进展，可以继续修复。如果错误、假设、修改和结果完全重复而无新进展，则：

```text
停止修改
→ 回退tracked code到last_good_commit
→ 保留runs和日志
→ Workflow FAILED
→ 生成code-repair-report.md
```

---

## 12. Chat Session 和上下文压缩

### 12.1 兼容扩展现有 ChatSessionStore

```text
.cmo_lua_agent/chat_sessions/
├── active_session.json
└── sessions/
    └── <session_id>/
        ├── session.json
        ├── messages.jsonl
        ├── summary.json
        └── tool-results/
```

旧 `sessions/<session_id>.json` 继续可读。首次修改旧 Session 时再迁移，不要求用户手工处理。

`session.json` 保存 session_id、active_workflow_id、workflow_history 和时间；不复制 generation、Candidate 或 CMO 状态。

### 12.2 完整历史与活跃上下文分离

所有用户、Assistant、tool use 和 tool result 都追加到 `messages.jsonl`。上下文压缩只改变下一次发送给模型的内容，不删除真实历史。

### 12.3 大 Tool Result 外置

```text
小结果
→ 直接进入活跃上下文

大结果
→ 完整写入tool-results
→ 活跃上下文只保留工具、摘要、重要错误和路径
```

CMO 和训练系统已经保存完整 Artifact 时，直接引用原路径，不重复复制。

### 12.4 不按固定聊天轮数压缩

ContextManager 根据实际请求体接近模型容量的程度逐层处理：

```text
外置旧的大工具结果
→ 压缩已结束任务
→ 更新Session滚动摘要
→ 保留当前任务和最近相关消息
```

每次 Main Agent 调用组装：

```text
系统规则
+ 当前用户消息
+ Session固定目标和active_workflow_id
+ Training state
+ Training summary
+ Session滚动摘要
+ 当前任务最近消息
+ 当前Repair上下文（如有）
```

### 12.5 Repair Context

Repair 期间固定保留 FailureRecord、traceback 路径、根因假设、修改文件、最新 diff、最新测试、Git 状态和下一步。修复提交并恢复训练后才压缩。

### 12.6 Prompt 过长

若 API 返回 prompt too long，从磁盘重新构建上下文，逐层移除所有可重新读取的内容，直到达到最小必要上下文。最小上下文仍无法调用时，报告模型配置或系统提示词本身过大，而不是无限重复相同请求。

---

## 13. 向后兼容要求

实施期间必须持续满足：

1. 原有手工 `prepare / preview / execute / inspect` 可以运行；
2. 原有六个 Campaign 工具接口第一阶段不变；
3. 旧 Campaign Spec 和 budget JSON 可以加载；
4. 已存在 Campaign 可以 inspect 和 resume；
5. Rolling Baseline 继续由现有实现读取上一代 Champion；
6. 新 Harness Campaign 仍能被旧 inspect API 读取；
7. 旧 Chat Session 可以恢复；
8. legacy orchestrator 在替代能力通过测试前不删除；
9. 每个实施阶段必须运行受影响测试和完整回归测试；
10. 真实旧流程单代冒烟通过后，才能运行新 Harness 真实多代。

---

## 14. 测试策略

### 14.1 现有行为保护测试

在重构前锁定：

- 手工 Prepare、Preview、Execute；
- Campaign inspect、pause、resume；
- Rolling Baseline；
- Phase 7；
- 旧 Phase 8；
- 旧 Campaign、budget 和 Chat Session 加载。

### 14.2 TrainingRunner 单元测试

覆盖 request/state 序列化、状态转换、next action、原子写入、Workflow 锁、TODO、summary、暂停恢复、无固定次数预算、末尾单次 Phase 8。

### 14.3 Fake 三代集成

```text
Prepare
→ Preview/Execute 0
→ Preview/Execute 1
→ Preview/Execute 2
→ Phase 8一次
→ Report
```

验证没有终端授权输入，Main Agent 可中途查询，TrainingRunner 不依赖聊天历史，新 Campaign 可被旧 inspect 读取。

### 14.4 崩溃注入

分别在 Prepare 后、Preview 后、Candidate 中间、CMO 启动后、generation-result 后、summary 前和 Phase 8 启动后终止 Runner。重启后不得重复已确认完成的操作，也不得从 generation 0 重来。

### 14.5 Repair Agent 集成

在临时 Git 仓库制造明确 Python Bug，验证回归测试、修复、commit、push、Replacement Runner 和原节点恢复。再制造无进展错误，验证 Git 回退和 Artifact 保留。

### 14.6 真实冒烟顺序

```text
原有手工单代
→ 新Harness真实单代
→ 新Harness真实2代
→ 终端重启恢复
→ 新Harness真实7代
```

---

## 15. 实施阶段

### Phase A：现状保护与最小架构收敛

- 增加旧流程特征测试；
- 确定唯一正式 Service 和 CampaignStore 边界；
- legacy orchestrator 停止新增引用；
- 增加公开 Campaign rehydrate/load API；
- 保持旧手工入口可用。

### Phase B：Training 状态与单代 Runner

- TrainingRequest；
- ScenarioInputResolver；
- TrainingStore、state、journal、TODO、summary；
- 独立 TrainingRunner；
- Fake 和真实单代。

### Phase C：恢复与多代循环

- Runner 所有权；
- Worker/operation/CMO 对账；
- 多代 Preview/Execute；
- STATUS、PAUSE、RESUME、STOP；
- Fake 三代和真实两代。

### Phase D：Main Agent Runtime 与 Session Context

- 移除固定 max_turns；
- 状态驱动 AgentLoop；
- 无进展检测；
- ChatSessionStore 兼容扩展；
- Tool Result 外置和滚动摘要。

### Phase E：自动代码修复

- FailureRecord 和错误分类；
- Repair Agent 工具边界；
- Git baseline、测试、commit、push；
- Replacement Runner；
- 无进展回退和修改报告。

### Phase F：最终 Phase 8 与报告

- 禁用新 Harness 每代 Phase 8；
- 冻结 Experience 输入；
- 统一离线 Phase 8；
- Training Report、Skill Report 和 Code Repair Report；
- 真实七代验收。

### Phase G：Legacy 清理

- 确认无生产引用；
- 删除被完全替代的 orchestrator、工具和重复状态；
- 完整回归和真实单代冒烟。

---

## 16. 第一版明确不做

- 通用 DAG Workflow Engine；
- Redis、Celery 或数据库任务队列；
- 分布式 CMO Worker；
- 多个真实 CMO Workflow 并行；
- 多 Main Agent 协作；
- 自动修改 ScenarioIR 或评分规则；
- 向量数据库和 Embedding Workflow History；
- 复杂 Token 预算系统；
- 为每个业务 Task 复制一套正式结果；
- 在新 Runner 稳定前大规模重排全部项目目录。

---

## 17. 第一版完成定义

同时满足以下条件才视为完成：

1. 用户一句自然语言可以用指定 ScenarioIR 启动 N 代训练；
2. 用户不需要提供 input package ID 或 budget-file；
3. 不出现逐代或逐项授权提示；
4. TrainingRunner 在独立进程中持续推进；
5. Main Agent 没有固定回合上限；
6. 用户可以随时查询、暂停、恢复和停止；
7. 终端关闭或 Runner 崩溃后可以从正式业务边界恢复；
8. CampaignStore 和正式 Artifact 始终是业务真值；
9. Harness 不重复实现 Champion、Rolling Baseline 和 Candidate 执行；
10. 所有代完成后只执行一次 Phase 8；
11. Phase 8 输入明确属于当前 Workflow；
12. 系统代码错误可以自动测试、修复、commit、push并恢复；
13. 无进展修复会回退 Git 基线，且训练 Artifact 保留；
14. 完整聊天和大工具输出可追溯，但活跃上下文保持聚焦；
15. 旧手工训练入口和旧 Campaign 仍可运行；
16. 新旧单代冒烟、Fake 多代、崩溃恢复和真实七代验收全部通过；
17. 生成 training-report、skill-generation-report 和 code-repair-report；
18. legacy 代码只在确认被完整替代后删除。

本设计完成后，再根据真实长期训练结果决定是否增加并行训练、任务队列或更通用的 Agent Runtime。
