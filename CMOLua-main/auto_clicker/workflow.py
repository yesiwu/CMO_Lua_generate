import sys
import time

import pyautogui
import pyperclip

from .config import AutomationConfig, build_default_config
from .files import choose_lua_file, ensure_file_exists, read_text_file
from .launcher import ensure_admin, run_as_admin
from .mouse import configure_pyautogui, run_click_steps


def paste_text(text: str) -> None:
    pyperclip.copy(text)
    pyautogui.hotkey("ctrl", "v")


def run_automation(config: AutomationConfig) -> None:
    ensure_file_exists(config.exe_path, "程序")
    ensure_file_exists(config.lua_file_path, "Lua 文件")

    configure_pyautogui()

    run_as_admin(config.exe_path)
    print("CMO 启动命令已执行")
    print(f"等待软件启动：{config.launch_wait_seconds} 秒")
    time.sleep(config.launch_wait_seconds)

    run_click_steps(config.pre_paste_steps)

    paste_text(read_text_file(config.lua_file_path))
    print("main.lua 内容已粘贴完成")
    print(f"等待 {config.step_wait_seconds} 秒")
    time.sleep(config.step_wait_seconds)

    run_click_steps(config.post_paste_steps)
    print("自动操作流程已全部完成。")


def main() -> None:
    if not ensure_admin():
        sys.exit(0)

    try:
        lua_file_path = choose_lua_file()
        run_automation(build_default_config(lua_file_path))
    except FileNotFoundError as exc:
        print(f"启动失败：{exc}")
