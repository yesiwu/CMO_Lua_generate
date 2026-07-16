# 通用工具执行进度展示设计

日期：2026-07-15

## 1. 目标

为所有 Agent Tool 提供统一、可复用的执行进度展示机制，使终端能够显示：

- 工具开始执行；
- 固定业务阶段；
- 实时关键输出；
- 当前正在执行的步骤；
- 工具成功、失败和警告；
- 最终摘要。

进度展示必须与工具最终结果分离：

- `ToolProgressEvent` 面向用户界面，可限流、折叠或丢弃；
- `ToolResult` 面向 Agent 控制流，必须完整、准确、可持久化。

## 2. 设计原则

1. 工具层不直接依赖 Rich、终端或具体 UI。
2. 所有工具使用同一套进度事件协议。
3. 领域日志解析留在领域模块中，例如 CMO 日志由 `cmo_progress_parser.py` 解释。
4. 现有工具可以渐进接入，不要求一次性全部重写。
5. 进度回调失败不能影响工具本体执行。
6. 完整原始日志仍保存到文件，终端只展示筛选后的关键内容。

## 3. 推荐架构

```text
AgentLoop
    │
    ├─ 创建 ToolContext
    │
    ▼
ToolRegistry.execute(tool_name, arguments, context)
    │
    ▼
具体 Tool
    │
    ├─ context.progress.tool_started(...)
    ├─ context.progress.step_started(...)
    ├─ context.progress.step_progress(...)
    ├─ context.progress.output(...)
    ├─ context.progress.step_completed(...)
    ├─ context.progress.tool_completed(...)
    └─ context.progress.tool_failed(...)
    │
    ▼
ToolProgressReporter
    │
    ▼
AgentEvent
    │
    ▼
UIState
    │
    ▼
TerminalDisplay
```

## 4. 新增组件

### 4.1 `ToolProgressEvent`

文件：

```text
src/cmo_lua_agent/tools/tool_base/progress.py
```

建议字段：

```python
@dataclass(frozen=True)
class ToolProgressEvent:
    tool_use_id: str
    tool_name: str
    event_type: str
    status: str
    message: str
    detail: str | None = None
    progress: float | None = None
    step_id: str | None = None
    parent_step_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

`event_type` 的稳定值：

```text
tool_started
step_started
step_progress
step_completed
output
tool_completed
tool_failed
```

`status` 的稳定值：

```text
pending
running
success
failed
warning
```

### 4.2 `ToolProgressReporter`

同样位于：

```text
src/cmo_lua_agent/tools/tool_base/progress.py
```

职责：

- 为工具封装事件构造；
- 自动补充 `tool_use_id` 和 `tool_name`；
- 调用统一 callback；
- 捕获 callback 异常，避免 UI 故障影响工具执行。

推荐接口：

```python
reporter.tool_started(message)
reporter.step_started(step_id, message, detail=None)
reporter.step_progress(step_id, message, detail=None, progress=None)
reporter.output(message, detail=None, metadata=None)
reporter.step_completed(step_id, message, detail=None)
reporter.tool_completed(message, detail=None)
reporter.tool_failed(message, detail=None)
```

### 4.3 `ToolContext`

文件：

```text
src/cmo_lua_agent/tools/tool_base/context.py
```

初始版本：

```python
@dataclass(frozen=True)
class ToolContext:
    tool_use_id: str
    tool_name: str
    progress: ToolProgressReporter
```

暂不加入取消信号、权限、运行目录等字段。后续有真实需求时再扩展。

## 5. Tool 接口兼容方案

现有接口：

```python
def execute(self, arguments: dict[str, Any]) -> ToolResult:
```

渐进升级为：

```python
def execute(
    self,
    arguments: dict[str, Any],
    context: ToolContext | None = None,
) -> ToolResult:
```

兼容规则：

- `context is None` 时工具照常执行；
- 已接入进度的工具通过 `context.progress` 上报；
- 未接入的旧工具无需立即修改；
- `ToolRegistry` 负责统一传入 `ToolContext`。

## 6. AgentLoop 与 Registry 的职责

### 6.1 `ToolRegistry`

`ToolRegistry.execute(...)` 增加 `context` 参数，并将其传递给具体工具。

若需兼容旧工具，可在过渡期检测 execute 方法是否支持 `context`，但最终应统一接口，避免长期保留反射分支。

### 6.2 `AgentLoop`

每次收到 `tool_use` 时：

1. 使用模型提供的 `tool_use_id` 创建 `ToolContext`；
2. 创建 `ToolProgressReporter`；
3. reporter 的 callback 将 `ToolProgressEvent` 转换为 `AgentEvent`；
4. 调用 `ToolRegistry.execute(...)`；
5. 工具结束后继续按现有协议将 `ToolResult` 写回模型消息。

## 7. UI 状态设计

文件：

```text
src/cmo_lua_agent/orchestration/ui_state.py
```

新增：

```python
@dataclass
class ToolStepState:
    step_id: str
    message: str
    status: str
    detail: str | None = None
    progress: float | None = None

@dataclass
class ToolExecutionState:
    tool_use_id: str
    tool_name: str
    status: str
    arguments: dict[str, Any]
    steps: list[ToolStepState]
    output_lines: list[str]
    current_message: str | None = None
    final_summary: str | None = None
```

UIState 根据事件更新对应的 `ToolExecutionState`。

## 8. TerminalDisplay 渲染规则

执行中：

```text
→ execute_cmo
  lua_path: D:\...\all.lua
  job_index: 0

  ✓ 校验 Lua 文件
  ✓ 创建运行目录：run_20260715_...
  ✓ 更新 CMO 任务配置
  ⠦ 正在执行 CMO 仿真
    加载想定：TOT_防御带反击
    仿真时间：00:45:00
    现实耗时：3.1 秒，脉冲：1418
```

完成后可压缩为：

```text
● execute_cmo
  └─ 执行成功，耗时 18.4 秒
```

失败时：

```text
✗ execute_cmo
  ├─ Lua 执行失败
  ├─ 位置：Console:132
  └─ 'in' expected near '('
```

渲染规则：

- 当前步骤使用 spinner；
- 完成步骤使用 `✓`；
- 失败步骤使用 `✗`；
- 普通输出使用缩进；
- 输出行数量设置上限，避免终端无限增长；
- 完整日志不在 UI 中保存，只保存在运行产物中。

## 9. CMO 进度适配

文件：

```text
src/cmo_lua_agent/execution/cmo_progress_parser.py
```

职责：

```text
CMO 原始控制台行
→ 判断是否值得展示
→ 生成结构化 CMOProgressMessage
→ 由 ExecuteCmoTool/CmoRunner 转为通用 ToolProgressEvent
```

展示的内容：

- 加载想定；
- Scenario 参数；
- Lua 后对象统计；
- 仿真时间和现实耗时；
- 成功；
- 失败；
- Lua 错误；
- 超时。

过滤的内容：

- `setlocal`；
- `tasklist`；
- `if not errorlevel`；
- 批处理命令回显；
- 重复进度；
- 无业务价值的调试输出。

`CmoProcessRunner` 从一次性 `communicate()` 调整为持续读取 stdout，同时累积所有原始字节，保证 `console_output` 和 `cmo_output.txt` 不丢失。

## 10. 非 CMO 工具示例

### 10.1 ReadFileTool

```text
● Read(D:\project\config.json)
  └─ Read 128 lines
```

### 10.2 SearchTool

```text
● Search(pattern="*.lua")
  └─ Found 27 files
```

### 10.3 测试工具

```text
✱ Running tests with coverage…
  ├─ 已发现 84 个测试
  ├─ 已完成 42/84
  └─ 当前：test_cmo_runner.py
```

所有工具使用同一事件协议，只有业务消息不同。

## 11. 错误处理

1. Progress callback 抛异常：记录日志，工具继续执行。
2. 工具失败：发出 `tool_failed`，同时返回 `ToolResult(is_error=True)`。
3. 工具自身抛异常：Registry 转换为错误 ToolResult，AgentLoop 发出失败事件。
4. UI 更新失败：不能中断工具执行。
5. CMO 原始日志解析失败：忽略该行，但仍保存原始日志。
6. 进度事件不得作为判断业务成功的依据。

## 12. 测试策略

### 12.1 基础模型测试

- Event 字段校验；
- progress 范围校验；
- metadata 默认值隔离；
- Reporter 自动补充工具标识。

### 12.2 Reporter 测试

- 每个便捷方法生成正确事件；
- callback 收到事件；
- callback 抛异常不影响调用方；
- 无 callback 时不报错。

### 12.3 Registry/AgentLoop 测试

- ToolContext 正确传给工具；
- tool_use_id 保持一致；
- 进度事件正确转换为 AgentEvent；
- ToolResult 回传逻辑不受影响。

### 12.4 UIState/TerminalDisplay 测试

- 多个工具执行状态互不污染；
- 步骤状态可更新；
- 当前步骤可替换；
- 输出行受上限限制；
- 成功、失败和警告渲染正确。

### 12.5 CMO 测试

- 正常日志提取关键进度；
- 语法错误立即显示；
- 批处理回显被过滤；
- 完整 console_output 不丢失；
- 没有 callback 时仍能执行；
- 超时处理保持原行为。

## 13. 实施顺序

1. `ToolProgressEvent` 和 `ToolProgressReporter`；
2. `ToolContext`；
3. `ToolRegistry` 支持 context；
4. `AgentLoop` 转换进度事件；
5. `UIState` 和 `TerminalDisplay` 通用渲染；
6. 使用 `EchoTool` 或 `ReadFileTool` 做端到端验证；
7. 创建 `cmo_progress_parser.py`；
8. 修改 `CmoProcessRunner` 支持实时输出；
9. `ExecuteCmoTool` 接入固定阶段和 CMO 关键日志；
10. 全量回归测试和一次真实 CMO 验证。

## 14. 明确不做的内容

当前版本不实现：

- 全局 EventBus；
- 多进程事件分发；
- WebSocket；
- 进度事件持久化；
- 任意深度的步骤树；
- 用户自定义终端主题；
- 完整原始日志实时刷屏；
- 工具并行执行 UI。

这些内容只有在出现真实需求后再设计。
