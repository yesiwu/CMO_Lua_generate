# CMO Lua Agent 架构地图

本参考将 `src/cmo_lua_agent` 中已经实现的应用能力映射为 Skill 可调用的工作流。
Skill 只引用这些能力，不导入或复制其 Python 实现。

```text
CLI / Chat / Tools
        ↓
ScenarioWorkflow
        ↓
ingest → contract → generation
        ↓              ↓
integrations/cmolua   artifacts
        ↓
execution (仅 execute_cmo)
```

## 输入、契约与生成

- `ingest/JsonLoader`：检查 JSON 文件存在、UTF-8 编码、`.json` 扩展名、语法和顶层对象。
- `contract/`：依次执行 Schema、语义、IR 和数据库解析；输出 Scenario IR、场景契约和
  已解析 Manifest。此层不调用 LLM、不生成 Lua、不启动 CMO。
- `integrations/cmolua/`：连接外部 `CMOLua-main` 的确定性生成器和 CMO SQLite 数据库。
  配置可由 `CMO_LUA_SKILL_ROOT`、`CMO_LUA_GENERATOR_PATH`、`CMO_DATABASE_PATH`、
  `CMO_OUTPUTS_DIR` 覆盖。
- `generation/`：从已解析 Manifest 调用 JSON→Lua 生成器并执行 Lua preflight。

`ScenarioWorkflow` 将这些阶段按固定顺序编排。任何验证失败都返回结构化结果，并停止后续
阶段；不能跳过数据库解析或 preflight 直接进入执行。

## 执行与交互

- `tools/`：把上述应用服务暴露为模型可调用工具；`ToolContext.progress` 负责终端进度。
- `execution/`：仅负责 BatchRunner、进程等待、日志增量解析、超时清理和 CMO 执行结果。
- `hooks/PermissionHook`：只有 `requires_approval=True` 的工具才触发审批；目前 CMO
  执行属于该类，读文件、列目录、Skill 加载和 Lua 生成不属于该类。
- `cli/terminal_display.py`：渲染模型正文、工具摘要、审批与进度。显示层不参与业务判断。

## 不要混淆的目录

`CMOLua-main/` 是本项目依赖的生成器、数据库和旧 Skill 资源；
`src/cmo_lua_agent/skills/cmo/cmo-lua/` 是本项目 Agent 使用的文档型 Skill。
前者提供确定性能力，后者告诉模型何时调用本项目工具。两者不应互相复制 Python 模块，
也不应让 Skill 自动执行其 `scripts/`。
