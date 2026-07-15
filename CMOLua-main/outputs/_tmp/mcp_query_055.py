import json
import os
import site
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
server = root / "mcp" / "server.py"
db = root / "mcp" / "db" / "DB3K_504.db3"

env = os.environ.copy()
env["SQLITE_DB_PATH"] = str(db)
env["PYTHONPATH"] = site.getusersitepackages() + os.pathsep + env.get("PYTHONPATH", "")


def send(proc, msg):
    proc.stdin.write((json.dumps(msg) + "\n").encode("utf-8"))
    proc.stdin.flush()


def read_id(proc, msg_id):
    while True:
        line = proc.stdout.readline()
        if not line:
            return None
        try:
            obj = json.loads(line.decode("utf-8"))
        except json.JSONDecodeError:
            continue
        if obj.get("id") == msg_id:
            return obj


def tool_text(response):
    content = response["result"]["content"][0]["text"]
    return json.loads(content)


proc = subprocess.Popen(
    [sys.executable, str(server)],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    env=env,
)

try:
    send(
        proc,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "codex-dbid-query", "version": "1.0"},
            },
        },
    )
    read_id(proc, 1)
    send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})

    send(
        proc,
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "query_dbid", "arguments": {"query": "055", "limit": 20}},
        },
    )
    natural = tool_text(read_id(proc, 2))

    sql = """
SELECT ID AS dbid, Name AS name, Type, OperatorCountry, YearCommissioned,
       YearDecommissioned, Deprecated, Comments AS description
FROM DataShip
WHERE Name LIKE '%Type 055%' OR Name LIKE '%055 Renhai%'
ORDER BY COALESCE(Deprecated, 0), ID
"""
    send(
        proc,
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "read_query", "arguments": {"sql": sql, "row_limit": 20}},
        },
    )
    exact = tool_text(read_id(proc, 3))

    print(json.dumps({"query_dbid_055": natural, "read_query_type_055": exact}, ensure_ascii=False, indent=2))
finally:
    try:
        proc.stdin.close()
        proc.terminate()
        proc.wait(timeout=3)
    except Exception:
        proc.kill()
