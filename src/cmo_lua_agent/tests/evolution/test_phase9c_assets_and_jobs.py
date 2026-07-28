from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

from cmo_lua_agent.evolution.controlled_input_package import (
    ControlledCampaignInputPackageLoader,
)
from cmo_lua_agent.evolution.baseline_failure_profile import (
    BaselineFailureProfileBuilder,
)
from cmo_lua_agent.evolution.production_assets import (
    ControlledScenarioAssetRegistry,
    ScenarioAssetVerificationService,
)
from cmo_lua_agent.evolution.production_models import (
    AttemptSlot,
    GenerationApprovalUsage,
    ScenarioAssetVerificationRecord,
)
from cmo_lua_agent.evolution.authorized_candidate_runner import (
    CampaignAuthorizedCandidateRunner,
)
from cmo_lua_agent.execution.dynamic_batch_job import DynamicBatchJobBuilder


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def test_verified_asset_is_copied_per_attempt_and_job_uses_current_lua(tmp_path: Path) -> None:
    scenario = tmp_path / "assets" / "fixture.scen"
    scenario.parent.mkdir()
    scenario.write_bytes(b"clean-scenario")
    registry_path = tmp_path / "config" / "cmo-assets.local.json"
    verification_root = tmp_path / "data" / "asset-verifications"
    registry_path.parent.mkdir()
    registry_path.write_text(
        json.dumps(
            {
                "assets": [
                    {
                        "asset_id": "fixture_scen",
                        "scenario_id": "scenario_fixture",
                        "absolute_path": str(scenario.resolve()),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    service = ScenarioAssetVerificationService(
        registry_path=registry_path,
        verification_root=verification_root,
    )
    service.verify(
        asset_id="fixture_scen",
        actor="tester",
        confirmed=True,
        verified_clean_initial_state=True,
    )
    registered = json.loads(registry_path.read_text(encoding="utf-8"))["assets"][0]
    assert registered["verification_record"].endswith("fixture_scen.json")
    assert registered["verified_sha256"] == _sha(scenario)
    asset = ControlledScenarioAssetRegistry(
        registry_path=registry_path,
        verification_root=verification_root,
    ).load_verified("fixture_scen")

    lua = tmp_path / "candidate.lua"
    lua.write_text("print('candidate')\n", encoding="utf-8")
    attempt = tmp_path / "attempts" / "attempt_00"
    job = DynamicBatchJobBuilder().build(
        attempt_dir=attempt,
        source_scenario=asset,
        lua_path=lua,
        campaign_id="campaign_fixture",
        generation_index=0,
        candidate_id="candidate_00",
        operation_id="g000:cmo:candidate_00:a00",
        attempt_index=0,
        audit_profile="phase9c",
    )

    assert job.scenario_path == attempt / "scenario.scen"
    assert job.scenario_path.read_bytes() == scenario.read_bytes()
    assert job.scenario_checksum == _sha(scenario)
    assert job.lua_path == attempt / "candidate.lua"
    assert job.lua_path.read_text(encoding="utf-8") == "print('candidate')\n"
    assert job.results_dir == attempt / "batch-results"
    payload = json.loads((attempt / "batch-job.json").read_text(encoding="utf-8"))
    assert payload["jobs"][0]["script"] == str(job.lua_path.resolve())
    assert payload["scenario"] == str(job.scenario_path.resolve())
    assert "all1v1.lua" not in json.dumps(payload)


def test_changed_source_asset_invalidates_verification(tmp_path: Path) -> None:
    scenario = tmp_path / "fixture.scen"
    scenario.write_bytes(b"one")
    registry = tmp_path / "cmo-assets.local.json"
    registry.write_text(
        json.dumps(
            {
                "assets": [
                    {
                        "asset_id": "fixture",
                        "scenario_id": "scenario_fixture",
                        "absolute_path": str(scenario.resolve()),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    records = tmp_path / "verifications"
    service = ScenarioAssetVerificationService(registry_path=registry, verification_root=records)
    service.verify(
        asset_id="fixture",
        actor="tester",
        confirmed=True,
        verified_clean_initial_state=True,
    )
    scenario.write_bytes(b"two")

    with pytest.raises(ValueError, match="scenario_asset_checksum_changed"):
        ControlledScenarioAssetRegistry(
            registry_path=registry,
            verification_root=records,
        ).load_verified("fixture")


def test_controlled_package_git_state_includes_untracked_files(
    tmp_path: Path,
) -> None:
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "phase9c@example.invalid"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Phase9C Fixture"],
        cwd=tmp_path,
        check=True,
    )
    (tmp_path / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "fixture"], cwd=tmp_path, check=True)
    (tmp_path / "untracked.txt").write_text("untracked\n", encoding="utf-8")

    _, dirty, diff_checksum = ControlledCampaignInputPackageLoader(
        project_root=tmp_path,
        require_clean_worktree=False,
    )._git_state()

    assert dirty is True
    assert diff_checksum


def test_baseline_failure_profile_reads_only_formal_phase3_artifacts(
    tmp_path: Path,
) -> None:
    (tmp_path / "execution-summary.json").write_text(
        json.dumps(
            {
                "run": {"run_id": "run_formal"},
                "official_score": {"initial": 0, "final": -40},
                "evidence_integrity": {"valid": True},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "semantic-validation.json").write_text(
        json.dumps(
            {
                "semantic_valid": False,
                "failure_indicators": ["missing_contact"],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "planned-vs-actual.json").write_text(
        json.dumps(
            {
                "execution_fidelity": "degraded",
                "deviations": [{"operation_id": "contact.red_cvn"}],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "console.txt").write_text(
        "model guess that must not enter the profile",
        encoding="utf-8",
    )

    profile = BaselineFailureProfileBuilder().build(tmp_path)

    assert profile is not None
    assert profile.run_id == "run_formal"
    assert profile.official_score == -40
    assert profile.failure_indicators == ("missing_contact",)
    assert "console.txt" not in profile.source_checksums
    assert set(profile.source_checksums) == {
        "execution-summary.json",
        "semantic-validation.json",
        "planned-vs-actual.json",
    }


def test_baseline_failure_profile_requires_all_formal_artifacts(
    tmp_path: Path,
) -> None:
    (tmp_path / "execution-summary.json").write_text(
        json.dumps({"run": {}, "official_score": {"final": 0}}),
        encoding="utf-8",
    )

    assert BaselineFailureProfileBuilder().build(tmp_path) is None


def test_phase9c_production_records_are_immutable_contracts() -> None:
    verification = ScenarioAssetVerificationRecord.create(
        asset_id="asset",
        scenario_id="scenario",
        absolute_path=r"C:\fixture.scen",
        sha256="a" * 64,
        size_bytes=10,
        modified_time_ns=20,
        verified_clean_initial_state=True,
        actor="operator",
        hostname="host",
        process_id=123,
        verified_at="2026-07-28T00:00:00+00:00",
    )
    slot = AttemptSlot(
        operation_id="g000:cmo:baseline:a00",
        candidate_id="baseline",
        attempt_index=0,
        status="available",
    )
    usage = GenerationApprovalUsage(
        approval_id="approval",
        maximum_cmo_attempts=5,
        consumed_operation_ids=("g000:cmo:baseline:a00",),
    )

    assert verification.actor_source == "local_os_user"
    assert verification.identity_strength == "local_os_attribution"
    assert ScenarioAssetVerificationRecord.from_dict(
        verification.to_dict()
    ) == verification
    assert slot.remaining is True
    assert usage.remaining_cmo_attempts == 4


def test_authorized_runner_checks_permission_before_fake_cmo_start(
    tmp_path: Path,
) -> None:
    scenario = tmp_path / "source.scen"
    scenario.write_bytes(b"clean")
    asset = SimpleNamespace(
        asset_id="asset",
        scenario_id="scenario",
        absolute_path=str(scenario),
        sha256=_sha(scenario),
    )
    lua = tmp_path / "attempt_00" / "candidate.lua"
    lua.parent.mkdir()
    lua.write_text("print('formal')\n", encoding="utf-8")
    events: list[str] = []

    class Broker:
        def authorize_attempt_slot(self, **kwargs):
            events.append(f"authorized:{kwargs['operation_id']}")

        def mark_attempt_started(self, operation_id):
            events.append(f"started:{operation_id}")

        def mark_attempt_completed(self, operation_id, **_kwargs):
            events.append(f"completed:{operation_id}")

    class FakeRunner:
        def run(self, **_kwargs):
            events.append("cmo_run")
            return SimpleNamespace(
                result=SimpleNamespace(success=True, error=None)
            )

    context = SimpleNamespace(
        preview=SimpleNamespace(
            snapshot_checksum="snapshot",
            candidate_set_checksum="candidate-set",
        ),
        permission_broker=Broker(),
        spec=SimpleNamespace(campaign_id="campaign"),
    )
    runner = CampaignAuthorizedCandidateRunner(
        candidate_id="candidate_00",
        generation_index=0,
        worker_context=context,
        scenario_asset=asset,
        cmo_runner_path=tmp_path / "CmoBatchRunner.exe",
        cmo_executable_path=tmp_path / "Command.exe",
        runner_factory=lambda _job: FakeRunner(),
    )

    runner.run(
        lua_path=lua,
        timeout_seconds=30,
        round_number=0,
        run_id="run",
    )

    assert events == [
        "authorized:g000:cmo:candidate_00:a00",
        "started:g000:cmo:candidate_00:a00",
        "cmo_run",
        "completed:g000:cmo:candidate_00:a00",
    ]
    job = json.loads(
        (lua.parent / "batch-job.json").read_text(encoding="utf-8")
    )
    assert job["scenario"] == str((lua.parent / "scenario.scen").resolve())
    assert job["jobs"][0]["script"] == str(lua.resolve())
