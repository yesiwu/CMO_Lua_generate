from __future__ import annotations

from copy import deepcopy

from cmo_lua_agent.contract import IRBuilder, IRValidator, ScenarioIR
from cmo_lua_agent.tests.contract.test_ir_builder import (
    _normalized_payload,
)


def _issue_pairs(result) -> list[tuple[str, str]]:
    return [(issue.code, issue.path) for issue in result.issues]


def _valid_ir() -> ScenarioIR:
    return IRBuilder().build(_normalized_payload())


def test_valid_ir_passes() -> None:
    result = IRValidator().validate(_valid_ir())

    assert result.valid is True
    assert result.issues == ()


def test_validator_reports_missing_required_sections_in_stable_order() -> None:
    ir = ScenarioIR(data={})

    result = IRValidator().validate(ir)

    assert _issue_pairs(result) == [
        ("ir.missing_field", "$.irVersion"),
        ("ir.missing_field", "$.scenario"),
        ("ir.missing_field", "$.sides"),
        ("ir.missing_field", "$.unitById"),
        ("ir.missing_field", "$.strikePlan"),
    ]


def test_validator_detects_side_index_and_unit_identity_mismatch() -> None:
    data = _valid_ir().to_dict()
    data["sides"]["red"]["unitIds"].append("missing-unit")
    data["sides"]["red"]["unitCount"] = 3
    data["unitById"]["red-carrier"]["id"] = "other-id"
    data["unitById"]["red-aircraft"]["sideKey"] = "blue"

    result = IRValidator().validate(ScenarioIR(data=data))

    assert _issue_pairs(result) == [
        ("ir.unknown_unit_id", "$.sides.red.unitIds[2]"),
        ("ir.unit_id_mismatch", "$.unitById.red-carrier.id"),
        ("ir.unit_side_mismatch", "$.unitById.red-aircraft.sideKey"),
    ]


def test_validator_detects_unassigned_and_duplicate_side_membership() -> None:
    data = _valid_ir().to_dict()
    data["sides"]["red"]["unitIds"].append("blue-target")
    data["sides"]["red"]["unitCount"] = 3
    data["sides"]["blue"]["unitIds"].remove("blue-target")
    data["sides"]["blue"]["unitCount"] = 0

    result = IRValidator().validate(ScenarioIR(data=data))

    assert _issue_pairs(result) == [
        ("ir.unit_side_mismatch", "$.unitById.blue-target.sideKey"),
    ]

    data = _valid_ir().to_dict()
    data["sides"]["blue"]["unitIds"].clear()
    data["sides"]["blue"]["unitCount"] = 0

    result = IRValidator().validate(ScenarioIR(data=data))

    assert _issue_pairs(result) == [
        ("ir.unassigned_unit", "$.unitById.blue-target"),
    ]


def test_validator_rejects_singular_or_unknown_strike_references() -> None:
    data = _valid_ir().to_dict()
    strike = data["strikePlan"][0]
    strike["shooter"] = strike.pop("shooters")[0]
    strike["targets"] = ["missing-target"]

    result = IRValidator().validate(ScenarioIR(data=data))

    assert _issue_pairs(result) == [
        ("ir.singular_shooter_forbidden", "$.strikePlan[0].shooter"),
        ("ir.missing_shooters", "$.strikePlan[0].shooters"),
        ("ir.unknown_target", "$.strikePlan[0].targets[0]"),
    ]


def test_validator_checks_position_mode_invariants() -> None:
    data = _valid_ir().to_dict()
    inherited = data["unitById"]["red-aircraft"]
    inherited["latitude"] = 20.5
    fixed = data["unitById"]["blue-target"]
    del fixed["speed"]

    result = IRValidator().validate(ScenarioIR(data=data))

    assert _issue_pairs(result) == [
        ("ir.inherited_position_has_coordinates", "$.unitById.red-aircraft.latitude"),
        ("ir.missing_fixed_position", "$.unitById.blue-target.speed"),
    ]


def test_validator_does_not_mutate_ir() -> None:
    ir = _valid_ir()
    before = deepcopy(ir.to_dict())

    IRValidator().validate(ir)

    assert ir.to_dict() == before
