from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from cmo_lua_agent.integrations.cmolua.config import CmoLuaIntegrationConfig
from cmo_lua_agent.integrations.cmolua.generator_adapter import (
    CmoLuaGenerationError,
    CmoLuaGeneratorAdapter,
    CmoLuaGeneratorImportError,
)


def _config(tmp_path: Path, generator_source: str) -> CmoLuaIntegrationConfig:
    skill_root = tmp_path / "CMOLua-main"
    generator_path = skill_root / "tools" / "json_to_lua.py"
    database_path = skill_root / "mcp" / "db" / "DB3K_504.db3"
    outputs_dir = tmp_path / "outputs" / "lua"

    generator_path.parent.mkdir(parents=True)
    database_path.parent.mkdir(parents=True)
    outputs_dir.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text("# test skill\n", encoding="utf-8")
    generator_path.write_text(generator_source, encoding="utf-8")
    database_path.write_bytes(b"test database")

    return CmoLuaIntegrationConfig(
        skill_root=skill_root,
        generator_path=generator_path,
        database_path=database_path,
        outputs_dir=outputs_dir,
    )


def _manifest(tmp_path: Path) -> Path:
    manifest_path = tmp_path / "resolved_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {"scenario": {"name": "golden"}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return manifest_path


def test_generate_loads_external_function_and_returns_lua(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(
        tmp_path,
        """
import json
from pathlib import Path


def generate_cmo_lua(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return f"-- {data['scenario']['name']}\\nfunction main() end\\n"
""",
    )
    manifest_path = _manifest(tmp_path)
    unrelated_cwd = tmp_path / "other"
    unrelated_cwd.mkdir()
    monkeypatch.chdir(unrelated_cwd)
    original_sys_path = tuple(sys.path)

    result = CmoLuaGeneratorAdapter(config).generate(manifest_path)

    assert result.lua_text == "-- golden\nfunction main() end\n"
    assert result.warnings == ()
    assert tuple(sys.path) == original_sys_path


def test_adapter_loads_external_module_only_once(tmp_path: Path) -> None:
    marker_path = tmp_path / "import-count.txt"
    config = _config(
        tmp_path,
        f"""
from pathlib import Path

marker = Path({str(marker_path)!r})
previous = marker.read_text(encoding="utf-8") if marker.exists() else ""
marker.write_text(previous + "x", encoding="utf-8")


def generate_cmo_lua(path):
    return "function main() end"
""",
    )
    manifest_path = _manifest(tmp_path)
    adapter = CmoLuaGeneratorAdapter(config)

    adapter.generate(manifest_path)
    adapter.generate(manifest_path)

    assert marker_path.read_text(encoding="utf-8") == "x"


def test_generate_captures_warn_lines_without_printing_them(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = _config(
        tmp_path,
        """
import sys


def generate_cmo_lua(path):
    print("[warn] missing optional doctrine", file=sys.stderr)
    print("generator diagnostic", file=sys.stderr)
    return "function main() end"
""",
    )

    result = CmoLuaGeneratorAdapter(config).generate(_manifest(tmp_path))
    captured = capsys.readouterr()

    assert result.warnings == ("missing optional doctrine",)
    assert captured.out == ""
    assert captured.err == ""


def test_generate_rejects_missing_manifest_file(tmp_path: Path) -> None:
    config = _config(
        tmp_path,
        """
def generate_cmo_lua(path):
    return "function main() end"
""",
    )
    missing_path = tmp_path / "missing.json"

    with pytest.raises(CmoLuaGenerationError, match="Manifest 文件不存在"):
        CmoLuaGeneratorAdapter(config).generate(missing_path)


def test_generate_raises_import_error_when_function_is_missing(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path, "VALUE = 1\n")

    with pytest.raises(CmoLuaGeneratorImportError, match="generate_cmo_lua"):
        CmoLuaGeneratorAdapter(config).generate(_manifest(tmp_path))


def test_generate_raises_import_error_for_invalid_python(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path, "def broken(:\n")

    with pytest.raises(CmoLuaGeneratorImportError, match="无法导入"):
        CmoLuaGeneratorAdapter(config).generate(_manifest(tmp_path))


def test_generate_wraps_external_execution_error(tmp_path: Path) -> None:
    config = _config(
        tmp_path,
        """
def generate_cmo_lua(path):
    raise ValueError("bad scenario")
""",
    )

    with pytest.raises(CmoLuaGenerationError, match="bad scenario"):
        CmoLuaGeneratorAdapter(config).generate(_manifest(tmp_path))


@pytest.mark.parametrize(
    "return_statement",
    ["return None", "return ''", "return '   '", "return 123"],
)
def test_generate_rejects_invalid_return_value(
    tmp_path: Path,
    return_statement: str,
) -> None:
    config = _config(
        tmp_path,
        f"""
def generate_cmo_lua(path):
    {return_statement}
""",
    )

    with pytest.raises(CmoLuaGenerationError, match="非空字符串"):
        CmoLuaGeneratorAdapter(config).generate(_manifest(tmp_path))