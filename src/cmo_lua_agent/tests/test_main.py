from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import cmo_lua_agent.main as main_module
from cmo_lua_agent.orchestration.chat_session_store import ChatSessionStore


@dataclass
class StubApplication:
    """Task 4.2 返回的最小应用对象。"""

    scenario_workflow: object


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        (SimpleNamespace(model_id="claude-sonnet"), "claude-sonnet"),
        (SimpleNamespace(model="claude-opus"), "claude-opus"),
        (SimpleNamespace(model_name="claude-haiku"), "claude-haiku"),
        (SimpleNamespace(), "Claude"),
    ],
)
def test_resolve_model_name_兼容三种字段(
    config: object,
    expected: str,
) -> None:
    assert main_module.resolve_model_name(config) == expected


def test_build_parser_保留_chat模式() -> None:
    parser = main_module.build_parser()

    args = parser.parse_args(["chat"])

    assert args.command == "chat"
    assert isinstance(args.workdir, Path)


def test_chat_system_prompt_requires_json_path_before_generation() -> None:
    prompt = main_module.CHAT_SYSTEM_PROMPT

    assert "用户没有提供明确的 JSON 路径时，直接询问路径" in prompt
    assert "优先调用 generate_cmo_lua" in prompt
    assert "不得用 read_file 猜测 CMOLua-main 中的路径" in prompt
    assert "优先调用 query_cmo_database 核验事实" in prompt
    assert "选择仍须用户明确确认" in prompt
    assert "必须等待用户明确同意后，才调用 edit_file" in prompt
    assert "第二次终端人工审批" in prompt
    assert "首次修复，默认使用 create_json_copy" in prompt
    assert "后续修复应针对 create_json_copy 返回的副本使用 edit_file" in prompt
    assert "只有用户明确输入“修改原文件”时才允许 edit_file 指向原文件" in prompt


def test_build_parser_解析run模式新增参数(
    tmp_path: Path,
) -> None:
    parser = main_module.build_parser()

    args = parser.parse_args(
        [
            "--workdir",
            str(tmp_path),
            "run",
            "inputs/scenario.json",
            "--runs-root",
            "custom-runs",
            "--run-id",
            "run-001",
        ]
    )

    assert args.command == "run"
    assert args.workdir == tmp_path
    assert args.input == Path("inputs/scenario.json")
    assert args.runs_root == Path("custom-runs")
    assert args.run_id == "run-001"


def test_build_parser_run模式使用默认产物目录() -> None:
    parser = main_module.build_parser()

    args = parser.parse_args(
        [
            "run",
            "inputs/scenario.json",
        ]
    )

    assert args.runs_root == Path("runs")
    assert args.run_id is None


def test_run_scenario_创建应用并调用ScenarioWorkflow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = object()
    application = StubApplication(
        scenario_workflow=workflow,
    )
    factory_calls: list[Path] = []
    workflow_calls: list[dict[str, Any]] = []

    def fake_create_application(
        project_root: Path,
    ) -> StubApplication:
        factory_calls.append(project_root)
        return application

    def fake_run_scenario_workflow(
        *,
        workflow: object,
        source_path: Path,
        runs_root: Path,
        run_id: str | None,
        platform_resolutions: Any | None,
        stdout: Any,
        stderr: Any,
    ) -> int:
        workflow_calls.append(
            {
                "workflow": workflow,
                "source_path": source_path,
                "runs_root": runs_root,
                "run_id": run_id,
                "platform_resolutions": platform_resolutions,
                "stdout": stdout,
                "stderr": stderr,
            }
        )
        return 2

    monkeypatch.setattr(
        main_module,
        "create_application",
        fake_create_application,
    )
    monkeypatch.setattr(
        main_module,
        "run_scenario_workflow",
        fake_run_scenario_workflow,
    )

    input_path = tmp_path / "inputs/scenario.json"
    runs_root = tmp_path / "runs"

    exit_code = main_module.run_scenario(
        input_path=input_path,
        workdir=tmp_path,
        runs_root=runs_root,
        run_id="run-001",
    )

    assert exit_code == 2
    assert factory_calls == [tmp_path]
    assert len(workflow_calls) == 1

    call = workflow_calls[0]
    assert call["workflow"] is workflow
    assert call["source_path"] == input_path
    assert call["runs_root"] == runs_root
    assert call["run_id"] == "run-001"
    assert call["platform_resolutions"] is None
    assert call["stdout"] is sys.stdout
    assert call["stderr"] is sys.stderr


def test_run_scenario_应用初始化失败时返回1(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_create_application(
        project_root: Path,
    ) -> StubApplication:
        raise FileNotFoundError(
            f"缺少 CMOLua-main: {project_root}"
        )

    def unexpected_workflow_call(**_: Any) -> int:
        raise AssertionError(
            "应用初始化失败后不应调用 ScenarioWorkflow"
        )

    monkeypatch.setattr(
        main_module,
        "create_application",
        fake_create_application,
    )
    monkeypatch.setattr(
        main_module,
        "run_scenario_workflow",
        unexpected_workflow_call,
    )

    exit_code = main_module.run_scenario(
        input_path=tmp_path / "scenario.json",
        workdir=tmp_path,
        runs_root=tmp_path / "runs",
        run_id=None,
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "CMO Lua 应用初始化失败" in captured.err
    assert "FileNotFoundError" in captured.err
    assert "缺少 CMOLua-main" in captured.err


def test_main_chat模式保留原来的Agent装配流程(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = SimpleNamespace(
        llm=SimpleNamespace(model_id="claude-test"),
    )
    agent_loop = object()
    display = object()
    calls: dict[str, Any] = {}

    def fake_load_config() -> object:
        calls["load_config"] = True
        return config

    def fake_build_chat_components(
        *,
        config: object,
        workdir: Path,
    ) -> tuple[object, object]:
        calls["chat_components"] = {
            "config": config,
            "workdir": workdir,
        }
        return agent_loop, display

    def fake_run_chat(
        *,
        agent_loop: object,
        display: object,
        session_store: ChatSessionStore,
    ) -> int:
        calls["run_chat"] = {
            "agent_loop": agent_loop,
            "display": display,
            "session_store": session_store,
        }
        return 7

    def unexpected_run_scenario(**_: Any) -> int:
        raise AssertionError(
            "chat 模式不应调用 run_scenario"
        )

    monkeypatch.setattr(
        main_module,
        "load_config",
        fake_load_config,
    )
    monkeypatch.setattr(
        main_module,
        "build_chat_components",
        fake_build_chat_components,
    )
    monkeypatch.setattr(
        main_module,
        "run_chat",
        fake_run_chat,
    )
    monkeypatch.setattr(
        main_module,
        "run_scenario",
        unexpected_run_scenario,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cmo-lua-agent",
            "--workdir",
            str(tmp_path),
            "chat",
        ],
    )

    exit_code = main_module.main()

    assert exit_code == 7
    assert calls["load_config"] is True
    assert calls["chat_components"] == {
        "config": config,
        "workdir": tmp_path.resolve(),
    }
    assert calls["run_chat"]["agent_loop"] is agent_loop
    assert calls["run_chat"]["display"] is display
    assert isinstance(calls["run_chat"]["session_store"], ChatSessionStore)


def test_main_run模式不加载LLM配置(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def unexpected_load_config() -> object:
        raise AssertionError(
            "run 模式不应加载 Claude/LLM 配置"
        )

    def fake_run_scenario(
        *,
        input_path: Path,
        workdir: Path,
        runs_root: Path,
        run_id: str | None,
        resolution_file: Path | None,
    ) -> int:
        calls.append(
            {
                "input_path": input_path,
                "workdir": workdir,
                "runs_root": runs_root,
                "run_id": run_id,
                "resolution_file": resolution_file,
            }
        )
        return 2

    monkeypatch.setattr(
        main_module,
        "load_config",
        unexpected_load_config,
    )
    monkeypatch.setattr(
        main_module,
        "run_scenario",
        fake_run_scenario,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cmo-lua-agent",
            "--workdir",
            str(tmp_path),
            "run",
            "inputs/scenario.json",
            "--runs-root",
            "runs-output",
            "--run-id",
            "run-002",
        ],
    )

    exit_code = main_module.main()

    assert exit_code == 2
    assert calls == [
        {
            "input_path": Path("inputs/scenario.json"),
            "workdir": tmp_path.resolve(),
            "runs_root": Path("runs-output"),
            "run_id": "run-002",
            "resolution_file": None,
        }
    ]


def test_main_chat配置加载失败时返回2(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_load_config() -> object:
        raise ValueError("缺少 ANTHROPIC_API_KEY")

    def unexpected_build_chat_components(**_: Any) -> tuple[object, object]:
        raise AssertionError(
            "配置加载失败后不应组装聊天组件"
        )

    monkeypatch.setattr(
        main_module,
        "load_config",
        fake_load_config,
    )
    monkeypatch.setattr(
        main_module,
        "build_chat_components",
        unexpected_build_chat_components,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cmo-lua-agent",
            "--workdir",
            str(tmp_path),
            "chat",
        ],
    )

    exit_code = main_module.main()
    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "配置加载失败" in captured.err
    assert "ValueError" in captured.err
    assert "缺少 ANTHROPIC_API_KEY" in captured.err


def test_main缺少子命令时保留argparse退出码2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["cmo-lua-agent"],
    )

    with pytest.raises(SystemExit) as exc_info:
        main_module.main()

    assert exc_info.value.code == 2


def test_main_help不会加载配置或应用(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_load_config() -> object:
        raise AssertionError(
            "--help 不应加载 LLM 配置"
        )

    def unexpected_create_application(
        project_root: Path,
    ) -> StubApplication:
        raise AssertionError(
            "--help 不应创建应用"
        )

    monkeypatch.setattr(
        main_module,
        "load_config",
        unexpected_load_config,
    )
    monkeypatch.setattr(
        main_module,
        "create_application",
        unexpected_create_application,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cmo-lua-agent",
            "--help",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        main_module.main()

    assert exc_info.value.code == 0
