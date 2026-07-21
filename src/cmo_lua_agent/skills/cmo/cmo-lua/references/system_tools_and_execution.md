# 系统工具与执行边界

本项目把“知识”和“动作”分开。`cmo-lua` Skill 提供工作顺序、CMO 领域约束与
参考模板；工具负责执行确定动作。不要把 Skill 文档中的示例当作可直接执行的命令。

## Chat 路径

在 `python -m cmo_lua_agent.main chat` 中，模型先用 `list_skills` 获取轻量目录，
再用 `load_skill` 读取入口或一个关联参考文件。对场景 JSON 使用：

```text
generate_cmo_lua(json_path, runs_root?, run_id?)
```

该工具调用 `ScenarioWorkflow`。它只接受工作区内的路径，默认把产物写入
`runs/`。返回 JSON 中最重要的字段为：

- `success`：是否完成所有生成与预检阶段；
- `run_id`、`run_root`：本次可复现运行的标识和根目录；
- `lua_path`：成功时为 `generation/original.lua`，预检失败时可能为
  `generation/rejected.lua`；
- `failed_stage`、`issues`、`warnings`：失败或警告的诊断入口；
- `workflow_result_path`、`resolved_manifest_path`：结构化产物位置。

成功生成不等于已经运行 CMO。若用户没有明确要求仿真，应停在生成结果并说明
Lua 与报告的位置。

## CMO 执行路径

只有用户明确要求后，才调用：

```text
execute_cmo(lua_path, job_index=0, timeout_seconds=600)
```

该工具会临时准备 BatchRunner 输入、启动外部 CMO 进程、轮询 `runner.log` 进度，
并保存本次执行的日志和结果。它有 `requires_approval=True`，交互终端必须等待用户
确认；用户拒绝不是 Lua 或 CMO 失败。

最终结果中的 `success` 由 BatchRunner 主进程状态和批次汇总共同决定。即使进程退出码
为 0，只要 `runner.log` 汇总存在失败场景，工具仍会返回失败。读取 `log_path` 或
`round_dir` 中的 `cmo_output.txt` 获取 Lua/CMO 错误；`batch_result_dir` 指向
BatchRunner 的 CMO 结果目录。

## 文件工具

`read_file` 与 `list_directory` 都不要求人工审批。前者读取 UTF-8 文本，后者只列出
直接子项且不递归读取内容。它们允许绝对路径，用于读取 CMO 的 `Results` 目录；但
路径是目录时不能调用 `read_file`。工具会返回 `suggested_tool`，必须按建议切换工具，
而不是重复同一失败调用。

## 自动化路径

CLI 的 `run` 子命令用于不依赖 Chat 的 JSON→Lua 流程：

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m cmo_lua_agent.main run .\inputs\scenario.json --runs-root .\runs
```

此命令只生成并预检 Lua，不请求审批，也不执行 CMO。批处理、CI 和无人值守流程必须
保持这一边界；需要真实 CMO 仿真时使用受控的执行入口，而不是让自动化流程等待交互审批。
