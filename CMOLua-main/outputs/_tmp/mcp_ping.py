"""
直接 spawn MCP server.py，按 MCP JSON-RPC 协议通过 stdin/stdout 测试。
验证 server 能不能跑、参数能不能传。
"""
import subprocess, sys, json, os, time
from pathlib import Path

PY = r"E:\Deep_learning\anconda\python.exe"
SCRIPT = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\server.py"
env = os.environ.copy()
env["SQLITE_DB_PATH"] = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3"

p = subprocess.Popen(
    [PY, SCRIPT],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    env=env,
)

def send(msg):
    line = json.dumps(msg) + "\n"
    print(f">>> {line.strip()}")
    p.stdin.write(line.encode("utf-8"))
    p.stdin.flush()

def read_response():
    while True:
        line = p.stdout.readline().decode("utf-8").strip()
        if not line:
            return None
        try:
            obj = json.loads(line)
            if "jsonrpc" in obj:  # 真响应
                print(f"<<< {line}")
                return obj
        except json.JSONDecodeError:
            print(f"<s {line}")

# 1) initialize
send({
  "jsonrpc": "2.0", "id": 1, "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {"name": "test", "version": "0.0.1"}
  }
})
read_response()

# 2) initialized 通知
send({"jsonrpc": "2.0", "method": "notifications/initialized"})

# 3) tools/list
send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
read_response()

# 4) tools/call query_dbid
send({
  "jsonrpc": "2.0", "id": 3, "method": "tools/call",
  "params": {"name": "query_dbid", "arguments": {"query": "J-16", "limit": 3}}
})
read_response()

# 5) tools/call get_dbid_by_country
send({
  "jsonrpc": "2.0", "id": 4, "method": "tools/call",
  "params": {"name": "get_dbid_by_country", "arguments": {"country": "China", "category": "facility", "limit": 5}}
})
read_response()

# 6) tools/call read_query
send({
  "jsonrpc": "2.0", "id": 5, "method": "tools/call",
  "params": {"name": "read_query", "arguments": {"sql": "SELECT ID, Name FROM DataAircraft WHERE Name LIKE '%J-16%' LIMIT 3"}}
})
read_response()

p.stdin.close()
err = p.stderr.read().decode("utf-8", errors="replace")
if err.strip():
    print("STDERR:", err[:1000])
p.wait(timeout=5)
print(f"exit={p.returncode}")
