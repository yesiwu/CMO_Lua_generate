# tools

## 1. 目录定位

`tools` 是 LLM 可调用的窄接口层，把内部服务包装成稳定 schema、审批和 ToolResult。

## 2. 核心职责

注册工具、验证参数、转发进度、处理异常，并将生成、读取、CMO 执行和 Skill 查询暴露给 Agent。

## 3. 输入与输出

输入是 Anthropic tool_use 参数和 ToolContext。输出是 ToolResult、结构化 JSON、ToolProgressEvent；工具不直接改变对话历史。

## 4. 主要文件

`execute_cmo_tool.py`、`read_file_tool.py`、未来的 `generate_cmo_lua_tool.py`、`search_cmo_skill_tool.py`、`read_cmo_skill_tool.py`。

## 5. 依赖关系

依赖 contract/generation/integrations/execution 和 tool_base；被 AgentLoop 调用。

## 6. 禁止职责

不得在工具中编排多轮修复、控制终端 Live 或隐式执行未授权动作。

## 7. 典型调用链

`AgentLoop` -> `ToolRegistry.dispatch` -> Tool -> Service/Runner -> `ToolResult`。

## 8. 测试要求

覆盖 schema、权限、异常包装、进度和 JSON 可序列化；使用 fake service，不运行真实 CMO。

## 9. 当前开发状态

部分实现。读取和执行工具已实现，CMOLua 生成/Skill 查询工具计划接入。
