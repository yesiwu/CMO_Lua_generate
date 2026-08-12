# 统一主 Agent Prompt 设计

## 目标

`python -m cmo_lua_agent.main chat` 是面向用户的完整主 Agent 入口。它使用一份正式核心 Prompt，并同时拥有普通场景、Training 和 Campaign 三类工具。显式 `--profile` 仅用于隔离调试：继续复用核心规则，再追加一小段当前工具范围说明，不维护独立的完整 Prompt。

本次只调整交互入口的 Prompt 组织和过时入口说明，不改写 `TrainingRunner`、Campaign 状态机、Recovery Harness、CodeRepairAgent 或工具权限实现。

## 入口与 Prompt 组合

| 启动方式 | 工具范围 | Prompt |
| --- | --- | --- |
| `chat` / `--profile all` | 普通场景 + Training + Campaign | `MAIN_SYSTEM_PROMPT` |
| `--profile standard` | 普通场景工具 | `MAIN_SYSTEM_PROMPT + STANDARD_DEBUG_APPENDIX` |
| `--profile training` | Training 工具 | `MAIN_SYSTEM_PROMPT + TRAINING_DEBUG_APPENDIX` |
| `--profile campaign` | Campaign 高层工具 | `MAIN_SYSTEM_PROMPT + CAMPAIGN_DEBUG_APPENDIX` |

附加 Prompt 只说明本次隔离调试开放的工具范围，以及超出范围时不得假装执行。正式业务规则只存在于 `MAIN_SYSTEM_PROMPT`。

## 核心 Prompt 职责

### 身份与路由

主 Agent 是系统的统一自然语言入口，根据用户意图选择最小必要动作：

- 普通知识问题直接回答，不为了展示能力而调用工具。
- 需要工作区事实时先读取，不假装已经读取、执行或修改。
- JSON→Lua 请求走确定性生成链；需要仿真时才执行 CMO。
- 用户给出 ScenarioIR 路径、目标和代数时直接启动持久化 Training。
- 训练查询和控制使用 Training 高层工具，不根据聊天历史猜状态。
- Campaign 工具只用于用户明确要求的手工 Campaign 调试；日常训练走 `TrainingService` 正式入口。

### 普通文件修改授权

普通聊天直接修改 JSON 或其他文件时：

1. 先读取目标文件。
2. 向用户说明文件、修改内容和影响。
3. 询问一次明确确认。
4. 确认后才调用写入工具；工具自身的终端审批保持不变。

JSON 首次修复默认创建副本。只有用户明确要求修改原文件时才允许写原文件。该授权边界只约束主聊天 Agent 的直接修改。

### 无人值守 Training

用户启动训练即授权指定代数的完整 Workflow。主 Agent不得再次询问：

- budget 文件；
- CMO、候选执行或逐代授权；
- Skill 摘要/正文发送授权；
- Phase 7 或最终 Phase 8 授权；
- 后台 CodeRepairAgent 的逐次源码修改授权。

Training 启动后由后台 Runtime 和持久化状态推进。主 Agent不在前台模拟 Runner、不循环占用对话等待，也不直接修改 `state.json`、journal、Campaign 状态或业务 Artifact。

### 恢复边界

主 Prompt 只描述后台恢复的责任边界：

```text
TRANSIENT → 自动重试
DOMAIN → 既有 Lua/Candidate 领域修复
CODE → CodeRepairCoordinator + CodeRepairAgent
UNKNOWN → 一次受限诊断或停止
```

主聊天 Agent不能用普通文件工具冒充后台 Code Repair。用户询问恢复进度时，通过 `inspect_training` 读取持久化事实并解释。

### 真实性和失败处理

- 工具失败不能宣称成功。
- 训练进度、代索引、Worker、Phase 8 和恢复状态必须来自工具返回或持久化事实。
- 工具给出建议动作时，先判断是否符合当前任务和权限边界，再继续。
- 缺少会实质改变结果的用户输入时才提问；能够由现有工具安全确定的事实应自行获取。

## `main.py` 职责说明更新

删除顶部过时的 `InteractiveScenarioService` 和 `auto mode` 架构描述，改为当前真实关系：

```text
main.py
  → 主 AgentLoop
      ├─ 普通场景工具
      ├─ TrainingService
      └─ ProductionEvolutionCampaignService

TrainingService
  → training.runtime
  → TrainingRunner
  → Recovery Harness
  → Campaign
```

`main.py` 仍是 CLI Composition Root，只负责参数解析和依赖组装；业务状态机与恢复实现继续留在各自模块。

## 测试

- 默认 `chat` 使用完整 `MAIN_SYSTEM_PROMPT`，不追加调试限制。
- 三种显式 profile 均以同一个核心 Prompt 开头，并追加各自唯一的调试说明。
- Prompt 选择与 ToolRegistry 的 profile 一致。
- 核心 Prompt 包含普通文件一次确认、Training 启动即授权、状态只读工具事实和后台 Code Repair 边界。
- 运行 CLI/工具装配相关测试和全量 pytest，保证旧 profile 调试入口继续可用。

## 非目标

- 不把 CodeRepairAgent 工具暴露给主聊天 Agent。
- 不新增 Agent、Runtime、状态文件或审批系统。
- 不删除 `--profile` 兼容参数。
- 不通过 Prompt 复制 Python 状态机的全部实现细节。
