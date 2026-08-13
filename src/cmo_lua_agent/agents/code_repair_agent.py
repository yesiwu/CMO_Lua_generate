"""使用现有 LLM 与 AgentLoop 完成受控 Python 代码修复。

``CodeRepairCoordinator`` 在建立可恢复快照后调用本 Agent。Agent 只负责观察代码、使用
专用工具修改 ``src/scripts/tests`` 并运行诊断；它不提交 Git、不推进 Workflow，也不把
内部测试当作最终验证。外层 VerificationGate 和 Campaign reconcile 才决定训练能否继续。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import subprocess
from typing import Callable

from cmo_lua_agent.orchestration.agent_loop import (
    AgentLoop,
    AgentLoopDeadlineExceeded,
    AgentLoopPolicy,
)
from cmo_lua_agent.orchestration.context_manager import ContextManager
from cmo_lua_agent.orchestration.events import AgentEvent
from cmo_lua_agent.tools.repair_tools import (
    RepairCommandRecord,
    RepairToolSession,
    build_repair_tool_registry,
)


class RepairAgentStatus(str, Enum):
    """Agent 工具循环的终止类型；不代表外部门禁或 Git 已成功。"""

    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True, slots=True)
class RepairAgentResult:
    """向 Harness 返回可判定结果，同时保留面向人的摘要。"""

    status: RepairAgentStatus
    summary: str
    modified_files: tuple[str, ...]
    tests_run: tuple[RepairCommandRecord, ...]
    stop_reason: str


_SYSTEM_PROMPT = """你是本项目的 CodeRepairAgent。你的任务是调查给定的 Python 系统错误并进行最小、可验证的修复。

必须遵守：
1. 先搜索和读取相关源码、调用方与测试，再修改。
2. 只能使用提供的六个工具；不得请求 Git、CMO、Campaign 或 Workflow 控制。
3. 只能修改 src、scripts、tests；不得删除 data、runs 或任何业务 Artifact。
4. edit_repair_file 要求旧文本唯一匹配，失败后必须重新读取，不能猜测。
5. 修改后运行针对性测试；测试失败时读取完整输出并继续修复。
6. 检查最终 diff，避免改变评分、场景和训练业务语义，保持兼容。
7. 最终用中文简要说明原因、修改文件和测试结果。
"""


class CodeRepairAgent:
    """把当前模型端点收窄为单 Agent、六工具的代码修复循环。"""

    def __init__(
        self,
        *,
        project_root: Path,
        llm_client: object,
        deadline_seconds: float = 1800,
        event_handler: Callable[[AgentEvent], None] | None = None,
        context_manager: ContextManager | None = None,
    ) -> None:
        self._root = Path(project_root).resolve()
        self._client = llm_client
        self._deadline_seconds = deadline_seconds
        self._event_handler = event_handler
        self._context_manager = context_manager or ContextManager(recent_message_count=12)

    def repair_with_result(
        self,
        context: str,
        *,
        workflow_id: str,
        attempt: int,
    ) -> RepairAgentResult:
        """运行一次无固定轮数的工具闭环；墙钟期限由 AgentLoopPolicy 执行。"""

        if not isinstance(context, str) or not context.strip():
            raise ValueError("code_repair_context_required")
        session = RepairToolSession(
            project_root=self._root,
            workflow_id=workflow_id,
            attempt=attempt,
        )
        registry = build_repair_tool_registry(
            project_root=self._root,
            workflow_id=workflow_id,
            attempt=attempt,
            session=session,
        )
        loop = AgentLoop(
            self._client,  # type: ignore[arg-type]
            registry,
            _SYSTEM_PROMPT,
            event_handler=self._event_handler,
            run_policy=AgentLoopPolicy.code_repair(
                deadline_seconds=self._deadline_seconds
            ),
            context_manager=self._context_manager,
        )
        try:
            summary = loop.run([{"role": "user", "content": context}]) or "模型未返回修复摘要。"
        except AgentLoopDeadlineExceeded as exc:
            return self._result(RepairAgentStatus.TIMED_OUT, str(exc), session, "deadline")
        except KeyboardInterrupt:
            return self._result(RepairAgentStatus.CANCELLED, "修复被取消。", session, "cancelled")
        except Exception as exc:
            return self._result(
                RepairAgentStatus.FAILED,
                f"修复 Agent 失败：{type(exc).__name__}: {exc}",
                session,
                "agent_error",
            )
        return self._result(RepairAgentStatus.COMPLETED, summary, session, "model_final")

    def repair(self, context: str) -> str:
        """兼容旧协调器的字符串接口；正式 Harness 使用 ``repair_with_result``。"""

        return self.repair_with_result(
            context,
            workflow_id="adhoc-code-repair",
            attempt=1,
        ).summary

    def _result(
        self,
        status: RepairAgentStatus,
        summary: str,
        session: RepairToolSession,
        stop_reason: str,
    ) -> RepairAgentResult:
        return RepairAgentResult(
            status=status,
            summary=summary,
            modified_files=self._modified_files(),
            tests_run=tuple(session.tests_run),
            stop_reason=stop_reason,
        )

    def _modified_files(self) -> tuple[str, ...]:
        """只读 Git 状态用于返回摘要；提交权限仍完全留在 Coordinator。"""

        completed = subprocess.run(
            ["git", "status", "--porcelain", "--", "src", "scripts", "tests"],
            cwd=self._root,
            text=True,
            capture_output=True,
            shell=False,
        )
        if completed.returncode != 0:
            return ()
        paths: list[str] = []
        for row in completed.stdout.splitlines():
            value = row[3:].strip() if len(row) >= 4 else ""
            if " -> " in value:
                value = value.split(" -> ", 1)[1]
            normalized = value.strip('"').replace("\\", "/")
            # pytest/compileall 会产生缓存，它们不是 Agent 的源码修改，不能进入提交判断。
            if normalized and "__pycache__" not in normalized and not normalized.endswith((".pyc", ".pyo")):
                paths.append(normalized)
        return tuple(sorted(dict.fromkeys(paths)))
