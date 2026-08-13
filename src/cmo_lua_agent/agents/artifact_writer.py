"""确定性 Lua 产物的原子写入边界。

Lua 合成 Agent 将已验证的文本和 Manifest 交给本模块落盘；调用方负责选择输出目录与
候选方案身份，本模块只保证两份文件不会在写入失败时留下不一致的半成品。
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


class ArtifactWriter:
    """将 Agent 产生的诊断/候选 Artifact 写入调用者指定的目录。

文件路径由上层 Workflow 决定；本类不选择候选、不改变 Campaign 状态，避免输出层反向
拥有业务决策权。
    """
    def write(self, *, output_dir: Path, stem: str, lua: str, manifest: dict) -> tuple[Path, Path]:
        """原子写入同名 Lua 与 Manifest，并返回两条最终路径。

        两个临时文件均写好后才执行替换；若 Manifest 临时写入或替换失败，会清理本次
        创建的文件，避免下游把孤立 Lua 误当成完整候选方案。
        """
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
        """在目标目录创建 UTF-8 临时文件，确保后续 ``os.replace`` 位于同一文件系统。"""
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
