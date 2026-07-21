"""
mcp_query.py — 智能 MCP 查询 wrapper

解决问题：Cursor MCP client 偶发吞参数（Input validation error: 'xxx' is required）
策略：
  1. 优先用 subprocess 直连 mcp/server.py 走 JSON-RPC stdio（已验证 100% 通）
  2. Cursor 端 CallMcpTool 容易丢第一次参数；wrapper 内部已经稳

用法（在 Cursor 里）：
  from mcp_query import query_dbid, read_query, get_dbid_by_name, describe_table
  print(query_dbid("J-15"))
  print(read_query("SELECT ID,Name FROM DataShip WHERE ID=2007"))
"""
import json
import os
from pathlib import Path
import subprocess
import sys

# 路径跟随当前 Skill 安装位置，不依赖开发者机器上的绝对路径。
_MCP_DIR = Path(__file__).resolve().parent
_PY = sys.executable
_SCRIPT = str(_MCP_DIR / "server.py")
_DEFAULT_DB = str(_MCP_DIR / "db" / "DB3K_504.db3")


def _send(p, msg):
    p.stdin.write((json.dumps(msg) + "\n").encode("utf-8"))
    p.stdin.flush()


def _read_response(p, expect_id):
    """读取 JSON-RPC 响应行，匹配 expect_id"""
    while True:
        line = p.stdout.readline()
        if not line:
            return None
        line = line.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("id") == expect_id:
            return obj
        # 跳过 notifications 或其它 id


def _parse_tool_result(resp):
    """从 JSON-RPC tools/call 响应里提取实际数据"""
    if not resp:
        return None
    if "error" in resp:
        raise RuntimeError(f"MCP error: {resp['error']}")
    result = resp.get("result", {})
    content = result.get("content", [])
    if not content:
        return result
    text = content[0].get("text", "")
    if not text:
        return result
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


class McpSession:
    """复用单次连接，避免每次查询都冷启"""
    def __init__(self):
        env = os.environ.copy()
        # 调用方可通过 SQLITE_DB_PATH 指定数据库；未指定时使用 Skill 默认库。
        env["SQLITE_DB_PATH"] = env.get("SQLITE_DB_PATH", _DEFAULT_DB)
        self.proc = subprocess.Popen(
            [_PY, _SCRIPT],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            bufsize=0,
        )
        self._id = 0
        _send(self.proc, {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "mcp_query_wrapper", "version": "1.0"}
            }
        })
        _read_response(self.proc, 1)
        _send(self.proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})

    def call(self, tool_name, arguments):
        self._id += 1
        _send(self.proc, {
            "jsonrpc": "2.0", "id": self._id, "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments}
        })
        resp = _read_response(self.proc, self._id)
        return _parse_tool_result(resp)

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=2)
        except Exception:
            self.proc.kill()


_session: "McpSession | None" = None


def _get_session():
    global _session
    if _session is None:
        _session = McpSession()
    return _session


# ====== 公共 API ======
def query_dbid(query, limit=50):
    """自然语言查询 DBID"""
    return _get_session().call("query_dbid", {"query": query, "limit": limit})


def get_dbid_by_name(name):
    """精确名称匹配"""
    return _get_session().call("get_dbid_by_name", {"name": name})


def get_dbid_by_country(country, type_=None):
    """按国家筛选装备"""
    args = {"country": country}
    if type_:
        args["type"] = type_
    return _get_session().call("get_dbid_by_country", args)


def list_tables():
    """列出所有表"""
    return _get_session().call("list_tables", {})


def describe_table(table_name):
    """查看表结构"""
    return _get_session().call("describe_table", {"table_name": table_name})


def read_query(
    sql,
    params=None,
    *,
    fetch_all=True,
    row_limit=1000,
):
    """执行带参数的只读 SELECT 查询。"""
    return _get_session().call(
        "read_query",
        {
            "sql": sql,
            "params": list(params or ()),
            "fetch_all": fetch_all,
            "row_limit": row_limit,
        },
    )


# ====== CLI 入口（可直接 python mcp_query.py dbid "J-15"）======
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  python mcp_query.py dbid <query>")
        print("  python mcp_query.py name <name>")
        print("  python mcp_query.py sql <sql>")
        print("  python mcp_query.py desc <table>")
        print("  python mcp_query.py tables")
        sys.exit(1)
    cmd = sys.argv[1]
    try:
        if cmd == "dbid":
            print(json.dumps(query_dbid(" ".join(sys.argv[2:])), ensure_ascii=False, indent=2))
        elif cmd == "name":
            print(json.dumps(get_dbid_by_name(" ".join(sys.argv[2:])), ensure_ascii=False, indent=2))
        elif cmd == "sql":
            print(json.dumps(read_query(" ".join(sys.argv[2:])), ensure_ascii=False, indent=2))
        elif cmd == "desc":
            print(json.dumps(describe_table(sys.argv[2]), ensure_ascii=False, indent=2))
        elif cmd == "tables":
            print(json.dumps(list_tables(), ensure_ascii=False, indent=2))
        else:
            print(f"未知命令: {cmd}")
            sys.exit(1)
    finally:
        if _session:
            _session.close()
