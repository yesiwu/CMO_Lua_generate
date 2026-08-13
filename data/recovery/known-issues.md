# Recovery Harness 已知问题

本文件只记录已经通过验证、原 action 重放、Git commit 与 push 的恢复经验。
TrainingRunner 在构造修复上下文时只读取有限长度内容，不把它当作状态真相或自动修改依据。
