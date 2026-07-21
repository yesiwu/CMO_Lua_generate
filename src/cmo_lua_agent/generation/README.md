# generation

## 1. 目录定位

`generation` 把通过 contract 和数据库补全的场景契约转换为 StrategySpec、候选方案和最终 Lua。它是代码生成层，不是执行层。

## 2. 核心职责

生成结构化策略，调用 CMOLua Generator Adapter，执行 Lua Preflight，返回带来源和警告的 LuaGenerationResult。

## 3. 输入与输出

输入是 ResolvedScenarioManifest、StrategySpec、模板资料和生成器配置。输出是 Lua 文本、输出路径、Preflight 错误/警告和生成元数据。

## 4. 主要文件

`strategy_spec.py`、`strategy_generator.py`、`candidate_generator.py`、`lua_generator.py`、`lua_preflight_validator.py`。未来增加 `lua_generation_service.py`。

## 5. 依赖关系

依赖 contract 和 integrations；不直接查询 SQLite，不修改 BatchRunner。

## 6. 禁止职责

不得执行 CMO、计算战斗奖励、控制修复状态机或把 warning 静默为成功。

## 7. 典型调用链

`ResolvedManifest` -> `StrategyGenerator` -> `CmoLuaGeneratorAdapter` -> `LuaPreflightValidator` -> `LuaGenerationResult`。

## 8. 测试要求

覆盖候选稳定性、生成器调用、禁止 API、Manifest 名称/DBID 对齐和输出路径安全；使用 fake adapter。

## 9. 当前开发状态

部分实现。策略与候选模块存在，统一服务和严格 Manifest 校验计划实现。
