# integrations

## 1. 目录定位

`integrations` 是外部系统适配层，隔离 CMOLua-main、CMO 数据库和未来其他工具。它把外部变化转换成内部稳定接口。

## 2. 核心职责

管理外部路径和版本配置，提供生成器、数据库和 Skill 文档的适配器，结构化处理外部异常。

## 3. 输入与输出

输入是外部目录、数据库路径、JSON 文件和查询参数。输出是 Lua 文本、只读查询结果、文档片段和明确异常；不输出终端状态。

## 4. 主要文件

`cmolua/` 是当前 CMOLua 适配；未来可以增加其他 CMO 版本适配而不改 contract。

## 5. 依赖关系

可以依赖外部文件、SQLite 和生成器，但不得依赖 AgentLoop、Rich 或工具审批。

## 6. 禁止职责

不得做业务语义校验、启动生产 CMO、修改数据库或决定是否重试。

## 7. 典型调用链

`contract.DatabaseResolver` -> `CmoDatabaseRepository`；`generation` -> `CmoLuaGeneratorAdapter`。

## 8. 测试要求

使用临时 SQLite、假 CMOLua 目录和最小生成器；测试路径注入、缺文件、外部异常和只读约束。

## 9. 当前开发状态

部分实现。CMOLua 适配边界已建立，版本冻结和完整数据库解析计划实现。
