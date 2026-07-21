# cli

## 1. 目录定位

`cli` 是用户与 Agent 交互的终端边界，负责 chat、未来的 run 命令、审批提示和 Rich 显示。它只呈现状态，不决定作战业务。

## 2. 核心职责

读取用户输入、启动对话循环、呈现 LLM 流式正文、显示工具进度、暂停 Live 以等待审批，并在工具完成后保留摘要和路径。

## 3. 输入与输出

输入是命令行参数、用户文本和 AgentEvent。输出是终端文本、审批结果和退出码；不会直接产生 CMO 结果目录。

## 4. 主要文件

`chat.py` 负责交互循环；`terminal_display.py` 管理 Live；`terminal_approval.py` 管理人工授权；`run_scenario.py` 为计划中的非交互入口。

## 5. 依赖关系

依赖 orchestration、tools 和 display library；不应依赖 SQLite、Lua 生成细节或 BatchRunner 私有实现。

## 6. 禁止职责

不得在 CLI 中修改任务 JSON、猜测 DBID、重试 CMO 或吞掉工具错误。

## 7. 典型调用链

`chat` -> `AgentLoop.run` -> 事件 -> `TerminalDisplay`；审批通过后由 Registry 执行工具。

## 8. 测试要求

测试流式 delta、审批暂停/恢复、Markdown 原文、异常和多轮工具调用；使用 fake event，不依赖真实终端窗口。

## 9. 当前开发状态

已实现 Chat、审批和流式显示；Run CLI 计划实现。
