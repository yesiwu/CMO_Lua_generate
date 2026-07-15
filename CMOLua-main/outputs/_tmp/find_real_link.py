"""验证 J-15 在 DataAircraftLoadouts 表里到底用哪个 ComponentID"""
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

# 1) 看 2496 这个飞机真实存在吗 + 字段
print("=== DataAircraft head 1 ===")
r = q("SELECT * FROM DataAircraft WHERE ID=2496", 2)
print(r)

# 2) 看 2496 在 DataAircraftLoadouts 里有没有
print("\n=== 2496 in DataAircraftLoadouts? ===")
r = q("SELECT COUNT(*) AS n FROM DataAircraftLoadouts WHERE ComponentID=2496", 3)
print(r)

# 3) 看 J-15 (2496) 的 ComponentNumber（如果存在）
print("\n=== 看 2496 是 ComponentNumber 还是 ComponentID ===")
r = q("SELECT COUNT(*) AS n FROM DataAircraftLoadouts WHERE ComponentNumber=2496", 4)
print("ComponentNumber=2496:", r)

# 4) 既然 2496 是 ComponentID=2496 但 DataAircraftLoadouts 是另一表
#    J-15 的 Loadout 究竟存哪？看 ComponentID 在 [2490..2500] 范围的
print("\n=== ComponentID 附近 5 个范围 ===")
for dbid in [2496, 4817, 6098, 2497, 2498, 4957]:
    cnt = q(f"SELECT COUNT(*) AS n FROM DataAircraftLoadouts WHERE ComponentID={dbid}", dbid+100)
    print(f"  ComponentID={dbid}: {cnt}")

# 5) J-15 主型 2496 是 Aircraft 里 ID，但 DataAircraftLoadouts 的 ComponentID 可能指不同的 entity type
#    找 J-15 name 在 DataAircraft 的所有变体
print("\n=== J-15 in DataAircraft ===")
r = q("SELECT ID, Name, OperatorCountry FROM DataAircraft WHERE Name LIKE '%J-15%'", 100)
print(r)

# 6) 看 DataAircraftLoadouts 表有几个不同 aircraft
print("\n=== ComponentID 不同且和 2496 接近的 ===")
r = q("""
    SELECT ComponentID, COUNT(*) AS n
    FROM DataAircraftLoadouts
    WHERE ComponentID BETWEEN 2400 AND 2600
    GROUP BY ComponentID ORDER BY ComponentID
""", 101)
for r2 in r: print(" ", r2)

# 7) 看 J-15 (2496) 的 Loadout 真实存哪？
#    可能是 DataAircraftLoadout 主键命名是 ID/ComponentID 但是反过来了 — ID=飞机, ComponentID=Loadout
#    测试一下：看 Loadout 表里 ID=2496 的
print("\n=== DataAircraftLoadouts WHERE ID=2496 (反着用) ===")
r = q("SELECT * FROM DataAircraftLoadouts WHERE ID=2496", 200)
print(r)

p.stdin.close(); p.wait(timeout=5)