# CMO Lua Agent 目录指南

## 从哪里开始修改

- 长期训练、自动重试、暂停恢复：`src/cmo_lua_agent/training/`
- Campaign 预览、执行、状态控制：`src/cmo_lua_agent/evolution/`
- LLM 或 Codex 自适应决策：`src/cmo_lua_agent/agents/`（保持扁平）
- CMO 进程调用：`src/cmo_lua_agent/execution/`
- Phase 7 经验学习：`src/cmo_lua_agent/learning/`
- Phase 8 Skill 聚合：`src/cmo_lua_agent/skills/`
- 模型端点与协议：`src/cmo_lua_agent/llm/`
- 正式运行产物：`runs/`
- 详细唯一调用链：`docs/architecture/runtime-entrypoints.md`

## 唯一训练链路

```text
TrainingService
  -> TrainingRunner
  -> ProductionCampaignDriver
  -> ProductionEvolutionCampaignService
  -> EvolutionCampaignService
  -> ProductionGenerationExecutor
  -> Phase 6 / Phase 7
  -> 全部代完成后统一 Phase 8
```

以后扩展训练流程，应修改这条链路的对应职责节点，不再新建平行
orchestrator、临时 CLI 或私有 CampaignStore 轮询脚本。

## agents/ 规则

`agents/` 不再建立 `strategy/` 等子目录。只有真正调用 LLM/Codex 做自适应
决策的类才放在这里；校验、状态机、文件存储、Git 回退、CMO 执行仍由各自
领域目录负责。完整 Agent 清单见 `src/cmo_lua_agent/agents/README.md`。

## 兼容边界

旧 Campaign/Training 状态继续可读取；历史 `request.json` 缺少
`execution_mode` 时按 `PRODUCTION_CMO` 解释。空目录保留，但不代表它是正式
入口。
