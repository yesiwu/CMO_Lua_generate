# Agent 中心化架构收敛设计

## 目标

在不破坏普通 JSON→Lua、Campaign 和持久化 TrainingRunner 的前提下，建立唯一且可追踪的正式训练链路，并把真正调用 LLM/Codex 做判断的组件集中到平铺的 `src/cmo_lua_agent/agents/`。

## 约束

- `agents/` 不再创建子目录。
- 空目录保留。
- Agent 负责诊断、决策和结构化提案；解析、校验、补丁应用、CMO 执行、状态机、持久化和 Git 操作保持确定性。
- 正式训练链路固定为 `TrainingService → TrainingRunner → TrainingCampaignAdapter → CampaignRuntime → CampaignEngine → ProductionGenerationExecutor`。
- 所有代完成后统一运行 Phase 8；不保留第二套逐代 Phase 8 orchestrator。
- 迁移先用测试固定行为，再修改生产代码。

## Agent 边界

平铺的 `agents/` 包含：

- `strategy_proposal_agent.py`：候选策略总协调。
- `strategy_intent_agent.py`：调用 LLM 生成候选意图。
- `strategy_patch_agent.py`：调用 LLM 生成受限策略补丁。
- `lua_repair_agent.py`：根据 CMO/Lua 错误生成结构化候选修复方案。
- `system_repair_agent.py`：根据 Python 系统错误调用 Codex/LLM 生成源码修改。
- `comparative_learning_agent.py`、`skill_author_agent.py`：Phase 7/8 的 LLM 决策。

确定性辅助组件继续位于领域包中。例如 CMO 错误解析位于 `execution/`，策略补丁校验和应用位于 `optimization/`，源码快照、测试、回退和 Git 提交位于 `training/`。

## Repair 链路

候选修复链路：

`CmoRunner → CmoErrorParser → RepairErrorRouter → LuaRepairAgent → deterministic validator/applier → rerender → CMO retry`。

生产候选请求必须从 Campaign 预算读取 repair 次数，不得再硬编码 `max_repairs=0`。Agent 不能直接执行 CMO，也不能绕过允许路径、Runtime Patch Registry 或语义校验。

系统源码修复链路：

`TrainingRunner → FailureClassifier → CodeRepairCoordinator → SystemRepairAgent → tests → scoped Git commit`。

`SystemRepairAgent` 只负责构造修复请求并调用后端；Coordinator 继续拥有源码快照、脏文件保护、测试、恢复和提交。

## 兼容与退役

- 删除不在正式链路中的旧 `EvolutionWorkflow`，避免逐代 Phase 8 与最终统一 Phase 8 冲突。
- 删除只解析参数而不执行流程的旧 Phase 9 CLI。
- 手工 Campaign 脚本必须只调用公开 Runtime API，不再访问 `_services`、`_build_core`、`_package_loader` 或 Engine 的 `_load`。
- 删除无法导入且已有正式替代者的旧模块。
- 历史运行目录和状态格式不迁移；读取旧 TrainingRequest 时补默认字段。

## 验证

- Agent 迁移和导入边界测试。
- 生产 FormalCandidateEvaluator repair 预算接线测试。
- TrainingRequest 旧格式恢复测试。
- 手工 CLI 不访问私有 Runtime 字段测试。
- Training、Evolution、ScenarioWorkflow、Main 和 Tool 测试。
- 全量 pytest、模块导入扫描和 `git diff --check`。
