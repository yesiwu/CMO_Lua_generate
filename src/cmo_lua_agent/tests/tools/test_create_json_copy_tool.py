from __future__ import annotations

import json
from pathlib import Path

from cmo_lua_agent.tools.create_json_copy_tool import CreateJsonCopyTool


def _payload(result: object) -> dict[str, object]:
    return json.loads(result.content)  # type: ignore[attr-defined]


def test_create_json_copy_changes_only_requested_json_pointers(
    tmp_path: Path,
) -> None:
    source = tmp_path / "scenario.json"
    source.write_text(
        json.dumps(
            {
                "units": [{"weapon": "YJ-18"}],
                "missileSummary": {"YJ-18": {"count": 2}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = CreateJsonCopyTool(workdir=tmp_path).execute(
        {
            "path": "scenario_fixed.json",
            "source_path": "scenario.json",
            "patches": [
                {
                    "path": "/units/0/weapon",
                    "value": "YJ-18 [3M54E Klub Copy]",
                }
            ],
        }
    )

    copied = json.loads((tmp_path / "scenario_fixed.json").read_text(encoding="utf-8"))
    assert result.is_error is False
    assert json.loads(source.read_text(encoding="utf-8"))["units"][0]["weapon"] == "YJ-18"
    assert copied["units"][0]["weapon"] == "YJ-18 [3M54E Klub Copy]"
    assert copied["missileSummary"] == {"YJ-18": {"count": 2}}
    assert _payload(result)["mode"] == "copy_with_json_patches"


def test_create_json_copy_rejects_missing_pointer_and_never_overwrites(
    tmp_path: Path,
) -> None:
    source = tmp_path / "scenario.json"
    source.write_text('{"units": []}', encoding="utf-8")
    target = tmp_path / "scenario_fixed.json"
    target.write_text('{"existing": true}', encoding="utf-8")
    tool = CreateJsonCopyTool(workdir=tmp_path)

    for arguments in (
        {
            "path": "scenario_fixed.json",
            "source_path": "scenario.json",
            "patches": [{"path": "/units/0/weapon", "value": "YJ-18"}],
        },
        {
            "path": "new.json",
            "source_path": "scenario.json",
            "patches": [{"path": "units/0/weapon", "value": "YJ-18"}],
        },
    ):
        result = tool.execute(arguments)
        assert result.is_error is True

    assert target.read_text(encoding="utf-8") == '{"existing": true}'
    assert not (tmp_path / "new.json").exists()
