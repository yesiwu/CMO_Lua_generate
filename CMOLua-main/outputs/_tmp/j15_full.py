"""完整查 J-15 (2496) 所有 Loadout + 武器清单 + 名称翻译"""
import subprocess, json, os
PY = r"E:\Deep_learning\anconda\python.exe"
SCRIPT = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\server.py"
env = os.environ.copy(); env["SQLITE_DB_PATH"] = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3"

p = subprocess.Popen([PY, SCRIPT], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
def send(m): p.stdin.write((json.dumps(m)+"\n").encode("utf-8")); p.stdin.flush()
def rid(i):
    while True:
        L = p.stdout.readline().decode("utf-8").strip()
        if not L: return None
        o = json.loads(L)
        if o.get("id")==i: return o
def q(sql, i):
    send({"jsonrpc":"2.0","id":i,"method":"tools/call","params":{"name":"read_query","arguments":{"sql":sql}}})
    r = rid(i); return json.loads(r["result"]["content"][0]["text"])

send({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"d","version":"1"}}})
rid(1); send({"jsonrpc":"2.0","method":"notifications/initialized"})

# 1) J-15 主型 DBID=2496 的所有 Loadout (ID, Name, ROF, Capacity, LoadoutRole)
print("=== J-15 (2496) 所有 Loadout ===")
rows = q("""
    SELECT DISTINCT al.ID, dl.Name, dl.Comments, dl.ROF, dl.Capacity,
           dl.LoadoutRole, dl.DefaultCombatRadius, dl.DefaultTimeOnStation, dl.Deprecated
    FROM DataAircraftLoadouts al
    JOIN DataLoadout dl ON dl.ID = al.ID
    WHERE al.ComponentID=2496 AND (dl.Deprecated=0 OR dl.Deprecated IS NULL)
    ORDER BY dl.LoadoutRole, al.ID
""", 2)
print(f"Count: {len(rows)}\n")
for r in rows:
    print(f"  LoadoutID={r['ID']:>5}  ROF={r['ROF']}  Cap={r['Capacity']:>3}  Role={r['LoadoutRole']}  "
          f"Radius={r['DefaultCombatRadius']}nm TOS={r['DefaultTimeOnStation']}s  {r['Name']}")

# 2) 每个 Loadout 的武器 (with weapon name)
print("\n=== J-15 (2496) 每个 Loadout 的武器清单 (反舰/空地优先显示) ===")
all_loadouts = q("""
    SELECT DISTINCT al.ID, dl.Name
    FROM DataAircraftLoadouts al JOIN DataLoadout dl ON dl.ID=al.ID
    WHERE al.ComponentID=2496 AND (dl.Deprecated=0 OR dl.Deprecated IS NULL)
    ORDER BY al.ID
""", 3)

# 一次性查所有 weapons 表 + 武器名称 JOIN
weapons_by_loadout = {}
for L in all_loadouts:
    lid = L["ID"]
    ws = q(f"""
        SELECT w.ComponentNumber AS mount, w.Optional AS opt, w.Internal AS internal,
               w.ComponentID AS weapon_dbid, dw.Name AS weapon_name
        FROM DataLoadoutWeapons w
        LEFT JOIN DataWeapon dw ON dw.ID = w.ComponentID
        WHERE w.ID={lid}
        ORDER BY w.ComponentNumber
    """, lid + 1000)
    weapons_by_loadout[lid] = (L["Name"], ws)

# 反舰关键词
AS_KEYS = ("YJ", "Eagle", "Eris", "KAB", "Kh-31", "Kh-35", "Kh-41", "Moskit",
           "Anti-Ship", "AS-", "YJ-12", "YJ-62", "YJ-83", "YJ-91", "CM-708",
           "反舰", "鹰击", "俄", "club", "klub")

print(f"\n找到 {len(all_loadouts)} 个 Loadout\n")
for lid, (lname, ws) in weapons_by_loadout.items():
    print(f"--- LoadoutID={lid}  {lname} ---")
    if not ws:
        print("  (无武器/空挂载)")
        continue
    has_as = False
    for w in ws:
        nm = (w.get("weapon_name") or "").lower()
        is_as = any(k.lower() in nm for k in AS_KEYS)
        if is_as: has_as = True
        flag = "  ⭐" if is_as else "    "
        print(f"{flag}  Mount#{w['mount']}  WpnDBID={w['weapon_dbid']:>5}  {w.get('weapon_name')}")
    if has_as: print("  >>> 反舰挂载 ⭐")

p.stdin.close(); p.wait(timeout=5)