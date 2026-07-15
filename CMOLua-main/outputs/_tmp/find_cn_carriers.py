"""查 Liaoning / Shandong / Fujian 航母 + 留意 CV 命名习惯。
也顺便看 003 / Type 003 / 常规动力 / 核动力的关键字段。
"""
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

# 1) 看 DataShip schema（注意 type 字段名）
print("=== DataShip schema 前 20 列 ===")
send({"jsonrpc":"2.0","id":99,"method":"tools/call","params":{"name":"describe_table","arguments":{"table_name":"DataShip"}}})
r = rid(99); cols = json.loads(r["result"]["content"][0]["text"])
for c in cols[:20]: print(" ", c["name"], c["type"])

# 2) 看 operator country 枚举
print("\n=== 中国/PLAN 相关枚举 ===")
for r in q("SELECT * FROM EnumOperatorCountry WHERE Description LIKE '%China%' OR Description LIKE '%Chinese%' LIMIT 10"):
    print(" ", r)

# 3) PRIMARY KEY — 因 DB3K 自带三个表 ID 不同，直接搜名字
print("\n=== Liaoning / Shandong / Fujian (主名匹配) ===")
for r in q("""
    SELECT ID, Name, Comments, OperatorCountry
    FROM DataShip
    WHERE Name LIKE '%Liaoning%'
       OR Name LIKE '%Shandong%'
       OR Name LIKE '%Fujian%'
       OR Name LIKE '%Type 001%'
       OR Name LIKE '%Type 002%'
       OR Name LIKE '%Type 003%'
    ORDER BY Name
"""):
    print(" ", r)

# 4) 模糊匹配 (含 CV / 航母关键字)
print("\n=== 模糊匹配 航母 (carrier/PLAN) ===")
for r in q("""
    SELECT ID, Name, Comments, OperatorCountry
    FROM DataShip
    WHERE (Name LIKE '%CV%' OR Name LIKE '%Carrier%')
      AND (OperatorCountry=2018 OR Name LIKE '%PLAN%' OR Name LIKE '%Liaoning%' OR Name LIKE '%Shandong%' OR Name LIKE '%Fujian%')
    ORDER BY Name
"""):
    print(" ", r)

# 5) operator 2018（China）所有 ships 中名字里含"PLA"或"PLAN"字样的
print("\n=== OperatorCountry=2018 (中国) 所有 Ship (前 30) ===")
rows = q("""
    SELECT ID, Name, Comments
    FROM DataShip
    WHERE OperatorCountry=2018
    ORDER BY ID LIMIT 100
""")
print(f"共 {len(rows)} 条 PLAN 船舶")
for r in rows[:30]: print(" ", r)

p.stdin.close(); p.wait(timeout=5)