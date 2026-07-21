# orchestration

## 1. 目录定位

`orchestration` 是流程编排层，连接输入、生成、执行、修复、评估和优化，但不实现这些组件的内部算法。

## 2. 核心职责

维护 AgentLoop、事件、WorkflowContext/State、执行策略和有限重试状态机；把阶段状态传给 CLI 和 artifacts。

## 3. 输入与输出

输入是用户请求、Scenario JSON、工具结果和策略配置。输出是 AgentEvent、WorkflowResult、阶段状态和运行产物引用。

## 4. 主要文件

`agent_loop.py`、`events.py`、`ui_state.py`、`execution_policy.py`、`scenario_workflow.py`、`lua_repair_workflow.py`、`optimization_workflow.py`、`training_workflow.py`。

## 5. 依赖关系

依赖 contract、generation、execution、repair、evaluation、memory 和 artifacts；不应依赖 Rich 具体绘制。

## 6. 禁止职责

不得直接写 SQL、拼装 Lua、杀任意进程或绕过权限 Hook。

## 7. 典型调用链

`ScenarioWorkflow`: JSON -> Contract -> Generate -> Preflight -> CmoRunner -> Artifact -> Evaluation。

## 8. 测试要求

验证状态迁移、失败分支、审批策略、进度事件和上下文隔离；使用 fake services。

## 9. 当前开发状态

部分实现。AgentLoop 和 UI 事件已实现，完整 ScenarioWorkflow 计划接入。
