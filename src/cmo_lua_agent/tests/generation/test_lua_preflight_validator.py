from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from cmo_lua_agent.contract import (
    ResolvedScenarioManifest,
    ScenarioContract,
)
from cmo_lua_agent.generation import LuaPreflightValidator


def _manifest() -> ResolvedScenarioManifest:
    return ResolvedScenarioManifest(
        data={
            "manifestVersion": "resolved-scenario-manifest-v1",
            "scenario": {
                "id": "demo",
                "name": "Demo",
            },
            "sides": {
                "red": {
                    "name": "红方",
                    "unitCount": 2,
                    "units": [
                        {
                            "id": "red_ship",
                            "name": "Red Ship",
                            "dbid": 100,
                            "type": "ship",
                            "latitude": 20.0,
                            "longitude": 120.0,
                            "heading": 90,
                            "speed": 20,
                            "databaseName": "Red DB Ship",
                            "platformCategory": "ship",
                        },
                        {
                            "id": "red_aircraft",
                            "name": "Red Aircraft",
                            "dbid": 200,
                            "type": "aircraft",
                            "base": "red_ship",
                            "positionMode": "inherit_base",
                            "loadoutId": 900,
                            "databaseName": "Red DB Aircraft",
                            "platformCategory": "aircraft",
                            "loadoutDatabaseName": "Strike Loadout",
                        },
                    ],
                },
                "blue": {
                    "name": "蓝方",
                    "unitCount": 1,
                    "units": [
                        {
                            "id": "blue_target",
                            "name": "Blue Target",
                            "dbid": 300,
                            "type": "ship",
                            "latitude": 21.0,
                            "longitude": 121.0,
                            "heading": 270,
                            "speed": 18,
                            "databaseName": "Blue DB Ship",
                            "platformCategory": "ship",
                        }
                    ],
                },
            },
            "strikePlan": [
                {
                    "id": "strike-1",
                    "shooters": [
                        "red_ship",
                        "red_aircraft",
                    ],
                    "weapon": "Weapon-A",
                    "weaponDbid": 500,
                    "loaded": 8,
                    "fired": 4,
                    "targets": ["blue_target"],
                }
            ],
        }
    )


def _contract() -> ScenarioContract:
    return ScenarioContract(
        scenario_id="demo",
        unit_ids=(
            "red_ship",
            "red_aircraft",
            "blue_target",
        ),
        unit_names=(
            "Red Ship",
            "Red Aircraft",
            "Blue Target",
        ),
        shooter_ids=(
            "red_ship",
            "red_aircraft",
        ),
        target_ids=("blue_target",),
    )


def _valid_lua() -> str:
    return r'''
local function main()
    local ok, err = pcall(function()
        ScenEdit_AddSide({side="红方"})
        ScenEdit_AddSide({side="蓝方"})

        ScenEdit_AddUnit({
            type="ship",
            side="红方",
            name="Red Ship",
            dbid=100,
            latitude=20.0,
            longitude=120.0
        })

        ScenEdit_AddUnit({
            type="aircraft",
            side="红方",
            name="Red Aircraft",
            dbid=200,
            loadoutid=900
        })

        ScenEdit_AddUnit({
            type="ship",
            side="蓝方",
            name="Blue Target",
            dbid=300,
            latitude=21.0,
            longitude=121.0
        })
    end)
end

local function clear()
end

local function reload()
end

main()
'''


def _generator_style_lua() -> str:
    """Representative output from CMOLua-main: top-level script plus pcall."""
    return r'''
local RED = "红方"
local BLUE = "蓝方"
local MANIFEST_SHIPS = {
    {name="Red Ship", dbid=100, latitude=20.0, longitude=120.0},
    {name="Blue Target", dbid=300, latitude=21.0, longitude=121.0},
}
local MANIFEST_AIRCRAFT = {
    {name="Red Aircraft", dbid=200, loadoutid=900},
}

do
    pcall(ScenEdit_AddSide, {name=RED})
    pcall(ScenEdit_AddSide, {name=BLUE})
    for _, unit in ipairs(MANIFEST_SHIPS) do
        pcall(ScenEdit_AddUnit, unit)
    end
    for _, unit in ipairs(MANIFEST_AIRCRAFT) do
        pcall(ScenEdit_AddUnit, unit)
    end
end
'''


def _validate(
    tmp_path: Path,
    lua_text: str,
    *,
    warnings: tuple[str, ...] = (),
    output_path: Path | None = None,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir(exist_ok=True)
    output = (
        output_path
        if output_path is not None
        else workspace / "runs/run-1/generation/original.lua"
    )

    return LuaPreflightValidator().validate(
        lua_text,
        manifest=_manifest(),
        contract=_contract(),
        output_path=output,
        workspace_root=workspace,
        generator_warnings=warnings,
    )


def test_valid_lua_passes_without_findings(tmp_path: Path) -> None:
    report = _validate(tmp_path, _valid_lua())

    assert report.valid is True
    assert report.issues == ()


def test_blank_lua_is_blocked(tmp_path: Path) -> None:
    report = _validate(tmp_path, " \n ")

    assert report.valid is False
    assert report.errors[0].code == "preflight.empty_lua"


@pytest.mark.parametrize(
    ("removed", "expected_code"),
    [
        (
            'ScenEdit_AddSide({side="红方"})',
            "preflight.missing_add_side",
        ),
        (
            "ScenEdit_AddUnit({",
            "preflight.missing_add_unit",
        ),
    ],
)
def test_missing_required_structure_is_blocked(
    tmp_path: Path,
    removed: str,
    expected_code: str,
) -> None:
    lua_text = _valid_lua().replace(removed, "", 1)

    report = _validate(tmp_path, lua_text)

    assert expected_code in {
        issue.code
        for issue in report.errors
    }


def test_generator_style_top_level_pcall_and_manifest_loops_pass(
    tmp_path: Path,
) -> None:
    report = _validate(tmp_path, _generator_style_lua())

    assert report.valid is True
    assert report.errors == ()


@pytest.mark.parametrize(
    "api_call",
    [
        'DumpAmmo("Red Ship")',
        'remove_weapon("Red Ship", 500)',
        'REMOVE_WEAPON("Red Ship", 500)',
    ],
)
def test_forbidden_api_call_is_blocked(
    tmp_path: Path,
    api_call: str,
) -> None:
    lua_text = _valid_lua().replace(
        "main()",
        f"{api_call}\nmain()",
    )

    report = _validate(tmp_path, lua_text)

    assert report.valid is False
    assert any(
        issue.code == "preflight.forbidden_api"
        for issue in report.errors
    )


def test_forbidden_api_words_in_comments_and_strings_are_ignored(
    tmp_path: Path,
) -> None:
    lua_text = _valid_lua().replace(
        "main()",
        '-- DumpAmmo("not a call")\n'
        'local message = "remove_weapon(not a call)"\n'
        "main()",
    )

    report = _validate(tmp_path, lua_text)

    assert not any(
        issue.code == "preflight.forbidden_api"
        for issue in report.issues
    )


def test_missing_manifest_unit_name_is_blocked(tmp_path: Path) -> None:
    lua_text = _valid_lua().replace(
        'name="Blue Target"',
        'name="Blue Typo"',
    )

    report = _validate(tmp_path, lua_text)

    assert any(
        issue.code == "preflight.unit_name_missing"
        and "Blue Target" in issue.message
        for issue in report.errors
    )


def test_unit_dbid_mismatch_is_blocked(tmp_path: Path) -> None:
    lua_text = _valid_lua().replace(
        'name="Red Ship",\n            dbid=100',
        'name="Red Ship",\n            dbid=999',
    )

    report = _validate(tmp_path, lua_text)

    issue = next(
        item
        for item in report.errors
        if item.code == "preflight.unit_dbid_mismatch"
    )
    assert "100" in issue.message
    assert "999" in issue.message


def test_loadout_mismatch_is_blocked(tmp_path: Path) -> None:
    lua_text = _valid_lua().replace(
        "loadoutid=900",
        "loadoutid=901",
    )

    report = _validate(tmp_path, lua_text)

    issue = next(
        item
        for item in report.errors
        if item.code == "preflight.loadout_mismatch"
    )
    assert "900" in issue.message
    assert "901" in issue.message


def test_output_outside_workspace_is_blocked(tmp_path: Path) -> None:
    outside = tmp_path / "outside/original.lua"

    report = _validate(
        tmp_path,
        _valid_lua(),
        output_path=outside,
    )

    assert any(
        issue.code == "preflight.output_outside_workspace"
        for issue in report.errors
    )


def test_existing_output_is_blocked(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    output = workspace / "runs/run-1/generation/original.lua"
    output.parent.mkdir(parents=True)
    output.write_text("existing", encoding="utf-8")

    report = _validate(
        tmp_path,
        _valid_lua(),
        output_path=output,
    )

    assert any(
        issue.code == "preflight.output_exists"
        for issue in report.errors
    )


def test_non_lua_output_suffix_is_blocked(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    output = workspace / "runs/run-1/generation/original.txt"

    report = _validate(
        tmp_path,
        _valid_lua(),
        output_path=output,
    )

    assert any(
        issue.code == "preflight.invalid_output_extension"
        for issue in report.errors
    )


@pytest.mark.parametrize(
    "warning",
    [
        "unknown target blue_target",
        "目标引用不存在",
        "invalid DBID 999",
        "Loadout does not belong to aircraft",
        "fired ammunition exceeds loaded",
        "非法经纬度坐标",
    ],
)
def test_critical_generator_warning_is_promoted_to_error(
    tmp_path: Path,
    warning: str,
) -> None:
    report = _validate(
        tmp_path,
        _valid_lua(),
        warnings=(warning,),
    )

    assert any(
        issue.code
        == "preflight.generator_warning_blocking"
        and issue.severity.value == "error"
        for issue in report.errors
    )


def test_advisory_generator_warning_remains_warning(
    tmp_path: Path,
) -> None:
    report = _validate(
        tmp_path,
        _valid_lua(),
        warnings=("建议补充更详细的 Lua 注释",),
    )

    assert report.valid is True
    assert [
        issue.code
        for issue in report.warnings
    ] == ["preflight.generator_warning"]


def test_missing_pcall_clear_and_reload_are_warnings_only(
    tmp_path: Path,
) -> None:
    lua_text = _valid_lua()
    lua_text = lua_text.replace(
        "local ok, err = pcall(function()",
        "do",
    ).replace(
        "    end)\nend",
        "    end\nend",
        1,
    )
    lua_text = lua_text.replace(
        "local function clear()\nend\n\n",
        "",
    )
    lua_text = lua_text.replace(
        "local function reload()\nend\n\n",
        "",
    )

    report = _validate(tmp_path, lua_text)

    assert report.valid is True
    assert {
        issue.code
        for issue in report.warnings
    } == {
        "preflight.missing_pcall",
        "preflight.missing_clear",
        "preflight.missing_reload",
    }


def test_validator_does_not_mutate_manifest_or_contract(
    tmp_path: Path,
) -> None:
    manifest = _manifest()
    contract = _contract()
    manifest_before = deepcopy(manifest.to_dict())
    contract_before = deepcopy(contract.to_dict())
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    LuaPreflightValidator().validate(
        _valid_lua(),
        manifest=manifest,
        contract=contract,
        output_path=workspace / "original.lua",
        workspace_root=workspace,
    )

    assert manifest.to_dict() == manifest_before
    assert contract.to_dict() == contract_before


def test_validate_rejects_wrong_argument_types(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    validator = LuaPreflightValidator()

    with pytest.raises(TypeError, match="manifest"):
        validator.validate(
            _valid_lua(),
            manifest={},  # type: ignore[arg-type]
            contract=_contract(),
            output_path=workspace / "original.lua",
            workspace_root=workspace,
        )

    with pytest.raises(TypeError, match="contract"):
        validator.validate(
            _valid_lua(),
            manifest=_manifest(),
            contract={},  # type: ignore[arg-type]
            output_path=workspace / "original.lua",
            workspace_root=workspace,
        )
