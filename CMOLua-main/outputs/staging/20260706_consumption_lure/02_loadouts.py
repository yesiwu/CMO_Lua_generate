"""EA-18G Loadout 深查 — 修 JSON 解析 bug"""
import json
import subprocess
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


# EA-18G Loadout 列所有
print(">>> EA-18G (dbid=343) 所有 LoadoutIDs")
for r in call_sql("SELECT ID, Name FROM DataAircraftLoadouts WHERE ComponentID = 343 ORDER BY ID"):
    if isinstance(r, dict):
        print(f"   LoadoutID={r.get('ID'):5d}  name={r.get('Name')}")
    elif isinstance(r, list):
        for x in r:
            print(f"   LoadoutID={x.get('ID'):5d}  name={x.get('Name')}")

# 顺便: J-16D (4632) Loadout 也来
print("\n>>> J-16D (dbid=4632) 所有 LoadoutIDs")
for r in call_sql("SELECT ID, Name FROM DataAircraftLoadouts WHERE ComponentID = 4632 ORDER BY ID"):
    if isinstance(r, dict):
        print(f"   LoadoutID={r.get('ID'):5d}  name={r.get('Name')}")
    elif isinstance(r, list):
        for x in r:
            print(f"   LoadoutID={x.get('ID'):5d}  name={x.get('Name')}")

# 列 DataLoadout 看具体武器
print("\n>>> DataLoadout 第 1821 行")
for r in call_sql("SELECT * FROM DataLoadout WHERE LoadoutID = 1821"):
    if isinstance(r, dict):
        for k, v in r.items():
            print(f"   {k}: {v}")
    elif isinstance(r, list):
        for x in r:
            for k, v in x.items():
                print(f"   {k}: {v}")

# 列 DataLoadoutWeapons 看每个Loadout的武器数量
print("\n>>> J-16 Loadout 1821 的武器内容 (DataLoadoutWeapons + DataWeapon)")
for r in call_sql("""
SELECT lw.Quantity, w.Name AS WeaponName
FROM DataLoadoutWeapons lw
JOIN DataWeapon w ON lw.WeaponID = w.ID
WHERE lw.LoadoutID = 1821
ORDER BY lw.Quantity DESC
"""):
    if isinstance(r, dict):
        print(f"   qty={r.get('Quantity'):3d}  {r.get('WeaponName')}")

print("\n>>> J-16 Loadout 3272 的武器")
for r in call_sql("""
SELECT lw.Quantity, w.Name AS WeaponName
FROM DataLoadoutWeapons lw
JOIN DataWeapon w ON lw.WeaponID = w.ID
WHERE lw.LoadoutID = 3272
ORDER BY lw.Quantity DESC
"""):
    if isinstance(r, dict):
        print(f"   qty={r.get('Quantity'):3d}  {r.get('WeaponName')}")