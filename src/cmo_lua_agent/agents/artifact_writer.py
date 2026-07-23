"""确定性 Lua 产物的原子写入边界。"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


class ArtifactWriter:
    def write(self, *, output_dir: Path, stem: str, lua: str, manifest: dict) -> tuple[Path, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        lua_path, manifest_path = output_dir / f"{stem}.lua", output_dir / f"{stem}.manifest.json"
        lua_tmp = self._write_temporary(lua_path, lua)
        try:
            manifest_tmp = self._write_temporary(
                manifest_path,
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            )
        except Exception:
            if os.path.exists(lua_tmp):
                os.unlink(lua_tmp)
            raise
        lua_existed = lua_path.exists()
        try:
            os.replace(lua_tmp, lua_path)
            os.replace(manifest_tmp, manifest_path)
        except OSError:
            if not lua_existed and lua_path.exists():
                lua_path.unlink()
            for path in (lua_tmp, manifest_tmp):
                if os.path.exists(path):
                    os.unlink(path)
            raise
        return lua_path, manifest_path

    @staticmethod
    def _write_temporary(path: Path, content: str) -> str:
        handle = tempfile.NamedTemporaryFile("w", delete=False, dir=path.parent, encoding="utf-8", newline="\n")
        try:
            handle.write(content)
            handle.close()
            return handle.name
        except Exception:
            if not handle.closed:
                handle.close()
            if os.path.exists(handle.name):
                os.unlink(handle.name)
            raise
        finally:
            if not handle.closed:
                handle.close()
