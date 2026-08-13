"""主 Agent 工作区工具共享的路径边界。

上游由读取、搜索、列目录和普通写入工具调用；本模块只判断路径是否可向模型暴露，
不负责审批或实际 I/O。确定性系统代码（配置加载、Git、会话持久化）不使用该策略，
因此禁止 Agent 读取隐藏路径不会破坏系统内部状态。
"""

from __future__ import annotations

from pathlib import Path
class WorkspacePathError(PermissionError):
    """携带稳定错误码的工作区路径拒绝。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class WorkspacePathPolicy:
    """统一禁止工作区外、隐藏组成部分和符号链接路径。"""

    def __init__(self, workdir: Path) -> None:
        self.root = Path(workdir).resolve(strict=True)

    def resolve_file(
        self,
        raw_path: object,
        *,
        must_exist: bool = False,
    ) -> Path:
        path = self._resolve(raw_path)
        if must_exist and not path.is_file():
            raise WorkspacePathError("file_not_found", f"文件不存在：{path}")
        return path

    def resolve_directory(
        self,
        raw_path: object = ".",
        *,
        must_exist: bool = False,
    ) -> Path:
        path = self._resolve(raw_path)
        if must_exist and not path.is_dir():
            raise WorkspacePathError("directory_not_found", f"目录不存在：{path}")
        return path

    def visible_children(self, raw_path: object = ".") -> list[Path]:
        directory = self.resolve_directory(raw_path, must_exist=True)
        return sorted(
            (
                child
                for child in directory.iterdir()
                if not child.name.startswith(".") and not child.is_symlink()
            ),
            key=lambda item: (not item.is_dir(), item.name.casefold()),
        )

    def _resolve(self, raw_path: object) -> Path:
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise WorkspacePathError("invalid_path", "path 必须是非空相对路径")
        relative = Path(raw_path)
        if relative.is_absolute():
            try:
                relative = relative.relative_to(self.root)
            except ValueError as exc:
                raise WorkspacePathError(
                    "path_outside_workspace",
                    "禁止访问工作区之外的路径",
                ) from exc
        if ".." in relative.parts:
            raise WorkspacePathError("path_parent_traversal", "禁止父目录路径穿越")
        if any(part.startswith(".") and part not in {"."} for part in relative.parts):
            raise WorkspacePathError("hidden_path_forbidden", "禁止访问点号开头的隐藏路径")

        candidate = self.root / relative
        self._reject_symlink_components(candidate)
        resolved = candidate.resolve(strict=False)
        if not (resolved == self.root or resolved.is_relative_to(self.root)):
            raise WorkspacePathError("path_outside_workspace", "路径已经逃逸工作区")
        return candidate

    def _reject_symlink_components(self, candidate: Path) -> None:
        current = self.root
        try:
            relative = candidate.relative_to(self.root)
        except ValueError as exc:
            raise WorkspacePathError("path_outside_workspace", "路径不在工作区内") from exc
        for part in relative.parts:
            current = current / part
            if current.exists() and current.is_symlink():
                raise WorkspacePathError("symlink_path_forbidden", "禁止通过符号链接访问文件")


__all__ = ["WorkspacePathError", "WorkspacePathPolicy"]
