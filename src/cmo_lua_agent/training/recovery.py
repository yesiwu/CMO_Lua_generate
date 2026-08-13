"""TrainingRunner 周围的轻量恢复能力。

本模块只统一错误事实、恢复路由、修复上下文和验证门禁；它不创建第二套 Runtime
状态机，所有恢复进度仍保存在现有 TrainingState 与 journal 中。
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import subprocess
import traceback as traceback_module
from typing import Any


_ALLOWED_ACTIONS = frozenset({"RETRY", "DOMAIN_REPAIR", "CODE_REPAIR", "STOP"})
_ALLOWED_CATEGORIES = frozenset({"TRANSIENT", "DOMAIN", "CODE", "UNKNOWN"})


@dataclass(frozen=True, slots=True)
class ErrorEnvelope:
    """一次 Training 失败的客观现场，不保存根因等推断信息。"""

    workflow_id: str
    stage: str
    generation: int | None
    task: str
    subtask: str | None
    error_type: str
    message: str
    traceback: str | None
    stdout_path: str | None
    stderr_path: str | None
    related_files: list[str]

    @classmethod
    def capture(
        cls,
        *,
        workflow_id: str,
        stage: str,
        generation: int | None,
        task: str,
        error: BaseException,
        subtask: str | None = None,
        stdout_path: str | Path | None = None,
        stderr_path: str | Path | None = None,
        related_files: Iterable[str | Path] = (),
    ) -> "ErrorEnvelope":
        """从异常与已持久化任务位置构造统一错误现场。"""

        rendered_traceback = "".join(
            traceback_module.format_exception(type(error), error, error.__traceback__)
        ).strip()
        return cls(
            workflow_id=str(workflow_id),
            stage=str(stage),
            generation=generation,
            task=str(task),
            subtask=None if subtask is None else str(subtask),
            error_type=type(error).__name__,
            message=str(error),
            traceback=rendered_traceback or None,
            stdout_path=_optional_path(stdout_path),
            stderr_path=_optional_path(stderr_path),
            related_files=[Path(path).as_posix() for path in related_files],
        )

    def to_dict(self) -> dict[str, object]:
        """返回可追加到 journal 或放入修复上下文的字典。"""

        return asdict(self)


@dataclass(frozen=True, slots=True)
class RecoveryDecision:
    """恢复路由的唯一结构化输出。"""

    category: str
    action: str
    reason: str
    relevant_files: list[str]


class RecoveryRouter:
    """优先用确定性规则路由，只有 UNKNOWN 才调用一次诊断器。"""

    def __init__(
        self,
        *,
        unknown_diagnoser: Callable[[ErrorEnvelope], RecoveryDecision] | None = None,
    ) -> None:
        self._unknown_diagnoser = unknown_diagnoser

    def decide(self, error: ErrorEnvelope) -> RecoveryDecision:
        """返回 RETRY、DOMAIN_REPAIR、CODE_REPAIR 或 STOP 之一。"""

        known = self._known_decision(error)
        if known is not None:
            return known
        if self._unknown_diagnoser is None:
            return RecoveryDecision("UNKNOWN", "STOP", "没有可用的未知错误诊断器", [])
        try:
            decision = self._unknown_diagnoser(error)
        except Exception as exc:
            return RecoveryDecision(
                "TRANSIENT",
                "RETRY",
                f"未知错误诊断端点暂时不可用：{type(exc).__name__}",
                [],
            )
        if not isinstance(decision, RecoveryDecision) or decision.action not in _ALLOWED_ACTIONS:
            return RecoveryDecision("TRANSIENT", "RETRY", "未知错误诊断响应不合法", [])
        return decision

    @staticmethod
    def _known_decision(error: ErrorEnvelope) -> RecoveryDecision | None:
        text = f"{error.error_type} {error.message}".lower()
        transient_markers = (
            "timeout", "timed out", "connection reset", "connection error",
            "temporarily unavailable", "bad gateway", "http 429", "http 502",
            "http 503", "status code 429", "status code 502", "status code 503",
            "resource busy", "cmo instance locked", "sharing violation", "winerror 32",
            "command.exe is still running", "launcher has not closed", "launcher still running",
        )
        temporary_worker_lock = error.error_type == "PermissionError" and any(
            marker in text for marker in ("/workers/", "\\workers\\", "cmo")
        )
        if temporary_worker_lock or error.error_type in {"TimeoutError", "ConnectionError", "APIConnectionError", "APITimeoutError"} or any(
            marker in text for marker in transient_markers
        ):
            return RecoveryDecision("TRANSIENT", "RETRY", "检测到可重试的临时故障", [])

        domain_types = {
            "CandidateProposalError",
            "StrategyValidationProposalError",
            "CandidateIntentConformanceError",
            "CandidateBatchQualityError",
            "LuaError",
        }
        domain_markers = (
            "lua syntax error",
            "lua runtime error",
            "cmo lua assertion",
            "strategyspec parameter",
            "策略参数非法",
            "no_effective_change",
        )
        if error.error_type in domain_types or any(
            marker in text for marker in domain_markers
        ):
            return RecoveryDecision("DOMAIN", "DOMAIN_REPAIR", "检测到领域执行或提案故障", [])

        code_types = {
            "AttributeError", "ImportError", "ModuleNotFoundError", "SyntaxError",
            "TypeError", "KeyError", "AssertionError", "NameError",
        }
        code_markers = (
            "traceback",
            "state-machine",
            "state machine",
            "schema compatibility",
            "api response schema",
            "path bug",
        )
        if error.error_type in code_types or any(marker in text for marker in code_markers):
            return RecoveryDecision("CODE", "CODE_REPAIR", "检测到 Python 系统代码故障", [])
        return None


class RepairContextBuilder:
    """收集 CODE 修复所需的有限现场，避免把整个仓库无差别塞给模型。"""

    def __init__(self, *, project_root: Path, max_text_chars: int = 12_000) -> None:
        self._root = Path(project_root).resolve()
        self._max_text_chars = max_text_chars

    def build(
        self,
        *,
        original_task: object,
        training_state: object,
        envelope: ErrorEnvelope,
        last_good_commit: str | None,
    ) -> str:
        """把任务、状态、日志、相关源码和修复约束组织为结构化中文文本。"""

        sections = [
            ("原始任务", self._render(original_task)),
            ("Training 状态", self._render(training_state)),
            ("ErrorEnvelope", self._render(envelope.to_dict())),
            ("Traceback", envelope.traceback or "无"),
            ("runner.log 摘要", self._read_tail(self._runner_log(envelope.workflow_id))),
            ("相关日志摘要", self._related_logs(envelope)),
            ("相关源码", self._related_source(envelope.related_files)),
            ("Git 基线", self._git_summary(last_good_commit)),
            (
                "已知恢复经验",
                self._read_tail(self._root / "data" / "recovery" / "known-issues.md"),
            ),
            (
                "修复约束",
                "只做最小修改；不改变评分或场景语义；不删除 Artifact；保持现有接口兼容；"
                "不要创建提交，验证通过后由 Harness 负责提交。",
            ),
        ]
        return "\n\n".join(f"## {title}\n{body}" for title, body in sections)

    def _runner_log(self, workflow_id: str) -> Path:
        return self._root / "runs" / "training" / workflow_id / "runner.log"

    def _related_logs(self, envelope: ErrorEnvelope) -> str:
        paths = [envelope.stdout_path, envelope.stderr_path]
        rendered = [self._read_tail(Path(path)) for path in paths if path]
        return "\n\n".join(rendered) if rendered else "无"

    def _related_source(self, paths: Iterable[str]) -> str:
        rendered: list[str] = []
        for relative in paths:
            path = (self._root / relative).resolve()
            try:
                path.relative_to(self._root)
            except ValueError:
                continue
            if path.is_file():
                rendered.append(f"### {Path(relative).as_posix()}\n{self._read_tail(path)}")
        return "\n\n".join(rendered) if rendered else "无"

    def _git_summary(self, last_good_commit: str | None) -> str:
        head = "未知"
        try:
            completed = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self._root,
                text=True,
                capture_output=True,
                check=True,
            )
            head = completed.stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            pass
        return f"HEAD: {head}\nlast_good_commit: {last_good_commit or '无'}"

    def _read_tail(self, path: Path) -> str:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return "无"
        return text[-self._max_text_chars :]

    @staticmethod
    def _render(value: object) -> str:
        try:
            return json.dumps(value, ensure_ascii=False, indent=2, default=str)
        except (TypeError, ValueError):
            return str(value)


class VerificationGate:
    """在业务重放前检查源码格式、针对性测试和受影响包回归。

    本类不再调用 TrainingRunner 的 action；Campaign reconcile/replay 必须由上层在门禁
    成功后单独执行，避免一次验证意外重放整代或重复启动 CMO。
    """

    def __init__(
        self,
        *,
        project_root: Path,
        command_runner: Callable[[tuple[str, ...]], bool] | None = None,
    ) -> None:
        self._root = Path(project_root).resolve()
        self._command_runner = command_runner or self._run_command

    def verify(
        self,
        *,
        changed_paths: Iterable[Path],
        targeted_test_argv: tuple[str, ...] | None = None,
        targeted_test_command: str | None = None,
    ) -> tuple[bool, tuple[str, ...]]:
        """三类门禁全过才成功；字符串参数仅为历史调用兼容入口。"""

        details: list[str] = []
        targeted = targeted_test_argv
        if targeted is None:
            if not targeted_test_command:
                raise ValueError("targeted_test_argv_required")
            # 旧调用点的测试命令均为固定 Python argv，不接受 shell 控制符。
            targeted = tuple(targeted_test_command.split())
        commands = [
            (("git", "diff", "--check", "--", "src", "scripts", "tests"), "git diff --check"),
            (targeted, "针对性测试"),
            (self._regression_command(changed_paths), "受影响包回归测试"),
        ]
        for command, label in commands:
            if not self._command_runner(command):
                details.append(f"{label}失败")
                return False, tuple(details)
            details.append(f"{label}通过")
        return True, tuple(details)

    def _regression_command(self, changed_paths: Iterable[Path]) -> tuple[str, ...]:
        test_roots: set[str] = set()
        prefix = ("src", "cmo_lua_agent")
        for path in changed_paths:
            parts = Path(path).parts
            if len(parts) < 3 or parts[:2] != prefix:
                continue
            package = parts[2]
            test_root = Path("src") / "cmo_lua_agent" / "tests" / package
            if (self._root / test_root).is_dir():
                test_roots.add(test_root.as_posix())
        targets = sorted(test_roots)
        if not targets:
            targets = ["src/cmo_lua_agent/tests"]
            if (self._root / "tests").is_dir():
                targets.append("tests")
        return ("python", "-m", "pytest", *targets, "-q")

    def _run_command(self, command: tuple[str, ...]) -> bool:
        completed = subprocess.run(
            list(command),
            cwd=self._root,
            text=True,
            capture_output=True,
        )
        return completed.returncode == 0


def _optional_path(value: str | Path | None) -> str | None:
    return None if value is None else str(Path(value))


def append_recovery_report(
    path: Path,
    *,
    envelope: ErrorEnvelope,
    decision: RecoveryDecision,
    attempt: int,
    result: str,
    details: str = "",
) -> None:
    """把一次恢复追加到单一连续报告，不创建额外 Incident 状态文件。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    heading = "# Recovery report\n" if not path.is_file() else ""
    block = "\n".join(
        (
            heading,
            f"## Incident {attempt}: {envelope.stage}/{envelope.task}",
            "",
            f"- Error: `{envelope.error_type}` — {envelope.message}",
            f"- Route: {decision.category} → {decision.action}",
            f"- Reason: {decision.reason}",
            f"- Result: {result}",
            f"- Relevant files: {', '.join(decision.relevant_files) or 'none'}",
            "",
            details.strip(),
            "",
        )
    )
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(block)


def make_unknown_diagnoser(json_client: object) -> Callable[[ErrorEnvelope], RecoveryDecision]:
    """把现有 JSON LLM 客户端收窄为一次 UNKNOWN 恢复分类调用。"""

    def diagnose(envelope: ErrorEnvelope) -> RecoveryDecision:
        complete = getattr(json_client, "complete_json")
        value = complete(
            system=(
                "你是 Training RecoveryRouter 的未知错误分类器。只输出一个 JSON 对象，"
                "字段必须是 category、action、reason、relevant_files；"
                "category 只能是 TRANSIENT、DOMAIN、CODE、UNKNOWN，action 只能是 "
                "RETRY、DOMAIN_REPAIR、CODE_REPAIR、STOP。不要输出 Markdown。"
            ),
            prompt=(
                "根据以下客观事故现场选择最保守且可执行的恢复动作。"
                "不要臆测不存在的文件或改变训练业务语义。\n\n"
                + json.dumps(envelope.to_dict(), ensure_ascii=False, indent=2)
            ),
        )
        if not isinstance(value, dict):
            raise ValueError("unknown_diagnosis_json_object_required")
        category = value.get("category")
        action = value.get("action")
        reason = value.get("reason")
        relevant_files = value.get("relevant_files")
        if category not in _ALLOWED_CATEGORIES or action not in _ALLOWED_ACTIONS:
            raise ValueError("unknown_diagnosis_enum_invalid")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("unknown_diagnosis_reason_required")
        if not isinstance(relevant_files, list) or not all(
            isinstance(path, str) for path in relevant_files
        ):
            raise ValueError("unknown_diagnosis_relevant_files_invalid")
        return RecoveryDecision(category, action, reason.strip(), list(relevant_files))

    return diagnose


def establish_training_baseline(
    *,
    project_root: Path,
    workflow_id: str,
    git_executor: Callable[[tuple[str, ...]], str] | None = None,
) -> str:
    """仅提交 src/scripts/tests 的训练前改动并推送，返回可恢复的 Git 基线 SHA。"""

    root = Path(project_root).resolve()

    def execute(command: tuple[str, ...]) -> str:
        if git_executor is not None:
            return git_executor(command)
        completed = subprocess.run(
            list(command),
            cwd=root,
            text=True,
            capture_output=True,
            check=True,
        )
        return completed.stdout

    status = execute(("git", "status", "--porcelain", "--", "src", "scripts", "tests"))
    if status.strip():
        execute(("git", "add", "--", "src", "scripts", "tests"))
        execute(
            (
                "git",
                "commit",
                "--only",
                "-m",
                f"chore(training): baseline {workflow_id}",
                "--",
                "src",
                "scripts",
                "tests",
            )
        )
    commit = execute(("git", "rev-parse", "HEAD")).strip()
    if not commit:
        raise RuntimeError("training_baseline_commit_missing")
    execute(("git", "push"))
    return commit


def append_known_issue(
    *,
    project_root: Path,
    envelope: ErrorEnvelope,
    decision: RecoveryDecision,
    root_cause: str,
    changed_files: Iterable[str | Path],
    verification: Iterable[str],
    commit_id: str,
) -> None:
    """幂等追加一次已完整验证并推送的轻量恢复经验。"""

    path = Path(project_root).resolve() / "data" / "recovery" / "known-issues.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.is_file() else "# Recovery Harness 已知问题\n"
    marker = f"{envelope.error_type}: {envelope.message}"
    if marker in existing:
        return
    block = "\n".join(
        (
            "",
            f"## {marker}",
            "",
            f"- 症状：{envelope.stage}/{envelope.task}，{envelope.message}",
            f"- 根因摘要：{root_cause}",
            f"- 恢复动作：{decision.action}（{decision.reason}）",
            "- 修改文件：" + (", ".join(Path(path).as_posix() for path in changed_files) or "none"),
            "- 验证方式：" + ("；".join(verification) or "未记录"),
            f"- Commit：`{commit_id}`",
            "",
        )
    )
    path.write_text(existing.rstrip() + "\n" + block, encoding="utf-8", newline="\n")
