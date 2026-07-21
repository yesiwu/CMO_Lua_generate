# ingest

## 1. 目录定位

`ingest` 是原始输入入口，负责把文件或字符串安全读取为 Python 对象。它位于 CLI 与 contract 之间，不理解具体 CMO 执行策略。

## 2. 核心职责

处理 UTF-8/BOM、JSON 解析错误、文件路径和输入概要统计；为后续结构校验提供稳定字典，并保留原始文本摘要用于审计。

## 3. 输入与输出

输入是 JSON 文件、用户提供的字典或文本。输出是原始 Python 字典、加载元数据和结构概要；不输出 Lua，不执行数据库查询。

## 4. 主要文件

`json_loader.py`、`json_profiler.py` 是当前预留入口；具体 schema 规则放在 contract。

## 5. 依赖关系

只依赖标准库和路径安全策略，下游是 contract，上游是 CLI 或 ScenarioWorkflow。

## 6. 禁止职责

不得自动修复字段、补写 DBID、改变阵营名或把 warning 转成成功。

## 7. 典型调用链

`JsonLoader.load` -> `ScenarioSchemaValidator` -> `ScenarioSemanticValidator`。

## 8. 测试要求

覆盖非法 JSON、BOM、空文件、数组/对象类型错误和路径越界；不需要 CMO 或 LLM。

## 9. 当前开发状态

部分实现。目录和调用边界已确定，严格 loader 尚需补齐。
