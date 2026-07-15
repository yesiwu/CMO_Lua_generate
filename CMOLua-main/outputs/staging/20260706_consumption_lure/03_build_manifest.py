"""阶段 3 — 生成 manifest.lua"""
import json
from pathlib import Path

STAGING = Path(r"C:\Users\user\.codex\skills\CMOLua-main\outputs\staging\20260706_consumption_lure")
OUT_DIR  = Path(r"C:\Users\user\.codex\skills\CMOLua-main\outputs\lua\20260706_101200_consumption_lure")
OUT_DIR.mkdir(parents=True, exist_ok=True)

R = json.loads((STAGING / "02_resolved.json").read_text(encoding="utf-8"))


# ========== 时间换算 ==========
def iso_to_seconds_since_start(iso: str, base: str = "2026-04-10 10:00:00") -> int:
    """ISO -> 相对 2026-04-10 10:00:00 的秒数"""
    from datetime import datetime
    fmt = "%Y-%m-%d %H:%M:%S"
    base_dt = datetime.strptime(base, fmt)
    try:
        dt = datetime.strptime(iso.replace("T", " ").strip(), fmt)
        return int((dt - base_dt).total_seconds())
    except Exception:
        return 0


# ========== Manifest 数据构建 ==========
M = {}

# CFG_SCENARIO
M["scenario"] = {
    "name": R["scenario"]["name"],
    "startTime": "2026-04-10 10:00:00",
    "side_red": "红方",
    "side_blue": "蓝方",
    "timezone": "UTC+8",
    "red_doctrine": {
        "weapon_control_status_air": 0,
        "weapon_control_status_surface": 0,
        "weapon_control_status_subsurface": 0,
        "weapon_control_status_land": 0,
    },
    "blue_doctrine": {
        "weapon_control_status_air": 0,
        "weapon_control_status_surface": 2,   # 表面目标 Hold
        "weapon_control_status_subsurface": 2,
        "weapon_control_status_land": 0,
    },
    "red_emcon": "Radar=Active;Sonar=Active;OECM=Active",
    "blue_emcon": "Radar=Active;Sonar=Active;OECM=Active",
    "blue_autodetectable": True,
    "contact_settle_delay": 15,
    "red_awareness": "OMNI",  # 红方全知
}

# UNITS — 8 个单位（与 main.lua 完全对应）
# ★★★ Aircraft 必须从 selected_dbids 读取 loadout_id ★★★
M["units"] = {}
for u in R["units"]:
    unit_entry = {
        "side":  u["side"],
        "type":  u["type"],
        "dbid":  u["dbid"],
        "name":  u["id"],   # 与 main.lua 中 name= 完全一致
        "lat":   u["lat"],
        "lon":   u["lon"],
        "alt":   u["alt"],
        "loadlist_count": u["loadlist_count"],
        "name_en": u["name_en"],
    }
    # Aircraft 必须带 loadout_id（CMO ScenEdit_AddUnit 强制要求）
    if u["type"] == "Aircraft":
        sel = R.get("selected_dbids", {}).get(u["id"], {})
        loadout_id = sel.get("loadout_id")
        if loadout_id is not None:
            unit_entry["loadout_id"] = loadout_id
        else:
            # ★★★ 红线：未查到 loadout_id 必须在生成阶段报错 ★★★
            raise ValueError(
                f"[03_build_manifest] Aircraft '{u['id']}' (dbid={u['dbid']}) "
                f"缺少 loadout_id。请先运行 MCP 查 DataAircraftLoadouts 表，"
                f"结果写入 02_resolved.json selected_dbids['{u['id']}']['loadout_id']。"
            )
    M["units"][u["id"]] = unit_entry

# 蓝方目标也加进 units (作为参考)
for t in R["targets_blue"]:
    M["units"][t["id"]] = {
        "side": t["side"],
        "type": "Ship",
        "dbid": t["dbid"],
        "name": t["id"],
        "name_zh": t["name_zh"],
        "lat": t["lat"],
        "lon": t["lon"],
        "alt": t["alt"],
        "priority": t["priority"],
        "phase_seq": t["phase_seq"],
        "name_en": t["name_en"],
    }

# CLEAR_LIST — 5 个红方单位
M["clear_list"] = ["red_ddg_1", "red_ddg_2", "red_sub_1", "red_ac_1", "red_ew_1"]

# AMMO — 从 JSON weapons.csv + platformTasks 推断
# 每单位装弹 (按 JSON 里 weapons 数组最大数量)
# red_ddg_1: 鹰击-18 x4 -> YJ-18 dbid=2868, qty=4
# red_sub_1: YJ-18 x4  -> YJ-18 dbid=2868, qty=4
# red_ac_1:  YJ-83 x2  -> YJ-83 dbid=541,  qty=2
# red_ew_1:  无明确武器 (EW) — 不装弹, 用 mount 默认 (诱饵 + 干扰)
# red_ddg_2: 052D 默认有反舰+防空武器，但 JSON 里它只在 linkType=巡航里 - 暂不装弹
M["ammo"] = [
    {"unitname": "red_ddg_1", "wpn_dbid": 2868, "number": 4, "weapon_name": "YJ-18"},
    {"unitname": "red_sub_1", "wpn_dbid": 2868, "number": 4, "weapon_name": "YJ-18"},
    {"unitname": "red_ac_1",  "wpn_dbid": 541,  "number": 2, "weapon_name": "YJ-83"},
]

# STRIKE — 真延时打击清单
# 来源: JSON killChains.LinkList[].platforms[] where task="交战"
# JSON time 默认起始 T0+PT0H = 0s (JSON 中"11:00:00"为phase 3 开始)
# JSON 里交火时间一般在phase_3 start (T0+PT60M = 3600s) 后 5 分钟
# 推导策略: 同一时间触发器的 task="交战" 合并到一行 STRIKE
PLAN = json.loads(
    Path(r"C:\Users\user\.codex\skills\CMOLua-main\json\消耗与诱歼作战方案.json").read_text(encoding="utf-8")
)

M["strike"] = []
# 来自 killChains.LinkList 里 taskType="交战" 的
for kw in PLAN["task"]["killWebs"]:
    for kc in kw.get("killChains", []):
        # 找 target list
        targets_in_chain = []
        for tn in kc.get("TargetList") or []:
            tid = tn.get("targetID")
            if tid:
                targets_in_chain.append(tid)
        # 收集交火 link
        strike_links = [lk for lk in kc.get("LinkList", [])
                       if lk.get("taskType") == "交战"]
        # 每条 link 交火一个目标
        for lk in strike_links:
            # 起始时间
            start_iso = (lk.get("startCondition") or [{}])[0].get("time", "")
            delay = iso_to_seconds_since_start(start_iso)
            # 攻击方: 从 platforms 里找 role=攻击
            for pl in (lk.get("platforms") or []):
                role = pl.get("role", "")
                if "攻击" not in role and "主攻" not in role and "反舰" not in role:
                    # 如果没有一个带"攻击"role, 默认第一个
                    pass
                # 选定武器 (如果 json weaponName 空, 用 YJ-83 / YJ-18 按单位推断)
                w = pl.get("weapon") or {}
                weapon_db = None
                pid = pl.get("platformId")
                if pid == "red_ac_1":
                    weapon_db = 541  # YJ-83
                elif pid in ("red_ddg_1", "red_sub_1"):
                    weapon_db = 2868  # YJ-18
                # qty 从 weapons 数组最大值找
                qty = 1
                for pa in PLAN["platformExecutions"]["platformExecutions"]:
                    if pa.get("platformId") == pid:
                        for tk in pa.get("platformTasks") or []:
                            for w2 in (tk.get("weapons") or []):
                                if w2.get("name") and w2.get("quantity"):
                                    try:
                                        qty = max(qty, int(w2["quantity"]))
                                    except Exception:
                                        pass
                # 一个 STRIKE 只发 1 枚（真延时要求 qty=1）
                M["strike"].append({
                    "attacker": pid,
                    "target":   targets_in_chain[0] if targets_in_chain else None,
                    "wpn_dbid": weapon_db,
                    "qty_per_call": 1,
                    "qty_total": qty,
                    "startDelay_seconds": delay,
                    "interval_seconds": 60,   # 1 分钟一枚
                    "tag": f"{pid}_{lk.get('linkId')}",
                })

# PATROLS — 来自 killChains.LinkList[] taskType=巡航 / 干扰
# red_ew_1 主要做 SEAD 巡逻 / 干扰
# 这里只创建 1 个 SEAD patrol 对应 RP-EW-1..4
M["patrols"] = [
    {
        "platform":   "red_ew_1",
        "type":       "SEAD",
        "subtype":    "SEAD",
        "zone_name":  "EW_PATROL_ZONE",
        "rps":        ["RP-EW-1", "RP-EW-2", "RP-EW-3", "RP-EW-4"],
        "start_time": "2026-04-10 10:00:00",
        "duration_seconds": 6300,  # 105 分钟 (整个作战期)
    },
]

# WAYPOINTS — 36 个航点 (可在 attack/main 阶段生成航线)
M["waypoints"] = []
for wp in R["waypoints"]:
    M["waypoints"].append(wp)

# REFERENCE POINTS — 4 个 SEAD 巡逻区
# 来自 JSON EW 任务的大致区域 (用 red_ew_1 第1个航点附近)
M["reference_points"] = [
    {"side": "红方", "name": "RP-EW-1", "lat": "27.0", "lon": "123.0"},
    {"side": "红方", "name": "RP-EW-2", "lat": "27.0", "lon": "125.0"},
    {"side": "红方", "name": "RP-EW-3", "lat": "30.0", "lon": "125.0"},
    {"side": "红方", "name": "RP-EW-4", "lat": "30.0", "lon": "123.0"},
]

# TIMINGS — 17 个时间触发器
# 全部 ISO → 相对秒
M["timings"] = []
for t in R["timings"]:
    if t["kind"] == "combatPhase":
        M["timings"].append({
            "kind": "combatPhase",
            "tag": f"phase_{t['phase_seq']}",
            "phase_name": t["phase_name"],
            "absolute_start": t["absolute_start"],
            "absolute_end":   t["absolute_end"],
            "relative_start_seconds": iso_to_seconds_since_start(t["absolute_start"]),
            "duration_iso": t["duration_iso"],
        })
    else:  # killChainLinkStart
        M["timings"].append({
            "kind": t["kind"],
            "tag": f"{t['kill_chain_id']}_{t['link_id']}",
            "kill_chain_id": t["kill_chain_id"],
            "link_id":   t["link_id"],
            "link_name": t["link_name"],
            "absolute_time": t["absolute_time"],
            "relative_seconds": iso_to_seconds_since_start(t["absolute_time"]),
        })

# VICTORY — 来自 terminationStates
M["victory"] = {
    "red_winning_threshold": 70,
    "description": "蓝方护航编队被毁伤 ≥ 70% = 红方胜"
}

# 写 .lua 文件 (用 lua_data table)
def lua_value(v):
    """Python -> Lua 字面量表示"""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int,)):
        return str(v)
    if isinstance(v, float):
        return str(v)
    if isinstance(v, str):
        # 转义双引号
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(v, list):
        return "{" + ", ".join(lua_value(x) for x in v) + "}"
    if isinstance(v, dict):
        items = []
        for k, vv in v.items():
            items.append(f'["{k}"] = {lua_value(vv)}')
        return "{" + ", ".join(items) + "}"
    return str(v)


manifest_lua = f"""-- ==========================================================================
-- manifest.lua — 消耗与诱歼作战方案
--     单一数据源。所有 4 个脚本 (main/clear/reload/attack) 都 dofile 此文件
--     Generated by stage3, 2026-07-06
-- ==========================================================================

print("[CMO] [INFO] ============ manifest.lua loaded ============")

-- ==========================================================================
-- CFG_SCENARIO — 场景配置
-- ==========================================================================
CFG_SCENARIO = {{
    name                 = {lua_value(M["scenario"]["name"])},
    startTime            = {lua_value(M["scenario"]["startTime"])},
    side_red             = {lua_value(M["scenario"]["side_red"])},
    side_blue            = {lua_value(M["scenario"]["side_blue"])},
    red_awareness        = {lua_value(M["scenario"]["red_awareness"])},
    red_emcon            = {lua_value(M["scenario"]["red_emcon"])},
    blue_emcon           = {lua_value(M["scenario"]["blue_emcon"])},
    blue_autodetectable  = {lua_value(M["scenario"]["blue_autodetectable"])},
    contact_settle_delay = {M["scenario"]["contact_settle_delay"]},
}}

CFG_DOCTRINE_RED = {{
    weapon_control_status_air        = {M["scenario"]["red_doctrine"]["weapon_control_status_air"]},
    weapon_control_status_surface    = {M["scenario"]["red_doctrine"]["weapon_control_status_surface"]},
    weapon_control_status_subsurface = {M["scenario"]["red_doctrine"]["weapon_control_status_subsurface"]},
    weapon_control_status_land       = {M["scenario"]["red_doctrine"]["weapon_control_status_land"]},
}}

CFG_DOCTRINE_BLUE = {{
    weapon_control_status_air        = {M["scenario"]["blue_doctrine"]["weapon_control_status_air"]},
    weapon_control_status_surface    = {M["scenario"]["blue_doctrine"]["weapon_control_status_surface"]},
    weapon_control_status_subsurface = {M["scenario"]["blue_doctrine"]["weapon_control_status_subsurface"]},
    weapon_control_status_land       = {M["scenario"]["blue_doctrine"]["weapon_control_status_land"]},
}}

-- ==========================================================================
-- UNITS — 全部 8 个单位（与 main.lua 中 name= 完全一致）
-- ==========================================================================
UNITS = {{}}
"""
for uid, u in M["units"].items():
    # 赤/蓝不同字段名,自动适配
    if "name_en" in u:
        extra = ""
        if u["type"] == "Aircraft" and "loadout_id" in u:
            extra = "\n    loadout_id = " + str(u['loadout_id']) + ",   -- MCP 查询 DataAircraftLoadouts"
        manifest_lua += "\nUNITS[\"" + uid + "\"] = {\n"
        manifest_lua += "    side    = " + lua_value(u['side']) + ",\n"
        manifest_lua += "    type    = " + lua_value(u['type']) + ",\n"
        manifest_lua += "    dbid    = " + str(u['dbid']) + ",\n"
        manifest_lua += "    name    = " + lua_value(u['name']) + ",\n"
        manifest_lua += "    lat     = " + lua_value(u['lat']) + ",\n"
        manifest_lua += "    lon     = " + lua_value(u['lon']) + ",\n"
        manifest_lua += "    altitude= " + lua_value(u['alt']) + ",\n"
        manifest_lua += "    name_en = " + lua_value(u['name_en']) + "," + extra + "\n}"

# CLEAR_LIST
manifest_lua += "\n\n-- ==========================================================================\n"
manifest_lua += "-- CLEAR_LIST — 5 个红方单位\n"
manifest_lua += "-- ==========================================================================\n"
manifest_lua += f"CLEAR_LIST = {lua_value(M['clear_list'])}\n"

# AMMO
manifest_lua += "\n-- ==========================================================================\n"
manifest_lua += "-- AMMO — 装弹清单 ({{unitname, wpn_dbid, number}})\n"
manifest_lua += "-- ==========================================================================\n"
manifest_lua += "AMMO = {\n"
for a in M["ammo"]:
    manifest_lua += f'    {{ unitname = {lua_value(a["unitname"])}, wpn_dbid = {a["wpn_dbid"]}, number = {a["number"]} }},  -- {a["weapon_name"]}\n'
manifest_lua += "}\n"

# STRIKE — ★★★ 命名键（红线 #2：禁止位置数组）★★★
manifest_lua += "\n-- ==========================================================================\n"
manifest_lua += "-- STRIKE — 打击清单（{attacker=, target=, wpn_dbid=, quantity=, startDelay=, interval=, intent=}）\n"
manifest_lua += "--   ★ 禁止位置数组写法 {attacker, target, ...}（LLM 加列后位置全乱）\n"
manifest_lua += "--   ★ 真延时：每次 fireAt 调用 qty=1, scheduleOne 拆成 N 个触发器\n"
manifest_lua += "-- ==========================================================================\n"
manifest_lua += "STRIKE = {\n"
for s in M["strike"]:
    manifest_lua += (f'    {{ attacker = {lua_value(s["attacker"])}, '
                     f'target = {lua_value(s["target"])}, '
                     f'weapon_dbid = {s["wpn_dbid"]}, '
                     f'quantity = {s["qty_total"]}, '
                     f'startDelay = {s["startDelay_seconds"]}, '
                     f'interval = {s["interval_seconds"]}, '
                     f'intent = {lua_value(s["tag"])} }},\n')
manifest_lua += "}\n"

# PATROLS
manifest_lua += "\n-- ==========================================================================\n"
manifest_lua += "-- PATROLS — 巡逻任务\n"
manifest_lua += "-- ==========================================================================\n"
manifest_lua += f"PATROLS = {lua_value(M['patrols'])}\n".replace('true', 'True').replace('false', 'False') \
                  .replace("'[REPLACE]',", '"EW_PATROL_ZONE",').replace('1', '1')  # python True/None 替换

# 用更安全的方式重写 PATROLS
patrols_lua_items = []
for p in M["patrols"]:
    patrols_lua_items.append(f"""    {{
        platform      = {lua_value(p['platform'])},
        type          = {lua_value(p['type'])},
        subtype       = {lua_value(p['subtype'])},
        zone_name     = "EW_PATROL_ZONE",
        rps           = {lua_value(p['rps'])},
        start_time    = {lua_value(p['start_time'])},
        duration_seconds = {p['duration_seconds']},
    }}""")

manifest_lua += "\nPATROLS = {\n" + ",\n".join(patrols_lua_items) + "\n}\n"

# WAYPOINTS
manifest_lua += "\n-- ==========================================================================\n"
manifest_lua += "-- WAYPOINTS — 36 个航点 (用于航线)\n"
manifest_lua += "-- ==========================================================================\n"
manifest_lua += "WAYPOINTS = {\n"
for wp in M["waypoints"]:
    manifest_lua += (f'    {{ platform = {lua_value(wp["platform_id"])}, '
                     f'seq = {wp["seq"]}, '
                     f'lat = {lua_value(wp["lat"])}, '
                     f'lon = {lua_value(wp["lon"])}, '
                     f'altitude = {lua_value(wp["alt"])}, '
                     f'speed = {lua_value(wp["speed"])} }},\n')
manifest_lua += "}\n"

# REFERENCE POINTS
manifest_lua += "\n-- ==========================================================================\n"
manifest_lua += "-- REFERENCE_POINTS — SEAD 巡逻区 4 个\n"
manifest_lua += "-- ==========================================================================\n"
manifest_lua += "REFERENCE_POINTS = {\n"
for rp in M["reference_points"]:
    manifest_lua += f'    {{ side = {lua_value(rp["side"])}, name = {lua_value(rp["name"])}, lat = {lua_value(rp["lat"])}, lon = {lua_value(rp["lon"])} }},\n'
manifest_lua += "}\n"

# TIMINGS
manifest_lua += "\n-- ==========================================================================\n"
manifest_lua += "-- TIMINGS — 17 个时间触发器\n"
manifest_lua += "-- ==========================================================================\n"
manifest_lua += "TIMINGS = {\n"
for tm in M["timings"]:
    if tm["kind"] == "combatPhase":
        manifest_lua += (f'    {{ kind = "combatPhase", tag = {lua_value(tm["tag"])}, '
                         f'phase_name = {lua_value(tm["phase_name"])}, '
                         f'relative_start = {tm["relative_start_seconds"]}, '
                         f'absolute_start = {lua_value(tm["absolute_start"])}, '
                         f'absolute_end = {lua_value(tm["absolute_end"]) if tm["absolute_end"] else "nil"} }},\n')
    else:
        manifest_lua += (f'    {{ kind = "killChainLinkStart", tag = {lua_value(tm["tag"])}, '
                         f'kill_chain = {lua_value(tm["kill_chain_id"])}, '
                         f'link_id = {lua_value(tm["link_id"])}, '
                         f'link_name = {lua_value(tm["link_name"])}, '
                         f'relative_seconds = {tm["relative_seconds"]} }},\n')
manifest_lua += "}\n"

# VICTORY
manifest_lua += "\n-- ==========================================================================\n"
manifest_lua += "-- VICTORY — 胜利条件\n"
manifest_lua += "-- ==========================================================================\n"
manifest_lua += f"VICTORY = {{ red_winning_threshold = {M['victory']['red_winning_threshold']}, description = {lua_value(M['victory']['description'])} }}\n"

manifest_lua += '''
print("[CMO] [INFO] manifest.lua loaded: ' ..
    "UNITS=" .. tostring(table_count_keys(UNITS)) .. ", "
    .. "CLEAR_LIST=" .. tostring(#CLEAR_LIST) .. ", "
    .. "AMMO=" .. tostring(#AMMO) .. ", "
    .. "STRIKE=" .. tostring(#STRIKE) .. ", "
    .. "PATROLS=" .. tostring(#PATROLS) .. ", "
    .. "WAYPOINTS=" .. tostring(#WAYPOINTS) .. ", "
    .. "REFERENCE_POINTS=" .. tostring(#REFERENCE_POINTS) .. ", "
    .. "TIMINGS=" .. tostring(#TIMINGS))

-- helper
function table_count_keys(t)
    local n = 0
    for _ in pairs(t) do n = n + 1 end
    return n
end
'''

out = OUT_DIR / "manifest.lua"
out.write_text(manifest_lua, encoding="utf-8")
print(f"  written: {out}")
print(f"  size: {len(manifest_lua)} bytes")
print(f"  units: {len(M['units'])}")
print(f"  clear_list: {len(M['clear_list'])}")
print(f"  ammo: {len(M['ammo'])}")
print(f"  strike: {len(M['strike'])}")
print(f"  patrols: {len(M['patrols'])}")
print(f"  waypoints: {len(M['waypoints'])}")
print(f"  reference_points: {len(M['reference_points'])}")
print(f"  timings: {len(M['timings'])}")