"""CMOLua MCP query wrapper public API contract tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_query_wrapper() -> ModuleType:
    project_root = Path(__file__).resolve().parents[5]
    query_path = project_root / "CMOLua-main" / "mcp" / "query.py"
    specification = importlib.util.spec_from_file_location(
        "_query_wrapper_under_test",
        query_path,
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_read_query_forwards_parameterized_query_options() -> None:
    module = _load_query_wrapper()
    calls: list[tuple[str, dict[str, object]]] = []

    class FakeSession:
        def call(
            self,
            tool_name: str,
            arguments: dict[str, object],
        ) -> list[dict[str, object]]:
            calls.append((tool_name, arguments))
            return []

    module._get_session = lambda: FakeSession()

    result = module.read_query(
        "SELECT * FROM DataWeapon WHERE ID = ?",
        [2137],
        fetch_all=False,
        row_limit=2,
    )

    assert result == []
    assert calls == [
        (
            "read_query",
            {
                "sql": "SELECT * FROM DataWeapon WHERE ID = ?",
                "params": [2137],
                "fetch_all": False,
                "row_limit": 2,
            },
        )
    ]
