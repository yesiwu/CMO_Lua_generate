# 运行产物与调试

每一次 JSON→Lua 工作流都创建独立运行目录：

```text
runs/<run_id>/
├── input/source.json
├── validation/
│   ├── schema_report.json
│   ├── semantic_report.json
│   ├── ir_report.json
│   ├── database_report.json
│   ├── manifest_report.json
│   └── lua_preflight_report.json
├── contract/
│   ├── scenario_ir.json
│   ├── scenario_contract.json
│   └── resolved_manifest.json
├── generation/original.lua
└── result/workflow_result.json
```

预检失败时，生成目录可能保存 `rejected.lua`，而不会产生可执行的 `original.lua`。
中间产物默认不可覆盖，最终 `workflow_result.json` 是同一次运行唯一允许更新的汇总文件。

## 推荐排查顺序

1. 先看工具返回中的 `failed_stage` 与 `issues`。
2. 使用 `read_file` 读取对应的 `validation/*_report.json` 或
   `result/workflow_result.json`。
3. 需要确认输出目录时先调用 `list_directory`；不要把目录传给 `read_file`。
4. 仅当 `original.lua` 存在且用户要求仿真时，调用 `execute_cmo`。
5. CMO 执行失败时，读取执行结果给出的 `log_path`、`round_dir` 或
   `cmo_output.txt`；随后按 Lua 错误、数据库错误、BatchRunner 错误或超时分类处理。

## 结果解释

`execute_cmo` 的成功不仅要求 BatchRunner 主进程退出正常，也要求批次汇总中失败数为零。
结果会包含执行耗时、成功/失败计数、运行目录和 CMO `Results` 目录。场景级失败、Lua 异常
或超时都必须作为失败报告给用户，不能因为进程退出码为零而声称仿真成功。

工具进度只是状态显示，不是完成依据。进程完成依据是 BatchRunner 主 PID 退出；
`runner.log` 用于展示当前场景、仿真时间、耗时和最终汇总。若进度暂时没有新行，应等待
工具完成或超时，不要重复启动第二个 CMO 批次。
