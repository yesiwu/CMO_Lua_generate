"""
阶段 2 完整脚本 — 查所有 5 个平台 + 2 个 Loadout + 3-4 个武器 + 3 个蓝方目标
输出: 02_resolved.json
"""
import json
import os
import subprocess
from pathlib import Path

env = os.environ.copy()
env["SQLITE_DB_PATH"] = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3"
env["PYTHONIOENCODING"] = "utf-8"

PYTHON = r"E:\Deep_learning\anconda\python.exe"
SERVER = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\server.py"

STAGING = Path(r"C:\Users\user\.codex\skills\CMOLua-main\outputs\staging\20260706_consumption_lure")


def call_mcp(payload: bytes, timeout: int = 60) -> str:
    try:
        proc = subprocess.run(
            [PYTHON, SERVER], input=payload,
            capture_output=True, timeout=timeout, env=env,
        )
        return proc.stdout.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return ""


def query_dbid(q: str, limit: int = 20) -> list:
    reqs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "phase2", "version": "1.0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "query_dbid",
                    "arguments": {"query": q, "limit": limit}}},
    ]
    payload = "\n".join(json.dumps(r, ensure_ascii=False) for r in reqs) + "\n"
    out = call_mcp(payload.encode("utf-8"))
    for line in reversed(out.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if "result" in obj and "content" in obj["result"]:
                return json.loads(obj["result"]["content"][0]["text"])
        except Exception:
            continue
    return [{"error": "no response", "raw": out[:200]}]


def read_query(sql: str) -> list:
    reqs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "phase2", "version": "1.0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "read_query", "arguments": {"sql": sql}}},
    ]
    payload = "\n".join(json.dumps(r, ensure_ascii=False) for r in reqs) + "\n"
    out = call_mcp(payload.encode("utf-8"))
    for line in reversed(out.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if "result" in obj and "content" in obj["result"]:
                return json.loads(obj["result"]["content"][0]["text"])
        except Exception:
            continue
    return [{"error": "no response", "raw": out[:200]}]


# ========== 主流程 ==========
RESULTS = {
    "stage": 2,
    "plan": "消耗与诱歼作战方案",
    "resolved_at": "2026-07-06",
    "platforms": {},   # 平台名 -> {dbid, candidates, loadout_id}
    "weapons": {},     # 武器名 -> {dbid, candidates}
    "targets_blue": {},
    "loadouts": {},    # 平台名 -> List of LoadoutID
    "queries_log": [],
}


def log_query(category: str, query: str, results):
    RESULTS["queries_log"].append({
        "category": category, "query": query,
        "num_results": len(results) if isinstance(results, list) else 1,
    })


# ==== 平台 ====
PLATFORMS = [
    ("red_ddg_1", "DDG_055", "Type 055 destroyer Renhai-class"),
    ("red_ddg_2", "DDG_052D", "Type 052D Luyang destroyer"),
    ("red_sub_1", "SUB_039C", "Type 039B 039C submarine Song-class"),
    ("red_ac_1",  "AC_J16",   "J-16 multirole fighter"),
    ("red_ew_1",  "EW_EA18G", "EA-18G Growler electronic warfare aircraft"),
]

print("=" * 70)
print("阶段 2: 平台 DBID 查询")
print("=" * 70)
for plat_id, plat_type, en_name in PLATFORMS:
    print(f"\n>>> {plat_id} ({plat_type})")
    res = query_dbid(en_name, 8)
    log_query("platform", en_name, res)
    if isinstance(res, list) and res:
        RESULTS["platforms"][plat_id] = {
            "type_code": plat_type, "english_query": en_name,
            "candidates": res, "selected_dbid": None, "selected_idx": None,
            "selected_name": None, "loadout_options": [],
        }
        for i, c in enumerate(res[:5]):
            print(f"   [{i+1}] dbid={c.get('dbid')} {c.get('name')} ({c.get('country')})")
    else:
        print("   ! no results")
        RESULTS["platforms"][plat_id] = {
            "type_code": plat_type, "english_query": en_name,
            "candidates": [], "selected_dbid": None, "selected_idx": None,
        }


# ==== 蓝方目标 (3 个 Ship, 模糊匹配 'Aegis Arleigh Burke DDG-51') ====
print("\n" + "=" * 70)
print("阶段 2: 蓝方目标 (Arleigh Burke DDG 系列)")
print("=" * 70)
BLUE_QUERIES = [
    ("blue_ddg_1", "Arleigh Burke Flight I DDG"),
    ("blue_ddg_2", "Arleigh Burke Flight IIA DDG"),
    ("blue_aux_1", "Supply ship fleet replenishment oiler"),
]
for tgt_id, q in BLUE_QUERIES:
    print(f"\n>>> {tgt_id}")
    res = query_dbid(q, 8)
    log_query("blue_target", q, res)
    if isinstance(res, list) and res:
        RESULTS["targets_blue"][tgt_id] = {
            "english_query": q, "candidates": res,
            "selected_dbid": None, "selected_idx": None,
        }
        for i, c in enumerate(res[:5]):
            print(f"   [{i+1}] dbid={c.get('dbid')} {c.get('name')} ({c.get('country')})")


# ==== 武器 ====
print("\n" + "=" * 70)
print("阶段 2: 武器 DBID")
print("=" * 70)
WEAPONS = [
    ("YJ-18", "YJ-18 anti-ship missile"),
    ("YJ-83", "YJ-83 anti-ship missile"),
]
for w_code, en_name in WEAPONS:
    print(f"\n>>> weapon: {w_code}")
    res = query_dbid(en_name, 8)
    log_query("weapon", en_name, res)
    if isinstance(res, list) and res:
        RESULTS["weapons"][w_code] = {
            "english_query": en_name, "candidates": res,
            "selected_dbid": None, "selected_idx": None,
        }
        for i, c in enumerate(res[:5]):
            print(f"   [{i+1}] dbid={c.get('dbid')} {c.get('name')} ({c.get('country')})")


# ==== Aircraft LoadoutID (J-16, EA-18G) ====
print("\n" + "=" * 70)
print("阶段 2: Aircraft LoadoutID")
print("=" * 70)
aircraft_loadout_targets = []
# 由于 selected_dbid 还是 None,先收集候选,用户挑后再查
print("\n(Loadout 查询将依赖您选择的 dbid,留待 selection 后查)")


# ==== 写 outputs ====
out_path = STAGING / "02_resolved_candidates.json"
out_path.write_text(json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n{'='*70}")
print(f"候选清单已写入: {out_path}")
print(f"{'='*70}")
print(f"\n下一步: 把候选清单给我,您指 1 个或 multiple 时我会:")
print(f"  1) 设置 selected_dbid / selected_idx")
print(f"  2) 对 Aircraft 调 read_query 查 LoadoutID")
print(f"  3) 生成最终 resolved.json")