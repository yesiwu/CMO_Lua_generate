from __future__ import annotations

import json
from pathlib import Path

from cmo_lua_agent.integrations.cmolua.config import CmoLuaIntegrationConfig
from cmo_lua_agent.integrations.cmolua.skill_repository import CmoSkillRepository
from cmo_lua_agent.orchestration import (
    ScenarioWorkflowResult,
    WorkflowStage,
    WorkflowState,
    WorkflowStatus,
)
from cmo_lua_agent.tools.generate_cmo_lua_tool import GenerateCmoLuaTool
from cmo_lua_agent.tools.search_cmo_skill_tool import SearchCmoSkillTool
from cmo_lua_agent.tools.tool_base.context import ToolContext
from cmo_lua_agent.tools.tool_base.progress import ToolProgressReporter


def _repository(tmp_path: Path) -> CmoSkillRepository:
    skill_root = tmp_path / "CMOLua-main"
    (skill_root / "references").mkdir(parents=True)
    (skill_root / "mcp" / "db").mkdir(parents=True)
    (skill_root / "tools").mkdir()
    (skill_root / "SKILL.md").write_text("# Skill\n", encoding="utf-8")
    (skill_root / "references" / "api.md").write_text(
        "Use ScenEdit_AddUnit.\n",
        encoding="utf-8",
    )
    generator_path = skill_root / "tools" / "json_to_lua.py"
    generator_path.write_text("", encoding="utf-8")
    database_path = skill_root / "mcp" / "db" / "DB3K_504.db3"
    database_path.write_bytes(b"")
    outputs_dir = tmp_path / "outputs" / "lua"
    outputs_dir.mkdir(parents=True)
    return CmoSkillRepository(
        CmoLuaIntegrationConfig(
            skill_root=skill_root,
            generator_path=generator_path,
            database_path=database_path,
            outputs_dir=outputs_dir,
        )
    )


def _context(events: list) -> ToolContext:
    return ToolContext(
        tool_use_id="tool-1",
        tool_name="test",
        progress=ToolProgressReporter(
            tool_use_id="tool-1",
            tool_name="test",
            callback=events.append,
        ),
    )


def test_search_tool_uses_repository_and_reports_progress(tmp_path: Path) -> None:
    events = []
    tool = SearchCmoSkillTool(skill_repository=_repository(tmp_path))

    result = tool.execute({"query": "scenedit"}, context=_context(events))

    assert result.is_error is False
    payload = json.loads(result.content)
    assert payload["count"] == 1
    assert payload["hits"][0]["relative_path"] == "references/api.md"
    assert [(event.event_type, event.step_id) for event in events] == [
        ("tool_started", None),
        ("step_started", "search"),
        ("step_completed", "search"),
        ("tool_completed", None),
    ]


def test_search_tool_returns_error_result_for_invalid_area(tmp_path: Path) -> None:
    tool = SearchCmoSkillTool(skill_repository=_repository(tmp_path))

    result = tool.execute({"query": "api", "area": "database"})

    assert result.is_error is True
    assert json.loads(result.content)["error"]["code"] == (
        "invalid_skill_search_request"
    )


class FakeWorkflow:
    def __init__(self, result: ScenarioWorkflowResult) -> None:
        self.result = result
        self.calls: list[tuple[Path, Path, str | None]] = []

    def run(
        self,
        source_path: Path,
        *,
        runs_root: Path,
        run_id: str | None,
    ) -> ScenarioWorkflowResult:
        self.calls.append((source_path, runs_root, run_id))
        return self.result


def _completed_result(workdir: Path) -> ScenarioWorkflowResult:
    paths = {
        "run_root": str(workdir / "runs" / "run-1"),
        "original_lua": str(workdir / "runs" / "run-1" / "original.lua"),
        "workflow_result": str(workdir / "runs" / "run-1" / "result.json"),
        "resolved_manifest": str(workdir / "runs" / "run-1" / "manifest.json"),
    }
    state = WorkflowState(
        run_id="run-1",
        status=WorkflowStatus.COMPLETED,
        stage=WorkflowStage.COMPLETED,
        artifact_paths=paths,
    )
    return ScenarioWorkflowResult(
        success=True,
        state=state,
        failed_stage=None,
        validation=None,
        generation=None,
    )


def test_generate_tool_delegates_to_workflow_and_reports_progress(tmp_path: Path) -> None:
    source_path = tmp_path / "scenario.json"
    source_path.write_text("{}", encoding="utf-8")
    workflow = FakeWorkflow(_completed_result(tmp_path))
    events = []
    tool = GenerateCmoLuaTool(scenario_workflow=workflow, workdir=tmp_path)

    result = tool.execute(
        {"json_path": "scenario.json", "run_id": "demo"},
        context=_context(events),
    )

    assert result.is_error is False
    assert json.loads(result.content)["lua_path"].endswith("original.lua")
    assert workflow.calls == [(source_path, tmp_path / "runs", "demo")]
    assert [(event.event_type, event.step_id) for event in events] == [
        ("tool_started", None),
        ("step_started", "validate_input"),
        ("step_completed", "validate_input"),
        ("step_started", "scenario_workflow"),
        ("step_completed", "scenario_workflow"),
        ("tool_completed", None),
    ]


def test_generate_tool_rejects_source_outside_workspace(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside.json"
    outside.write_text("{}", encoding="utf-8")
    tool = GenerateCmoLuaTool(
        scenario_workflow=FakeWorkflow(_completed_result(tmp_path)),
        workdir=tmp_path,
    )

    result = tool.execute({"json_path": str(outside)})

    assert result.is_error is True
    assert json.loads(result.content)["error"]["code"] == (
        "invalid_generation_request"
    )
