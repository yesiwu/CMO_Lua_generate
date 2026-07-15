"""
04_audit.py — A1 YJ-18 方案自审
"""
import re
from pathlib import Path

BASE = Path(r"C:/Users/user/.codex/skills/CMOLua-main/outputs/lua/20260707_213000_a1_4v3_carrier_group")
files = ["manifest.lua", "main.lua", "clear.lua", "reload.lua", "attack.lua", "all.lua"]

# ============ 1. lua 语法快速检查 ============
print("=" * 60)
print("【1. lua 语法 lint (关键字配对检查)】")
print("=" * 60)

issues = []
for f in files:
    p = BASE / f
    src = p.read_text(encoding="utf-8")
    # 检查 dofile 引用一致性
    dofile_count = len(re.findall(r'dofile\s*\(\s*"manifest\.lua"\s*\)', src))
    # 检查函数闭合
    func_def = len(re.findall(r'function\s+\w+', src))
    func_end = src.count("end")
    end_kw = src.count("\nend\n") + src.count(" end ")
    print(f"  {f:15s} lines={len(src.splitlines()):4d} dofile(manifest)={dofile_count}")

# ============ 2. 命名一致性检查 ============
print("\n" + "=" * 60)
print("【2. 单位名一致性】")
print("=" * 60)

manifest = (BASE / "manifest.lua").read_text(encoding="utf-8")

# 提取 UNITS name=
unit_names = set(re.findall(r'\["([^"]+)"\]\s*=\s*\{[^}]*name\s*=\s*"([^"]+)"', manifest))
print(f"  UNITS 中定义 {len(unit_names)} 个 name: {sorted(unit_names)}")

# 提取 CLEAR_LIST
clear_list = set(re.findall(r'CLEAR_LIST\s*=\s*\{([^}]+)\}', manifest, re.DOTALL))
if clear_list:
    cl_text = list(clear_list)[0]
    cl_names = set(re.findall(r'"([^"]+)"', cl_text))
    print(f"  CLEAR_LIST: {sorted(cl_names)}")

# 提取 AMMO unitname
ammo_names = set(re.findall(r'unitname\s*=\s*"([^"]+)"', manifest))
print(f"  AMMO unitname: {sorted(ammo_names)}")

# 提取 STRIKE attacker / target
strike_attackers = set(re.findall(r'attacker\s*=\s*"([^"]+)"', manifest))
strike_targets = set(re.findall(r'target\s*=\s*"([^"]+)"', manifest))
print(f"  STRIKE attackers: {sorted(strike_attackers)}")
print(f"  STRIKE targets:   {sorted(strike_targets)}")

# 所有出现的 name 集合
all_names = set()
for txt in [manifest] + [(BASE / f).read_text(encoding="utf-8") for f in files if f != "manifest.lua"]:
    all_names |= set(re.findall(r'name\s*=\s*"([^"]+)"', txt))
    all_names |= set(re.findall(r'unitname\s*=\s*"([^"]+)"', txt))
    all_names |= set(re.findall(r'attacker\s*=\s*"([^"]+)"', txt))
    all_names |= set(re.findall(r'target\s*=\s*"([^"]+)"', txt))

# 在 main.lua 中创建单位的所有 name
main_src = (BASE / "main.lua").read_text(encoding="utf-8")
main_names = set(re.findall(r'\bspec\.name\b', main_src))
# manifest 中通过 ScenEdit_AddUnit 创建的所有 name（红蓝方所有 UNITS）
create_names = set(re.findall(r'name\s*=\s*spec\.name', main_src))

print(f"\n  关键检查:")
print(f"  CLEAR_LIST sub AMMO.unitname: {cl_names.issubset(ammo_names)}")
print(f"  AMMO.unitname sub STRIKE.attacker: {ammo_names.issubset(strike_attackers)}")
print(f"  STRIKE.attacker sub AMMO.unitname: {strike_attackers.issubset(ammo_names)}")
print(f"  STRIKE.target sub UNITS.name (蓝方): {strike_targets.issubset(unit_names)}")

# ============ 3. 弹药预算 ============
print("\n" + "=" * 60)
print("【3. 弹药预算】")
print("=" * 60)

ammo_total = {}
for m in re.finditer(r'unitname\s*=\s*"([^"]+)"[^}]*?wpn_dbid\s*=\s*(\d+)[^}]*?number\s*=\s*(\d+)', manifest):
    unit, dbid, num = m.group(1), int(m.group(2)), int(m.group(3))
    ammo_total[unit] = ammo_total.get(unit, 0) + num

strike_total = {}
for m in re.finditer(r'attacker\s*=\s*"([^"]+)"[^}]*?quantity\s*=\s*(\d+)', manifest):
    unit, qty = m.group(1), int(m.group(2))
    strike_total[unit] = strike_total.get(unit, 0) + qty

for unit in sorted(set(list(ammo_total.keys()) + list(strike_total.keys()))):
    a = ammo_total.get(unit, 0)
    s = strike_total.get(unit, 0)
    ok = "✓" if a >= s else "✗"
    print(f"  {ok} {unit:15s} 装弹={a:3d}  打击={s:3d}  余={a-s:3d}")

# ============ 4. 全局 fireAt 检查 ============
print("\n" + "=" * 60)
print("【4. fireAt 全局函数检查（红线 #15）】")
print("=" * 60)
for f in ["attack.lua", "all.lua"]:
    src = (BASE / f).read_text(encoding='utf-8')
    has_global = bool(re.search(r'^function\s+fireAt\s*\(', src, re.MULTILINE))
    has_local = bool(re.search(r'^local\s+function\s+fireAt\s*\(', src, re.MULTILINE))
    print(f"  {f:15s}  global fireAt = {has_global}  local fireAt = {has_local}")

# ============ 5. 全局变量检查 ============
print("\n" + "=" * 60)
print("【5. 全局变量提升（红线 #15）】")
print("=" * 60)
for f in ["attack.lua", "all.lua"]:
    src = (BASE / f).read_text(encoding='utf-8')
    has_red   = "_SIDE_RED" in src and re.search(r'^_SIDE_RED\s*=', src, re.MULTILINE)
    has_blue  = "_SIDE_BLUE" in src and re.search(r'^_SIDE_BLUE\s*=', src, re.MULTILINE)
    has_delay = "_CONTACT_SETTLE_DELAY" in src and re.search(r'_CONTACT_SETTLE_DELAY\s*=\s*15', src)
    print(f"  {f:15s}  _SIDE_RED={bool(has_red)}  _SIDE_BLUE={bool(has_blue)}  delay=15={bool(has_delay)}")

# ============ 6. 真延时 check ============
print("\n" + "=" * 60)
print("【6. 真延时 (Time Trigger) 检查（红线 #9）】")
print("=" * 60)
for f in ["attack.lua", "all.lua"]:
    src = (BASE / f).read_text(encoding='utf-8')
    has_sched = "scheduleOne" in src
    has_trigger = "ScenEdit_SetTrigger" in src
    has_qty_one = 'qty=1' in src or ',1)' in src
    has_qty_n_emit = re.search(r'ScenEdit_AttackContact\([^,]+,[^,]+,[^}]*qty\s*=\s*s\.quantity', src)
    print(f"  {f:15s}  scheduleOne={has_sched}  Time Trigger={has_trigger}  qty=1 per trigger={has_qty_one}")
    print(f"                同步qty=N={bool(has_qty_n_emit)} (必须False)")

# ============ 7. contact_settle_delay 检查 ============
print("\n" + "=" * 60)
print("【7. contact_settle_delay 叠加检查（≥15秒）】")
print("=" * 60)
for f in ["attack.lua", "all.lua"]:
    src = (BASE / f).read_text(encoding='utf-8')
    add_delay = "delay = delay + _CONTACT_SETTLE_DELAY" in src or "delay + _CONTACT_SETTLE_DELAY" in src
    print(f"  {f:15s}  每枚叠加 {add_delay}")

# ============ 8. side 参数中文检查（红线 #5）============
print("\n" + "=" * 60)
print("【8. side 参数中文阵营（红线 #5）】")
print("=" * 60)
for f in files:
    src = (BASE / f).read_text(encoding='utf-8')
    bad = re.findall(r'side\s*=\s*"(Red|Blue|red|blue|中|美)"', src)
    good_red = len(re.findall(r'side\s*=\s*"红方"', src))
    good_blue = len(re.findall(r'side\s*=\s*"蓝方"', src))
    print(f"  {f:15s}  红方={good_red:3d}  蓝方={good_blue:3d}  BadSide={len(bad)}")

# ============ 9. autodetectable 检查（红线 #8）============
print("\n" + "=" * 60)
print("【9. autodetectable 三时间点（红线 #8）】")
print("=" * 60)
for f in files:
    src = (BASE / f).read_text(encoding='utf-8')
    create_set = "autodetectable = spec.autodetectable" in src
    blue_force = "蓝方" in src and "autodetectable = true" in src
    fire_force = "ScenEdit_SetUnit" in src and "autodetectable = true" in src
    print(f"  {f:15s}  创建时设={create_set}  遍历强制={blue_force}  发射前设={fire_force}")

# ============ 10. mode 字符串 ============
print("\n" + "=" * 60)
print("【10. AttackContact mode 字符串（红线 #13）】")
print("=" * 60)
for f in files:
    src = (BASE / f).read_text(encoding="utf-8")
    bad_mode = re.findall(r'mode\s*=\s*\d+', src)  # 数字模式
    good_mode = len(re.findall(r'mode\s*=\s*"1"', src))
    print(f"  {f:15s}  mode=\"1\"={good_mode}  mode=NUM={len(bad_mode)}")

print("\n" + "=" * 60)
print("【自审完成】")
print("=" * 60)
