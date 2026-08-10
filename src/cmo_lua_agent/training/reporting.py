"""Small deterministic reports written when a training workflow reaches a terminal state."""

from __future__ import annotations

import json

from cmo_lua_agent.training.models import TrainingState
from cmo_lua_agent.training.store import TrainingStore


class TrainingReportWriter:
    def __init__(self, store: TrainingStore) -> None:
        self._store = store

    def write(self, state: TrainingState) -> None:
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
        repair = self._store.root / "code-repair-report.md"
        if not repair.is_file():
            self._write(
                "code-repair-report.md",
                "# Code repair\n\n- Status: COMPLETED\n- No code repair was required for this workflow.\n",
            )

    def _events(self) -> list[str]:
        journal = self._store.root / "journal.jsonl"
        if not journal.is_file():
            return []
        values: list[str] = []
        for line in journal.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            values.append(str(row.get("event", "unknown")))
        return values

    def _experience_ids(self, state: TrainingState) -> list[str]:
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
        (self._store.root / name).write_text(content, encoding="utf-8", newline="\n")
