"""主 Agent 通用仓库调查链的显式真实端点验收。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from cmo_lua_agent.hooks.manager import HookManager
from cmo_lua_agent.llm.client import ClaudeClient
from cmo_lua_agent.llm_config import load_config
from cmo_lua_agent.main import MAIN_SYSTEM_PROMPT
from cmo_lua_agent.orchestration.agent_loop import AgentLoop
from cmo_lua_agent.orchestration.context_manager import ContextManager
from cmo_lua_agent.orchestration.events import AgentEventType
from cmo_lua_agent.tools.read_file_tool import ReadFileTool
from cmo_lua_agent.tools.search_workspace_tool import SearchWorkspaceTool
from cmo_lua_agent.tools.tool_base.registry import ToolRegistry


pytestmark = [
    pytest.mark.real_llm,
    pytest.mark.skipif(
        os.environ.get("RUN_REAL_LLM_GENERAL") != "1",
        reason="设置 RUN_REAL_LLM_GENERAL=1 才调用真实 LLM 端点",
    ),
]


def test_real_main_agent_searches_then_reads_before_answering(tmp_path: Path) -> None:
    """不连接 CMO，只验证真实 DeepSeek 的通用 tool_use/tool_result 闭环。"""

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "fixture.py").write_text(
        "HARNESS_ACCEPTANCE_VALUE = 'general-agent-ready'\n",
        encoding="utf-8",
    )
    (tmp_path / ".pytest-tmp").mkdir()
    (tmp_path / ".pytest-tmp" / "secret.py").write_text(
        "HARNESS_ACCEPTANCE_VALUE = 'hidden-wrong-value'\n",
        encoding="utf-8",
    )
    registry = ToolRegistry(hook_manager=HookManager())
    registry.register(SearchWorkspaceTool(tmp_path))
    registry.register(ReadFileTool(tmp_path))
    tool_names: list[str] = []

    def observe(event) -> None:
        if event.type is AgentEventType.TOOL_STARTED:
            tool_names.append(str(event.data.get("tool_name")))

    config = load_config().llm
    loop = AgentLoop(
        llm_client=ClaudeClient(config),
        tool_registry=registry,
        system_prompt=MAIN_SYSTEM_PROMPT,
        event_handler=observe,
        context_manager=ContextManager(
            context_window_tokens=config.context_window_tokens
        ),
    )

    answer = loop.run(
        [
            {
                "role": "user",
                "content": (
                    "请先搜索 HARNESS_ACCEPTANCE_VALUE 的定义，再读取命中文件并告诉我值。"
                    "不要读取任何点号开头的目录。"
                ),
            }
        ]
    )

    assert tool_names[:2] == ["search_workspace", "read_file"]
    assert answer is not None and "general-agent-ready" in answer
    assert "hidden-wrong-value" not in answer
