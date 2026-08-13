"""训练 Workflow 到达终态时写入的简洁确定性报告。

报告从已持久化请求、状态和事件日志重建，不依赖模型总结；这样即使后台进程重启，
最终交付给用户的训练、Phase 8 与代码修复记录仍可复核。
"""

from __future__ import annotations

import json

from cmo_lua_agent.training.models import TrainingState
from cmo_lua_agent.training.store import TrainingStore


class TrainingReportWriter:
    """从已持久化事实生成终态报告，不承担训练状态推进职责。"""

    def __init__(self, store: TrainingStore) -> None:
        self._store = store

    def write(self, state: TrainingState) -> None:
        """写入训练、Skill 聚合与缺省代码修复报告。

        经验 ID 从每代正式结果读取，而不是从内存缓存读取，保证后台进程重启后报告内容
        与 Campaign 产物一致。
        """
        request = self._store.load_request()
        events = self._events()
        self._write(
            "training-report.md",
            "\n".join((
                "# Training report",
                "",
                f"- Workflow: `{state.workflow_id}`",
                f"- Campaign: `{state.campaign_id or ''}`",
                f"- Status: {state.status.value}",
                f"- Objective: {request.objective}",
                f"- Input: `{request.input_path}`",
                f"- Completed generations: {', '.join(map(str, state.completed_generations)) or 'none'}",
                f"- Phase 8: {state.phase8.status.value}",
                "",
                "## Recorded events",
                *[f"- {event}" for event in events],
                "",
            )),
        )
        self._write(
            "skill-generation-report.md",
            "\n".join((
                "# Skill generation report",
                "",
                f"- Workflow: `{state.workflow_id}`",
                f"- Phase 8 status: {state.phase8.status.value}",
                f"- Phase 8 job: `{state.phase8.job_id or ''}`",
                "",
                "## Frozen experience IDs",
                *[f"- `{experience_id}`" for experience_id in self._experience_ids(state)],
                "",
            )),
        )

    def _events(self) -> list[str]:
        """按写入顺序读取事件日志，日志缺失时返回空列表以支持早期失败报告。"""
        journal = self._store.root / "journal.jsonl"
        if not journal.is_file():
            return []
        values: list[str] = []
        for line in journal.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            values.append(str(row.get("event", "unknown")))
        return values

    def _experience_ids(self, state: TrainingState) -> list[str]:
        """收集已完成代正式结果中的 Phase 7 经验 ID，不触发新的经验查询或聚合。"""
        if not state.campaign_id:
            return ["none"]
        project_root = self._store.root.parents[2]
        root = project_root / "runs" / "evolution" / state.campaign_id / "generations"
        experience_ids: set[str] = set()
        for generation_index in state.completed_generations:
            path = root / f"generation_{generation_index:03d}" / "generation-result.json"
            if not path.is_file():
                continue
            value = json.loads(path.read_text(encoding="utf-8"))
            phase7 = value.get("phase7", {})
            if isinstance(phase7, dict):
                experience_ids.update(str(item) for item in phase7.get("experience_ids", ()) if item)
        return sorted(experience_ids) or ["none"]

    def _write(self, name: str, content: str) -> None:
        """以统一 UTF-8 与换行格式写入报告文件。"""
        (self._store.root / name).write_text(content, encoding="utf-8", newline="\n")
