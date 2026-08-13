# Semantic Context Compaction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使用当前 LLM 端点语义压缩旧对话，并在失败时安全降级。

**Architecture:** 新增无工具 `ContextSummaryAgent`，通过协议注入 `ContextManager`。`AgentLoop` 继续只负责事件桥接，普通聊天和训练 Runtime 负责依赖组装。

**Tech Stack:** Python 3.13、Anthropic 兼容 Messages API、pytest。

## Global Constraints

- 所有新增注释、docstring 和 Prompt 使用中文。
- 完整会话历史不得因压缩被修改。
- 不增加新的 Runtime、数据库或工具 Agent。
- 摘要失败必须回退到确定性压缩。

---

### Task 1: ContextSummaryAgent

**Files:**
- Create: `src/cmo_lua_agent/agents/context_summary_agent.py`
- Test: `src/cmo_lua_agent/tests/agents/test_context_summary_agent.py`

**Interfaces:**
- Produces: `ContextSummaryAgent.summarize(messages) -> str`

- [ ] 先编写成功、非法字段和中文 Prompt 的失败测试。
- [ ] 运行测试确认因为组件不存在而失败。
- [ ] 使用 `ClaudeJsonClient` 完成单次、无工具、严格 JSON 摘要。
- [ ] 运行测试确认通过。

### Task 2: ContextManager 语义压缩与降级

**Files:**
- Modify: `src/cmo_lua_agent/orchestration/context_manager.py`
- Modify: `src/cmo_lua_agent/tests/orchestration/test_context_manager.py`

**Interfaces:**
- Consumes: `ContextSummarizer.summarize(messages) -> str`
- Produces: 包含 `strategy` 与安全 `fallback_reason` 的压缩通知。

- [ ] 先编写阈值调用、最近消息保留和失败降级测试。
- [ ] 运行测试确认缺少语义路径而失败。
- [ ] 注入摘要器并保留确定性降级实现。
- [ ] 运行上下文管理测试确认通过。

### Task 3: 终端事件与运行时装配

**Files:**
- Modify: `src/cmo_lua_agent/cli/terminal_display.py`
- Modify: `src/cmo_lua_agent/main.py`
- Modify: `src/cmo_lua_agent/training/runtime.py`
- Modify: `src/cmo_lua_agent/tests/cli/test_chat_debug.py`
- Modify: `src/cmo_lua_agent/tests/test_main.py`

**Interfaces:**
- 普通聊天及 CodeRepairAgent 注入 `ContextSummaryAgent(ClaudeJsonClient(llm_client))`。

- [ ] 先编写智能压缩与降级终端文案测试。
- [ ] 运行测试确认旧文案导致失败。
- [ ] 更新事件显示并完成两个正式入口的依赖装配。
- [ ] 运行相关测试确认通过。

### Task 4: 全量验证

- [ ] 运行全量 pytest。
- [ ] 运行 `python -m compileall -q src/cmo_lua_agent scripts`。
- [ ] 运行 `git diff --check -- src scripts tests docs pytest.ini`。
