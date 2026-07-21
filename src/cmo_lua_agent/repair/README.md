# repair

## 1. 目录定位

`repair` 提供 Lua 修复服务和修复前后校验，负责一次修复建议，不负责整个重试状态机。

## 2. 核心职责

根据结构化 CMO 错误、相关 references 和原始 Lua 生成最小修改候选，并检查修改是否越过策略和安全边界。

## 3. 输入与输出

输入是 Lua 文本、CmoError、错误文档片段和原始策略。输出是 RepairCandidate、差异说明和验证报告。

## 4. 主要文件

`lua_repair_service.py` 是服务边界；未来增加 `models.py` 和 `repair_validator.py`。`orchestration/lua_repair_workflow.py` 负责循环。

## 5. 依赖关系

依赖 generation preflight、integrations 文档和 LLM 客户端；不直接启动 BatchRunner。

## 6. 禁止职责

不得无限重试、改变原始任务意图、删除失败证据或自行决定生产执行授权。

## 7. 典型调用链

`CmoRunner` 失败 -> `CmoErrorParser` -> `LuaRepairService` -> `RepairValidator` -> 再交给 `CmoRunner`。

## 8. 测试要求

测试最小差异、错误类别映射、最大轮次和策略偏移；使用 fake LLM 和固定错误文本。

## 9. 当前开发状态

计划实现。当前只有兼容边界，完整修复闭环尚未接入生产流程。
