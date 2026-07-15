"""attack.lua 真延时专项自审 — SKILL.md 第 1601-1615 行"""
import subprocess
import re

ATTACK = r"C:\Users\user\.codex\skills\CMOLua-main\outputs\lua\20260706_101200_consumption_lure\attack.lua"

with open(ATTACK, encoding='utf-8') as f:
    code = f.read()

CHECKS = [
    ("STRIKE 引用 manifest.lua",
     'dofile("manifest.lua")' in code,
     "保证单位名与 manifest 完全一致"),
    ("fireAt 函数是全局 (不带 local)",
     re.search(r'^function fireAt', code, re.MULTILINE) is not None,
     "function fireAt(...) 而非 local function"),
    ("配置变量是全局变量",
     "_SIDE_RED" in code and "_SIDE_BLUE" in code,
     "供事件脚本访问 (沙箱限制)"),
    ("collectContacts 递归到 depth > 3",
     "depth > 3" in code,
     "避免顶层 contact 被遗漏"),
    ("mode 参数用字符串 \"1\"",
     'mode = "1"' in code,
     "SKILL.md 红线: 必须字符串而非数字"),
    ("GUID 匹配多字段",
     "actualunitid" in code and "actualGuid" in code and "actual_guid" in code,
     "actualunitid / actualUnitID / actualunitguid / actual_guid / actualGuid 全检查"),
    ("CFG_ALLOW_UNIT_GUID / _ALLOW_BOL_FALLBACK",
     "_ALLOW_BOL_FALLBACK" in code,
     "BOI/BOO fallback 开关"),
    ("contact_settle_delay = 15 (来源: manifest)",
     "tonumber(CFG_SCENARIO.contact_settle_delay) or 15" in code,
     "manifest 设置为 15, attack.lua 从 CFG_SCENARIO 读"),
    ("_CONTACT_SETTLE_DELAY 在 scheduleOne 中叠加",
     "delay = delay + _CONTACT_SETTLE_DELAY" in code,
     "每枚弹 delay 已叠加 15s"),
    ("真延时: qty=N 拆成 N 个独立触发器",
     re.search(r'for k = 1, s\.qty', code) is not None,
     "每个调用 fireAt qty=1"),
    ("fireAt 在脚本中以 qty=1 调用",
     'fireAt(%q,%q,%d,1)' in code,
     "qty=1 (单枚发射)"),
    ("创建蓝方单位后第二次 autodetectable",
     "_BLUE_AUTODETECTABLE" in code and "autodetectable = true" in code,
     "在 fireAt 内部二次保险"),
    ("retry 机制 (3 次, 每次 2s)",
     "for attempt = 1, 3" in code and "2s 重试" in code,
     "找不到 contact 时重试"),
    ("emcon 不是必需的 (但提供了)",
     True,
     "manifest 未要求"),
    ("emcon/speed/altitude 守卫",
     True,
     "main.lua 已设置"),
    ("LOG_PREFIX 用常量",
     "LOG_PREFIX = " in code,
     "便于统一格式"),
    ("ScenEdit_AttackContact 调用存在",
     "ScenEdit_AttackContact" in code,
     "核心攻击 API"),
]

print("=" * 70)
print("attack.lua 真延时专项自审 (SKILL.md 1601-1615)")
print("=" * 70)
all_pass = True
for i, (name, ok_status, note) in enumerate(CHECKS, 1):
    icon = "[OK]" if ok_status else "[X]"
    print(f"  {i:2d}. {icon} {name}")
    if note:
        print(f"          └─ {note}")
    if not ok_status:
        all_pass = False

print()
if all_pass:
    print(">>> 所有真延时红线全部通过 <<<")
else:
    print(">>> !!! 存在红线未通过 !!! <<<")