# memory

## 1. 目录定位

`memory` 保存和检索经过验证的历史经验，为后续生成、修复和优化提供参考，不保存未经验证的模型猜测。

## 2. 核心职责

持久化任务摘要、失败原因、修复结果、评分和可复用规则，按场景特征检索相关经验。

## 3. 输入与输出

输入是 Evaluation 结果、Trajectory、RepairReport 和标签。输出是排序后的 ExperienceRecord，不直接输出 Lua 或执行命令。

## 4. 主要文件

`experience_store.py` 负责存储；`experience_retriever.py` 负责查询和排序。

## 5. 依赖关系

依赖 evaluation 和 trajectory，被 generation/repair/optimization 使用；不依赖 CLI。

## 6. 禁止职责

不得写入秘密、原始 API Key、未经脱敏的运行日志或未经校验的 DBID。

## 7. 典型调用链

`RunArtifact` -> `Evaluation` -> `ExperienceStore`；生成前由 `ExperienceRetriever` 提供摘要。

## 8. 测试要求

使用临时 SQLite，测试写入、检索、去重、版本隔离和损坏记录处理。

## 9. 当前开发状态

部分实现。存储和检索基础代码存在，经验 schema 和脱敏策略需冻结。
