# Chat 默认新会话 Implementation Plan

**Goal:** `chat` 每次启动默认创建空白会话，并允许用户显式恢复最近或指定历史会话。

**Architecture:** 保持 `ChatSessionStore` 的持久化格式不变；由 CLI 参数决定 `run_chat`
启动时调用 `create()`、`load_active()` 或 `activate(session_id)`。交互内的会话命令不变。

**Tech Stack:** Python 3.13、argparse、pytest。

## 实施步骤

- [ ] 为默认新建、恢复最近、恢复指定会话和参数互斥编写失败测试。
- [ ] 在 `run_chat` 增加显式恢复参数，并把默认分支改为 `create()`。
- [ ] 在 `main.py chat` 增加 `--resume`、`--session` 并传递给 `run_chat`。
- [ ] 更新入口文档并运行定向与全量测试。
