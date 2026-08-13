"""旧名称兼容层；正式实现已经迁移到 ``CodeRepairAgent``。

保留本模块是为了不破坏已有导入和注入测试。新生产链路不再启动本地 Codex CLI。
"""

from __future__ import annotations

from typing import Callable

from cmo_lua_agent.agents.code_repair_agent import CodeRepairAgent


class SystemRepairAgent:
    """兼容旧 ``repair(context)->str`` 接口的轻量适配器。"""

    def __init__(
        self,
        *,
        project_root,
        llm_client: object | None = None,
        backend: Callable[[str], str] | None = None,
    ) -> None:
        if backend is None and llm_client is None:
            raise ValueError("system_repair_llm_client_required")
        self._backend = backend
        self._agent = (
            CodeRepairAgent(project_root=project_root, llm_client=llm_client)
            if llm_client is not None
            else None
        )

    def repair(self, prompt: str) -> str:
        """执行修复提示并返回后端摘要；空提示直接拒绝，其他验证由协调器承担。"""
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("system_repair_prompt_required")
        if self._backend is not None:
            return self._backend(prompt)
        assert self._agent is not None
        return self._agent.repair(prompt)
