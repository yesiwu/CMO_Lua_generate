import time

import pyautogui

from .config import ClickStep


def configure_pyautogui() -> None:
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.3


def click_and_wait(step: ClickStep) -> None:
    pyautogui.click(step.x, step.y)

    suffix = f" - {step.name}" if step.name else ""
    print(f"点击完成：({step.x}, {step.y}){suffix}")
    print(f"等待 {step.wait_seconds} 秒")
    time.sleep(step.wait_seconds)


def run_click_steps(steps: tuple[ClickStep, ...]) -> None:
    for step in steps:
        click_and_wait(step)
