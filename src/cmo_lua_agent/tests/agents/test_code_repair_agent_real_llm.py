from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest

from cmo_lua_agent.agents.code_repair_agent import CodeRepairAgent, RepairAgentStatus
from cmo_lua_agent.llm.client import ClaudeClient
from cmo_lua_agent.llm_config import load_config
from cmo_lua_agent.orchestration.events import AgentEventType


pytestmark = [
    pytest.mark.real_llm,
    pytest.mark.skipif(
        os.environ.get("RUN_REAL_LLM_REPAIR") != "1",
        reason="设置 RUN_REAL_LLM_REPAIR=1 才调用真实 LLM 端点",
    ),
]


def test_real_llm_completes_two_stage_code_repair_tool_loop(tmp_path: Path) -> None:
    """验收真实 tool_use/tool_result 多轮协议，不连接 CMO 或正式训练 Artifact。"""

    source = tmp_path / "src" / "fixture" / "value.py"
    test = tmp_path / "tests" / "test_value.py"
    source.parent.mkdir(parents=True)
    test.parent.mkdir(parents=True)
    (source.parent / "__init__.py").write_text("", encoding="utf-8")
    source.write_text("def repaired_value():\n    return 0\n", encoding="utf-8")
    test.write_text(
        "from fixture.value import repaired_value\n\ndef test_value():\n    assert repaired_value() == 1\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "src", "tests"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "fixture"], cwd=tmp_path, check=True, capture_output=True)

    tool_names: list[str] = []
    switched = False

    def observe(event) -> None:
        nonlocal switched
        tool_name = event.data.get("tool_name")
        if event.type is AgentEventType.TOOL_STARTED and isinstance(tool_name, str):
            tool_names.append(tool_name)
        if (
            not switched
            and event.type is AgentEventType.TOOL_COMPLETED
            and tool_name == "run_repair_command"
        ):
            try:
                payload = json.loads(str(event.data.get("content", "")))
            except ValueError:
                return
            if payload.get("exit_code") == 0:
                # 首次成功后切换隐藏的第二阶段，迫使真实模型观察新失败并进行第二次修改。
                test.write_text(
                    "from fixture.value import repaired_value\n\ndef test_value():\n    assert repaired_value() == 73\n",
                    encoding="utf-8",
                )
                switched = True

    agent = CodeRepairAgent(
        project_root=tmp_path,
        llm_client=ClaudeClient(load_config().llm),
        deadline_seconds=600,
        event_handler=observe,
    )
    result = agent.repair_with_result(
        (
            "修复 tests/test_value.py。先搜索并读取实现和测试，修改后运行 pytest。"
            "这是两阶段 fixture：第一次测试成功后测试契约会切换；你必须重新读取测试、"
            "再次运行 pytest，观察新失败后进行第二次修改，最后检查 diff。"
        ),
        workflow_id="real-llm-repair",
        attempt=1,
    )

    final_test = subprocess.run(
        [os.sys.executable, "-m", "pytest", "tests/test_value.py", "-q"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONPATH": str(tmp_path / "src")},
    )
    assert result.status is RepairAgentStatus.COMPLETED
    assert switched is True
    assert tool_names.count("edit_repair_file") >= 2
    assert tool_names.count("run_repair_command") >= 2
    assert "search_code" in tool_names
    assert "read_repair_file" in tool_names
    assert "inspect_repair_diff" in tool_names
    assert final_test.returncode == 0, final_test.stdout + final_test.stderr
