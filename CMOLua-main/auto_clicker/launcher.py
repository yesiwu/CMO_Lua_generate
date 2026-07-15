import ctypes
import subprocess
import sys
from pathlib import Path


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except OSError:
        return False


def relaunch_self_as_admin() -> bool:
    script_path = Path(sys.argv[0]).resolve()
    params = subprocess.list2cmdline([str(script_path), *sys.argv[1:]])
    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        sys.executable,
        params,
        str(Path.cwd()),
        1,
    )
    return result > 32


def ensure_admin() -> bool:
    if is_admin():
        return True

    print("当前不是管理员权限，正在请求管理员权限重新启动...")
    if relaunch_self_as_admin():
        print("已启动管理员权限的新窗口，当前窗口即将退出。")
    else:
        print("管理员权限请求被取消或启动失败。")

    return False


def run_as_admin(exe_path: Path) -> None:
    """Start an executable with administrator privileges."""
    ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        str(exe_path),
        None,
        str(exe_path.parent),
        1,
    )
