"""
终端人工审批实现。

TerminalApprover 负责：

怎么向终端用户提问
怎么获取用户回答


当工具被标记为 requires_approval=True 时，
PermissionHook 可以调用本模块提供的审批器，在终端中展示
工具名称和调用参数，并要求用户明确允许或拒绝。

本模块只负责命令行交互，不负责判断哪些工具需要审批。
"""

from __future__ import annotations

from typing import Any


class TerminalApprover:
    """
    基于命令行输入的人工审批器。

    实例可以直接作为函数调用：

        approved = approver(tool_name, arguments)
    """

    def __call__(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> bool:
        print()
        print("=" * 60)
        print(f"工具请求执行：{tool_name}")
        print(f"调用参数：{arguments}")
        print("=" * 60)

        try:
            answer = input(
                "是否允许执行？[y/N] "
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return False

        return answer in {
            "y",
            "yes",
        }