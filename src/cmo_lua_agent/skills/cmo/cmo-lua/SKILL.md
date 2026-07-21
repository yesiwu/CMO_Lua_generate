---
name: cmo-lua
description: 使用本项目已注册的工具，把受约束的 CMO 场景 JSON 验证并生成 Lua，检查运行产物，或经用户审批后执行 CMO BatchRunner。适用于 CMO 场景构建、JSON 转 Lua、Lua 预检、CMO 执行与错误排查。
version: 3.0.0
metadata:
  cmo_lua_agent:
    tags: [cmo, lua, simulation, scenario-json, batchrunner]
---

# CMO Lua Agent Skill

本 Skill 是本项目 `cmo_lua_agent` 的工作方法和领域规则入口。它不自行
运行脚本、不绕过已注册工具直接访问 SQLite，也不替代 Python 工作流；实际动作必须调用已注册工具。

## 工作顺序

1. 用户已提供明确 JSON 路径时，直接调用 `generate_cmo_lua`。仅在需要规则、模板
   或报错解释时，才使用 `list_skills` / `load_skill`。
2. 用户要求生成但未提供 JSON 路径时，直接询问路径；不要浏览工作区或猜测输入文件。
3. 对 JSON 输入调用 `generate_cmo_lua`。该工具会执行输入、语义、IR、数据库、
   Manifest 和 Lua 预检流程，但**不会启动 CMO**。
4. 读取生成结果中的 `lua_path`、`run_root` 和校验问题。成功时 Lua 位于本次
   `runs/<run_id>/generation/original.lua`。
5. 只有用户明确要求执行仿真时，才调用 `execute_cmo`。该工具会请求人工审批。
6. 执行后先读取工具返回的结构化结果；需要更多细节时，使用 `read_file` 读取
   运行目录中的日志，或用 `list_directory` 查看目录内容。

不要绕过 `generate_cmo_lua` 手写 DBID、LoadoutID 或已解析的单位信息。
当数据库校验提示武器、平台或 Loadout 问题时，可调用 `query_cmo_database`
核验真实记录。查询结果不是作战配置决策：不得据此自动改写 JSON、选择候选 DBID
或切换平台类别；必须向用户展示候选项并等待明确确认。
当只知道飞机 DBID 而不知道可用挂载方案时，调用
`query_cmo_database(operation="loadouts_for_aircraft", aircraft_dbid=...)`；
不要声称无法查询可用 Loadout。
不要因一次校验或执行失败重复相同调用；先读取错误码、失败阶段和运行产物。
`load_skill` 返回 `linked_files` 后，只能使用返回的相对路径再次调用 `load_skill`；
不得猜测 `CMOLua-main` 中的文档路径。

## 工具边界

| 目标 | 工具 | 审批 |
| --- | --- | --- |
| 发现或加载 Skill | `list_skills`、`load_skill` | 否 |
| 生成并预检 Lua | `generate_cmo_lua` | 否 |
| 查询武器、平台或挂载方案 | `query_cmo_database` | 否 |
| 执行 CMO BatchRunner | `execute_cmo` | 是 |
| 读取文本日志或产物 | `read_file` | 否 |
| 查看目录内容 | `list_directory` | 否 |

`read_file` 只能读取文件；路径是目录时应改用 `list_directory`。
`generate_cmo_lua` 的 `json_path` 和可选 `runs_root` 必须位于当前工作区。

## 按需参考

- 输入 JSON、契约与校验阶段：`references/scenario_input_contract.md`
- 工具调用、CLI 与执行边界：`references/system_tools_and_execution.md`
- 运行目录、产物与诊断步骤：`references/run_artifacts_and_debugging.md`
- Python 应用模块和调用方向：`references/system_architecture_map.md`
- CMO DBID、Lua 规则、载机、攻击模板和 CMO 错误：现有 `references/cmo_*.md`
- 旧版完整 CMO 规则库：`references/cmo_lua_legacy_v2.md`

优先加载与当前问题直接有关的一份参考文件，不要一次性读取全部资料。
