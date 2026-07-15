"""
工具权限检查 Hook。



在工具执行前检查工具是否需要人工审批。

如果工具 requires_approval=False，则直接允许执行。
如果工具需要审批，则调用外部传入的 approval_function。
如果没有配置审批函数，则默认拒绝，以避免危险工具被静默执行。
"""

from __future__ import annotations

from typing import Any, Callable


ApprovalFunction = Callable[
    [str, dict[str, Any]],
    bool,
]


class PermissionHook:
    """
    PermissionHook 负责：

    判断是否需要审批
    决定拒绝还是允许
    """
    def __init__(
        self,
        approval_function: ApprovalFunction | None = None,
    ) -> None:
        self._approval_function = approval_function

    def handle(
        self,
        event: str,
        context: dict[str, Any],
    ) -> None:
        if event != "before_tool_call":
            return

        tool = context["tool"]

        if not tool.requires_approval:
            return

        if self._approval_function is None:
            raise PermissionError(
                f"工具 {tool.name} 需要人工审批，"
                "但当前运行模式没有配置审批方式"
            )

        approved = self._approval_function(
            tool.name,
            context["arguments"],
        )

        if not approved:
            raise PermissionError(
                f"用户拒绝执行工具 {tool.name}"
            )