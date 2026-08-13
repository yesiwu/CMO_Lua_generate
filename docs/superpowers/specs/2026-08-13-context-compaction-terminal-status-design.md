# 上下文压缩终端状态设计

## 目标

当 `ContextManager` 因请求估算达到上下文窗口 80% 而压缩本轮请求副本时，终端明确显示压缩开始和完成；未触发压缩时不增加噪声。

## 边界

- `ContextManager` 是是否压缩及压缩统计的唯一真相，通过无 UI 依赖的回调报告事实。
- `AgentLoop` 把回调转换为 `AgentEvent`，不复制压缩判断。
- `TerminalDisplay` 把事件渲染成当前活动和一条完成记录。
- `ChatSessionStore` 继续保存完整历史，事件不包含消息正文。
- Code Repair 复用同一事件；后台 journal 只保留事件类型与数字统计。

## 事件

- `CONTEXT_COMPACTION_STARTED`：包含压缩前估算、窗口、阈值和目标。
- `CONTEXT_COMPACTION_COMPLETED`：包含压缩前后估算、保留的近期消息数量和耗时。

显示示例：

```text
⠋ 正在压缩上下文 · 预计 812,400 / 1,000,000 tokens
✓ 上下文压缩完成 · 812,400 → 598,200 tokens · 保留最近 12 条消息
⠋ 正在请求模型
```

压缩异常不会发出完成事件，继续由现有 `AGENT_FAILED` 收口。
