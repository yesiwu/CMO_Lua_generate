"""Structured progress parsing for CmoBatchRunner runner.log files."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Iterable


_TIMESTAMP_RE = re.compile(r"^\[[^\]]+\]\s*")
_SCENARIO_START_RE = re.compile(
    r"^\[(?P<index>\d+)/(?P<total>\d+)\]\s+加载想定并执行：(?P<name>.+)$"
)
_SCENARIO_RESULT_RE = re.compile(
    r"^\[(?P<index>\d+)/(?P<total>\d+)\]\s+"
    r"(?P<outcome>成功|失败)，状态=(?P<state>[^，]+)，"
    r"原因=(?P<reason>[^，]+)，现实耗时=(?P<elapsed>[\d.]+)秒"
    r"(?:，错误=(?P<error>.*))?$"
)
_SIMULATION_RE = re.compile(
    r"^仿真时间\s+(?P<time>.+?)，现实耗时\s+(?P<elapsed>[\d.]+)\s+秒，"
    r"脉冲\s+(?P<pulse>\d+)$"
)
_SUMMARY_RE = re.compile(r"^执行结束：成功\s+(?P<success>\d+)，失败\s+(?P<failure>\d+)。?$")
_RESULT_DIR_RE = re.compile(r"^批次目录：(?P<path>.+)$")


@dataclass(frozen=True)
class CmoProgressMessage:
    """A domain-level progress update independent of terminal rendering."""

    kind: str
    status: str
    message: str
    detail: str | None = None
    progress: float | None = None
    scenario_index: int | None = None
    scenario_total: int | None = None
    scenario_name: str | None = None
    simulation_time: str | None = None
    real_elapsed_seconds: float | None = None
    pulse: int | None = None
    success_count: int | None = None
    failure_count: int | None = None
    error_message: str | None = None
    result_dir: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class CmoProgressParser:
    """Parse meaningful, non-duplicated updates from incremental log lines."""

    def __init__(self) -> None:
        self._seen_lines: set[str] = set()
        self._scenario_names: dict[int, str] = {}

    def feed(self, lines: Iterable[str]) -> list[CmoProgressMessage]:
        events: list[CmoProgressMessage] = []
        for raw_line in lines:
            normalized = raw_line.strip().lstrip("\ufeff")
            line = _TIMESTAMP_RE.sub("", normalized).strip()
            if not line or line in self._seen_lines:
                continue
            event = self._parse_line(line)
            if event is None:
                continue
            self._seen_lines.add(line)
            events.append(event)
        return events

    def _parse_line(self, line: str) -> CmoProgressMessage | None:
        if line == "CMO 批量推演与战斗采集启动。":
            return CmoProgressMessage(
                kind="batch_started",
                status="running",
                message="CMO 批次已启动",
            )

        match = _SCENARIO_START_RE.match(line)
        if match:
            index = int(match.group("index"))
            total = int(match.group("total"))
            name = match.group("name").strip()
            self._scenario_names[index] = name
            return CmoProgressMessage(
                kind="scenario_started",
                status="running",
                message=f"[{index}/{total}] 加载场景 {name}",
                progress=(index - 1) / total if total else None,
                scenario_index=index,
                scenario_total=total,
                scenario_name=name,
            )

        if line.startswith("Scenario.GameResolution="):
            return CmoProgressMessage(
                kind="scenario_config",
                status="running",
                message="场景运行参数已加载",
                detail=line,
            )

        if line.startswith("Lua后对象："):
            return CmoProgressMessage(
                kind="lua_objects",
                status="running",
                message="Lua 对象已创建",
                detail=line.removeprefix("Lua后对象："),
            )

        match = _SIMULATION_RE.match(line)
        if match:
            simulation_time = match.group("time")
            elapsed = float(match.group("elapsed"))
            pulse = int(match.group("pulse"))
            return CmoProgressMessage(
                kind="simulation_progress",
                status="running",
                message=f"仿真时间 {simulation_time}",
                detail=f"现实耗时 {elapsed:g} 秒 · 脉冲 {pulse}",
                simulation_time=simulation_time,
                real_elapsed_seconds=elapsed,
                pulse=pulse,
            )

        match = _SCENARIO_RESULT_RE.match(line)
        if match:
            index = int(match.group("index"))
            total = int(match.group("total"))
            elapsed = float(match.group("elapsed"))
            name = self._scenario_names.get(index)
            error = match.group("error")
            succeeded = match.group("outcome") == "成功"
            label = name or f"场景 {index}"
            detail = error or (
                f"原因={match.group('reason')} · 现实耗时 {elapsed:g} 秒"
            )
            return CmoProgressMessage(
                kind="scenario_completed" if succeeded else "scenario_failed",
                status="success" if succeeded else "failed",
                message=f"[{index}/{total}] {label} 执行{'成功' if succeeded else '失败'}",
                detail=detail,
                progress=index / total if total else None,
                scenario_index=index,
                scenario_total=total,
                scenario_name=name,
                real_elapsed_seconds=elapsed,
                error_message=error,
                metadata={
                    "state": match.group("state"),
                    "reason": match.group("reason"),
                },
            )

        match = _SUMMARY_RE.match(line)
        if match:
            success = int(match.group("success"))
            failure = int(match.group("failure"))
            return CmoProgressMessage(
                kind="batch_completed",
                status="success" if failure == 0 else "failed",
                message=f"批次完成：成功 {success}，失败 {failure}",
                success_count=success,
                failure_count=failure,
            )

        match = _RESULT_DIR_RE.match(line)
        if match:
            result_dir = match.group("path").strip()
            return CmoProgressMessage(
                kind="result_dir",
                status="success",
                message="CMO 结果目录已生成",
                detail=result_dir,
                result_dir=result_dir,
            )

        return None
