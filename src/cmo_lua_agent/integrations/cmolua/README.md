# integrations/cmolua

## 1. 目录定位

本目录连接外部 `CMOLua-main` skill，不复制整套 Skill 到 Agent，也不替代现有 BatchRunner。

## 2. 核心职责

集中管理 CMOLua 根路径、`tools/json_to_lua.py`、`SKILL.md`、references/templates/examples/errors 和 DB3K 数据库，提供生成器调用、只读查询和按需文档检索。

## 3. 输入与输出

输入是外部根目录、JSON 路径、查询参数和相对文档路径。输出是生成 Lua、数据库行、SkillDocument 或结构化异常。

## 4. 主要文件

`config.py` 定义路径；`generator_adapter.py` 动态加载 `generate_cmo_lua`；`database_repository.py` 实现只读 SQLite；`skill_repository.py` 支持搜索和分段读取。

## 5. 依赖关系

被 contract、generation 和工具层调用；不依赖 Chat、终端和 CmoRunner。

## 6. 禁止职责

不得在适配器中补猜 DBID、修改 JSON、把整份 SKILL.md 注入 Prompt 或直接执行生成脚本。

## 7. 典型调用链

`CmoLuaIntegrationConfig` -> `CmoLuaGeneratorAdapter.generate` -> `LuaPreflightValidator`。

## 8. 测试要求

验证最小 JSON 生成、文档搜索、数据库只读和路径越界；不启动真实 MCP 子进程。

## 9. 当前开发状态

已实现基础适配器，数据库 Loadout 关联和版本清单仍为计划实现。
