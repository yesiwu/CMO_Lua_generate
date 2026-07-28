"""
工具注册和分发模块。

负责：
1. 注册工具并防止名称冲突；
2. 生成提供给 LLM 的 Anthropic 工具 Schema；
3. 根据工具名称查找并执行具体工具；
4. 统一处理未知工具、权限拒绝和执行异常；
5. 在工具执行前后触发 Hook。

Registry 只负责“有哪些工具”和“如何分发一次调用”，
不负责维护对话历史，也不负责构造 Anthropic tool_result 消息。

当前采用显式注册，不使用模块自动扫描或导入时自注册，
便于测试、依赖注入和理解程序实际启用了哪些工具。
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any

from cmo_lua_agent.hooks.manager import HookManager
from cmo_lua_agent.hooks.permission_hook import ToolApprovalDeniedError
from cmo_lua_agent.tools.tool_base.base import BaseTool, ToolResult
from cmo_lua_agent.tools.tool_base.context import ToolContext


logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    保存所有已注册工具，并提供统一查询和调用入口。
    """

    def __init__(
        self,
        hook_manager: HookManager | None = None,
    ) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._hook_manager = hook_manager

    def register(self, tool: BaseTool) -> None:
        """
        注册一个工具。

        工具名称必须唯一，避免后注册的工具无意覆盖已有工具。
        """
        if tool.name in self._tools:
            raise ValueError(
                f"工具名称重复：{tool.name}"
            )

        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        """
        按名称获取工具。

        工具不存在时返回 None。
        """
        return self._tools.get(name)

    def get_definitions(
        self,
        enabled_toolsets: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        返回提供给 LLM 的工具定义。

        enabled_toolsets 为 None 时返回全部可用工具。
        指定集合时，只返回属于这些 toolset 的工具。
        """
        definitions: list[dict[str, Any]] = []

        for tool in self._tools.values():
            if (
                enabled_toolsets is not None
                and tool.toolset not in enabled_toolsets
            ):
                continue


            definitions.append(
                tool.to_anthropic_schema()
            )

        return definitions

    #
    def dispatch(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        context: ToolContext | None = None,
    ) -> ToolResult:
        """
        根据工具名称执行工具。

        无论工具成功、失败或抛出异常，本方法都会返回 ToolResult，
        避免工具异常直接中断整个 Agent Loop。
        """
        tool = self.get(name)

        if tool is None:
            return ToolResult(
                content=f"未知工具：{name}",
                is_error=True,
            )

        hook_context: dict[str, Any] = {
            "tool_name": name,
            "arguments": arguments,
            "tool": tool,
        }

        try:
            if self._hook_manager is not None:
                self._hook_manager.emit(
                    "before_tool_call",
                    hook_context,
                )

            execution_context = context
            if context is not None and hook_context.get("approval_receipt") is not None:
                execution_context = replace(context, approval_receipt=hook_context["approval_receipt"])

            raw_result = (
                tool.execute(arguments, context=execution_context)
                if execution_context is not None
                else tool.execute(arguments)
            )

            result = self._normalize_result(
                raw_result
            )

        except ToolApprovalDeniedError as exc:
            result = ToolResult(
                content=f"工具权限被拒绝：{exc}",
                is_error=True,
            )

            self._emit_error_hook(
                context=hook_context,
                result=result,
                exception=exc,
            )

            return result

        except PermissionError as exc:
            result = ToolResult(
                content=(
                    f"工具 {name} 访问文件或系统资源失败："
                    f"{type(exc).__name__}: {exc}"
                ),
                is_error=True,
            )

            self._emit_error_hook(
                context=hook_context,
                result=result,
                exception=exc,
            )

            return result

        except Exception as exc:
            result = ToolResult(
                content=(
                    f"工具 {name} 执行失败："
                    f"{type(exc).__name__}: {exc}"
                ),
                is_error=True,
            )

            self._emit_error_hook(
                context=hook_context,
                result=result,
                exception=exc,
            )

            return result

        if self._hook_manager is not None:
            try:
                self._hook_manager.emit(
                    "after_tool_call",
                    {
                        **hook_context,
                        "result": result,
                    },
                )
            except Exception:
                # 工具已经执行成功。
                # after Hook 失败不能让 Agent 重复执行有副作用的工具。
                logger.exception(
                    "after_tool_call Hook 执行失败，"
                    "但工具结果仍然保留"
                )

        return result


    @staticmethod
    def _normalize_result(
        raw_result: object,
    ) -> ToolResult:
        """
        将工具返回值转换成统一 ToolResult。

        当前兼容：
        - ToolResult；
        - 普通字符串；
        - 其他可转换为字符串的对象。
        """
        if isinstance(raw_result, ToolResult):
            return raw_result

        if isinstance(raw_result, str):
            return ToolResult(
                content=raw_result
            )

        return ToolResult(
            content=str(raw_result)
        )

    def _emit_error_hook(
        self,
        context: dict[str, Any],
        result: ToolResult,
        exception: Exception,
    ) -> None:
        """
        尽力触发 tool_error Hook。

        错误 Hook 自身失败时只记录日志，
        不覆盖原始工具错误。
        """
        if self._hook_manager is None:
            return

        try:
            self._hook_manager.emit(
                "tool_error",
                {
                    **context,
                    "result": result,
                    "exception": exception,
                },
            )
        except Exception:
            logger.exception(
                "tool_error Hook 执行失败"
            )

    #未来扩展
    # def get_tool_names(...):
    #     ...

    # def get_toolset_tools(...):
    #     ...
