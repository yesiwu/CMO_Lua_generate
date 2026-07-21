"""Tool factory registration tests."""

from __future__ import annotations

from pathlib import Path

from cmo_lua_agent.bootstrap import (
    create_application,
    create_tool_services,
)
from cmo_lua_agent.hooks.manager import HookManager
from cmo_lua_agent.tools.generate_cmo_lua_tool import (
    GenerateCmoLuaTool,
)
from cmo_lua_agent.tools.list_directory_tool import ListDirectoryTool
from cmo_lua_agent.tools.edit_file_tool import EditFileTool
from cmo_lua_agent.tools.create_file_tool import CreateFileTool
from cmo_lua_agent.tools.create_json_copy_tool import CreateJsonCopyTool
from cmo_lua_agent.tools.query_cmo_database_tool import QueryCmoDatabaseTool
from cmo_lua_agent.tools.tool_base.factory import (
    build_tool_registry,
)


def _create_cmolua_dependency_tree(project_root: Path) -> None:
    skill_root = project_root / "CMOLua-main"
    generator_path = skill_root / "tools" / "json_to_lua.py"
    database_path = skill_root / "mcp" / "db" / "DB3K_504.db3"

    generator_path.parent.mkdir(parents=True)
    database_path.parent.mkdir(parents=True)
    (project_root / "outputs" / "lua").mkdir(parents=True)
    (skill_root / "SKILL.md").write_text("# CMOLua\n", encoding="utf-8")
    generator_path.write_text("", encoding="utf-8")
    database_path.write_bytes(b"")


def test_factory_registers_cmolua_tools_when_services_are_provided(
    tmp_path: Path,
) -> None:
    _create_cmolua_dependency_tree(tmp_path)
    application = create_application(tmp_path)

    registry = build_tool_registry(
        workdir=tmp_path,
        hook_manager=HookManager(),
        cmo_runner_path=tmp_path / "CmoBatchRunner.exe",
        cmo_config_path=tmp_path / "batch-config.json",
        cmo_lua_services=create_tool_services(application),
    )

    assert isinstance(registry.get("generate_cmo_lua"), GenerateCmoLuaTool)
    assert isinstance(registry.get("edit_file"), EditFileTool)
    assert isinstance(registry.get("create_file"), CreateFileTool)
    assert isinstance(registry.get("create_json_copy"), CreateJsonCopyTool)
    assert isinstance(registry.get("query_cmo_database"), QueryCmoDatabaseTool)
    assert isinstance(registry.get("list_directory"), ListDirectoryTool)
    assert registry.get("list_skills") is not None
    assert registry.get("load_skill") is not None
    assert registry.get("search_cmo_skill") is None
    assert registry.get("read_cmo_skill") is None
    definition_names = {
        definition["name"] for definition in registry.get_definitions()
    }
    assert {
        "list_skills",
        "load_skill",
        "generate_cmo_lua",
        "query_cmo_database",
        "edit_file",
        "create_file",
        "create_json_copy",
    } <= definition_names
    assert "search_cmo_skill" not in definition_names
    assert "read_cmo_skill" not in definition_names
