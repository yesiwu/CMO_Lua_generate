from __future__ import annotations

import os
from pathlib import Path

import pytest

from cmo_lua_agent.tools.workspace_policy import WorkspacePathError, WorkspacePathPolicy


def test_workspace_policy_accepts_visible_relative_path(tmp_path: Path) -> None:
    target = tmp_path / "src" / "module.py"
    target.parent.mkdir()
    target.write_text("VALUE = 1\n", encoding="utf-8")

    resolved = WorkspacePathPolicy(tmp_path).resolve_file("src/module.py", must_exist=True)

    assert resolved == target


@pytest.mark.parametrize(
    "raw_path",
    [".env", ".github/workflow.yml", "src/.cache/value.py", "../outside.py"],
)
def test_workspace_policy_rejects_hidden_and_parent_paths(
    tmp_path: Path,
    raw_path: str,
) -> None:
    with pytest.raises(WorkspacePathError):
        WorkspacePathPolicy(tmp_path).resolve_file(raw_path)


def test_workspace_policy_rejects_absolute_path_outside_workspace(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.py"

    with pytest.raises(WorkspacePathError):
        WorkspacePathPolicy(tmp_path).resolve_file(str(outside))


def test_workspace_policy_filters_hidden_directory_entries(tmp_path: Path) -> None:
    (tmp_path / "visible.py").write_text("", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=x", encoding="utf-8")
    (tmp_path / ".pytest-tmp").mkdir()

    names = [path.name for path in WorkspacePathPolicy(tmp_path).visible_children(".")]

    assert names == ["visible.py"]


def test_workspace_policy_rejects_symbolic_link_escape(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir(exist_ok=True)
    link = tmp_path / "linked"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"当前环境不能创建符号链接：{exc}")

    with pytest.raises(WorkspacePathError):
        WorkspacePathPolicy(tmp_path).resolve_file("linked/file.py")
