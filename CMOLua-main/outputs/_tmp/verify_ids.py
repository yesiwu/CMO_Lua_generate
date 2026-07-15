"""验证用户脚本里的 dbid：055D=3883, CG-59 Princeton=2862, YJ-83K weapon"""
import subprocess, json, os
PY = r"E:\Deep_learning\anconda\python.exe"
SCRIPT = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\server.py"
env = os.environ.copy()
env["SQLITE_DB_PATH"] = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3"
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

# 1) 055D 是 3883 吗？
print("=== dbid=3883 是什么 ===")
for r in q("SELECT ID, Name, Type, OperatorCountry FROM DataShip WHERE ID=3883"):
    print(" ", r)

print("\n=== 真正 055A 全部候选 (含 055/RenHai/Nanchang/Tpye 055) ===")
for r in q("""
    SELECT ID, Name, OperatorCountry, YearCommissioned
    FROM DataShip
    WHERE Name LIKE '%055%' OR Name LIKE '%Renhai%' OR Name LIKE '%Type 055%'
    ORDER BY ID
"""):
    print(" ", r)

# 2) CG-59 Princeton 是 2862 吗？
print("\n=== dbid=2862 是什么 ===")
for r in q("SELECT ID, Name, Type, OperatorCountry FROM DataShip WHERE ID=2862"):
    print(" ", r)

print("\n=== CG-59 / Princeton / Ticonderoga 候选 ===")
for r in q("""
    SELECT ID, Name, OperatorCountry, YearCommissioned
    FROM DataShip
    WHERE Name LIKE '%CG-59%' OR Name LIKE '%Princeton%' OR Name LIKE '%Ticonderoga%'
    ORDER BY ID
"""):
    print(" ", r)

# 3) YJ-83K / C-802AK WeaponDBID
print("\n=== YJ-83K / C-802AK weapon dbid ===")
for r in q("""
    SELECT ID, Name, Comments
    FROM DataWeapon
    WHERE Name LIKE '%YJ-83%'
       OR Name LIKE '%C-802%'
       OR Name LIKE '%YJ-8%'
       OR Name LIKE '%Eris%'
       OR Name LIKE '%C-802A%'
    ORDER BY Name
"""):
    print(" ", r)

p.stdin.close(); p.wait(timeout=5)