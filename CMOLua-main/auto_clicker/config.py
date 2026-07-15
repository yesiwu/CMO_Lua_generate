from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ClickStep:
    x: int
    y: int
    wait_seconds: float
    name: str = ""


@dataclass(frozen=True)
class AutomationConfig:
    exe_path: Path
    lua_file_path: Path
    launch_wait_seconds: float
    startup_click_wait_seconds: float
    step_wait_seconds: float
    pre_paste_steps: tuple[ClickStep, ...]
    post_paste_steps: tuple[ClickStep, ...]


DEFAULT_EXE_PATH = Path(
    r"E:\game\Command Modern Operations Showcase Icebreakers\Command.exe"
)

LAUNCH_WAIT_SECONDS = 15
STARTUP_CLICK_WAIT_SECONDS = 30
STEP_WAIT_SECONDS = 1


def build_default_config(lua_file_path: Path) -> AutomationConfig:
    return AutomationConfig(
        exe_path=DEFAULT_EXE_PATH,
        lua_file_path=lua_file_path,
        launch_wait_seconds=LAUNCH_WAIT_SECONDS,
        startup_click_wait_seconds=STARTUP_CLICK_WAIT_SECONDS,
        step_wait_seconds=STEP_WAIT_SECONDS,
        pre_paste_steps=(
            ClickStep(1175, 690, STARTUP_CLICK_WAIT_SECONDS, "启动后确认"),
            ClickStep(1375, 621, STEP_WAIT_SECONDS, "进入下一步"),
            ClickStep(828, 45, STEP_WAIT_SECONDS, "打开菜单"),
            ClickStep(965, 702, STEP_WAIT_SECONDS, "选择 Lua 控制台"),
            ClickStep(930, 768, STEP_WAIT_SECONDS, "确认打开"),
        ),
        post_paste_steps=(
            ClickStep(1780, 398, STEP_WAIT_SECONDS, "执行 Lua"),
            ClickStep(1887, 12, STEP_WAIT_SECONDS, "关闭窗口"),
        ),
    )
