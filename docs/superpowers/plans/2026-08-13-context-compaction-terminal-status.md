# 上下文压缩终端状态 Implementation Plan

**Goal:** 为上下文压缩增加独立、可观察且不泄露正文的终端状态。

**Architecture:** `ContextManager` 通过可选 observer 报告 started/completed；`AgentLoop` 转换成标准事件；`TerminalDisplay` 更新当前活动并打印完成摘要。

**Tech Stack:** Python 3.13、现有 AgentEvent/UIState/TerminalDisplay、pytest。

## 实施步骤

- [ ] 为压缩回调的触发条件、顺序与统计编写失败测试。
- [ ] 为 AgentLoop 的事件转换编写失败测试。
- [ ] 为终端活动和完成摘要编写失败测试。
- [ ] 实现 `ContextCompactionNotice` 与 `ContextManager.build(..., compaction_observer=...)`。
- [ ] 增加两类 `AgentEventType` 并在 AgentLoop 中桥接。
- [ ] 更新 TerminalDisplay，并运行定向、全量、编译和差异检查。
