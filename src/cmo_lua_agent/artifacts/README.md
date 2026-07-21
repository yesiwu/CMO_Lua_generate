# artifacts

## 1. 目录定位

`artifacts` 管理一次运行的可复现产物，是执行和训练之间的持久化边界。

## 2. 核心职责

创建 run/round 目录，保存原始 Lua、控制台日志、结构化结果、进度和 checkpoint 引用。

## 3. 输入与输出

输入是 run id、Lua、CmoRunResult 和日志文本。输出是 RunPaths、RoundPaths、result.json 和路径引用。

## 4. 主要文件

`run_artifact_store.py`；旧 `core/run_artifact_store.py` 是兼容入口。

## 5. 依赖关系

被 execution、orchestration、trajectory 调用；不依赖 CLI 或 LLM。

## 6. 禁止职责

不得解析策略、运行 CMO、删除用户输入或把未完成结果标成功。

## 7. 典型调用链

`CmoRunner` -> `RunArtifactStore.create_run` -> `prepare_round` -> 保存日志和结果。

## 8. 测试要求

覆盖目录创建、路径越界、重复 run、复制失败和 JSON 序列化。

## 9. 当前开发状态

已实现。Checkpoint 和统一 serializer 计划补充。
