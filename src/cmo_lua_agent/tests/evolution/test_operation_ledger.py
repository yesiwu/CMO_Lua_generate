from __future__ import annotations

from pathlib import Path

from cmo_lua_agent.evolution.campaign_store import CampaignStore
from cmo_lua_agent.evolution.models import OperationKind, OperationStatus


def test_started_operation_is_reconciled_from_trusted_artifact_without_rerun(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "campaign")
    operation = store.prepare_operation(
        generation_index=0,
        kind=OperationKind.PHASE6,
        input_checksum="input-sha",
    )
    store.mark_operation_started(operation.operation_id)
    (store.root / "generations" / "generation_000").mkdir(parents=True)
    artifact = store.root / "generations" / "generation_000" / "phase6-ref.json"
    artifact.write_text('{"input_checksum":"input-sha","result_ref":"runs/example"}', encoding="utf-8")

    reconciled = store.reconcile_operation(operation.operation_id, artifact)

    assert reconciled.status is OperationStatus.COMPLETED
    assert reconciled.output_ref == str(artifact)
