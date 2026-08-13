"""Controlled external CMO scenario asset registration and verification."""

from __future__ import annotations

from datetime import UTC, datetime
import getpass
from hashlib import sha256
import json
import os
from pathlib import Path
import socket
from typing import Any

from cmo_lua_agent.evolution.production_models import (
    ControlledScenarioAsset,
    ScenarioAssetVerificationRecord,
)


def file_sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


class ScenarioAssetVerificationService:
    """验证 Campaign 使用的场景资产与运行输入是否可安全定位和读取。"""
    def __init__(self, *, registry_path: Path, verification_root: Path) -> None:
        self.registry_path = Path(registry_path).resolve()
        self.verification_root = Path(verification_root).resolve()

    def inspect(self, asset_id: str) -> dict[str, Any]:
        asset = self._registry_entry(asset_id)
        path = Path(asset["absolute_path"]).resolve()
        record_path = self.verification_root / f"{asset_id}.json"
        return {
            **asset,
            "exists": path.is_file(),
            "computed_sha256": file_sha256(path) if path.is_file() else None,
            "size_bytes": path.stat().st_size if path.is_file() else None,
            "verification_record": str(record_path),
            "verified": record_path.is_file(),
        }

    def verify(
        self,
        *,
        asset_id: str,
        confirmed: bool,
        verified_clean_initial_state: bool,
        actor: str | None = None,
    ) -> dict[str, Any]:
        if not confirmed:
            raise ValueError("scenario_asset_verification_not_confirmed")
        asset = self._registry_entry(asset_id)
        path = Path(asset["absolute_path"]).resolve()
        if not path.is_file() or not os.access(path, os.R_OK):
            raise ValueError("scenario_asset_unreadable")
        now = datetime.now(UTC).isoformat()
        record_model = ScenarioAssetVerificationRecord.create(
            asset_id=asset_id,
            scenario_id=str(asset["scenario_id"]),
            absolute_path=str(path),
            sha256=file_sha256(path),
            size_bytes=path.stat().st_size,
            modified_time_ns=path.stat().st_mtime_ns,
            verified_clean_initial_state=bool(verified_clean_initial_state),
            actor=actor or getpass.getuser(),
            hostname=socket.gethostname(),
            process_id=os.getpid(),
            verified_at=now,
        )
        record = record_model.to_dict()
        record_path = self.verification_root / f"{asset_id}.json"
        _atomic_json(record_path, record)
        registry = json.loads(self.registry_path.read_text(encoding="utf-8"))
        updated = []
        for item in registry.get("assets", []):
            if item.get("asset_id") == asset_id:
                item = {
                    **item,
                    "verification_record": str(record_path),
                    "verified_sha256": record["sha256"],
                }
            updated.append(item)
        _atomic_json(self.registry_path, {**registry, "assets": updated})
        return record

    def _registry_entry(self, asset_id: str) -> dict[str, Any]:
        if not self.registry_path.is_file():
            raise ValueError("scenario_asset_registry_missing")
        value = json.loads(self.registry_path.read_text(encoding="utf-8"))
        for item in value.get("assets", []):
            if item.get("asset_id") == asset_id:
                return dict(item)
        raise ValueError("scenario_asset_not_registered")


class ControlledScenarioAssetRegistry:
    """登记已验证的场景资产，向输入包加载器提供统一的受控引用。"""
    def __init__(self, *, registry_path: Path, verification_root: Path) -> None:
        self._service = ScenarioAssetVerificationService(
            registry_path=registry_path,
            verification_root=verification_root,
        )

    def load_verified(self, asset_id: str) -> ControlledScenarioAsset:
        """Load an executable asset; verification data is audit-only metadata."""
        asset = self._service._registry_entry(asset_id)
        record_path = self._service.verification_root / f"{asset_id}.json"
        path = Path(asset["absolute_path"]).resolve()
        if not path.is_file() or not os.access(path, os.R_OK):
            raise ValueError("scenario_asset_unreadable")
        record = (
            json.loads(record_path.read_text(encoding="utf-8"))
            if record_path.is_file()
            else {}
        )
        return ControlledScenarioAsset(
            asset_id=asset_id,
            scenario_id=str(asset["scenario_id"]),
            absolute_path=str(path),
            sha256=file_sha256(path),
            size_bytes=path.stat().st_size,
            verification_record_path=str(record_path),
            verified_clean_initial_state=bool(record.get("verified_clean_initial_state", False)),
        )
