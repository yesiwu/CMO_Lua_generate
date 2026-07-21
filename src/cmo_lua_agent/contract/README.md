# contract

## 1. 目录定位

`contract` 把原始场景数据变成可验证、可生成、可执行的稳定契约。它位于输入读取和 Lua 生成之间：JSON -> Schema -> Semantic -> IR -> Manifest。

## 2. 核心职责

检查字段类型和范围，检查单位/阵营/射手/目标/弹药关系，构建 Scenario IR 和 Execution Manifest，并把数据库补全结果固化为无歧义数据。

## 3. 输入与输出

输入是 JsonLoader 的字典、标准化配置和数据库解析结果。输出是 ValidationReport、ScenarioIR、ScenarioContract 和 ResolvedScenarioManifest。

## 4. 主要文件

`models.py`、`scenario_schema_validator.py`、`scenario_semantic_validator.py`、`ir_builder.py`、`ir_validator.py`、`manifest_builder.py`、`database_resolver.py`。

## 5. 依赖关系

可以调用 integrations 的只读数据库接口，但不能调用 LLM、CLI、BatchRunner 或终端。

## 6. 禁止职责

不得生成 Lua、改变有歧义的作战意图、自动忽略关键校验错误或保存战斗评分。

## 7. 典型调用链

`JsonLoader` -> `SchemaValidator` -> `SemanticValidator` -> `IRBuilder` -> `DatabaseResolver` -> `ManifestBuilder`。

## 8. 测试要求

覆盖缺字段、类型错误、重复 ID、错误引用、弹药超量、未知 DBID 和 Loadout 不匹配；使用 fake repository。

## 9. 当前开发状态

部分实现。目录已建立，严格契约模型和数据库解析仍在完善。
