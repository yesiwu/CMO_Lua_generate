# 轻量通用 Agent Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将主聊天循环从旧 JSON→Lua 专用保护改造成轻量通用 Agent Harness，并补齐统一工作区工具、按 DeepSeek 上下文占用率触发的压缩和唯一核心 Prompt。

**Architecture:** `AgentLoop` 只维护模型/工具协议、重复失败恢复、中断和可选期限；任务路由进入统一核心 Prompt。主 Agent 文件工具共享 `WorkspacePathPolicy`，上下文由 `ContextManager` 在达到 1M 窗口的 80% 前保持完整，达到阈值后确定性压缩到约 60%。

**Tech Stack:** Python 3.13、Anthropic SDK、DeepSeek Anthropic API、pytest、现有 ToolRegistry/AgentEvent/ChatSessionStore。

## Global Constraints

- 所有 Python 命令使用 `C:\Users\13689\.conda\envs\py313\python.exe`。
- 直接在当前工作区修改，不创建 worktree，不覆盖或回退用户已有改动。
- 主 Agent不得访问任一路径组成部分以 `.` 开头的路径，也不得通过绝对工作区外路径、`..` 或符号链接逃逸。
- 不恢复用户已删除的 `prompts/`、`configs/`。
- 不新增 Runtime、Agent、数据库、向量检索或复杂 checkpoint。
- 默认 DeepSeek 上下文窗口 1,000,000 tokens；80% 即 800,000 触发压缩；目标约 600,000。
- 普通聊天文件写入继续要求用户确认；Training 启动后执行、Phase 7/8 和后台 Code Repair 不逐次确认。

---

### Task 1: 通用 AgentLoop 停滞检测

**Files:**
- Modify: `src/cmo_lua_agent/orchestration/agent_loop.py`
- Modify: `src/cmo_lua_agent/tests/test_agent_loop_guards.py`

**Interfaces:**
- Consumes: `AgentLoopPolicy`、`ToolResult`、`AgentEvent`。
- Produces: 与任务领域无关的重复失败处理；连续成功搜索/读取不再提前结束。

- [ ] **Step 1: 写失败测试**

增加测试：连续四轮 `list_directory/read_file` 后第五轮返回最终回答，断言没有 `AGENT_NEEDS_INPUT`；一次权限错误后成功读取不再把旧错误作为最终状态；相同工具+参数+错误连续出现时向模型返回结构化 `repeated_identical_failure`，允许模型重新规划并最终回答。

- [ ] **Step 2: 运行测试确认 RED**

Run: `python -m pytest src/cmo_lua_agent/tests/test_agent_loop_guards.py -q -p no:cacheprovider`

Expected: 旧“三轮探索终止”测试或新增连续读取测试失败。

- [ ] **Step 3: 最小实现**

删除 `_DISCOVERY_TOOLS`、`_MAX_NONPRODUCTIVE_TURNS`、`nonproductive_turns`、`has_explicit_json_path` 和 `_has_explicit_json_path()`。保留同一调用失败计数，但第二次相同失败时将结构化错误作为 `tool_result` 返回模型，不直接调用 `_finish_needs_input`；任一同 key 成功后清除该 key 的失败记录。删除固定场景 JSON 收尾文案和不可达的回合预算分支。

- [ ] **Step 4: 运行测试确认 GREEN**

Run: `python -m pytest src/cmo_lua_agent/tests/test_agent_loop_guards.py src/cmo_lua_agent/tests/test_agent_loop_history.py -q -p no:cacheprovider`

Expected: PASS。

---

### Task 2: 统一工作区路径策略

**Files:**
- Create: `src/cmo_lua_agent/tools/workspace_policy.py`
- Modify: `src/cmo_lua_agent/tools/read_file_tool.py`
- Modify: `src/cmo_lua_agent/tools/list_directory_tool.py`
- Modify: `src/cmo_lua_agent/tools/edit_file_tool.py`
- Modify: `src/cmo_lua_agent/tools/create_file_tool.py`
- Modify: `src/cmo_lua_agent/tools/create_json_copy_tool.py`
- Test: `src/cmo_lua_agent/tests/tools/test_workspace_policy.py`
- Modify: existing file-tool tests under `src/cmo_lua_agent/tests/tools/`

**Interfaces:**
- Produces: `WorkspacePathPolicy(workdir: Path)`；`resolve_read(raw_path, *, expect)`；`resolve_write(raw_path, *, allow_existing)`；`visible_children(path)`。

- [ ] **Step 1: 写失败测试**

覆盖普通相对路径通过，绝对工作区外路径、`..`、`.env`、`.github/x`、`src/.cache/x` 和符号链接逃逸拒绝；`list_directory` 过滤隐藏子项；读写与 JSON 副本使用相同规则。

- [ ] **Step 2: 运行测试确认 RED**

Run: `python -m pytest src/cmo_lua_agent/tests/tools/test_workspace_policy.py src/cmo_lua_agent/tests/tools/test_read_file_tool.py src/cmo_lua_agent/tests/tools/test_create_file_tool.py -q -p no:cacheprovider`

Expected: `WorkspacePathPolicy` 不存在或旧工具仍允许外部路径。

- [ ] **Step 3: 最小实现**

集中执行相对路径、工作区边界、隐藏组成部分和符号链接检查；工具不再各自 `resolve()` 后直接放行。路径错误返回中文人类可读说明，稳定错误码保持英文。

- [ ] **Step 4: 运行测试确认 GREEN**

运行全部 `tests/tools/test_*file*`、`test_workspace_policy.py`。

---

### Task 3: 通用搜索、分页读取与大输出保真

**Files:**
- Create: `src/cmo_lua_agent/tools/search_workspace_tool.py`
- Create: `src/cmo_lua_agent/tools/workspace_artifacts.py`
- Modify: `src/cmo_lua_agent/tools/read_file_tool.py`
- Modify: `src/cmo_lua_agent/tools/tool_base/factory.py`
- Create: `src/cmo_lua_agent/tests/tools/test_search_workspace_tool.py`
- Modify: `src/cmo_lua_agent/tests/tools/test_read_file_tool.py`
- Modify: `src/cmo_lua_agent/tests/tools/test_tool_factory.py`

**Interfaces:**
- Produces: `search_workspace(query, paths?, glob?, max_results?)`；`read_file(path, start_line?, end_line?)`；大输出 `{summary, truncated, artifact_path}`。

- [ ] **Step 1: 写失败测试**

搜索普通 `.py/.json/.md` 命中，隐藏目录内容不命中，路径越界拒绝；读取行区间准确；含 NUL 或已知二进制扩展的文件拒绝；超过阈值的完整输出写入 `runs/agent-artifacts/<session>/` 并可由 `read_file` 分页读取。

- [ ] **Step 2: 运行测试确认 RED**

Run: `python -m pytest src/cmo_lua_agent/tests/tools/test_search_workspace_tool.py src/cmo_lua_agent/tests/tools/test_read_file_tool.py -q -p no:cacheprovider`

- [ ] **Step 3: 最小实现**

搜索优先使用 `rg --json/--line-number` 的 argv 调用，`shell=False`，若 `rg` 不存在使用受路径策略约束的 Python 文本遍历；不跟随符号链接。Artifact 文件名使用随机 ID，目录非隐藏且不承担状态真相。主 Registry 注册 `search_workspace`。

- [ ] **Step 4: 运行测试确认 GREEN**

Run: 工具定向测试与 `test_tool_factory.py`。

---

### Task 4: 80% 阈值上下文管理

**Files:**
- Modify: `src/cmo_lua_agent/llm_config.py`
- Modify: `src/cmo_lua_agent/orchestration/context_manager.py`
- Modify: `src/cmo_lua_agent/orchestration/agent_loop.py`
- Modify: `src/cmo_lua_agent/cli/chat.py`
- Modify: `src/cmo_lua_agent/main.py`
- Modify: `src/cmo_lua_agent/agents/code_repair_agent.py`
- Modify: `src/cmo_lua_agent/tests/orchestration/test_context_manager.py`
- Modify: `src/cmo_lua_agent/tests/test_agent_loop_history.py`
- Modify: `src/cmo_lua_agent/tests/cli/test_chat_sessions.py`

**Interfaces:**
- Produces: `ContextManager(context_window_tokens=1_000_000, compression_threshold_ratio=0.8, compression_target_ratio=0.6)`；`build(messages, system_prompt, tools)`；`observe_usage(actual_input_tokens)`。

- [ ] **Step 1: 写失败测试**

低于 800K 时 `build()` 保持所有消息及内容；达到阈值才压缩；压缩结果估算不超过约 600K；不能产生孤立 tool_use/tool_result；真实 usage 校准下一轮估算。聊天保存完整历史，压缩副本不反向污染 Session。

- [ ] **Step 2: 运行测试确认 RED**

Run: `python -m pytest src/cmo_lua_agent/tests/orchestration/test_context_manager.py src/cmo_lua_agent/tests/test_agent_loop_history.py src/cmo_lua_agent/tests/cli/test_chat_sessions.py -q -p no:cacheprovider`

- [ ] **Step 3: 最小实现**

估算 system、tools 和 messages 的完整 JSON 内容；中文字符按 0.6、ASCII 字符按 0.3、其他字符按 0.6，首次乘保守系数，后续用最近真实 `input_tokens / raw_estimate` 的有界校准系数。压缩旧前缀为确定性事实摘要，保留最近协议组；`AgentLoop` 每轮请求前调用，但 ContextManager 仅在阈值到达时改变内容。`run_chat` 直接把完整 history 交给 Loop。

- [ ] **Step 4: 运行测试确认 GREEN**

运行上述测试和 CodeRepairAgent 测试。

---

### Task 5: 统一主 Prompt 与调试附加 Prompt

**Files:**
- Modify: `src/cmo_lua_agent/main.py`
- Modify: `src/cmo_lua_agent/tests/test_main.py`
- Modify: `src/cmo_lua_agent/tests/evolution/test_phase9c_production_wiring.py`
- Modify: `docs/architecture/runtime-entrypoints.md`
- Modify: `docs/architecture/系统学习与面试指南.md`

**Interfaces:**
- Produces: `MAIN_SYSTEM_PROMPT`、`STANDARD_DEBUG_APPENDIX`、`TRAINING_DEBUG_APPENDIX`、`CAMPAIGN_DEBUG_APPENDIX`、`system_prompt_for_profile(profile)`。

- [ ] **Step 1: 写失败测试**

默认 all 精确使用核心 Prompt；三个调试 profile 均以核心 Prompt 开头并只追加对应范围；Prompt 包含工具路由、普通文件一次确认、Training 启动即授权、持久化状态真实性、Recovery/CodeRepair 边界和“仓库问题先搜索后读取”。

- [ ] **Step 2: 运行测试确认 RED**

Run: `python -m pytest src/cmo_lua_agent/tests/test_main.py src/cmo_lua_agent/tests/evolution/test_phase9c_production_wiring.py -q -p no:cacheprovider`

- [ ] **Step 3: 最小实现**

删除重复的完整 `CHAT_SYSTEM_PROMPT/TRAINING_SYSTEM_PROMPT`，保留一个正式核心 Prompt 和三个短 Appendix；更新 `main.py` 顶部为当前真实入口图。文档同步修正 `SystemRepairAgent` 旧称和统一入口说明。

- [ ] **Step 4: 运行测试确认 GREEN**

运行 CLI、主入口和工具装配测试。

---

### Task 6: 端到端验收

**Files:**
- Modify tests only if verification exposes a real regression and first add a reproducing test.

- [ ] **Step 1: 定向回归**

Run:

```powershell
python -m pytest src/cmo_lua_agent/tests/test_agent_loop_guards.py src/cmo_lua_agent/tests/test_agent_loop_history.py src/cmo_lua_agent/tests/orchestration/test_context_manager.py src/cmo_lua_agent/tests/tools src/cmo_lua_agent/tests/test_main.py src/cmo_lua_agent/tests/training src/cmo_lua_agent/tests/agents/test_code_repair_agent.py -q -p no:cacheprovider
```

- [ ] **Step 2: 真实主 Agent 对话验收**

使用当前 DeepSeek 配置启动或脚本化主 Agent，提出“查找主系统 Prompt 的定义和调用位置”，断言可调用 `search_workspace/read_file` 多轮后正常回答，不访问隐藏路径且不出现固定场景 JSON 收尾。该验收不启动 CMO。

- [ ] **Step 3: 全量验证**

Run:

```powershell
python -m pytest -q -p no:cacheprovider
python -m compileall -q src/cmo_lua_agent scripts
git diff --check -- src scripts tests docs pytest.ini
```

Expected: 全部退出码 0；真实端点不可达时单独报告环境问题，不把离线测试标记失败。
