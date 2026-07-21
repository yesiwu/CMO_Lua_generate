# tools/tool_base

## 1. 目录定位

本目录定义所有工具共享的抽象、上下文、进度协议、Registry 和 Hook 连接方式。

## 2. 核心职责

提供 BaseTool、ToolResult、ToolContext、ToolProgressReporter 和 ToolRegistry，统一 schema、dispatch、异常和进度接口。

## 3. 输入与输出

输入是工具名称、参数和上下文。输出是 Anthropic schema、ToolResult 和 ToolProgressEvent。

## 4. 主要文件

`base.py`、`context.py`、`progress.py`、`registry.py`、`factory.py`。

## 5. 依赖关系

只依赖 hooks 和基础标准库；具体工具依赖它，不反过来依赖某个具体工具。

## 6. 禁止职责

不得实现 CMO 业务、解析场景、直接操作终端或记录完整 Transcript。

## 7. 典型调用链

`AgentLoop` -> `ToolRegistry` -> `ToolContext.progress` -> `TerminalDisplay`。

## 8. 测试要求

覆盖重复注册、未知工具、异常归一化、tool_result 配对和进度回调异常隔离。

## 9. 当前开发状态

已实现。后续只扩展协议，不改变现有工具结果兼容格式。
