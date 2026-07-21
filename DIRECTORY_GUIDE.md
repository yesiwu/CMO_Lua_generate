# CMO Lua Agent 目录总览

## 1. 项目分层

本项目把 CMO 自动化拆成输入、契约、领域适配、生成、执行、评估和编排七层。外部 `CMOLua-main` 只通过 `integrations/cmolua/` 接入；现有 BatchRunner 仍由 `execution/` 管理。目录重构采用兼容入口，旧的 `core/`、`rl/` 路径暂时保留转发，不影响现有 Chat 流程。

## 2. 核心调用链

```text
CLI / Tool
  -> AgentLoop / Workflow
  -> ingest
  -> contract
  -> integrations.cmolua.database_repository
  -> generation
  -> artifacts
  -> execution.CmoRunner
  -> evaluation / memory / trajectory
```

Chat 模式维持工具审批和 Rich 进度显示；Run 模式面向确定性场景输入；Optimize 模式在后期消费评估和经验数据。`execute_cmo` 仍是同步 BatchRunner 工具，原有超时、日志、结果目录和部分失败语义不变。

## 3. 依赖方向

上层可以调用下层接口，下层不得反向依赖 CLI、终端或 AgentLoop。`contract` 不访问 SQLite，`generation` 不启动 CMO，`execution` 不控制 LLM，`integrations` 不输出终端。所有运行产物进入 `artifacts`，每次执行写入 `runs/`。

## 4. 当前阶段

已实现：Chat、工具注册、CMO BatchRunner、流式输出、工具进度、产物保存、CMOLua 生成器适配边界。部分实现：contract、严格数据库解析、Lua preflight、repair/evaluation。计划实现：根目录测试迁移、完整 ScenarioWorkflow、策略一致性校验和候选优化。后期创建：可回放 trajectory 与独立 training 服务。

## 5. 数据生命周期

`inputs/` 保存用户输入和标准样例；`outputs/` 保存独立生成结果；`runs/` 保存一次完整 Workflow 的 JSON、Lua、日志和结果目录；`docs/` 保存架构、契约和计划。生成结果不能替代运行产物，运行产物也不应反向修改输入。

## 6. 快速索引

应用代码位于 `src/cmo_lua_agent/`，测试位于 `tests/` 和现有兼容测试目录，领域资料通过 `CMOLua-main` 提供。新代码优先使用新目录，旧导入路径只用于兼容。
