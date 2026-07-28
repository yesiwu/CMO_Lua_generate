"""Exclusive filesystem lock for the one production CMO instance."""

from __future__ import annotations

import json
import os
from pathlib import Path


class CmoLockError(RuntimeError):
    pass


class CmoInstanceLock:
    def __init__(self, path: Path, *, campaign_id: str) -> None:
        self._path = Path(path).resolve()
        self._campaign_id = campaign_id
        self._held = False

    def acquire(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(self._path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise CmoLockError("cmo_instance_locked") from exc
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump({"campaign_id": self._campaign_id, "pid": os.getpid()}, stream, sort_keys=True)
        self._held = True

    def release(self) -> None:
        if self._held and self._path.is_file():
            self._path.unlink()
        self._held = False

    def __enter__(self) -> "CmoInstanceLock":
        self.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.release()
