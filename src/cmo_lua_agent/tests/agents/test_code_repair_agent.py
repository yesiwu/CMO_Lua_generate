from __future__ import annotations

from pathlib import Path
import subprocess
from types import SimpleNamespace
from typing import Any

from cmo_lua_agent.agents.code_repair_agent import (
    CodeRepairAgent,
    RepairAgentStatus,
)


def _tool_use(call_id: str, name: str, arguments: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=call_id, name=name, input=arguments)


def _response(*content: Any, stop_reason: str = "tool_use") -> SimpleNamespace:
    return SimpleNamespace(content=list(content), stop_reason=stop_reason, usage=None)


class _SequencedClient:
    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self._responses = iter(responses)
        self.requests: list[dict[str, Any]] = []

    def stream_message(self, **kwargs: Any) -> SimpleNamespace:
        self.requests.append(kwargs)
        return next(self._responses)


def _init_fixture(root: Path) -> None:
    source = root / "src" / "demo" / "calculator.py"
    test = root / "tests" / "test_calculator.py"
    source.parent.mkdir(parents=True)
    test.parent.mkdir(parents=True)
    source.write_text("def answer():\n    return 0\n", encoding="utf-8")
    test.write_text(
        "from demo.calculator import answer\n\ndef test_answer():\n    assert answer() == 2\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=root, check=True)
    subprocess.run(["git", "add", "src", "tests"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "fixture"], cwd=root, check=True, capture_output=True)


def test_code_repair_agent_observes_failed_test_and_edits_again(tmp_path: Path) -> None:
    _init_fixture(tmp_path)
    responses = [
        _response(_tool_use("1", "search_code", {"query": "def answer", "paths": ["src"]})),
        _response(_tool_use("2", "read_repair_file", {"path": "src/demo/calculator.py", "start_line": 1, "end_line": 20})),
        _response(_tool_use("3", "edit_repair_file", {"path": "src/demo/calculator.py", "old_text": "return 0", "new_text": "return 1"})),
        _response(_tool_use("4", "run_repair_command", {"argv": ["pytest", "tests/test_calculator.py", "-q"]})),
        _response(_tool_use("5", "edit_repair_file", {"path": "src/demo/calculator.py", "old_text": "return 1", "new_text": "return 2"})),
        _response(_tool_use("6", "run_repair_command", {"argv": ["pytest", "tests/test_calculator.py", "-q"]})),
        _response(_tool_use("7", "inspect_repair_diff", {})),
        _response(SimpleNamespace(type="text", text="修复完成并通过回归测试。"), stop_reason="end_turn"),
    ]
    client = _SequencedClient(responses)
    agent = CodeRepairAgent(project_root=tmp_path, llm_client=client, deadline_seconds=60)

    result = agent.repair_with_result(
        "修复 answer，使回归测试通过。",
        workflow_id="repair-fixture",
        attempt=1,
    )

    assert result.status is RepairAgentStatus.COMPLETED
    assert result.modified_files == ("src/demo/calculator.py",)
    assert len(result.tests_run) == 2
    assert result.tests_run[0].succeeded is False
    assert result.tests_run[1].succeeded is True
    assert "return 2" in (tmp_path / "src" / "demo" / "calculator.py").read_text(encoding="utf-8")
    assert len(client.requests) == 8


def test_repair_keeps_string_return_compatibility(tmp_path: Path) -> None:
    _init_fixture(tmp_path)
    client = _SequencedClient([
        _response(SimpleNamespace(type="text", text="无需修改。"), stop_reason="end_turn")
    ])
    agent = CodeRepairAgent(project_root=tmp_path, llm_client=client, deadline_seconds=60)

    assert agent.repair("检查问题") == "无需修改。"
