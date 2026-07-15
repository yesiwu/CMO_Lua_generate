"""
直接调 mcp/server.py 的轻量示例
（保留作为 mcp/query.py 的精简参考版）
"""
import subprocess, json, os
PY = r"E:\Deep_learning\anconda\python.exe"
SCRIPT = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\server.py"
env = os.environ.copy(); env["SQLITE_DB_PATH"] = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3"
p = subprocess.Popen([PY, SCRIPT], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
def send(m): p.stdin.write((json.dumps(m)+"\n").encode()); p.stdin.flush()
def rid(i):
    while True:
        L = p.stdout.readline().decode().strip()
        if not L: return None
        o = json.loads(L)
        if o.get("id")==i: return o
send({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"d","version":"1"}}})
rid(1); send({"jsonrpc":"2.0","method":"notifications/initialized"})
def q(sql):
    rid_c = 100
    send({"jsonrpc":"2.0","id":rid_c,"method":"tools/call","params":{"name":"read_query","arguments":{"sql":sql}}})
    return json.loads(rid(rid_c)["result"]["content"][0]["text"])
print(q("SELECT ID,Name FROM DataShip WHERE ID IN (2007,3187,3466)"))
p.stdin.close(); p.wait()