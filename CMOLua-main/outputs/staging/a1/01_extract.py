"""
01_extract.py — 从 A1 场景 JSON 抽取所有 UnitName + 装备信息
"""
import json
import sys
from pathlib import Path

JSON_PATH = Path(r"C:\Users\user\.codex\skills\CMOLua-main\json\A1场景_new.json")

with JSON_PATH.open(encoding="utf-8-sig") as f:
    data = json.load(f)

# ForceSides 结构
warpower = data.get("WarPower", {})
sides = warpower.get("ForceSides", [])

print("=" * 70)
print(f"场景名: {data.get('ScenarioInfo', {}).get('ScenarioName', '?')}")
print(f"时间: {data.get('ScenarioInfo', {}).get('ScenarioStartTime', '?')}")
print(f"阵营数: {len(sides)}")
print("=" * 70)

for i, side in enumerate(sides):
    side_name = side.get("SideName") or side.get("SideID") or f"Side{i+1}"
    print(f"\n--- 阵营 [{i+1}]: {side_name} ---")
    for j, unit in enumerate(side.get("Unit", [])):
        name = unit.get("UnitName", "?")
        uid = unit.get("UnitID", "?")
        utype = unit.get("UnitType", "?")
        speed = unit.get("Speed", 0)
        eqs = unit.get("Equipments", [])
        print(f"  [{j+1}] {uid} | {name} | {utype} | speed={speed} | 装备数={len(eqs)}")
        for k, eq in enumerate(eqs):
            loc = eq.get("Location", {})
            etype = eq.get("EquipmentType", "?")
            ename = eq.get("EquipmentName", "?")
            lat = loc.get("Latitude", "?")
            lon = loc.get("Longitude", "?")
            alt = loc.get("Altitude", 0)
            eid = eq.get("EquipmentID", "?")
            print(f"      k={k+1} {eid} {ename} type={etype} lat={lat} lon={lon} alt={alt}")
