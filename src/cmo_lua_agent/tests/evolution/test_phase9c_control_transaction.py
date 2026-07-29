from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from cmo_lua_agent.evolution.campaign_store import CampaignStore
from cmo_lua_agent.evolution.control_plane import EvolutionCampaignService
from cmo_lua_agent.evolution.models import CampaignState
from cmo_lua_agent.evolution.production_models import GenerationApprovalGrant


def _grant(*, maximum: int = 2) -> GenerationApprovalGrant:
    now = datetime.now(UTC)
    return GenerationApprovalGrant.issue(
        campaign_id="campaign_fixture",
        generation_index=0,
        preview_revision=0,
        snapshot_checksum="snapshot",
        candidate_set_checksum="candidates",
        baseline_checksum="baseline",
        contract_checksum="contract",
        budget_revision=0,
        approved_operation_ids=(
            "g000:cmo:baseline:a00",
            "g000:cmo:candidate_00:a00",
        ),
        maximum_cmo_attempts=maximum,
        actor="tester",
        hostname="host",
        process_id=123,
        approved_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=5)).isoformat(),
        receipt_checksum="receipt",
    )


def test_attempt_authorization_and_start_are_transactionally_accounted(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "campaign")
    store.save_campaign_state(CampaignState(campaign_id="campaign_fixture"))
    grant = _grant()
    store.initialize_control_state(max_cmo_runs=5, budget_revision=0)
    store.persist_generation_approval(grant)

    store.authorize_attempt_slot(
        approval_id=grant.approval_id,
        operation_id="g000:cmo:baseline:a00",
        expected_contract_checksum="contract",
        expected_snapshot_checksum="snapshot",
        expected_candidate_set_checksum="candidates",
    )
    authorized = store.load_control_state()
    assert authorized["attempt_slots"]["g000:cmo:baseline:a00"]["status"] == "authorized"
    assert authorized["budget"]["cmo_runs_started"] == 0

    store.mark_attempt_started("g000:cmo:baseline:a00")
    started = store.load_control_state()
    assert started["attempt_slots"]["g000:cmo:baseline:a00"]["status"] == "started"
    assert started["budget"]["cmo_runs_started"] == 1
    assert started["approval_usage"][grant.approval_id]["started_attempts"] == 1
    assert store.load_campaign_state().cmo_run_count == 1


def test_concurrent_duplicate_authorization_cannot_consume_slot_twice(tmp_path: Path) -> None:
    store_a = CampaignStore(tmp_path / "campaign")
    store_b = CampaignStore(tmp_path / "campaign")
    store_a.save_campaign_state(CampaignState(campaign_id="campaign_fixture"))
    grant = _grant(maximum=1)
    store_a.initialize_control_state(max_cmo_runs=1, budget_revision=0)
    store_a.persist_generation_approval(grant)
    kwargs = {
        "approval_id": grant.approval_id,
        "operation_id": "g000:cmo:baseline:a00",
        "expected_contract_checksum": "contract",
        "expected_snapshot_checksum": "snapshot",
        "expected_candidate_set_checksum": "candidates",
    }

    store_a.authorize_attempt_slot(**kwargs)
    with pytest.raises(ValueError, match="attempt_slot_not_available"):
        store_b.authorize_attempt_slot(**kwargs)


def test_resume_abandons_authorized_slot_but_never_replays_started_unknown(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "campaign")
    store.save_campaign_state(CampaignState(campaign_id="campaign_fixture"))
    grant = _grant()
    store.initialize_control_state(max_cmo_runs=5, budget_revision=0)
    store.persist_generation_approval(grant)
    for operation_id in grant.approved_operation_ids:
        store.authorize_attempt_slot(
            approval_id=grant.approval_id,
            operation_id=operation_id,
            expected_contract_checksum="contract",
            expected_snapshot_checksum="snapshot",
            expected_candidate_set_checksum="candidates",
        )
    store.mark_attempt_started("g000:cmo:candidate_00:a00")
    store.mark_attempt_unknown("g000:cmo:candidate_00:a00", reason="worker_lost")

    result = store.reconcile_control_state_for_resume()

    state = store.load_control_state()
    assert state["attempt_slots"]["g000:cmo:baseline:a00"]["status"] == "available"
    assert state["attempt_slots"]["g000:cmo:candidate_00:a00"]["status"] == "unknown"
    assert result["reconciliation_required"] == ["g000:cmo:candidate_00:a00"]
    assert not state["approvals"][grant.approval_id]["valid"]


def test_default_generation_approval_has_only_one_initial_slot_per_frozen_strategy() -> None:
    assert EvolutionCampaignService._attempt_slot_ids(0) == (
        "g000:cmo:baseline:a00",
        "g000:cmo:candidate_00:a00",
        "g000:cmo:candidate_01:a00",
        "g000:cmo:candidate_02:a00",
        "g000:cmo:candidate_03:a00",
    )
