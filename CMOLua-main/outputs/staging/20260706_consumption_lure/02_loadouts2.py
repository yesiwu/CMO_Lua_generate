"""Loadout 完整深查 + 全部组装 resolved.json"""
import json
import subprocess
from pathlib import Path
import os

env = os.environ.copy()
env["SQLITE_DB_PATH"] = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3"
env["PYTHONIOENCODING"] = "utf-8"


def call_sql(sql: str):
    reqs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "phase2", "version": "1.0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "read_query",
                    "arguments": {"sql": sql}}},
    ]
    payload = "\n".join(json.dumps(r, ensure_ascii=False) for r in reqs) + "\n"
    proc = subprocess.run(
        [r"E:\Deep_learning\anconda\python.exe",
         r"C:\Users\user\.codex\skills\CMOLua-main\mcp\server.py"],
        input=payload.encode("utf-8"),
        capture_output=True, timeout=30, env=env,
    )
    out = proc.stdout.decode("utf-8", errors="replace")
    for line in reversed(out.splitlines()):
        line = line.strip()
        if not line: continue
        try:
            obj = json.loads(line)
            if "result" in obj and "content" in obj["result"]:
                return json.loads(obj["result"]["content"][0]["text"])
        except Exception:
            continue
    return []


# J-16 Loadout 1821 / 3272 的武器
print("=" * 60)
print("J-16 Loadout 1821 — 武器清单")
print("=" * 60)
rows = call_sql("""
SELECT lw.Quantity, w.ID, w.Name
FROM DataLoadoutWeapons lw
JOIN DataWeapon w ON lw.WeaponID = w.ID
WHERE lw.LoadoutID = 1821 ORDER BY lw.Quantity DESC
""")
for r in rows:
    print(f"   qty={r.get('Quantity'):3d}  dbid={r.get('ID'):5d}  {r.get('Name')}")

print("\n>>> J-16 Loadout 3272")
rows = call_sql("""
SELECT lw.Quantity, w.ID, w.Name
FROM DataLoadoutWeapons lw
JOIN DataWeapon w ON lw.WeaponID = w.ID
WHERE lw.LoadoutID = 3272 ORDER BY lw.Quantity DESC
""")
for r in rows:
    print(f"   qty={r.get('Quantity'):3d}  dbid={r.get('ID'):5d}  {r.get('Name')}")

# EA-18G Loadout
print("\n" + "=" * 60)
print("EA-18G LoadoutIDs (ComponentID = 343)")
print("=" * 60)
# Schema 没 ID 列, 试试 RAW 看实际返回
rows = call_sql("SELECT * FROM DataAircraftLoadouts WHERE ComponentID = 343")
print(f"   returned {len(rows)} rows:")
for r in rows[:20]:
    print(f"   {r}")

# 估计 LoadoutIDs (list of ints from DataLoadout where name has EA-18G)
print("\n>>> EA-18G Loadouts from DataLoadout by Name pattern")
rows = call_sql("SELECT ID, Name, Comments FROM DataLoadout WHERE Name LIKE '%EA-18G%' LIMIT 20")
for r in rows:
    print(f"   LoadoutID={r.get('ID'):5d}  Name={r.get('Name')!r}")

# 如果没,试 AESA/Growler
print("\n>>> Growler / AESA loadouts")
rows = call_sql("SELECT ID, Name, Comments FROM DataLoadout WHERE Name LIKE '%Growler%' LIMIT 10")
for r in rows:
    print(f"   LoadoutID={r.get('ID'):5d}  Name={r.get('Name')!r}")

# 通用 - 看 ComponentID 343 关联的 LoadoutID
print("\n>>> 关联 ComponentID=343 的 LoadoutIDs 全部")
rows = call_sql("SELECT DISTINCT LoadoutID FROM DataAircraftLoadouts WHERE ComponentID = 343")
print(f"   returned {len(rows)} rows")
for r in rows[:20]:
    if isinstance(r, dict):
        print(f"   LoadoutID={r.get('LoadoutID')}")
    elif isinstance(r, list):
        for x in r:
            print(f"   LoadoutID={x.get('LoadoutID')}")