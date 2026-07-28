"""Per-attempt CMO BatchRunner job construction."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil

from cmo_lua_agent.evolution.production_assets import file_sha256
from cmo_lua_agent.evolution.production_models import ControlledScenarioAsset


@dataclass(frozen=True, slots=True)
class DynamicBatchJob:
    campaign_id: str
    generation_index: int
    candidate_id: str
    operation_id: str
    attempt_index: int
    scenario_path: Path
    scenario_checksum: str
    lua_path: Path
    lua_checksum: str
    results_dir: Path
    job_path: Path


class DynamicBatchJobBuilder:
    def build(
        self,
        *,
        attempt_dir: Path,
        source_scenario: ControlledScenarioAsset,
        lua_path: Path,
        campaign_id: str,
        generation_index: int,
        candidate_id: str,
        operation_id: str,
        attempt_index: int,
        audit_profile: str,
        cmo_executable: Path | None = None,
        wall_timeout_seconds: int = 300,
    ) -> DynamicBatchJob:
        attempt = Path(attempt_dir).resolve()
        attempt.mkdir(parents=True, exist_ok=True)
        protected = (
            attempt / "scenario.scen",
            attempt / "batch-job.json",
            attempt / "attempt-manifest.json",
            attempt / "batch-results",
        )
        if any(path.exists() for path in protected):
            raise ValueError("attempt_runtime_assets_already_exist")
        source = Path(source_scenario.absolute_path).resolve()
        if file_sha256(source) != source_scenario.sha256:
            raise ValueError("scenario_asset_checksum_changed")
        scenario_copy = attempt / "scenario.scen"
        lua_copy = attempt / "candidate.lua"
        shutil.copy2(source, scenario_copy)
        source_lua = Path(lua_path).resolve()
        if source_lua != lua_copy:
            shutil.copy2(source_lua, lua_copy)
        if file_sha256(scenario_copy) != source_scenario.sha256:
            raise ValueError("scenario_copy_checksum_mismatch")
        results = attempt / "batch-results"
        results.mkdir()
        job_path = attempt / "batch-job.json"
        payload = {
            "cmoExecutable": (
                str(Path(cmo_executable).resolve())
                if cmo_executable is not None
                else ""
            ),
            "scenario": str(scenario_copy),
            "scenarioChecksum": source_scenario.sha256,
            "outputDirectory": str(results),
            "simulation": {
                "enabled": True,
                "pulseSeconds": 1,
                "stopWhenScenarioEnds": True,
                "wallTimeoutSeconds": int(wall_timeout_seconds),
            },
            "jobs": [
                {
                    "name": operation_id,
                    "script": str(lua_copy),
                    "auditProfile": {
                        "profile": audit_profile,
                        "campaign_id": campaign_id,
                        "generation_index": generation_index,
                        "candidate_id": candidate_id,
                        "operation_id": operation_id,
                        "attempt_index": attempt_index,
                        "script_checksum": file_sha256(lua_copy),
                    },
                }
            ],
        }
        temporary = job_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, job_path)
        manifest_path = attempt / "attempt-manifest.json"
        manifest = {**payload, "jobPath": str(job_path)}
        temporary = manifest_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, manifest_path)
        return DynamicBatchJob(
            campaign_id=campaign_id,
            generation_index=generation_index,
            candidate_id=candidate_id,
            operation_id=operation_id,
            attempt_index=attempt_index,
            scenario_path=scenario_copy,
            scenario_checksum=source_scenario.sha256,
            lua_path=lua_copy,
            lua_checksum=file_sha256(lua_copy),
            results_dir=results,
            job_path=job_path,
        )

    @staticmethod
    def verify_source_unchanged(asset: ControlledScenarioAsset) -> None:
        if file_sha256(Path(asset.absolute_path)) != asset.sha256:
            raise ValueError("scenario_asset_changed_during_attempt")
