"""验证 3 艘航母 type/category，以及它们能不能直接 type='Ship' AddUnit"""
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

rid_counter = 10
def q(sql):
    global rid_counter; rid_counter += 1
    send({"jsonrpc":"2.0","id":rid_counter,"method":"tools/call","params":{"name":"read_query","arguments":{"sql":sql}}})
    r = rid(rid_counter); return json.loads(r["result"]["content"][0]["text"])

def desc(t, id_):
    send({"jsonrpc":"2.0","id":id_,"method":"tools/call","params":{"name":"describe_table","arguments":{"table_name":t}}})
    r = rid(id_); return json.loads(r["result"]["content"][0]["text"])

# 1) 3 艘航母完整属性
print("=== 3 艘航母全字段 ===")
for r in q("SELECT * FROM DataShip WHERE ID IN (2007, 3187, 3466)"):
    print(f"\nDBID={r['ID']}  {r['Name']}")
    for k, v in r.items():
        if k in ("Name",): continue
        print(f"  {k} = {v}")

# 2) EnumShipType / Category
print("\n=== EnumShipType (全部 / 含 Carrier) ===")
for r in q("SELECT * FROM EnumShipType ORDER BY ID"):
    nm = r.get("Description") or r.get("Name") or "?"
    if "Carrier" in nm or "Aircraft" in nm or "Cruiser" in nm or "Destroyer" in nm or "Frig" in nm or "CV" in nm or "Tanker" in nm:
        print(f"  {r['ID']:>5}  {nm}")

# 3) Ship Type&Category enum 表名
print("\n=== Enum 表中含 'Ship' / 'Type' 的 ===")
for r in q("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE 'EnumShip%' OR name LIKE 'EnumCat%')"):
    print(" ", r["name"])

p.stdin.close(); p.wait(timeout=5)