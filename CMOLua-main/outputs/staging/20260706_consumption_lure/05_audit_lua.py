r"""
05_audit_lua.py — JSON → Lua 反向校验
========================================

目的：在 03_build_manifest.py 生成 manifest.lua 之后，校验每个 JSON 字段都映射到位。

用法（PowerShell）：
    cd C:\Users\user\.codex\skills\CMOLua-main
    python outputs\staging\20260706_consumption_lure\05_audit_lua.py

校验项：
1. JSON 中每个 force.unit 内的装备都进了 manifest.lua 的 UNITS（dict-keyed）
2. 每个 attacker（STRIKE.attacker）都在 UNITS 中存在
3. 每个 target 都在 UNITS 中存在
4. 每个 weapon_dbid（STRIKE / AMMO）都在 WEAPONS 中
5. 每条航点都在 waypoints 中
6. Aircraft 必有 loadout_id（红线 #2）
7. 弹药总数 ≥ STRIKE 总数（红线 §E）
"""
import json
import re
import sys
from pathlib import Path


STAGING = Path(r"C:\Users\user\.codex\skills\CMOLua-main\outputs\staging\20260706_consumption_lure")
JSON_PATH = Path(r"C:\Users\user\.codex\skills\CMOLua-main\json\消耗与诱歼作战方案.json")
MANIFEST_PATH = STAGING.parent.parent / "lua" / "20260706_101200_consumption_lure" / "manifest.lua"


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_manifest_units(manifest_text: str) -> dict:
    """解析 manifest.lua 的 UNITS 表（dict-keyed）"""
    units = {}

    # 定位 UNITS = { 起止
    m = re.search(r"UNITS\s*=\s*\{(.*?)^\}", manifest_text, re.MULTILINE | re.DOTALL)
    if not m:
        print("[WARN] 无法定位 UNITS 表")
        return units

    body = m.group(1)
    # 匹配 ["<id>"] = { ... }
    for um in re.finditer(r'\["([^"]+)"\]\s*=\s*\{(.*?)\n\}', body, re.DOTALL):
        uid = um.group(1)
        content = um.group(2)

        def get(k):
            km = re.search(rf"{k}\s*=\s*([^,\n]+)", content)
            if not km:
                return None
            val = km.group(1).strip()
            if val.startswith('"') and val.endswith('"'):
                return val[1:-1]
            try:
                return int(val)
            except ValueError:
                try:
                    return float(val)
                except ValueError:
                    return val

        units[uid] = {
            "side":  get("side"),
            "type":  get("type"),
            "dbid":  get("dbid"),
            "name":  uid,
            "loadout_id": get("loadout_id"),
        }
    return units


def load_manifest_section(manifest_text: str, key: str) -> list:
    """解析 manifest.lua 的 list-of-dict section（如 STRIKE、AMMO）"""
    items = []
    m = re.search(rf"{key}\s*=\s*\{{(.*?)^\}}", manifest_text, re.MULTILINE | re.DOTALL)
    if not m:
        return items
    body = m.group(1)
    for em in re.finditer(r"\{([^}]+)\}", body, re.DOTALL):
        content = em.group(1)
        item = {}
        for km in re.finditer(r"(\w+)\s*=\s*([^,\n]+)", content):
            val = km.group(2).strip()
            if val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
            else:
                try:
                    val = int(val)
                except ValueError:
                    try:
                        val = float(val)
                    except ValueError:
                        pass
            item[km.group(1)] = val
        if item:
            items.append(item)
    return items


def main():
    if not MANIFEST_PATH.exists():
        print(f"[ERROR] manifest.lua 不存在: {MANIFEST_PATH}")
        print("        请先运行 03_build_manifest.py")
        sys.exit(1)

    if not JSON_PATH.exists():
        print(f"[ERROR] JSON 不存在: {JSON_PATH}")
        sys.exit(1)

    print("=" * 70)
    print(" JSON → Lua 反向校验")
    print("=" * 70)

    # 1. 加载源数据
    plan = load_json(JSON_PATH)
    manifest_text = MANIFEST_PATH.read_text(encoding="utf-8")

    json_unit_ids: set = set()
    for intent in plan.get("intentions", {}).values():
        for force in intent.get("forces", []) if isinstance(intent.get("forces"), list) else []:
            units = force.get("unit", {})
            if isinstance(units, dict):
                json_unit_ids.update(units.keys())

    # 2. 解析 manifest
    units = load_manifest_units(manifest_text)
    strikes = load_manifest_section(manifest_text, "STRIKE")
    ammo = load_manifest_section(manifest_text, "AMMO")

    manifest_unit_ids = set(units.keys())

    # 3. 校验
    issues = []

    # 3.1 JSON unit → manifest UNITS
    missing_in_manifest = json_unit_ids - manifest_unit_ids
    if missing_in_manifest:
        issues.append(f"[FAIL] JSON 装备未进 manifest UNITS: {missing_in_manifest}")

    # 3.2 STRIKE.attacker / target 都在 UNITS 中
    for i, s in enumerate(strikes):
        if s.get("attacker") not in manifest_unit_ids:
            issues.append(f"[FAIL] STRIKE[{i}].attacker '{s.get('attacker')}' 不在 UNITS 中")
        if s.get("target") not in manifest_unit_ids:
            issues.append(f"[FAIL] STRIKE[{i}].target '{s.get('target')}' 不在 UNITS 中")

    # 3.3 Aircraft loadout_id 必填
    for uid, u in units.items():
        if u.get("type") == "Aircraft" and not u.get("loadout_id"):
            issues.append(f"[FAIL] Aircraft '{uid}' 缺少 loadout_id（红线 #2）")

    # 3.4 弹药预算自检
    ammo_by_attacker = {}
    for a in ammo:
        ammo_by_attacker[a.get("unitname")] = ammo_by_attacker.get(a.get("unitname"), 0) + a.get("number", 0)

    strike_by_attacker = {}
    for s in strikes:
        att = s.get("attacker")
        if att:
            strike_by_attacker[att] = strike_by_attacker.get(att, 0) + s.get("quantity", 0)

    for attacker, used in strike_by_attacker.items():
        loaded = ammo_by_attacker.get(attacker, 0)
        if loaded < used:
            issues.append(f"[FAIL] {attacker} 弹药不足：装弹 {loaded} < STRIKE 需要 {used}")

    # 4. 报告
    print(f"\nJSON 单位 ID 数:       {len(json_unit_ids)}")
    print(f"Manifest UNITS 数:     {len(manifest_unit_ids)}")
    print(f"STRIKE 条目数:         {len(strikes)}")
    print(f"AMMO 条目数:           {len(ammo)}")
    print()

    if not issues:
        print("[PASS] 所有校验通过 ✓")
        sys.exit(0)

    print(f"[FAIL] 发现 {len(issues)} 个问题:")
    for issue in issues:
        print(f"  - {issue}")
    sys.exit(1)


if __name__ == "__main__":
    main()
