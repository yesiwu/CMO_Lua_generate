# cmo_lua_agent

## 1. 目录定位

应用主包是 CMO Lua Agent 的边界，负责把 CLI、LLM、工具、工作流和 CMO 执行组件组合起来。它不是一个单独的 CMO SDK，也不应把领域规则、终端绘制和进程管理全部塞进根包。

## 2. 核心职责

根包提供稳定的 Python 包名和子模块组织；`main.py` 负责命令行入口，`llm_config.py` 负责模型配置。具体业务按 ingest、contract、generation、execution 等目录分层。

## 3. 输入与输出

输入来自 CLI 参数、用户文本、结构化 JSON 和环境变量。输出是工具定义、Agent 事件、生成 Lua、BatchRunner 结果和可序列化运行产物。根包不直接定义场景字段，也不直接访问 CMO SQLite。

## 4. 主要文件

`main.py`、`llm_config.py`、`__init__.py` 是稳定入口；其余能力通过子包暴露。

## 5. 依赖关系

根包可以依赖所有内部子包，但子包不应依赖根包中的隐式全局状态。外部 CMOLua 通过 integrations 接入。

## 6. 禁止职责

不得在根包执行屏幕点击、拼接 SQL、保存临时日志或绕过工具审批。

## 7. 典型调用链

`python -m cmo_lua_agent.main chat` -> `cli.chat` -> `orchestration.agent_loop` -> `tools` -> `execution`。

## 8. 测试要求

根包测试应验证入口解析和依赖装配，不启动真实 CMO；真实执行放在显式集成测试。

## 9. 当前开发状态

已实现。目录边界已形成，contract 和完整 Run Workflow 仍在逐步补齐。
