from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event

import pytest

from cmo_lua_agent.evolution.control_plane import (
    ApprovalMode,
    CampaignPermissionBroker,
    CampaignPermissionReceipt,
    EvolutionCampaignService,
    GenerationExecutionResult,
    GenerationPreviewPayload,
)
from cmo_lua_agent.evolution.campaign_store import CampaignStore
from cmo_lua_agent.evolution.models import OperationKind, OperationStatus
from cmo_lua_agent.evolution.models import (
    CampaignBudget,
    CampaignExecutionMode,
    CampaignStatus,
    EvolutionCampaignSpec,
)


def _spec() -> EvolutionCampaignSpec:
    return EvolutionCampaignSpec(
        campaign_id="control_fixture",
        scenario_id="six_v_four",
        scenario_ref="scenario.json",
        scenario_checksum="scenario",
        initial_strategy_ref="strategy.json",
        runtime_contract_checksum="runtime",
        renderer_contract_checksum="renderer",
        score_contract_checksum="score",
        semantic_contract_checksum="semantic",
        code_revision="revision",
        allowed_strategy_paths=("/attacks/0/fire_quantity",),
        generation_objective="improve",
        execution_mode=CampaignExecutionMode.FAKE_FIXTURE,
        budget=CampaignBudget(2, 10, 1, 1, 0, 4, 20, 20, 0, 0, 0, 0, 3600, 1200, 600),
    )


@dataclass
class _PreviewBuilder:
    calls: int = 0

    def build(self, *, spec: EvolutionCampaignSpec, generation_index: int, preview_revision: int) -> GenerationPreviewPayload:
        self.calls += 1
        return GenerationPreviewPayload(
            knowledge_snapshot_checksum=f"snapshot-{preview_revision}",
            candidate_set_checksum=f"candidates-{preview_revision}",
            strategy_diffs=({"candidate_id": "candidate_00", "changed_paths": ["/attacks/0/fire_quantity"]},),
            proposal_llm_calls=1,
        )


class _Executor:
    def __init__(self) -> None:
        self.calls = 0
        self.started = Event()
        self.release = Event()

    def run(self, context) -> GenerationExecutionResult:
        self.calls += 1
        self.started.set()
        self.release.wait(timeout=2)
        if context.control_action() == "stop":
            return GenerationExecutionResult.cancelled_incomplete("manual_stop_requested")
        if context.control_action() == "pause":
            return GenerationExecutionResult.paused("manual_pause_requested")
        return GenerationExecutionResult.completed({"leaderboard": "leaderboard.json"})


def _service(tmp_path: Path, *, synchronous: bool = True) -> tuple[EvolutionCampaignService, _PreviewBuilder, _Executor]:
    preview, executor = _PreviewBuilder(), _Executor()
    return (
        EvolutionCampaignService(
            campaigns_root=tmp_path / "runs" / "evolution",
            preview_builder=preview,
            generation_executor=executor,
            synchronous_fake_workers=synchronous,
        ),
        preview,
        executor,
    )


def test_preview_is_idempotent_and_regeneration_invalidates_approval(tmp_path: Path) -> None:
    service, preview_builder, _ = _service(tmp_path)
    service.prepare_campaign(_spec())

    first = service.preview_generation(campaign_id="control_fixture", generation_index=0)
    same = service.preview_generation(campaign_id="control_fixture", generation_index=0)
    assert first.preview_revision == same.preview_revision == 0
    assert preview_builder.calls == 1

    approval = service.authorize_generation(
        campaign_id="control_fixture", generation_index=0,
        receipt=CampaignPermissionReceipt.trusted_for_tests("execute_evolution_generation"),
    )
    regenerated = service.preview_generation(campaign_id="control_fixture", generation_index=0, regenerate_preview=True)

    assert regenerated.preview_revision == 1
    assert preview_builder.calls == 2
    assert not service.is_approval_valid(approval.approval_id)


def test_execute_is_async_and_concurrent_execute_reuses_operation(tmp_path: Path) -> None:
    service, _, executor = _service(tmp_path, synchronous=False)
    service.prepare_campaign(_spec())
    service.preview_generation(campaign_id="control_fixture", generation_index=0)
    receipt = CampaignPermissionReceipt.trusted_for_tests("execute_evolution_generation")
    service.authorize_generation(campaign_id="control_fixture", generation_index=0, receipt=receipt)

    first = service.execute_generation(campaign_id="control_fixture", generation_index=0)
    assert executor.started.wait(timeout=1)
    second = service.execute_generation(campaign_id="control_fixture", generation_index=0)
    assert first.operation_id == second.operation_id
    assert executor.calls == 1
    executor.release.set()
    service.wait_for_worker(first.operation_id, timeout_seconds=2)
    assert service.inspect_campaign("control_fixture")["status"] == CampaignStatus.RUNNING.value


def test_pause_invalidates_approval_and_resume_never_executes(tmp_path: Path) -> None:
    service, _, executor = _service(tmp_path, synchronous=False)
    service.prepare_campaign(_spec())
    service.preview_generation(campaign_id="control_fixture", generation_index=0)
    approval = service.authorize_generation(
        campaign_id="control_fixture", generation_index=0,
        receipt=CampaignPermissionReceipt.trusted_for_tests("execute_evolution_generation"),
    )
    operation = service.execute_generation(campaign_id="control_fixture", generation_index=0)
    assert executor.started.wait(timeout=1)
    service.pause_campaign("control_fixture")
    executor.release.set()
    service.wait_for_worker(operation.operation_id, timeout_seconds=2)
    assert service.inspect_campaign("control_fixture")["status"] == CampaignStatus.PAUSED.value
    assert not service.is_approval_valid(approval.approval_id)
    service.resume_campaign("control_fixture")
    assert executor.calls == 1
    assert service.inspect_campaign("control_fixture")["status"] == "awaiting_approval"


def test_stop_marks_incomplete_generation_without_follow_on_stages(tmp_path: Path) -> None:
    service, _, executor = _service(tmp_path, synchronous=False)
    service.prepare_campaign(_spec())
    service.preview_generation(campaign_id="control_fixture", generation_index=0)
    service.authorize_generation(
        campaign_id="control_fixture", generation_index=0,
        receipt=CampaignPermissionReceipt.trusted_for_tests("execute_evolution_generation"),
    )
    operation = service.execute_generation(campaign_id="control_fixture", generation_index=0)
    assert executor.started.wait(timeout=1)
    service.stop_campaign("control_fixture")
    executor.release.set()
    service.wait_for_worker(operation.operation_id, timeout_seconds=2)
    generation = service.inspect_generation("control_fixture", 0)
    assert generation["status"] == "cancelled_incomplete"
    assert "leaderboard" not in generation["result"]


def test_execution_requires_permission_receipt_and_valid_preview(tmp_path: Path) -> None:
    service, _, _ = _service(tmp_path)
    service.prepare_campaign(_spec())
    service.preview_generation(campaign_id="control_fixture", generation_index=0)
    with pytest.raises(ValueError, match="trusted_permission_receipt_required"):
        service.authorize_generation(campaign_id="control_fixture", generation_index=0, receipt=None)
    with pytest.raises(ValueError, match="generation_approval_required"):
        service.execute_generation(campaign_id="control_fixture", generation_index=0)


def test_each_cmo_attempt_is_authorized_and_generation_cap_covers_repair_reruns(tmp_path: Path) -> None:
    service, _, executor = _service(tmp_path, synchronous=False)
    service.prepare_campaign(_spec())
    service.preview_generation(campaign_id="control_fixture", generation_index=0)
    approval = service.authorize_generation(
        campaign_id="control_fixture",
        generation_index=0,
        receipt=CampaignPermissionReceipt.trusted_for_tests("execute_evolution_generation"),
        authorization_mode=ApprovalMode.GENERATION_CAP,
        max_cmo_attempts=1,
    )
    worker = service.execute_generation(campaign_id="control_fixture", generation_index=0)
    assert executor.started.wait(timeout=1)
    root = tmp_path / "runs" / "evolution" / "control_fixture"
    store = CampaignStore(root)
    broker = CampaignPermissionBroker(store=store, spec=_spec(), generation_index=0, worker_operation_id=worker.operation_id)

    attempt = broker.authorize_cmo_attempt(attempt_input_checksum="first-attempt")
    assert store.get_operation(attempt).status is OperationStatus.AUTHORIZED
    broker.mark_cmo_started(attempt)
    assert store.load_campaign_state().cmo_run_count == 1
    with pytest.raises(ValueError, match="generation_approval_cap_exhausted"):
        broker.authorize_cmo_attempt(attempt_input_checksum="repair-rerun")
    executor.release.set()
    service.wait_for_worker(worker.operation_id, timeout_seconds=2)


def test_resume_marks_started_operation_for_reconciliation_without_replaying_worker(tmp_path: Path) -> None:
    service, _, executor = _service(tmp_path)
    service.prepare_campaign(_spec())
    store = CampaignStore(tmp_path / "runs" / "evolution" / "control_fixture")
    operation = store.prepare_operation(generation_index=0, kind=OperationKind.CMO, input_checksum="cmo-input")
    store.mark_operation_unknown(operation.operation_id, "worker_process_lost")

    summary = service.resume_campaign("control_fixture")
    assert summary["reconciliation_required_operations"] == [operation.operation_id]
    assert executor.calls == 0
