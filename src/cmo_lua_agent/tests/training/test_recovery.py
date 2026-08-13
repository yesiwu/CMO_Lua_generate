from __future__ import annotations

from pathlib import Path

from cmo_lua_agent.training.recovery import (
    ErrorEnvelope,
    RecoveryDecision,
    RecoveryRouter,
    RepairContextBuilder,
    VerificationGate,
    establish_training_baseline,
    make_unknown_diagnoser,
    append_known_issue,
)


def _envelope(error_type: str, message: str) -> ErrorEnvelope:
    return ErrorEnvelope(
        workflow_id="training-001",
        stage="EVOLUTION",
        generation=2,
        task="PREVIEW",
        subtask="candidate_02",
        error_type=error_type,
        message=message,
        traceback="traceback text",
        stdout_path=None,
        stderr_path="runs/training/training-001/runner.log",
        related_files=[],
    )


def test_error_envelope_captures_persisted_task_and_traceback(tmp_path: Path) -> None:
    log = tmp_path / "runner.log"
    log.write_text("failure", encoding="utf-8")

    envelope = ErrorEnvelope.capture(
        workflow_id="training-001",
        stage="EVOLUTION",
        generation=3,
        task="EXECUTE",
        subtask="candidate_02",
        error=AttributeError("worker missing result"),
        stderr_path=log,
        related_files=(Path("src/cmo_lua_agent/training/runner.py"),),
    )

    assert envelope.error_type == "AttributeError"
    assert envelope.message == "worker missing result"
    assert "AttributeError: worker missing result" in (envelope.traceback or "")
    assert envelope.stderr_path == str(log)
    assert envelope.related_files == ["src/cmo_lua_agent/training/runner.py"]


def test_recovery_router_routes_known_failures_without_llm() -> None:
    calls: list[ErrorEnvelope] = []
    router = RecoveryRouter(unknown_diagnoser=lambda error: calls.append(error))

    assert router.decide(_envelope("APIStatusError", "HTTP 502 bad gateway")).action == "RETRY"
    assert router.decide(_envelope("LuaError", "Lua syntax error near end")).action == "DOMAIN_REPAIR"
    assert router.decide(_envelope("AttributeError", "missing worker state")).action == "CODE_REPAIR"
    assert calls == []


def test_recovery_router_keeps_transient_cmo_process_failures_out_of_domain_repair() -> None:
    router = RecoveryRouter()

    assert router.decide(_envelope("CmoLockError", "Command.exe is still running")).action == "RETRY"
    assert router.decide(_envelope("RuntimeError", "Launcher has not closed yet")).action == "RETRY"
    assert router.decide(_envelope("PermissionError", "[WinError 32] sharing violation")).action == "RETRY"


def test_recovery_router_distinguishes_business_validation_from_system_schema_bug() -> None:
    router = RecoveryRouter()

    domain = router.decide(
        _envelope("StrategyValidationProposalError", "StrategySpec quantity is invalid")
    )
    code = router.decide(
        _envelope("RuntimeError", "API response schema compatibility error in state machine")
    )

    assert domain.action == "DOMAIN_REPAIR"
    assert code.action == "CODE_REPAIR"


def test_recovery_router_uses_one_bounded_unknown_diagnosis() -> None:
    calls: list[ErrorEnvelope] = []

    def diagnose(error: ErrorEnvelope) -> RecoveryDecision:
        calls.append(error)
        return RecoveryDecision("CODE", "CODE_REPAIR", "schema parser failed", ["src/cmo_lua_agent/training/store.py"])

    decision = RecoveryRouter(unknown_diagnoser=diagnose).decide(
        _envelope("StrangeFailure", "unrecognized incident")
    )

    assert decision.action == "CODE_REPAIR"
    assert decision.relevant_files == ["src/cmo_lua_agent/training/store.py"]
    assert len(calls) == 1


def test_recovery_router_treats_unknown_diagnosis_outage_as_transient() -> None:
    def diagnose(_error: ErrorEnvelope) -> RecoveryDecision:
        raise ConnectionError("diagnostic endpoint unavailable")

    decision = RecoveryRouter(unknown_diagnoser=diagnose).decide(
        _envelope("StrangeFailure", "unrecognized incident")
    )

    assert decision.category == "TRANSIENT"
    assert decision.action == "RETRY"


def test_recovery_router_rejects_unknown_actions() -> None:
    router = RecoveryRouter(
        unknown_diagnoser=lambda _error: RecoveryDecision("CODE", "DELETE_WORKSPACE", "bad", [])
    )

    decision = router.decide(_envelope("StrangeFailure", "unrecognized incident"))

    assert decision.category == "TRANSIENT"
    assert decision.action == "RETRY"


def test_repair_context_contains_bounded_runtime_evidence_and_constraints(
    tmp_path: Path,
) -> None:
    workflow_id = "training-001"
    run_dir = tmp_path / "runs" / "training" / workflow_id
    run_dir.mkdir(parents=True)
    (run_dir / "runner.log").write_text("older\nlatest failure\n", encoding="utf-8")
    known_issues = tmp_path / "data" / "recovery" / "known-issues.md"
    known_issues.parent.mkdir(parents=True)
    known_issues.write_text("# 已知问题\n\n- 连接重置后重试。\n", encoding="utf-8")
    source = tmp_path / "src" / "cmo_lua_agent" / "training" / "runner.py"
    source.parent.mkdir(parents=True)
    source.write_text("def run_once():\n    pass\n", encoding="utf-8")
    envelope = _envelope("AttributeError", "runner has no attribute action")
    envelope = ErrorEnvelope(
        **{
            **envelope.to_dict(),
            "related_files": ["src/cmo_lua_agent/training/runner.py"],
        }
    )

    context = RepairContextBuilder(project_root=tmp_path).build(
        original_task="连续运行 7 代训练",
        training_state={"status": "RECOVERING", "generation": 2},
        envelope=envelope,
        last_good_commit="abc123",
    )

    assert "连续运行 7 代训练" in context
    assert "latest failure" in context
    assert "runner has no attribute action" in context
    assert "def run_once" in context
    assert "连接重置后重试" in context
    assert "abc123" in context
    assert "最小修改" in context
    assert "不改变评分或场景语义" in context
    assert "Harness 负责提交" in context


def test_verification_gate_runs_all_steps_in_order(tmp_path: Path) -> None:
    regression = tmp_path / "src" / "cmo_lua_agent" / "tests" / "training"
    regression.mkdir(parents=True)
    commands: list[tuple[str, ...]] = []

    def command_runner(command: tuple[str, ...]) -> bool:
        commands.append(command)
        return True

    gate = VerificationGate(project_root=tmp_path, command_runner=command_runner)
    succeeded, details = gate.verify(
        changed_paths=[Path("src/cmo_lua_agent/training/runner.py")],
        targeted_test_argv=("python", "-m", "pytest", "focused_test.py", "-q"),
    )

    assert succeeded is True
    assert commands == [
        ("git", "diff", "--check", "--", "src", "scripts", "tests"),
        ("python", "-m", "pytest", "focused_test.py", "-q"),
        ("python", "-m", "pytest", "src/cmo_lua_agent/tests/training", "-q"),
    ]
    assert details[-1] == "受影响包回归测试通过"


def test_verification_gate_uses_full_suite_when_no_matching_test_directory(
    tmp_path: Path,
) -> None:
    commands: list[tuple[str, ...]] = []
    gate = VerificationGate(
        project_root=tmp_path,
        command_runner=lambda command: commands.append(command) or True,
    )

    succeeded, _details = gate.verify(
        changed_paths=[Path("scripts/launch_training.py")],
        targeted_test_argv=("python", "-m", "pytest", "focused_test.py", "-q"),
    )

    assert succeeded is True
    assert commands[-1] == (
        "python",
        "-m",
        "pytest",
        "src/cmo_lua_agent/tests",
        "-q",
    )


def test_verification_gate_stops_after_failed_regression(
    tmp_path: Path,
) -> None:
    (tmp_path / "src" / "cmo_lua_agent" / "tests" / "training").mkdir(parents=True)
    calls = 0

    def command_runner(_command: tuple[str, ...]) -> bool:
        nonlocal calls
        calls += 1
        return calls < 3

    succeeded, details = VerificationGate(
        project_root=tmp_path,
        command_runner=command_runner,
    ).verify(
        changed_paths=[Path("src/cmo_lua_agent/training/runner.py")],
        targeted_test_argv=("python", "-m", "pytest", "focused_test.py", "-q"),
    )

    assert succeeded is False
    assert "失败" in details[-1]


def test_verification_gate_includes_root_tests_when_falling_back_to_full_suite(
    tmp_path: Path,
) -> None:
    (tmp_path / "tests").mkdir()
    commands: list[tuple[str, ...]] = []
    gate = VerificationGate(
        project_root=tmp_path,
        command_runner=lambda command: commands.append(command) or True,
    )

    succeeded, _ = gate.verify(
        changed_paths=[Path("scripts/launch_training.py")],
        targeted_test_argv=("python", "-m", "pytest", "focused_test.py", "-q"),
    )

    assert succeeded is True
    assert commands[-1] == (
        "python",
        "-m",
        "pytest",
        "src/cmo_lua_agent/tests",
        "tests",
        "-q",
    )


def test_unknown_diagnoser_uses_one_strict_json_completion() -> None:
    calls: list[dict[str, str]] = []

    class JsonClient:
        def complete_json(self, **kwargs):
            calls.append(kwargs)
            return {
                "category": "CODE",
                "action": "CODE_REPAIR",
                "reason": "状态字段兼容错误",
                "relevant_files": ["src/cmo_lua_agent/training/store.py"],
            }

    decision = make_unknown_diagnoser(JsonClient())(
        _envelope("StrangeFailure", "unknown state failure")
    )

    assert decision.action == "CODE_REPAIR"
    assert decision.relevant_files == ["src/cmo_lua_agent/training/store.py"]
    assert len(calls) == 1
    assert "只输出一个 JSON 对象" in calls[0]["system"]


def test_training_baseline_limits_git_scope_and_pushes() -> None:
    commands: list[tuple[str, ...]] = []

    def git_executor(command: tuple[str, ...]) -> str:
        commands.append(command)
        if command[:2] == ("git", "status"):
            return " M src/cmo_lua_agent/training/runner.py\n M data/private.json\n"
        if command[:3] == ("git", "rev-parse", "HEAD"):
            return "abc123\n"
        return ""

    commit = establish_training_baseline(
        project_root=Path("."),
        workflow_id="training-001",
        git_executor=git_executor,
    )

    assert commit == "abc123"
    assert ("git", "add", "--", "src", "scripts", "tests") in commands
    commit_command = next(command for command in commands if command[:2] == ("git", "commit"))
    assert commit_command[-4:] == ("--", "src", "scripts", "tests")
    assert all("data" not in command for command in commands)
    assert commands[-1] == ("git", "push")


def test_known_issue_is_appended_once_after_verified_recovery(tmp_path: Path) -> None:
    envelope = _envelope("AttributeError", "missing campaign adapter")
    decision = RecoveryDecision(
        "CODE", "CODE_REPAIR", "适配器字段缺失", ["src/cmo_lua_agent/training/runtime.py"]
    )

    for _ in range(2):
        append_known_issue(
            project_root=tmp_path,
            envelope=envelope,
            decision=decision,
            root_cause="兼容层未暴露新字段",
            changed_files=["src/cmo_lua_agent/training/runtime.py"],
            verification=["针对性测试通过", "原始 action 重放通过"],
            commit_id="abc123",
        )

    text = (tmp_path / "data" / "recovery" / "known-issues.md").read_text(encoding="utf-8")
    assert text.count("## AttributeError: missing campaign adapter") == 1
    assert "abc123" in text
