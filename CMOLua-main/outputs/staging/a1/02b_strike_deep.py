"""
02b_strike_deep.py — 深度提取 A1 打击信息
完整解析所有 Unit，ComponentList 含真实导弹余量
"""
import json
from pathlib import Path

JSON_PATH = Path(r"C:\Users\user\.codex\skills\CMOLua-main\json\A1场景_new.json")

with JSON_PATH.open(encoding="utf-8-sig") as f:
    data = json.load(f)

warpower = data.get("WarPower", {})
sides_raw = warpower.get("ForceSides", [])
units_all = []
sides_map = {}

# 第一个 ForceSide → 红方，第二个 → 蓝方
side_labels = ["红方", "蓝方"]

for idx, side in enumerate(sides_raw):
    side_label = side_labels[idx] if idx < len(side_labels) else f"Side{idx+1}"
    # 尝试从 Unit 里找到 ForceSideID 来判断阵营
    for unit in side.get("Unit", []):
        unit["_side_label"] = side_label
        unit["_side_idx"] = idx
    units_all.extend(side.get("Unit", []))

print(f"总 Unit 数: {len(units_all)}")

# 按 _side_label 分组
red_units = [u for u in units_all if u.get("_side_label") == "红方"]
blue_units = [u for u in units_all if u.get("_side_label") == "蓝方"]
print(f"红方 Unit 数: {len(red_units)}")
print(f"蓝方 Unit 数: {len(blue_units)}")

def summarize_ammo(unit):
    """提取 ComponentList 中所有导弹"""
    items = []
    total = 0
    for eq in unit.get("Equipments", []):
        for comp in eq.get("ComponentList", []):
            name = comp.get("componentName", "?")
            qty  = comp.get("QuantityRemaining", 0)
            items.append(f"{name}×{qty}")
            total += qty
    return items, total

def first_eq_pos(unit):
    """取第一个装备的 lat/lon"""
    eqs = unit.get("Equipments", [])
    if not eqs:
        return None, None
    loc = eqs[0].get("Location", {})
    return loc.get("Latitude"), loc.get("Longitude")

# ---- 红方打击力量汇总 ----
print("\n" + "=" * 70)
print("【红方】打击力量 — ComponentList 导弹清单")
print("=" * 70)

red_weapons = {}  # weapon_name -> {qty, units:[]}

for unit in red_units:
    eqs = unit.get("Equipments", [])
    if not eqs:
        continue
    lat, lon = first_eq_pos(unit)
    ammo_items, ammo_total = summarize_ammo(unit)
    if not ammo_items:
        ammo_str = "（无 ComponentList — 预警/保障/情报等支援单位）"
        ammo_total = 0
    else:
        ammo_str = "，".join(ammo_items)

    print(f"\n[红方] {unit.get('UnitName','?')} | {unit.get('UnitID','?')}")
    print(f"  位置: {lat}, {lon} | 装备数: {len(eqs)} | 导弹总数: {ammo_total}")
    print(f"  详情: {ammo_str}")

    # 累加
    for eq in eqs:
        for comp in eq.get("ComponentList", []):
            wpn = comp.get("componentName", "?")
            qty = comp.get("QuantityRemaining", 0)
            if wpn not in red_weapons:
                red_weapons[wpn] = {"qty": 0, "units": [], "type": "?"}
            red_weapons[wpn]["qty"] += qty
            red_weapons[wpn]["units"].append(unit.get("UnitName", "?"))

print("\n" + "=" * 70)
print("【红方】导弹武器库汇总")
print("=" * 70)
grand_total = 0
for wpn, info in sorted(red_weapons.items(), key=lambda x: -x[1]["qty"]):
    print(f"  {wpn:20s}  ×{info['qty']:4d}  [{' + '.join(info['units'])}]")
    grand_total += info["qty"]
print(f"  {'总计':20s}  ×{grand_total:4d}")

# ---- 蓝方目标清单 ----
print("\n" + "=" * 70)
print("【蓝方】单位清单（打击目标）")
print("=" * 70)

blue_targets = {}
for unit in blue_units:
    eqs = unit.get("Equipments", [])
    lat, lon = first_eq_pos(unit)
    ammo_items, ammo_total = summarize_ammo(unit)
    eq_types = [eq.get("EquipmentType", "?") for eq in eqs[:3]]
    print(f"\n[蓝方] {unit.get('UnitName','?')} | {unit.get('UnitID','?')}")
    print(f"  位置: {lat}, {lon} | 装备类型: {eq_types}")
    print(f"  导弹: {ammo_items if ammo_items else '（无/空）'}")

    # 按 EquipmentType 归类
    for eq in eqs:
        etype = eq.get("EquipmentType", "?")
        if etype not in blue_targets:
            blue_targets[etype] = []
        blue_targets[etype].append({
            "name": unit.get("UnitName", "?"),
            "lat": lat, "lon": lon,
            "etype": etype,
        })

# ---- 打击对应关系 ----
print("\n" + "=" * 70)
print("【打击对应】红方火力 → 蓝方目标（根据作战想定推断）")
print("=" * 70)

strike_plan = [
    # 阶段1：DF-26 反舰/对陆打击
    {"phase": "阶段1 — DF-26 反舰导弹突击", "t": "T+0~10min",
     "attackers": "D02 02打击大队 (DF-26B×20 = 80枚)\nD03 03打击大队 (DF-26D×20 = 80枚)",
     "targets": "蓝方水面舰艇（航母/两栖/驱逐舰）+ 陆上设施",
     "weapons": "DF-26B / DF-26D (反舰型)",
     "note": "componentName: DF26B(4发/车), DF26D(4发/车)"},
    {"phase": "阶段2 — 水面舰艇 YJ-21 反舰", "t": "T+10~20min",
     "attackers": "DDG01 01水面舰艇支队 (052D×2 + 055×1 + 054A×2)\nDDG02 02水面舰艇支队 (052D×1 + 054A×1)\nDDG03 02水面舰艇护卫 (054A×1)",
     "targets": "蓝方航母编队 (CVN+CG+DDG×4+FFG+补给)",
     "weapons": "YJ-21 (componentName: yj21, 4发/机)",
     "note": "DDG01 DDG02 DDG03 的 ComponentList 含 yj21+HQ9B"},
    {"phase": "阶段3 — 轰炸机群对地突击", "t": "T+20~30min",
     "attackers": "H06 06轰炸机大队 (轰-6K×8 = pl10×32枚)\nH02 02轰炸机大队 (轰-6K×6 = pl10×24枚)",
     "targets": "蓝方两栖编队 + 陆上目标",
     "weapons": "pl10 (PL-10 近距空空/对地), YJ-21",
     "note": "H06 ComponentList: pl10×4/机; H02 ComponentList: pl10×4/机"},
    {"phase": "阶段4 — 战斗机群多波次打击", "t": "T+30~45min",
     "attackers": "Z05 05战斗机大队 (歼-16×6 = pl10×24+yj21×24)\nZ06 06战斗机大队 (歼-16×6 = pl10×24+yj21×24)\nZ07 07战斗机大队 (歼-20×4)\nZ08 08战斗机大队 (歼-20×4)",
     "targets": "蓝方 F-35 隐身机群 + 宙斯盾舰艇",
     "weapons": "PL-10 + YJ-21",
     "note": "Z07/Z08 无 ComponentList（歼-20 内置弹仓，挂载不暴露在 ComponentList）"},
    {"phase": "阶段5 — 潜射鱼雷封锁", "t": "T+35~50min",
     "attackers": "SUB01 01潜艇护卫 (039C×1 = yu10×4)\nSUB02 02潜艇护卫 (039C×1 = yu10×4)",
     "targets": "蓝方高价值舰艇（航母/两栖/驱逐舰）",
     "weapons": "YU-10 鱼雷 (componentName: yu10, 4发/艇)",
     "note": "ComponentList: yu10×4"},
    {"phase": "阶段6 — 蓝方反击（反向打击）", "t": "T+?",
     "attackers": "蓝方：HMS01 远程火箭营 (rocket_300mm×36)\n蓝方：TYPHON02 中导营 (标准-3×16)",
     "targets": "红方陆上/海上目标",
     "weapons": "rocket_300mm (300mm火箭) / 标准-3 防空/反导",
     "note": "蓝方 HMS/TYPHON ComponentList 已在上方 blue_units 提取"},
]

for i, plan in enumerate(strike_plan, 1):
    print(f"\n--- {plan['phase']} ({plan['t']}) ---")
    print(f"  攻击方: {plan['attackers']}")
    print(f"  目标:   {plan['targets']}")
    print(f"  武器:   {plan['weapons']}")
    print(f"  依据:   {plan['note']}")

# 最终统计
print("\n" + "=" * 70)
print("【总弹药统计】")
print("=" * 70)
print(f"红方导弹总数: {grand_total} 枚（含 ComponentList）")
print(f"蓝方 HMS 火箭弹: 36 枚")
print(f"蓝方 TYPHON 标准-3: 16 枚")
print(f"\n【说明】")
print("1. ComponentList = JSON 中每个发射单元当前剩余导弹数量")
print("2. '无 ComponentList' 的 Unit 表示预警/保障/情报单位，无独立打击任务")
print("3. YJ-21 = 鹰击-21 超音速反舰导弹（舰载）")
print("4. DF-26B/D = 东风-26 反舰弹道导弹（陆基）")
print("5. pl10 = 霹雳-10 近距空空导弹（机载）")
print("6. yu10 = 鱼-10 重型鱼雷（潜艇）")
print("7. rocket_300mm = 300mm制导火箭弹（蓝方 HMS）")
print("8. 标准-3 = SM-3 防空/反导导弹（蓝方 TYPHON）")
