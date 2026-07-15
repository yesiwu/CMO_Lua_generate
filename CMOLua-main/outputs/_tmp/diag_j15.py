"""反复横跳测：1) Cursor 客户端通道 2) 直连 server stdin/stdout"""
import subprocess, json, os, sys, time

PY = r"E:\Deep_learning\anconda\python.exe"
SCRIPT = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\server.py"
env = os.environ.copy()
env["SQLITE_DB_PATH"] = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3"

p = subprocess.Popen([PY, SCRIPT], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
print(f"PID: {p.pid}")

def send(msg):
    line = json.dumps(msg) + "\n"
    p.stdin.write(line.encode("utf-8"))
    p.stdin.flush()

def read_id(target_id):
    while True:
        line = p.stdout.readline().decode("utf-8").strip()
        if not line:
            return None
        try:
            obj = json.loads(line)
            if "jsonrpc" in obj and obj.get("id") == target_id:
                return obj
        except Exception:
            pass

# init
send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
       "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                  "clientInfo": {"name": "diag", "version": "1.0"}}})
r = read_id(1)
print("init:", "OK" if r else "FAIL")

send({"jsonrpc": "2.0", "method": "notifications/initialized"})

# === J-15 精准查询 ===
send({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
       "params": {"name": "query_dbid", "arguments": {"query": "J-15", "limit": 10}}})
r = read_id(2)
if r:
    result_text = r["result"]["content"][0]["text"]
    print("\n=== J-15 DBIDs (前 10) ===")
    for item in json.loads(result_text):
        print(f"  dbid={item['dbid']:>5}  type={item['type']:>10}  {item['name']}")
        if item.get('description'): print(f"          desc={item['description']}")
    # 拿第一个 (主型)
    first = json.loads(result_text)[0]
    j15_dbid = first['dbid']
    print(f"\n主型 J-15 DBID = {j15_dbid}")

    # === 反舰挂载 DataAircraftLoadouts ===
    send({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
           "params": {"name": "read_query",
                       "arguments": {"sql": f"SELECT LoadoutID, Name, Category FROM DataAircraftLoadouts WHERE AircraftDBID={j15_dbid} AND (Name LIKE '%反舰%' OR Name LIKE '%Anti-Ship%' OR Name LIKE '%YJ%' OR Name LIKE '%YJ-83%' OR Name LIKE '%YJ-62%' OR Name LIKE '%YJ-12%' OR Name LIKE '%Kh-31%' OR Name LIKE '%AS%' OR Name LIKE '%YJ%' OR Category=4002)"}}})
    r2 = read_id(3)
    if r2:
        rt = r2["result"]["content"][0]["text"]
        rows = json.loads(rt)
        if not rows:
            print("(空)")
        elif isinstance(rows, dict) and "error" in rows:
            print("ERROR:", rows["error"])
        else:
            print(f"\n=== J-15 (DBID={j15_dbid}) 反舰挂载候选 (LoadoutID) ===")
            for r3 in rows:
                if not isinstance(r3, dict): continue
                # 字段名可能是 LoadoutID 或 loadoutid
                lid = r3.get("LoadoutID") or r3.get("loadoutid") or r3.get("LoadoutId")
                cat = r3.get("Category") or r3.get("category")
                nm = r3.get("Name") or r3.get("name")
                print(f"  LoadoutID={lid:>5}  Cat={cat:>4}  {nm}")

    # === 列出所有 J-15 Loadout 数量前 30 ===
    send({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
           "params": {"name": "read_query",
                       "arguments": {"sql": f"SELECT COUNT(*) AS n FROM DataAircraftLoadouts WHERE AircraftDBID={j15_dbid}"}}})
    r3 = read_id(4)
    print(f"\nJ-15 (DBID={j15_dbid}) 总 Loadout 数 = {json.loads(r3['result']['content'][0]['text'])[0]['n']}")

    # === 全部 Loadout 一览前 60（按 Category 排序）===
    send({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
           "params": {"name": "read_query",
                       "arguments": {"sql": f"SELECT LoadoutID, Category, Name FROM DataAircraftLoadouts WHERE AircraftDBID={j15_dbid} ORDER BY Category, LoadoutID LIMIT 60"}}})
    r4 = read_id(5)
    rt = r4["result"]["content"][0]["text"]
    payload = json.loads(rt)
    print(f"\n=== J-15 (DBID={j15_dbid}) 前 60 个 Loadout（按 Category, LoadoutID） ===")
    rows = payload if isinstance(payload, list) else payload.get("rows", [])
    for r5 in rows:
        if not isinstance(r5, dict): continue
        lid = r5.get("LoadoutID") or r5.get("loadoutid") or r5.get("LoadoutId")
        cat = r5.get("Category") or r5.get("category")
        nm = r5.get("Name") or r5.get("name")
        print(f"  LoadoutID={lid:>5}  Cat={cat:>4}  {nm}")
else:
    print("FAIL on query_dbid:", r)

p.stdin.close()
try: err = p.stderr.read().decode("utf-8", errors="replace")
except: err = ""
if err.strip(): print("STDERR:", err[:500])
p.wait(timeout=5)
print(f"exit={p.returncode}")