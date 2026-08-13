# 语义上下文压缩设计

## 目标

把现有“旧消息逐条截取前 400 字符”的确定性压缩升级为模型驱动的语义摘要，同时保留确定性算法作为失败降级路径。完整会话历史继续由会话存储保存，压缩只影响当前发送给模型的请求副本。

## 架构

```text
AgentLoop
  → ContextManager（估算请求并判断 80% 阈值）
  → ContextSummaryAgent（无工具、单次 JSON 模型调用）
  → 结构化摘要 + 最近协议完整消息
  → 主模型请求
```

`ContextManager` 只依赖一个摘要接口，不直接依赖 `ClaudeClient`。普通聊天和训练修复运行时负责用当前 DeepSeek 兼容端点创建 `ContextSummaryAgent` 并注入。这样不会形成嵌套 `AgentLoop`，摘要过程也不会再次触发压缩。

## 摘要契约

摘要 Agent 使用中文 system prompt，禁止工具调用，只允许输出 JSON 对象。摘要必须保留用户目标、确认约束、已完成工作、当前状态、关键路径/ID/参数、工具事实、未解决问题、下一步和失败方案；不得补充原文没有的事实，也不得把推测写成结论。

输出字段固定为：

- `goal`
- `constraints`
- `completed`
- `current_state`
- `important_facts`
- `open_issues`
- `next_steps`
- `failed_attempts`

## 协议与失败恢复

最近 12 条消息继续保留原文；切分点如果落在 `tool_result` 前，会向前包含对应的 `assistant/tool_use`，避免产生孤立工具结果。智能摘要失败、返回非法 JSON 或字段类型错误时，自动使用原有确定性摘要，不让主 Agent 因辅助压缩失败而中断。

终端开始时显示“正在智能压缩上下文”。成功时显示压缩前后估算值；降级时明确显示“智能压缩失败，已使用确定性降级压缩”。通知只携带统计与失败类型，不包含对话正文。

## 验收

- 低于 80% 不调用摘要 Agent。
- 达到阈值时较早消息由摘要 Agent 生成结构化中文摘要。
- 最近消息及工具协议对保持完整。
- 摘要异常自动降级，并向终端显示独立状态。
- 普通聊天和 CodeRepairAgent 均使用当前配置的同一 LLM 端点进行摘要。
- 全量测试、`compileall` 与 `git diff --check` 通过。
