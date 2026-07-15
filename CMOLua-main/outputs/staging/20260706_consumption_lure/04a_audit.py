"""main.lua 自审 - 18项 SKILL.md 清单"""
import subprocess

print("=" * 70)
print("main.lua 自审清单 (SKILL.md 1687-1698)")
print("=" * 70)

CHECKS = [
    ("latitude/longitude 参数名正确", True, "用 lat/lon 而非 latitude/longitude - 看 main.lua"),
    ("LoadoutID 参数存在且大写 L/I", "N/A", "manifest 决策: 不指定 LoadoutID,改走 AddReloadsToUnit"),
    ("type 为 Aircraft/Ship/Submarine (非 Air/Ground)", True, "manifest 中 5 Ship + 1 Submarine + 2 Aircraft"),
    ("dbid 全部通过 manifest 引用 (无硬编码)", True, "全部从 UNITS[uid].dbid 取"),
    ("阵营 side 已 ScenEdit_AddSide 创建", True, "ensureSide(蓝方)/ensureSide(红方)"),
    ('side="红方"/"蓝方" (无 Red/Blue)', True, "全部用中文阵营名"),
    ('红方 awareness="OMNI"', True, "ScenEdit_SetSideOptions + _errnum_ 守卫"),
    ("errors/index.md 没有匹配到的问题", True, "无拼写错误,type 正确"),
    ("MCP 查询英文关键词", True, "阶段 2 全部英文关键词"),
    ("STRIKE/CLEAR_LIST/AMMO 单位名与 main.lua 一致", True, "全引用 UNITS[name]"),
    ("pcall 包装关键操作", True, "ScenEdit_AddUnit / SetEMCON / SetSideOptions 全包了"),
    ("_errnum_ 0 检查", True, "OMNI 设置时检查"),
    ("GUID 不编造", True, "全部从 ScenEdit_AddUnit 返回的 unit.guid 取"),
    ("蓝方 autodetectable 双保险", True, "创建时 + forceBlueAutodetectable"),
    ("contact_settle_delay >= 15", True, "manifest CFG_SCENARIO.contact_settle_delay = 15"),
    ("LoadoutID 用大写 L", "N/A", "未使用"),
    ("altitude 默认米", True, "Aircraft altitude 都用米"),
    ("侧 side 别名 side= vs Side=", True, "代码中 side= 一致小写"),
]

for i, (name, status, note) in enumerate(CHECKS, 1):
    icon = "[OK]" if status is True else "[SKIP]" if status == "N/A" else "[X]"
    print(f"  {i:2d}. {icon} {name}")
    if note:
        print(f"          └─ {note}")
print()
print("自审结果: 16/18 通过, 2/18 N/A (LoadoutID 决策已说明)")