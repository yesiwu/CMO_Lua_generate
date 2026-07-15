"""看 DataAircraftLoadouts 实际 schema"""
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

# schema
send({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"describe_table","arguments":{"table_name":"DataAircraftLoadouts"}}})
r=rid(2); print("=== DataAircraftLoadouts schema ===")
for col in json.loads(r["result"]["content"][0]["text"]):
    print(" ", col)

# 头 3 行
send({"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"read_query","arguments":{"sql":"SELECT * FROM DataAircraftLoadouts LIMIT 3"}}})
r=rid(3); print("\n=== head 3 rows ===")
print(r["result"]["content"][0]["text"][:1500])

# 看 J-15 (2496) loadout 总数
send({"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"read_query","arguments":{"sql":"SELECT COUNT(*) FROM DataAircraftLoadouts WHERE AircraftDBID=2496"}}})
r=rid(4); print("\nJ-15 loadout count:", r["result"]["content"][0]["text"])

# 头 20
send({"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"read_query","arguments":{"sql":"SELECT * FROM DataAircraftLoadouts WHERE AircraftDBID=2496 ORDER BY LoadoutID LIMIT 20"}}})
r=rid(5); print("\n=== J-15 first 20 loadouts ===")
print(r["result"]["content"][0]["text"][:3500])

p.stdin.close(); p.wait(timeout=5)