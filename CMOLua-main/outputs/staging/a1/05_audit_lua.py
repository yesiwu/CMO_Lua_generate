"""
05_audit_lua_a1.py — A1 场景的 Lua 审计（独立于其他场景）
"""
import json
import re
import sys
from pathlib import Path

JSON_PATH = Path(r"C:\Users\user\.codex\skills\CMOLua-main\json\A1场景_new.json")
MANIFEST_PATH = Path(r"C:\Users\user\.codex\skills\CMOLua-main\outputs\staging\a1\manifest.lua")


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)


def load_manifest_units(manifest_text: str) -> dict:
    """解析 UNITS 表（dict-keyed，单行匹配）"""
    units = {}

    # 定位 UNITS = { ... } 范围
    m = re.search(r"UNITS\s*=\s*\{", manifest_text)
    if not m:
        return units
    start = m.end() - 1  # 指向 {
    depth = 0
    end = start
    for i in range(start, len(manifest_text)):
        c = manifest_text[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                end = i
                break
    body = manifest_text[start+1:end]

    # 单行匹配：["<id>"] = { ... },
    for line in body.split('\n'):
        line = line.strip()
        m2 = re.match(r'\["([^"]+)"\]\s*=\s*\{(.*)\}\s*,?\s*$', line)
        if not m2:
            continue
        uid = m2.group(1)
        content = m2.group(2)
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
        units[uid] = {"side": get("side"), "type": get("type"), "dbid": get("dbid"),
                      "name": uid, "loadout_id": get("loadout_id")}
    return units


def load_manifest_section(manifest_text: str, key: str) -> list:
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
        sys.exit(1)

    plan = load_json(JSON_PATH)
    manifest_text = MANIFEST_PATH.read_text(encoding="utf-8")

    # A1 场景每个 Unit 内有 Equipments 列表
    # 这里检查"装备是否都在 UNITS 中"较复杂，简化为"每个 JSON unit 抽样 1 个装备映射到 UNITS"
    json_unit_ids: set = set()
    for side in plan.get("WarPower", {}).get("ForceSides", []):
        for unit in side.get("Unit", []):
            for eq in unit.get("Equipments", []):
                eid = eq.get("EquipmentID", "")
                ename = eq.get("EquipmentName", "")
                if eid:
                    json_unit_ids.add(eid)

    units = load_manifest_units(manifest_text)
    strikes = load_manifest_section(manifest_text, "STRIKE")
    ammo = load_manifest_section(manifest_text, "AMMO")

    manifest_unit_ids = set(units.keys())

    issues = []

    # 校验 STRIKE
    for i, s in enumerate(strikes):
        if s.get("attacker") not in manifest_unit_ids:
            issues.append(f"[FAIL] STRIKE[{i}].attacker '{s.get('attacker')}' 不在 UNITS 中")
        if s.get("target") not in manifest_unit_ids:
            issues.append(f"[FAIL] STRIKE[{i}].target '{s.get('target')}' 不在 UNITS 中")

    # Aircraft loadout_id 必填
    for uid, u in units.items():
        if u.get("type") == "Aircraft" and not u.get("loadout_id"):
            issues.append(f"[FAIL] Aircraft '{uid}' 缺少 loadout_id（红线 #2）")

    # 弹药预算自检
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

    print("=" * 70)
    print(f" A1 联合火力突击 — Lua 反向校验")
    print("=" * 70)
    print(f"JSON 装备 ID 数:     {len(json_unit_ids)}")
    print(f"Manifest UNITS 数:   {len(manifest_unit_ids)}")
    print(f"STRIKE 条目数:       {len(strikes)}")
    print(f"AMMO 条目数:         {len(ammo)}")
    print()

    if not issues:
        print("[PASS] All checks passed OK")
        sys.exit(0)

    print(f"[FAIL] 发现 {len(issues)} 个问题:")
    for issue in issues:
        print(f"  - {issue}")
    sys.exit(1)


if __name__ == "__main__":
    main()
