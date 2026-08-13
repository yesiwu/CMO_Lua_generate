# Project Instructions

- Run every Python command in the `py313` Conda environment. In PowerShell,
  activate it first: `conda activate py313; python ...`.

## User Preferences

- Keep new workflow features lightweight. Do not add extra security/audit
  mechanisms such as frozen contracts, SHA-256 validation, or clean-working-tree
  requirements unless the user explicitly requests them.
- Preserve the existing minimal runtime state and error logs needed to resume a
  task and diagnose failures.

## 中文注释与可理解性

- 优先保证代码结构清晰；中文注释只解释职责边界、调用关系、输入输出、状态
  变化、恢复策略和非显而易见的设计意图，不做逐行翻译。
- 新增或重构核心模块时，使用中文模块/类 docstring 说明上游调用者、下游
  依赖、持久化状态或 Artifact，以及该模块明确不负责的事情。
- 为 Service 公开接口、Workflow/Runner、Executor、持久化、恢复和自动修复
  的关键函数说明输入、返回、副作用和异常后的恢复语义。
- 修改既有流程时同步修正过期注释；简单 getter、setter、明显的辅助函数不
  强行添加长篇说明。
