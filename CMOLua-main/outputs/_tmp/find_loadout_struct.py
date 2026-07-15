"""枚举 J-15 (2496) 所有 LoadoutID + 看武器挂载表"""
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

send({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"d","version":"1"}}})
rid(1); send({"jsonrpc":"2.0","method":"notifications/initialized"})

def q(sql, id_):
    send({"jsonrpc":"2.0","id":id_,"method":"tools/call","params":{"name":"read_query","arguments":{"sql":sql}}})
    r=rid(id_)
    txt = r["result"]["content"][0]["text"]
    try: return json.loads(txt)
    except: return txt

# 1) J-15 主型 (2496) 全部 LoadoutID
print("=== J-15 (2496) LoadoutID ===")
rows = q("SELECT DISTINCT ID FROM DataAircraftLoadouts WHERE ComponentID=2496 ORDER BY ID", 2)
if isinstance(rows, list):
    print(f"Total distinct LoadoutIDs: {len(rows)}")
    loadouts = [r["ID"] for r in rows]
    print("IDs:", loadouts)
else:
    print(rows)

# 2) 看 Loadout → 武器的关联表
print("\n=== 找 'Loadout → 武器' 关联表 ===")
tables = q("SELECT name FROM sqlite_master WHERE type='table' AND lower(name) LIKE '%loadout%'", 3)
for t in tables: print(" ", t["name"])

# 3) 看 schema
for tname in ["DataLoadout", "DataAircraftLoadout", "DataLoadoutWeapons", "DataLoadoutItems", "DataLoadoutMunition", "DataWeaponLoadout"]:
    print(f"\n--- {tname} ---")
    try:
        send({"jsonrpc":"2.0","id":hash(tname)&0xFFFF,"method":"tools/call","params":{"name":"describe_table","arguments":{"table_name":tname}}})
        r = rid(hash(tname)&0xFFFF)
        for c in json.loads(r["result"]["content"][0]["text"]):
            print(" ", c["name"], c["type"])
        # 看 3 行
        send({"jsonrpc":"2.0","id":(hash(tname)&0xFFFF)+1,"method":"tools/call","params":{"name":"read_query","arguments":{"sql":f"SELECT * FROM {tname} LIMIT 3"}}})
        r2 = rid((hash(tname)&0xFFFF)+1)
        print(" sample:", r2["result"]["content"][0]["text"][:400])
    except Exception as e:
        print(" err:", e)

p.stdin.close(); p.wait(timeout=5)