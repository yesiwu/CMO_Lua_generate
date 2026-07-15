from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs/lua"


def read_text_file(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"找不到 Lua 文件：{path}")

    return path.read_text(encoding="utf-8")


def ensure_file_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"找不到{label}：{path}")


def list_lua_plans(output_dir: Path = OUTPUT_DIR) -> list[Path]:
    if not output_dir.exists():
        raise FileNotFoundError(f"找不到 output 文件夹：{output_dir}")

    plans = [
        plan_dir
        for plan_dir in output_dir.iterdir()
        if plan_dir.is_dir() and (plan_dir / "main.lua").is_file()
    ]
    return sorted(plans, key=lambda path: path.name)


def choose_lua_file(output_dir: Path = OUTPUT_DIR) -> Path:
    plans = list_lua_plans(output_dir)
    if not plans:
        raise FileNotFoundError(f"output 文件夹下没有找到包含 main.lua 的方案：{output_dir}")

    print("请选择要读取的方案：")
    for index, plan_dir in enumerate(plans, start=1):
        print(f"{index}. {plan_dir.name}")

    while True:
        choice = input(f"输入编号 1-{len(plans)}：").strip()
        if choice.isdigit():
            index = int(choice)
            if 1 <= index <= len(plans):
                selected = plans[index - 1] / "main.lua"
                print(f"已选择：{selected}")
                return selected

        print("输入无效，请重新输入。")
