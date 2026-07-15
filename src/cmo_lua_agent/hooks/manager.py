"""
Hook 生命周期管理模块。

负责注册 Hook，并在指定生命周期事件发生时依次调用它们。

当前只提供最小的同步 Hook 机制，后续可以扩展：
- Hook 执行优先级；
- 异步 Hook；
- 权限审批暂停；
- Hook 异常隔离；
- 按事件类型注册 Hook。


PermissionHook
    before_tool_call 时检查危险操作

AuditHook
    记录工具名称、参数和执行结果

ArtifactHook
    自动保存 Lua、CMD 输出和错误日志

BudgetHook
    限制工具调用次数和 CMO 执行次数

CmoSnapshotHook
    CMO 执行前后保存场景状态
"""

from __future__ import annotations

from typing import Any, Protocol


class Hook(Protocol):
    """
    所有 Hook 需要遵循的公共接口。

    event 表示当前生命周期事件，例如：
    - before_tool_call
    - after_tool_call
    - tool_error

    context 保存本次事件相关的信息。
    """

    def handle(
        self,
        event: str,
        context: dict[str, Any],
    ) -> None:
        ...


class HookManager:
    """
    保存 Hook，并按注册顺序触发生命周期事件。
    """

    def __init__(self) -> None:
        self._hooks: list[Hook] = []

    def register(self, hook: Hook) -> None:
        """
        注册一个 Hook。
        """
        self._hooks.append(hook)

    def emit(
        self,
        event: str,
        context: dict[str, Any],
    ) -> None:
        """
        触发一个生命周期事件。

        使用 Hook 列表快照进行遍历，避免某个 Hook 在执行过程中
        注册新的 Hook，导致当前遍历顺序发生变化。
        """
        for hook in tuple(self._hooks):
            hook.handle(event, context)