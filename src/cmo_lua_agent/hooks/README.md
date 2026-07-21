# hooks

## 1. 目录定位

`hooks` 提供工具调用前后和错误路径的横切扩展点，供权限、审计和指标接入。

## 2. 核心职责

维护 HookManager、权限 Hook 和事件载荷约定；保证 Hook 失败不会重复执行工具或吞掉原始错误。

## 3. 输入与输出

输入是工具名、参数、工具实例、结果和异常。输出是允许/拒绝决定、审计事件和日志。

## 4. 主要文件

`manager.py`、`permission_hook.py`。

## 5. 依赖关系

被 tools/tool_base 调用；不得依赖终端显示和 CMO 内部实现。

## 6. 禁止职责

不得修改工具参数、自动批准危险操作或直接执行替代命令。

## 7. 典型调用链

`ToolRegistry.before` -> `PermissionHook` -> `Tool.execute` -> `after/error hook`。

## 8. 测试要求

覆盖允许、拒绝、Hook 异常和嵌套审批；不依赖真实用户输入。

## 9. 当前开发状态

已实现基础 Hook；细粒度场景权限和审计持久化计划实现。
