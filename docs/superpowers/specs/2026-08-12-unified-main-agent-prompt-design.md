# 统一主 Agent Prompt 与轻量通用 Harness 设计

## 目标

`python -m cmo_lua_agent.main chat` 是面向用户的完整主 Agent 入口。它使用一份正式核心 Prompt，并同时拥有普通场景、Training 和 Campaign 三类工具。显式 `--profile` 仅用于隔离调试：继续复用核心规则，再追加一小段当前工具范围说明，不维护独立的完整 Prompt。

本次同时收敛主 Agent 的通用 Harness：移除旧 JSON→Lua 专用的“三轮探索终止”，补齐工作区搜索、通用文本读取、隐藏路径策略和按上下文占用率触发的压缩。不改写 `TrainingRunner`、Campaign 状态机、Recovery Harness 或 CodeRepairAgent。

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

## 轻量通用 Agent Harness

### 删除领域专用的循环终止判断

通用 `AgentLoop` 不再把 `list_directory`、`read_file`、Skill 浏览等行为判定为“无效轮次”，也不再检查用户是否提供 `.json` 路径。代码理解、架构分析和配置审计本来就可能连续搜索、列目录和读取多个文件。

保留的通用保护只有：

- Anthropic `tool_use/tool_result` 协议完整性；
- 用户 Esc/Ctrl+C 中断；
- 调用方可选的墙钟期限；
- 相同工具、相同参数、相同错误结果的连续重复检测；
- 工具明确建议的无副作用恢复（例如误用 `read_file` 读取目录后改用 `list_directory`）。

相同失败重复出现时，将结构化失败和“重新规划、换工具或明确说明缺少什么”的指令返回模型。Harness 不再生成与当前任务无关的固定“请提供场景 JSON”结论。成功工具调用会清除对应连续失败状态，避免较早的权限错误污染最终回答。

### 通用工作区工具

新增只读 `search_workspace`，用于按文本、相对路径和 glob 搜索工作区。主 Agent面对“某个类、Prompt 或配置在哪里”时应先搜索，再按命中结果读取，而不是猜测多个目录。

`read_file` 继续作为通用文本工具，不按业务扩展名分裂工具，支持 `.py`、`.json`、`.yaml/.yml`、`.md`、`.txt`、`.lua`、`.toml`、`.ini`、`.log`、`.csv` 等文本。它增加：

- `start_line/end_line` 分页读取；
- 二进制内容检测，拒绝图片、数据库、压缩包、可执行文件等；
- 大结果保真：完整输出写入非隐藏的本次 Agent Artifact，返回摘要和可继续分页读取的相对路径。

`list_directory` 默认只列直接子项；搜索和读取均不递归跟随符号链接。

### 统一 `WorkspacePathPolicy`

所有提供给主 Agent 的工作区文件工具复用同一条路径策略：

1. 用户路径必须解析后仍位于项目工作区。
2. 任一路径组成部分以 `.` 开头即拒绝，直接指定和间接访问行为一致。
3. 不允许通过 `..`、绝对工作区外路径或符号链接逃逸。
4. 读取、搜索、列目录、编辑、新建和 JSON 副本工具全部使用同一策略。

因此 `.pytest-tmp`、`.git`、`.gitignore`、`.github`、`.env`、`.agents`、`.codex`、`.cmo_lua_agent` 等都不会向主 Agent展示或开放。该限制只约束 Agent 工具；配置加载、聊天持久化和 Git baseline 等确定性系统代码仍可访问其内部所需路径。

已经删除的 `prompts/`、`configs/` 不再恢复。正式主 Prompt 继续由单一代码入口组装，避免重新制造看似有效、实际空置的配置来源。

## 上下文达到 80% 才压缩

当前 DeepSeek 官方模型页给出的 V4 上下文长度为 1,000,000 tokens；`deepseek-chat` 兼容名对应 V4 Flash 非思考模式。因此默认阈值为：

```text
context_window = 1,000,000
compression_threshold = 80% = 800,000 tokens
compression_target = 60% = 600,000 tokens
```

上下文占用包括 system Prompt、工具 Schema 和消息历史。低于 800,000 时原样发送完整上下文，不做摘要或截断。达到阈值才执行确定性压缩：

- 保留最近完整消息，不能拆开 `tool_use/tool_result` 对；
- 较早普通文本、工具参数和工具结果压缩成有长度上限的事实摘要；
- 保留用户目标、关键文件路径、成功/失败事实、尚未完成事项；
- 不保留隐藏推理；
- 压缩后目标不超过约 600,000 tokens，为新工具结果和模型输出留出空间；
- `ChatSessionStore` 仍保存完整历史，压缩只影响发给模型的当前请求。

Token 计算优先使用模型上一轮返回的真实 `usage.input_tokens` 校准后续增量；首次请求或 usage 缺失时，按 DeepSeek 官方字符换算比例做保守本地估算。不引入向量库、新对话 Checkpoint 或每轮 LLM 摘要请求。

模型窗口和阈值通过 LLM 配置提供默认值，不能把 `deepseek-chat` 字符串写死在 `ContextManager`。未来更换模型时只调整配置映射或环境变量。

资料依据（核对日期：2026-08-12）：

- [DeepSeek 官方模型与价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing)：V4 Flash/Pro 上下文长度为 1M，并说明旧 `deepseek-chat` 兼容映射。
- [DeepSeek 官方 Token 用量说明](https://api-docs.deepseek.com/quick_start/token_usage/)：精确用量以响应 `usage` 为准；本地估算可参考英文字符约 0.3 token、中文字符约 0.6 token。
- [DeepSeek Anthropic API 兼容说明](https://api-docs.deepseek.com/guides/anthropic_api)：流式、system、tools 与 tool_result 均受支持。

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
- 连续搜索/列目录/读取超过三轮仍可继续并最终回答。
- 相同失败循环触发重新规划提示；一次失败后的成功不会继续显示旧错误。
- `search_workspace` 能搜索普通源码，并跳过所有隐藏路径。
- 所有主 Agent 文件工具拒绝工作区外、`..`、隐藏路径和符号链接逃逸。
- `read_file` 可分页读取常见文本文件并拒绝二进制文件。
- 估算占用低于 800,000 tokens 时上下文对象保持完整；达到阈值后才压缩到约 600,000，且保持工具协议配对。
- 运行 CLI/工具装配相关测试和全量 pytest，保证旧 profile 调试入口继续可用。

## 非目标

- 不把 CodeRepairAgent 工具暴露给主聊天 Agent。
- 不新增 Agent、Runtime、状态文件或审批系统。
- 不删除 `--profile` 兼容参数。
- 不通过 Prompt 复制 Python 状态机的全部实现细节。
- 不恢复已删除的 `prompts/` 或 `configs/` 旧占位目录。
- 不在每次模型调用前无条件摘要上下文。
