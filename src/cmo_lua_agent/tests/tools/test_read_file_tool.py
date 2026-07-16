from pathlib import Path

from cmo_lua_agent.tools.read_file_tool import ReadFileTool


def test_read_file_allows_paths_outside_workdir(tmp_path: Path) -> None:
    workdir = tmp_path / "project"
    workdir.mkdir()
    result_file = tmp_path / "Results" / "runner.log"
    result_file.parent.mkdir()
    result_file.write_text("batch output", encoding="utf-8")

    result = ReadFileTool(workdir=workdir).execute(
        {"path": str(result_file)}
    )

    assert result == "batch output"
