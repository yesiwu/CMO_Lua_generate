"""
结构化解析 CmoBatchRunner 输出的 runner.log 进度日志
作用：把原始文本日志，转换成结构化、可供上层实时消费的进度事件
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Iterable

# 匹配行首时间戳，用于剥离日志前缀 [2026-08-13 12:00:00]
_TIMESTAMP_RE = re.compile(r"^\[[^\]]+\]\s*")
# 匹配：[1/10] 加载想定并执行：辽宁舰对抗
_SCENARIO_START_RE = re.compile(
    r"^\[(?P<index>\d+)/(?P<total>\d+)\]\s+加载想定并执行：(?P<name>.+)$"
)
# 匹配单场想定结束结果行，捕获成功/失败、状态、原因、耗时、错误信息
_SCENARIO_RESULT_RE = re.compile(
    r"^\[(?P<index>\d+)/(?P<total>\d+)\]\s+"
    r"(?P<outcome>成功|失败)，状态=(?P<state>[^，]+)，"
    r"原因=(?P<reason>[^，]+)，现实耗时=(?P<elapsed>[\d.]+)秒"
    r"(?:，错误=(?P<error>.*))?$"
)
# 匹配仿真实时脉冲进度：仿真时间 xxxx，现实耗时 xx 秒，脉冲 xxx
_SIMULATION_RE = re.compile(
    r"^仿真时间\s+(?P<time>.+?)，现实耗时\s+(?P<elapsed>[\d.]+)\s+秒，"
    r"脉冲\s+(?P<pulse>\d+)$"
)
# 匹配批次最终汇总统计：执行结束：成功 x，失败 x
_SUMMARY_RE = re.compile(r"^执行结束：成功\s+(?P<success>\d+)，失败\s+(?P<failure>\d+)。?$")
# 匹配批次输出目录路径
_RESULT_DIR_RE = re.compile(r"^批次目录：(?P<path>.+)$")


@dataclass(frozen=True)
class CmoProgressMessage:
    """
    领域统一进度消息结构体
    与终端原始文本解耦，上层（前端/监控/调度器）统一消费该对象，不用解析原始日志
    """
    # 事件类型：batch_started / scenario_started / simulation_progress / scenario_completed ...
    kind: str
    # 运行状态：running / success / failed
    status: str
    # 对外展示简短消息
    message: str
    # 可选：附加详情文本
    detail: str | None = None
    # 全局批次进度 [0~1]
    progress: float | None = None
    # 当前想定序号
    scenario_index: int | None = None
    # 本批次总想定数量
    scenario_total: int | None = None
    # 当前想定名称
    scenario_name: str | None = None
    # CMO内部仿真时间（游戏时间）
    simulation_time: str | None = None
    # 现实世界耗时（秒）
    real_elapsed_seconds: float | None = None
    # CMO仿真脉冲号
    pulse: int | None = None
    # 批次成功总数
    success_count: int | None = None
    # 批次失败总数
    failure_count: int | None = None
    # 错误文本
    error_message: str | None = None
    # 本轮批次结果文件夹路径
    result_dir: str | None = None
    # 预留扩展元数据，存放零散自定义字段
    metadata: dict[str, Any] = field(default_factory=dict)


class CmoProgressParser:
    """
    增量日志解析器
    特点：支持逐行持续喂日志、自动去重、只产出有效进度事件，不重复推送相同日志
    """

    def __init__(self) -> None:
        # 存放已经处理过的日志行，避免重复解析、重复推送事件
        self._seen_lines: set[str] = set()
        # 记录 {想定序号: 想定名称}，想定结束时回填名称
        self._scenario_names: dict[int, str] = {}

    def feed(self, lines: Iterable[str]) -> list[CmoProgressMessage]:
        """
        批量喂入若干日志行，返回本轮新增解析出来的进度事件列表
        :param lines: 一批原始日志文本行
        :return: 解析得到的结构化进度消息数组
        """
        events: list[CmoProgressMessage] = []
        for raw_line in lines:
            # 清洗：去除首尾空白、清除UTF-8 BOM标记
            normalized = raw_line.strip().lstrip("\ufeff")
            # 剥离行首时间戳前缀
            line = _TIMESTAMP_RE.sub("", normalized).strip()
            # 空行 或者 已经解析过的行直接跳过，防止重复推送
            if not line or line in self._seen_lines:
                continue
            # 尝试解析单行日志
            event = self._parse_line(line)
            if event is None:
                continue
            # 标记该行已处理
            self._seen_lines.add(line)
            events.append(event)
        return events

    def _parse_line(self, line: str) -> CmoProgressMessage | None:
        """
        内部单行解析核心逻辑，匹配不同日志模板生成对应进度事件
        无法匹配任意规则返回 None
        """
        # 批次整体启动
        if line == "CMO 批量推演与战斗采集启动。":
            return CmoProgressMessage(
                kind="batch_started",
                status="running",
                message="CMO 批次已启动",
            )

        # 匹配【单个想定开始执行】
        match = _SCENARIO_START_RE.match(line)
        if match:
            index = int(match.group("index"))
            total = int(match.group("total"))
            name = match.group("name").strip()
            # 缓存序号-名称映射，后面想定结束时使用
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

        # 场景仿真分辨率参数加载日志
        if line.startswith("Scenario.GameResolution="):
            return CmoProgressMessage(
                kind="scenario_config",
                status="running",
                message="场景运行参数已加载",
                detail=line,
            )

        # Lua对象初始化日志
        if line.startswith("Lua后对象："):
            return CmoProgressMessage(
                kind="lua_objects",
                status="running",
                message="Lua 对象已创建",
                detail=line.removeprefix("Lua后对象："),
            )

        # 匹配【仿真脉冲实时进度】，持续刷新当前推演进度
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

        # 匹配【单个想定执行结束（成功/失败）】
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
                # 区分成功/失败两种事件类型，上层方便分别处理
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

        # 匹配【整批次全部推演完成，汇总统计结果】
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

        # 匹配批次输出目录
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

        # 当前行不匹配任何预定义日志模板，返回空，丢弃该行
        return None