"""J-15 (dbid=2496) LoadoutID 反向查询：扫描 DataAircraftLoadouts 看哪条 ComponentID=2496 记录"""
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

# 1) 用全表扫描 - 找 ComponentID=2496 的所有记录
print("=== ComponentID=2496 in DataAircraftLoadouts (任何存在) ===")
rows = q("SELECT * FROM DataAircraftLoadouts WHERE ComponentID=2496", 2)
print(f"Count: {len(rows)}")
for r in rows: print(" ", r)

# 2) ComponentID 是反向。ComponentID 是 aircraft-dbid，而 ID 应该是 LoadoutID。
# 刚才查询 SELECT COUNT(*) ComponentID=2496 是 0，说明 2496 不是 ComponentID
# 但 SELECT * WHERE ID=2496 返回多条。
# 所以 字段名可能：
#   ID = Aircraft-dbid (反着的命名!)
#   ComponentID = LoadoutID

# 反过来：WHERE ID=2496 查 LoadoutID
print("\n=== ID=2496 (作 Aircraft-dbid) 关联的 Loadout ===")
rows = q("SELECT ComponentID AS LoadoutID FROM DataAircraftLoadouts WHERE ID=2496", 3)
print(f"Count: {len(rows)}")
loadouts = sorted(set(r["LoadoutID"] for r in rows))
print(f"LoadoutIDs: {loadouts}")

# 3) 验证：找 4817 (J-15D) 的 LoadoutID
print("\n=== J-15D (4817) LoadoutID (反着用) ===")
rows = q("SELECT ComponentID AS LoadoutID FROM DataAircraftLoadouts WHERE ID=4817", 4)
print(f"Count: {len(rows)}")
loadouts2 = sorted(set(r["LoadoutID"] for r in rows))
print(f"LoadoutIDs: {loadouts2}")

# 4) 拿 LoadoutID 列表查 DataLoadout 表
print(f"\n=== J-15 (2496) 全部 Loadout 详情 ===")
lids_str = ",".join(str(x) for x in loadouts)
rows = q(f"""
    SELECT ID, Name, Comments, ROF, Capacity, LoadoutRole,
           DefaultCombatRadius, DefaultTimeOnStation, Deprecated
    FROM DataLoadout
    WHERE ID IN ({lids_str})
    ORDER BY LoadoutRole, ID
""", 5)
print(f"Count: {len(rows)}\n")
for r in rows:
    print(f"  LoadoutID={r['ID']:>5}  ROF={r['ROF']:>2}  Cap={r['Capacity']:>3}  "
          f"Role={r['LoadoutRole']}  Radius={r['DefaultCombatRadius']}nm  "
          f"TOS={r['DefaultTimeOnStation']}s  Dep={r['Deprecated']}  {r['Name']}")

# 5) 对每个 Loadout 查武器清单
print(f"\n=== J-15 (2496) 每个 Loadout 的武器清单 (反舰 ⭐ 高亮) ===")
AS_KEYS = ("YJ", "鹰击", "Kh-31", "Kh-35", "Kh-41", "Moskit", "club", "AS-",
           "Anti-Ship", "C-802", "C-803", "CM-708", "AGM-84", "Harpoon",
           "AGM-65", "鱼雷", "torpedo", "KD-59", "KD-63", "KD-88",
           "鹰击-12", "鹰击-83", "鹰击-62", "鹰击-91", "俄", "Su-33")

for lid in loadouts:
    ws = q(f"""
        SELECT w.ComponentNumber AS mount, w.Optional AS opt, w.Internal AS internal,
               w.ComponentID AS weapon_dbid, dw.Name AS weapon_name
        FROM DataLoadoutWeapons w
        LEFT JOIN DataWeapon dw ON dw.ID = w.ComponentID
        WHERE w.ID={lid}
        ORDER BY w.ComponentNumber
    """, 1000 + lid)
    lname = next((r["Name"] for r in rows if r["ID"] == lid), "?")
    print(f"\n--- LoadoutID={lid}  {lname} ---")
    has_as = False
    if not ws:
        print("  (空)")
        continue
    for w in ws:
        nm = (w.get("weapon_name") or "").lower()
        is_as = any(k.lower() in nm for k in AS_KEYS)
        if is_as: has_as = True
        flag = "  ⭐" if is_as else "    "
        print(f"{flag}  Mount#{w['mount']}  WpnDBID={w['weapon_dbid']:>5}  {w.get('weapon_name')}")
    if has_as: print("  >>> 反舰挂载 ⭐⭐⭐")

p.stdin.close(); p.wait(timeout=5)