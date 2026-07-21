# bootstrap

## 1. 目录定位

`bootstrap` 负责应用装配，把配置、Hook、工具 Registry、LLM Client 和显示层组合成可运行对象。它是组合根，不承载业务规则。

## 2. 核心职责

未来的 `app_factory.py` 和 `tool_factory.py` 应在这里创建依赖，集中处理默认路径和可替换实现，避免 `main.py` 里出现大量构造细节。

## 3. 输入与输出

输入是工作目录、CMO Runner 路径、配置文件、模型设置和权限策略。输出是 AgentLoop、ToolRegistry、HookManager 等已连接实例。

## 4. 主要文件

当前工具装配仍位于 `tools/tool_base/factory.py`；bootstrap 是迁移目标，尚未取代旧入口。

## 5. 依赖关系

可以依赖所有基础设施和工具模块，但不能被业务模块反向依赖。

## 6. 禁止职责

不得解析场景 JSON、生成 Lua、启动 BatchRunner 或绘制终端。

## 7. 典型调用链

`main` 读取 CLI -> `bootstrap.app_factory` -> 创建 `AgentLoop` -> `cli.chat` 运行。

## 8. 测试要求

使用 fake client、fake runner 和内存 Hook 检查装配；不要要求真实 API Key 或 CMO 安装。

## 9. 当前开发状态

计划实现。当前代码通过旧 factory 兼容运行。
