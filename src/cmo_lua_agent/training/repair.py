"""Training Runtime 的受控 Python 源码自动修复事务。

TrainingRunner 只在 RecoveryRouter 选择 CODE_REPAIR 后调用本模块。CodeRepairAgent 负责
调查和修改 ``src/scripts/tests``；本协调器负责持久化快照、外部验证、失败 action 重放、
Git commit/push 和失败收口。Lua/CMO 业务修复仍由 Campaign 既有链路负责。
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
from typing import Any, Callable
from uuid import uuid4
import zipfile

from cmo_lua_agent.agents.code_repair_agent import RepairAgentResult, RepairAgentStatus
from cmo_lua_agent.agents.system_repair_agent import SystemRepairAgent
from cmo_lua_agent.training.failures import FailureKind, FailureRecord
from cmo_lua_agent.training.recovery import ErrorEnvelope, VerificationGate


_REPAIR_ROOTS = (Path("src"), Path("scripts"), Path("tests"))
_IGNORED_REPAIR_PARTS = frozenset({"__pycache__", ".pytest_cache"})
ProgressCallback = Callable[[str, dict[str, object]], None]


class RepairSnapshot:
    """把一次修复前的三目录文件保存为可跨进程恢复的单一快照。

    Coordinator 在启动 Agent 前创建快照；TrainingRunner 重启时只需读取 state 中的
    ``snapshot_path`` 即可恢复，不需要恢复模型对话。快照明确不覆盖 data/runs，因此
    CMO 与训练 Artifact 永远不会被回滚或删除。
    """

    def __init__(self, *, project_root: Path, archive_path: Path) -> None:
        self._root = Path(project_root).resolve()
        self.path = Path(archive_path)
        if not self.path.is_absolute():
            self.path = self._root / self.path
        self.path = self.path.resolve(strict=False)
        workflow_root = (self._root / "runs" / "training").resolve(strict=False)
        if not self.path.is_relative_to(workflow_root):
            raise ValueError("repair_snapshot_must_be_in_training_workflow")

    def create(self) -> Path:
        """原子写入 zip；只有完整关闭的临时包才会替换正式快照。"""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for relative, source in _repair_scope_files(self._root).items():
                    archive.write(source, relative.as_posix())
            os.replace(temporary, self.path)
        finally:
            if temporary.exists():
                temporary.unlink()
        return self.path

    def restore(self) -> None:
        """恢复原文件并删除修复新增文件；操作范围始终限制在三目录。"""

        if not self.path.is_file():
            raise FileNotFoundError(f"repair snapshot missing: {self.path}")
        with zipfile.ZipFile(self.path, "r") as archive:
            members: dict[Path, bytes] = {}
            for name in archive.namelist():
                relative = Path(name)
                if not _is_allowed_repair_relative(relative):
                    raise ValueError(f"invalid repair snapshot member: {name}")
                members[relative] = archive.read(name)
        current = _repair_scope_files(self._root)
        for relative in sorted(set(current) - set(members), reverse=True):
            current[relative].unlink()
        for relative, content in members.items():
            target = self._root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(f".{target.name}.{uuid4().hex}.restore.tmp")
            try:
                temporary.write_bytes(content)
                os.replace(temporary, target)
            finally:
                if temporary.exists():
                    temporary.unlink()

    def discard(self) -> None:
        """仅在修复成功或已经安全恢复后移除临时恢复边界。"""

        if self.path.is_file():
            self.path.unlink()


@dataclass(frozen=True, slots=True)
class RepairResult:
    succeeded: bool
    summary: str
    report_path: Path
    commit_id: str | None = None
    push_failed: bool = False
    changed_files: tuple[str, ...] = ()
    verification: tuple[str, ...] = ()
    snapshot_path: Path | None = None
    commit_failed_after_replay: bool = False
    agent_result: RepairAgentResult | None = None


class CodeRepairCoordinator:
    """将自适应修复 Agent 包在可恢复、可验证的源码修改事务中。"""

    def __init__(
        self,
        *,
        project_root: Path,
        system_repair_agent: object | None = None,
        repair_command: Callable[[str], str] | None = None,
        test_runner: Callable[[str], bool] | None = None,
        verification_gate: VerificationGate | None = None,
        push_runner: Callable[[], bool] | None = None,
    ) -> None:
        self._root = Path(project_root).resolve()
        self._agent = system_repair_agent
        if self._agent is None and repair_command is not None:
            self._agent = SystemRepairAgent(project_root=self._root, backend=repair_command)
        self._verification_gate = verification_gate or VerificationGate(
            project_root=self._root,
            command_runner=(
                (lambda command: test_runner(subprocess.list2cmdline(command)))
                if test_runner is not None
                else None
            ),
        )
        self._push_runner = push_runner or self._push

    def repair(
        self,
        *,
        workflow_id: str,
        record: FailureRecord,
        test_command: str,
        envelope: ErrorEnvelope | None = None,
        repair_context: str | None = None,
        replay_task: Callable[[], object] | None = None,
        attempt: int = 1,
        progress_callback: ProgressCallback | None = None,
    ) -> RepairResult:
        """执行一次可跨进程恢复的代码修复事务。

        Agent、门禁或 replay 失败时恢复 snapshot。replay 已成功后若 commit 失败，则保留
        已验证源码和业务 Artifact 并停止，由人工完成 Git 收口，避免新 Artifact 配合旧源码。
        """

        report_path = self._root / "runs" / "training" / workflow_id / "recovery-report.md"
        snapshot = RepairSnapshot(
            project_root=self._root,
            archive_path=report_path.parent / "repair-snapshot.zip",
        )
        if record.kind is not FailureKind.CODE:
            return self._write_report(report_path, False, "已跳过修复：故障不属于代码错误。")
        if self._agent is None:
            return self._write_report(report_path, False, "没有配置 CodeRepairAgent。")
        prompt = repair_context or (
            "修复这个 Python 训练系统错误。只进行最小且正确的源码与回归测试修改。"
            f"错误类型：{record.error_type}\n错误详情：{record.message}\n"
            f"必须执行的验证：{test_command}\n最后输出简短的修改日志。"
        )
        before = self._snapshot_repair_scope()
        dirty_paths = self._dirty_paths()
        snapshot.create()
        self._notify(
            progress_callback,
            "REPAIRING",
            snapshot_path=snapshot.path.relative_to(self._root).as_posix(),
            attempt=attempt,
        )
        try:
            agent_result = self._run_agent(prompt, workflow_id=workflow_id, attempt=attempt)
        except Exception as exc:
            return self._restore_and_report(
                snapshot,
                report_path,
                f"修复 Agent 异常：{type(exc).__name__}: {exc}",
                progress_callback,
                "agent_exception",
            )
        if agent_result.status is not RepairAgentStatus.COMPLETED:
            return self._restore_and_report(
                snapshot,
                report_path,
                agent_result.summary,
                progress_callback,
                agent_result.stop_reason,
                agent_result=agent_result,
            )

        changed_paths = self._changed_paths(before)
        self._notify(progress_callback, "VERIFYING", attempt=attempt)
        verified, verification_details = self._verification_gate.verify(
            changed_paths=changed_paths,
            targeted_test_command=test_command,
        )
        if not verified:
            return self._restore_and_report(
                snapshot,
                report_path,
                "修复验证失败，源码已恢复。\n\n" + "\n".join(verification_details),
                progress_callback,
                "verification_failed",
                agent_result=agent_result,
                verification=verification_details,
            )
        changed_paths = self._changed_paths(before)
        if any(path in dirty_paths for path in changed_paths):
            return self._restore_and_report(
                snapshot,
                report_path,
                "修复触及训练前已修改文件，源码已恢复。",
                progress_callback,
                "dirty_path_touched",
                agent_result=agent_result,
                verification=verification_details,
            )

        try:
            (replay_task or (lambda: None))()
        except Exception as exc:
            details = (*verification_details, f"失败 action 对账/重放失败：{type(exc).__name__}: {exc}")
            return self._restore_and_report(
                snapshot,
                report_path,
                "失败 action 对账/重放失败，源码已恢复。",
                progress_callback,
                "replay_failed",
                agent_result=agent_result,
                verification=details,
            )
        verification_details = (*verification_details, "失败 action 对账/重放通过")

        try:
            commit_id = self._commit_repair(workflow_id, changed_paths)
        except Exception as exc:
            # replay 可能已产生业务 Artifact，不能再恢复旧源码造成二者不一致。
            self._notify(progress_callback, "FAILED", stop_reason="commit_failed_after_replay")
            return self._write_report(
                report_path,
                False,
                f"重放成功后 Git commit 失败；保留已验证源码和 Artifact：{type(exc).__name__}: {exc}",
                changed_files=tuple(path.as_posix() for path in changed_paths),
                verification=tuple(verification_details),
                snapshot_path=snapshot.path,
                commit_failed_after_replay=True,
                agent_result=agent_result,
            )

        self._notify(
            progress_callback,
            "COMMITTED",
            commit_id=commit_id,
            push_completed=False,
        )
        changed_files = tuple(path.as_posix() for path in changed_paths)
        detail = (
            f"{agent_result.summary}\n\n修改文件：{', '.join(changed_files) or '无'}\n"
            f"验证：{'; '.join(verification_details)}\nGit commit：{commit_id or '无需提交'}"
        )
        if commit_id is not None and not self._push_runner():
            self._notify(progress_callback, "FAILED", stop_reason="push_failed", commit_id=commit_id)
            return self._write_report(
                report_path,
                False,
                f"{detail}\n\nGit push 失败；保留已验证本地 commit。",
                commit_id=commit_id,
                push_failed=True,
                changed_files=changed_files,
                verification=tuple(verification_details),
                snapshot_path=snapshot.path,
                agent_result=agent_result,
            )
        self._notify(
            progress_callback,
            "COMMITTED",
            commit_id=commit_id,
            push_completed=True,
        )
        snapshot.discard()
        return self._write_report(
            report_path,
            True,
            f"{detail}\nGit push：{'完成' if commit_id is not None else '无需推送'}",
            commit_id=commit_id,
            changed_files=changed_files,
            verification=tuple(verification_details),
            agent_result=agent_result,
        )

    def resume_committed(self, *, workflow_id: str, commit_id: str) -> RepairResult:
        """进程在本地 commit 后退出时，只补做幂等 push，不重新运行 Agent 或测试。"""

        report_path = self._root / "runs" / "training" / workflow_id / "recovery-report.md"
        head = self._run_git("rev-parse", "HEAD").strip()
        if head != commit_id:
            return self._write_report(
                report_path,
                False,
                f"无法继续推送：HEAD {head} 与已记录 commit {commit_id} 不一致。",
                commit_id=commit_id,
            )
        if not self._push_runner():
            return self._write_report(
                report_path,
                False,
                "恢复本地已验证 commit 的 push 失败。",
                commit_id=commit_id,
                push_failed=True,
            )
        return self._write_report(
            report_path,
            True,
            "已恢复并推送本地验证 commit。",
            commit_id=commit_id,
        )

    def _run_agent(self, prompt: str, *, workflow_id: str, attempt: int) -> RepairAgentResult:
        detailed = getattr(self._agent, "repair_with_result", None)
        if callable(detailed):
            result = detailed(prompt, workflow_id=workflow_id, attempt=attempt)
            if not isinstance(result, RepairAgentResult):
                raise TypeError("repair_with_result_must_return_RepairAgentResult")
            return result
        summary = self._agent.repair(prompt)
        return RepairAgentResult(
            RepairAgentStatus.COMPLETED,
            str(summary),
            (),
            (),
            "legacy_repair_completed",
        )

    def _restore_and_report(
        self,
        snapshot: RepairSnapshot,
        report_path: Path,
        body: str,
        callback: ProgressCallback | None,
        stop_reason: str,
        *,
        agent_result: RepairAgentResult | None = None,
        verification: tuple[str, ...] = (),
    ) -> RepairResult:
        try:
            snapshot.restore()
            snapshot.discard()
        except Exception as exc:
            body += f"\n\n快照恢复失败：{type(exc).__name__}: {exc}"
            stop_reason = "snapshot_restore_failed"
        self._notify(callback, "FAILED", stop_reason=stop_reason)
        return self._write_report(
            report_path,
            False,
            body,
            verification=tuple(verification),
            snapshot_path=snapshot.path if snapshot.path.exists() else None,
            agent_result=agent_result,
        )

    @staticmethod
    def _notify(callback: ProgressCallback | None, status: str, **metadata: object) -> None:
        if callback is not None:
            callback(status, dict(metadata))

    def _write_report(
        self,
        path: Path,
        succeeded: bool,
        body: str,
        *,
        commit_id: str | None = None,
        push_failed: bool = False,
        changed_files: tuple[str, ...] = (),
        verification: tuple[str, ...] = (),
        snapshot_path: Path | None = None,
        commit_failed_after_replay: bool = False,
        agent_result: RepairAgentResult | None = None,
    ) -> RepairResult:
        """追加连续恢复报告，并返回 Runner 更新状态所需的结构化结果。"""

        path.parent.mkdir(parents=True, exist_ok=True)
        heading = "# Recovery report\n\n" if not path.is_file() else ""
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(
                f"{heading}## Code repair\n\n- Status: {'completed' if succeeded else 'failed'}\n\n{body}\n\n"
            )
        return RepairResult(
            succeeded,
            body,
            path,
            commit_id,
            push_failed,
            changed_files,
            verification,
            snapshot_path,
            commit_failed_after_replay,
            agent_result,
        )

    def _snapshot_repair_scope(self) -> dict[Path, bytes]:
        return {relative: path.read_bytes() for relative, path in _repair_scope_files(self._root).items()}

    def _changed_paths(self, before: dict[Path, bytes]) -> tuple[Path, ...]:
        current = self._snapshot_repair_scope()
        return tuple(
            path
            for path in sorted(set(before) | set(current))
            if before.get(path) != current.get(path)
        )

    def _dirty_paths(self) -> set[Path]:
        """记录修复前已有改动，防止 Agent 把用户工作混入自动 commit。"""

        output = self._run_git("status", "--porcelain", "--", "src", "scripts", "tests")
        paths: set[Path] = set()
        for line in output.splitlines():
            if len(line) >= 4:
                paths.add(Path(line[3:].replace("\\", "/")))
        return paths

    def _commit_repair(self, workflow_id: str, paths: tuple[Path, ...]) -> str | None:
        """仅提交本次三目录修复路径；Agent 本身无法调用此函数。"""

        if not paths:
            return None
        relative_paths = [path.as_posix() for path in paths]
        # 新增回归测试尚未被 Git 跟踪，必须先显式暂存本次 changed_paths；范围不会扩散。
        self._run_git("add", "--", *relative_paths)
        self._run_git("commit", "--only", "-m", f"fix(training): repair {workflow_id}", "--", *relative_paths)
        return self._run_git("rev-parse", "HEAD").strip()

    def _run_git(self, *arguments: str) -> str:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=self._root,
            text=True,
            capture_output=True,
            check=True,
            shell=False,
        )
        return completed.stdout

    def _push(self) -> bool:
        try:
            self._run_git("push")
        except (OSError, subprocess.CalledProcessError):
            return False
        return True


def _repair_scope_files(root: Path) -> dict[Path, Path]:
    """列出可修复普通文件，不跟随符号链接或收集 Python/pytest 缓存。"""

    files: dict[Path, Path] = {}
    for relative_root in _REPAIR_ROOTS:
        source_root = root / relative_root
        if not source_root.is_dir() or source_root.is_symlink():
            continue
        for directory, names, filenames in os.walk(source_root, followlinks=False):
            current = Path(directory)
            names[:] = [
                name
                for name in names
                if name not in _IGNORED_REPAIR_PARTS and not (current / name).is_symlink()
            ]
            for filename in filenames:
                path = current / filename
                if path.is_symlink() or path.suffix in {".pyc", ".pyo"}:
                    continue
                files[path.relative_to(root)] = path
    return files


def _is_allowed_repair_relative(path: Path) -> bool:
    if path.is_absolute() or ".." in path.parts or not path.parts:
        return False
    return Path(path.parts[0]) in _REPAIR_ROOTS
