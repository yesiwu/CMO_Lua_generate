"""
MCP server providing natural-language DBID lookup against the CMO sqlite database.
"""
import sys
import sqlite3
import os
import re
import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
import asyncio

# Make project root importable
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# --- DB path & connections ----------------------------------------------------
def get_db_path() -> Path:
    env_path = os.environ.get('SQLITE_DB_PATH')
    if env_path:
        return Path(env_path)
    return Path(__file__).parent / "db" / "DB3K_504.db3"


DB_PATH = get_db_path()

QUERY_TIMEOUT = 10    # seconds for sqlite3.connect timeout
CACHE_TTL_SHORT = 30
CACHE_TTL_LONG = 60

_conn: Optional[sqlite3.Connection] = None
_cache: Dict[str, tuple] = {}
_TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_db_exists():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"数据库文件未找到: {DB_PATH}\n"
            "请将 CMO 数据库文件 (如 DB3K_504.db3) 复制到此目录。"
        )


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(
            str(DB_PATH),
            timeout=QUERY_TIMEOUT,
            check_same_thread=False,
        )
        _conn.row_factory = sqlite3.Row
        try:
            _conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.OperationalError:
            pass
    return _conn


def cache_get(key: str):
    if key in _cache:
        exp, val = _cache[key]
        if time.time() < exp:
            return val
        _cache.pop(key, None)
    return None


def cache_set(key: str, val, ttl: int = CACHE_TTL_SHORT):
    _cache[key] = (time.time() + ttl, val)


def contains_multiple_statements(sql: str) -> bool:
    in_s, in_d = False, False
    for c in sql:
        if c == "'" and not in_d:
            in_s = not in_s
        elif c == '"' and not in_s:
            in_d = not in_d
        elif c == ';' and not in_s and not in_d:
            return True
    return False


# --- Tool implementations ------------------------------------------------------
def query_dbid_impl(query: str, limit: int = 50) -> List[Dict[str, Any]]:
    validate_db_exists()
    query = query.strip()

    cache_key = f"qdbid:{query}:{limit}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    if query.lower().startswith('select'):
        result = read_query_impl(query, row_limit=limit)
        cache_set(cache_key, result)
        return result

    search_pattern = f"%{query}%"
    all_results = []

    try:
        conn = get_conn()
        cursor = conn.cursor()

        # 4 分类表并行扫描（共享同一连接）
        categories = [
            ("DataAircraft", "Aircraft"),
            ("DataShip", "Ship"),
            ("DataSubmarine", "Submarine"),
            ("DataFacility", "Facility"),
        ]
        for table, unit_type in categories:
            sql = f"""
                SELECT ID as dbid, Name as name, ? as type,
                       OperatorCountry as country, Comments as description
                FROM {table}
                WHERE Name LIKE ? OR Comments LIKE ?
                LIMIT ?
            """
            try:
                cursor.execute(sql, (unit_type, search_pattern, search_pattern, limit))
            except sqlite3.OperationalError:
                continue
            for row in cursor.fetchall():
                all_results.append(dict(row))

        result = all_results[:limit]
        cache_set(cache_key, result)
        return result
    except sqlite3.OperationalError:
        return fallback_query(query, limit)


def fallback_query(query: str, limit: int) -> List[Dict[str, Any]]:
    search_pattern = f"%{query}%"
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ID as dbid, Name as name, 'Aircraft' as type, OperatorCountry as country
            FROM DataAircraft
            WHERE Name LIKE ? OR Comments LIKE ?
            LIMIT ?
        """, (search_pattern, search_pattern, limit))
        results = cursor.fetchall()
        if results:
            return [dict(row) for row in results]
    except sqlite3.OperationalError:
        pass
    return [{"error": "未找到匹配的装备", "query": query}]


def read_query_impl(sql: str, params: Optional[List[Any]] = None,
                    fetch_all: bool = True, row_limit: int = 1000) -> List[Dict[str, Any]]:
    validate_db_exists()
    sql = sql.strip()
    if sql.endswith(';'):
        sql = sql[:-1].strip()
    if contains_multiple_statements(sql):
        raise ValueError("Multiple SQL statements are not allowed")
    sql_lower = sql.lower()
    if not any(sql_lower.startswith(p) for p in ('select', 'with')):
        raise ValueError("Only SELECT queries (including WITH clauses) are allowed")

    cache_key = f"rquery:{hash((sql, repr(params), row_limit))}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    params = params or []
    try:
        conn = get_conn()
        cursor = conn.cursor()
        if 'limit' not in sql_lower:
            sql = f"{sql} LIMIT {row_limit}"
        cursor.execute(sql, params)
        rows = cursor.fetchall() if fetch_all else [cursor.fetchone()]
        result = [dict(row) for row in rows if row is not None]
        cache_set(cache_key, result)
        return result
    except sqlite3.Error as e:
        raise ValueError(f"SQLite error: {str(e)}")


def list_tables_impl() -> List[str]:
    cache_key = "list_tables"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    validate_db_exists()
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table'
        ORDER BY name
    """)
    result = [row['name'] for row in cursor.fetchall()]
    cache_set(cache_key, result, ttl=CACHE_TTL_LONG)
    return result


def describe_table_impl(table_name: str) -> List[Dict[str, str]]:
    validate_db_exists()

    # 第一层：正则白名单防 SQL 注入
    if not _TABLE_RE.match(table_name):
        raise ValueError(f"非法表名 '{table_name}'：仅允许字母数字下划线")

    # 第二层：实际表名白名单
    valid_tables = set(list_tables_impl())
    if table_name not in valid_tables:
        raise ValueError(f"Table '{table_name}' does not exist")

    # 复用只读连接查 PRAGMA
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    return [dict(row) for row in columns]


def get_dbid_by_name_impl(name: str) -> Dict[str, Any]:
    validate_db_exists()
    search_pattern = f"%{name}%"

    cache_key = f"gdbid:{name}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    tables = [
        ("DataAircraft", "Aircraft"),
        ("DataShip", "Ship"),
        ("DataSubmarine", "Submarine"),
        ("DataFacility", "Facility"),
    ]
    conn = get_conn()
    for table, unit_type in tables:
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT ID as dbid, Name as name, ? as type, "
                f"OperatorCountry as country, Comments as description "
                f"FROM {table} WHERE Name LIKE ? LIMIT 1",
                (unit_type, search_pattern)
            )
            result = cursor.fetchone()
            if result:
                d = dict(result)
                cache_set(cache_key, d)
                return d
        except sqlite3.OperationalError:
            continue

    err = {"error": f"未找到 '{name}' 的 DBID"}
    cache_set(cache_key, err)
    return err


def get_dbid_by_country_impl(country: str, category: Optional[str] = None,
                             limit: int = 20) -> List[Dict[str, Any]]:
    validate_db_exists()
    search_pattern = f"%{country}%"
    all_results = []
    try:
        conn = get_conn()
        cursor = conn.cursor()

        if not category or 'air' in category.lower():
            try:
                cursor.execute("""
                    SELECT ID as dbid, Name as name, 'Aircraft' as type,
                           OperatorCountry as country, Comments as description
                    FROM DataAircraft WHERE OperatorCountry LIKE ? LIMIT ?
                """, (search_pattern, limit))
                for row in cursor.fetchall():
                    all_results.append(dict(row))
            except sqlite3.OperationalError:
                pass

        if not category or any(k in category.lower() for k in ('ship', 'naval', 'boat')):
            try:
                cursor.execute("""
                    SELECT ID as dbid, Name as name, 'Ship' as type,
                           OperatorCountry as country, Comments as description
                    FROM DataShip WHERE OperatorCountry LIKE ? LIMIT ?
                """, (search_pattern, limit))
                for row in cursor.fetchall():
                    all_results.append(dict(row))
            except sqlite3.OperationalError:
                pass

        result = all_results[:limit]
        return result
    except sqlite3.Error as e:
        return [{"error": str(e)}]


# --- MCP server plumbing -------------------------------------------------------
TOOLS = [
    Tool(
        name="query_dbid",
        description="自然语言查询 DBID - 查询飞机、舰艇、潜艇、设施的数据库ID",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "自然语言查询，如 'F-16' 或 '战斗机'"},
                "limit": {"type": "integer", "description": "返回结果数量限制", "default": 50},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="read_query",
        description="执行 SELECT SQL 查询（含结果缓存 30s）",
        inputSchema={
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "SELECT SQL 查询语句"},
                "params": {"type": "array", "description": "可选的查询参数"},
                "fetch_all": {"type": "boolean", "description": "是否获取所有结果", "default": True},
                "row_limit": {"type": "integer", "description": "最大返回行数", "default": 1000},
            },
            "required": ["sql"],
        },
    ),
    Tool(
        name="list_tables",
        description="列出数据库中的所有表（含缓存 60s）",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="describe_table",
        description="获取表的结构信息（表名需通过白名单校验）",
        inputSchema={
            "type": "object",
            "properties": {"table_name": {"type": "string", "description": "表名"}},
            "required": ["table_name"],
        },
    ),
    Tool(
        name="get_dbid_by_name",
        description="通过名称精确查找 DBID",
        inputSchema={
            "type": "object",
            "properties": {"name": {"type": "string", "description": "装备名称（如 'F-22'）"}},
            "required": ["name"],
        },
    ),
    Tool(
        name="get_dbid_by_country",
        description="按国家查询 DBID",
        inputSchema={
            "type": "object",
            "properties": {
                "country": {"type": "string", "description": "国家名称"},
                "category": {"type": "string", "description": "可选，装备类别"},
                "limit": {"type": "integer", "description": "返回数量限制", "default": 20},
            },
            "required": ["country"],
        },
    ),
]

server = Server("HKBQ_SqlDB")


@server.list_tools()
async def list_tools():
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]):
    try:
        if name == "query_dbid":
            result = query_dbid_impl(arguments.get("query", ""), arguments.get("limit", 50))
        elif name == "read_query":
            result = read_query_impl(
                sql=arguments.get("sql", ""),
                params=arguments.get("params"),
                fetch_all=arguments.get("fetch_all", True),
                row_limit=arguments.get("row_limit", 1000),
            )
        elif name == "list_tables":
            result = list_tables_impl()
        elif name == "describe_table":
            result = describe_table_impl(arguments.get("table_name", ""))
        elif name == "get_dbid_by_name":
            result = get_dbid_by_name_impl(arguments.get("name", ""))
        elif name == "get_dbid_by_country":
            result = get_dbid_by_country_impl(
                country=arguments.get("country", ""),
                category=arguments.get("category"),
                limit=arguments.get("limit", 20),
            )
        else:
            raise ValueError(f"Unknown tool: {name}")
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
