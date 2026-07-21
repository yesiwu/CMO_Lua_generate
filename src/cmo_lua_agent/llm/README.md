# llm

## 1. 目录定位

`llm` 封装 Anthropic 客户端和流式消息协议，使 AgentLoop 不依赖 SDK 细节。

## 2. 核心职责

发送系统提示、消息、工具定义，转发文本 delta、tool_use、完成和异常事件。

## 3. 输入与输出

输入是 LLM 配置、消息历史和工具 schema。输出是 SDK Message 或流式回调事件；不执行工具。

## 4. 主要文件

`client.py`；配置位于 `llm_config.py`。

## 5. 依赖关系

被 orchestration 调用，依赖 Anthropic SDK；不得依赖 CMO、SQLite 或终端。

## 6. 禁止职责

不得自行修复 tool_use/tool_result 历史、绕过 API 错误或修改工具参数。

## 7. 典型调用链

`AgentLoop` -> `ClaudeClient.stream_message` -> delta/tool events -> AgentLoop。

## 8. 测试要求

使用 fake SDK 测试多段 Markdown、工具调用、异常和中断；禁止真实 API Key 测试。

## 9. 当前开发状态

已实现流式客户端；重试和供应商抽象计划实现。
