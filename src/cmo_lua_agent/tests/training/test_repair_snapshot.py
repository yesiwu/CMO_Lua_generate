from __future__ import annotations

from pathlib import Path

from cmo_lua_agent.training.repair import RepairSnapshot


def test_persistent_snapshot_restores_src_scripts_tests_without_touching_data(
    tmp_path: Path,
) -> None:
    originals = {
        "src/package/module.py": "SRC = 'before'\n",
        "scripts/launch.py": "SCRIPT = 'before'\n",
        "tests/test_module.py": "TEST = 'before'\n",
    }
    for relative, content in originals.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    data = tmp_path / "data" / "artifact.json"
    data.parent.mkdir(parents=True)
    data.write_text('{"result":"before"}', encoding="utf-8")
    archive = tmp_path / "runs" / "training" / "training-001" / "repair-snapshot.zip"
    snapshot = RepairSnapshot(project_root=tmp_path, archive_path=archive)

    snapshot.create()
    for relative in originals:
        (tmp_path / relative).write_text("BROKEN\n", encoding="utf-8")
    added = tmp_path / "tests" / "test_added.py"
    added.write_text("ADDED = True\n", encoding="utf-8")
    data.write_text('{"result":"must remain"}', encoding="utf-8")
    snapshot.restore()

    assert archive.is_file()
    assert {relative: (tmp_path / relative).read_text(encoding="utf-8") for relative in originals} == originals
    assert added.exists() is False
    assert data.read_text(encoding="utf-8") == '{"result":"must remain"}'


def test_snapshot_is_written_atomically_and_can_be_deleted_after_success(tmp_path: Path) -> None:
    source = tmp_path / "src" / "module.py"
    source.parent.mkdir(parents=True)
    source.write_text("VALUE = 1\n", encoding="utf-8")
    archive = tmp_path / "runs" / "training" / "training-001" / "repair-snapshot.zip"
    snapshot = RepairSnapshot(project_root=tmp_path, archive_path=archive)

    snapshot.create()

    assert archive.is_file()
    assert not archive.with_suffix(".zip.tmp").exists()
    snapshot.discard()
    assert archive.exists() is False
