"""
02_strike_info.py — 从 A1 场景 JSON 提取打击信息
"""
import json
from pathlib import Path

JSON_PATH = Path(r"C:\Users\user\.codex\skills\CMOLua-main\json\A1场景_new.json")

with JSON_PATH.open(encoding="utf-8-sig") as f:
    data = json.load(f)

sides = data.get("WarPower", {}).get("ForceSides", [])

# 提取所有 Unit，按 UnitType 分类
all_units = []
for side in sides:
    side_name = side.get("SideName", "未知")
    for unit in side.get("Unit", []):
        unit["_side"] = side_name
        all_units.append(unit)

print("=" * 70)
print(f"场景: {data['ScenarioInfo']['ScenarioName']}")
print(f"总 Unit 数: {len(all_units)}")
print("=" * 70)

# 按 UnitType 分类
from collections import defaultdict
by_type = defaultdict(list)
for u in all_units:
    by_type[u.get("UnitType", "?")].append(u)

print("\n=== UnitType 分布 ===")
for t, units in sorted(by_type.items(), key=lambda x: -len(x[1])):
    print(f"  {t:10s} x{len(units)}")

# 打击 Unit 详情
print("\n=== 打击 Unit 详情 ===")
strike_units = by_type.get("打击", [])
for unit in strike_units:
    eqs = unit.get("Equipments", [])
    total_ammo = 0
    ammo_detail = []
    for eq in eqs:
        comps = eq.get("ComponentList", [])
        for c in comps:
            qty = c.get("QuantityRemaining", 0)
            name = c.get("componentName", "?")
            ammo_detail.append(f"{name}×{qty}")
            total_ammo += qty

    loc = unit.get("UnitLocation", {})
    lat = loc.get("Latitude") or unit.get("Equipments", [{}])[0].get("Location", {}).get("Latitude", "?")
    lon = loc.get("Longitude") or unit.get("Equipments", [{}])[0].get("Location", {}).get("Longitude", "?")

    print(f"\n[{unit['_side']}] {unit.get('UnitName','?')} | {unit.get('UnitID','?')}")
    print(f"  位置: {lat}, {lon}")
    print(f"  导弹详情: {', '.join(ammo_detail) if ammo_detail else '无ComponentList'}")
    print(f"  导弹总数: {total_ammo}")
    print(f"  装备数: {len(eqs)}")

# 蓝方所有 Unit
print("\n=== 蓝方 Unit 清单 ===")
blue_units = [u for u in all_units if u.get("_side") == "Side2"]
by_blue_type = defaultdict(list)
for u in blue_units:
    by_blue_type[u.get("UnitType", "?")].append(u)
for t, units in sorted(by_blue_type.items()):
    print(f"\n  [{t}] ×{len(units)}")
    for u in units:
        eqs = u.get("Equipments", [])
        eq_names = [eq.get("EquipmentType", "?") for eq in eqs[:3]]
        loc = u.get("UnitLocation", {})
        lat = loc.get("Latitude") or (eqs[0].get("Location", {}).get("Latitude") if eqs else "?")
        lon = loc.get("Longitude") or (eqs[0].get("Location", {}).get("Longitude") if eqs else "?")
        print(f"    {u.get('UnitName','?')} | lat={lat} lon={lon} | 装备={eq_names}")

# 作战背景中的打击计划说明
print("\n=== 作战想定（打击意图）===")
desc = data.get("ScenarioInfo", {}).get("ScenarioDescription", "")
print(desc)
print()
det = data.get("ScenarioInfo", {}).get("OperationalDetermination", "")
print(det)
