# trajectory

## 1. 目录定位

`trajectory` 保存可回放的完整执行过程，它是运行数据基础设施，不属于任何单一 RL 算法。

## 2. 核心职责

记录用户输入、模型回复、工具调用、审批、CMO 进度、修复过程、结果和奖励，支持回放、故障分析和数据集构建。

## 3. 输入与输出

输入是 AgentEvent、ToolProgress、CmoRunResult 和 Evaluation。输出是 Trajectory、TrajectoryStep 以及可持久化记录。

## 4. 主要文件

`models.py` 定义数据结构；`store.py` 负责 SQLite/文件存储。旧 `rl/trajectory*.py` 仅保留兼容转发。

## 5. 依赖关系

依赖基础数据模型和 artifacts，被 memory、evaluation、optimization、training 使用。

## 6. 禁止职责

不得训练模型、启动 CMO、决定奖励或修改生产策略。

## 7. 典型调用链

`AgentLoop` 事件 -> `TrajectoryRecorder`（计划）-> `TrajectoryStore` -> `DatasetBuilder`。

## 8. 测试要求

覆盖序列顺序、断点恢复、重复写入、JSON 序列化和损坏记录隔离；不得依赖真实 CMO。

## 9. 当前开发状态

部分实现。模型和存储已迁移，Recorder 与统一事件接入后期实现。
