"""阶段 2 收尾 — 生成 02_resolved.json"""
import json
from pathlib import Path

STAGING = Path(r"C:\Users\user\.codex\skills\CMOLua-main\outputs\staging\20260706_consumption_lure")

# 用户拍板的 DBID 选择
SELECTED = {
    # ===== 红方平台 =====
    "red_ddg_1": {
        "dbid": 3883,
        "name_en": "Type 055 Renhai [101 Nanchang]",
        "platform_type": "DDG_055",
        "class": "Ship",
        "loadout_strategy": "default (no LoadoutID — will use ScenEdit_AddReloadsToUnit)",
        "notes": "JSON says DDG_055; DB has 2834 and 3883, user picked 3883 (used in all.lua history).",
    },
    "red_ddg_2": {
        "dbid": 2296,
        "name_en": "Type 052D Luyang III [172 Kunming]",
        "platform_type": "DDG_052D",
        "class": "Ship",
        "loadout_strategy": "default",
    },
    "red_sub_1": {
        "dbid": 124,
        "name_en": "Type 039G1 Song",
        "platform_type": "SUB_039C",
        "class": "Submarine",
        "loadout_strategy": "default (no LoadoutID for submarine)",
    },
    "red_ac_1": {
        "dbid": 2853,
        "name_en": "J-16 Flying Shark [Su-30MKK Copy]",
        "platform_type": "AC_J16",
        "class": "Aircraft",
        "loadout_strategy": "Aircraft, will add YJ-83 via ScenEdit_AddReloadsToUnit (skip LoadoutID)",
    },
    "red_ew_1": {
        "dbid": 343,
        "name_en": "EA-18G Growler",
        "platform_type": "EW_EA18G",
        "class": "Aircraft",
        "loadout_strategy": "Aircraft, will add EMP weapons via ScenEdit_AddReloadsToUnit",
    },
    # ===== 蓝方目标 =====
    "blue_ddg_1": {
        "dbid": 112,
        "name_en": "DDG 51 Arleigh Burke [Arleigh Burke Flight I]",
        "class": "Ship",
        "platform_type": "AEGIS_BURKE_FLIGHT_I",
    },
    "blue_ddg_2": {
        "dbid": 797,
        "name_en": "DDG 51 Arleigh Burke [Arleigh Burke Flight I]",
        "class": "Ship",
        "platform_type": "AEGIS_BURKE_FLIGHT_I",
    },
    "blue_aux_1": {
        "dbid": 26,
        "name_en": "T-AO 187 Henry J. Kaiser [Mod Cimarron]",
        "class": "Ship",
        "platform_type": "OILER",
    },
    # ===== 武器 =====
    "weapon_yj18": {
        "dbid": 2868,
        "name_en": "YJ-18 [3M54E Klub Copy]",
        "name_zh": "鹰击-18反舰导弹 / YJ-18反舰导弹(潜艇同型号)",
        "category": "anti-ship missile",
    },
    "weapon_yj83": {
        "dbid": 541,
        "name_en": "YJ-83 [C-802A, CSS-N-8 Saccade]",
        "name_zh": "YJ-83反舰导弹",
        "category": "anti-ship missile",
    },
}

# LoadoutID 信息 (备查 — 但 manifest 阶段不用,改用 mount 装弹)
LOADOUT_NOTE = {
    "red_ac_1": "DB has LoadoutID 1821 and 3272 for ComponentID=2853, but DataLoadoutWeapons schema doesn't directly map ID->WeaponID cleanly. Using ScenEdit_AddReloadsToUnit per mount is safer.",
    "red_ew_1": "DB has LoadoutID 102, 963, 995 for ComponentID=343. Same caveat as above.",
}

# 阶段 1 提取的原始数据 (从 extract_meta.json 加载)
META = json.loads((STAGING / "extract_meta.json").read_text(encoding="utf-8"))
RAW_UNITS = META["raw_units"]

# 组装 resolved.json
RESOLVED = {
    "version": "phase2",
    "plan": "消耗与诱歼作战方案",
    "resolved_at": "2026-07-06",
    "scenario": {
        "name": META["planName"],
        "side": META["side"],
        "combat_time": META["combatTime"],
        "side_red": "红方",
        "side_blue": "蓝方",
    },
    "selected_dbids": SELECTED,
    "loadout_notes": LOADOUT_NOTE,
    "units": [],   # resolved units (coordinates + dbid)
    "targets_blue": [],
    "weapons": [],
    "waypoints": [],
    "timings": [],
    "platform_tasks": [],
}

# 从原始单位数据 + selected dbid 组装 units
for r in RAW_UNITS:
    rid = r["id"]
    if rid in SELECTED:
        sd = SELECTED[rid]
        lat = r["lat"]; lon = r["lon"]
        # 清洗坐标: 去掉单位后缀
        if isinstance(lat, str) and "m" in lat: lat = lat.replace("m", "").strip()
        if isinstance(lon, str) and "m" in lon: lon = lon.replace("m", "").strip()
        # 清洗 speed: "15节" -> "15"
        RESOLVED["units"].append({
            "id": rid,
            "side": r["side"],
            "type": r["type"],
            "dbid": sd["dbid"],
            "name_en": sd["name_en"],
            "platform_type_zh": r["platform_type"],
            "platform_class_zh": r["platform_class"],
            "lat": lat,
            "lon": lon,
            "alt": r["alt"],
            "loadlist_count": len(r["loadList"]) if isinstance(r["loadList"], list) else 0,
        })

# 重新读 JSON 提 targets/waypoints/timings/tasks
PLAN = json.loads(
    (Path(r"C:\Users\user\.codex\skills\CMOLua-main\json\消耗与诱歼作战方案.json")).read_text(encoding="utf-8")
)

# 蓝方目标
for kw in PLAN["task"]["killWebs"]:
    for tgt in kw.get("targets", []):
        tid = tgt.get("targetID")
        sd = SELECTED.get(tid, {})
        loc = tgt.get("location", {})
        lat = str(loc.get("latitude", "")).replace("m", "")
        lon = str(loc.get("longitude", "")).replace("m", "")
        RESOLVED["targets_blue"].append({
            "id": tid,
            "name_zh": tgt.get("targetName"),
            "side": (tgt.get("affiliation") or {}).get("forceSideName"),
            "object_type": tgt.get("objectType"),
            "lat": lat,
            "lon": lon,
            "alt": str(loc.get("altitude", 0)).replace("m", ""),
            "priority": tgt.get("priorityLevel"),
            "phase_seq": tgt.get("phaseSequence"),
            "phase_name": tgt.get("phaseName"),
            "dbid": sd.get("dbid"),
            "name_en": sd.get("name_en"),
        })

# 武器 (从 platformTasks.weapons + killChains.LinkList)
seen = set()
for pe in PLAN["platformExecutions"]["platformExecutions"]:
    pid = pe.get("platformId")
    for tk in pe.get("platformTasks", []):
        for w in tk.get("weapons", []) or []:
            key = (w.get("name"), w.get("type"))
            if not w.get("name") or key in seen:
                continue
            seen.add(key)
            # 对应 dbid
            wname = w["name"]
            dbid = None
            if "YJ-18" in wname or "鹰击-18" in wname:
                dbid = SELECTED["weapon_yj18"]["dbid"]
            elif "YJ-83" in wname or "鹰击-83" in wname:
                dbid = SELECTED["weapon_yj83"]["dbid"]
            RESOLVED["weapons"].append({
                "weapon_name_zh": wname,
                "weapon_type": w.get("type"),
                "dbid": dbid,
                "qty_max": w.get("quantity"),
                "platform_used": pid,
            })

# Waypoints (清洗 speed)
for pe in PLAN["platformExecutions"]["platformExecutions"]:
    pid = pe.get("platformId")
    route = pe.get("route") or {}
    for i, wp in enumerate(route.get("waypoints") or [], 1):
        speed = str(wp.get("speed", "0"))
        # "15节" -> "15"
        speed = speed.replace("节", "").replace("m", "")
        RESOLVED["waypoints"].append({
            "platform_id": pid,
            "seq": i,
            "lat": str(wp.get("latitude", "")).replace("m", ""),
            "lon": str(wp.get("longitude", "")).replace("m", ""),
            "alt": str(wp.get("altitude", "0")).replace("m", ""),
            "speed": speed,
        })

# Timings
for p in PLAN["mission"]["combatPhases"]:
    tw = p.get("timeWindow") or {}
    RESOLVED["timings"].append({
        "kind": "combatPhase",
        "phase_seq": str(p.get("phaseSequence")),
        "phase_name": p.get("phaseName"),
        "absolute_start": tw.get("startTime"),
        "absolute_end": tw.get("endTime"),
        "duration_iso": tw.get("duration"),
    })

for kw in PLAN["task"]["killWebs"]:
    for kc in kw.get("killChains", []):
        for link in kc.get("LinkList", []):
            for sc in link.get("startCondition", []) or []:
                RESOLVED["timings"].append({
                    "kind": "killChainLinkStart",
                    "kill_chain_id": kc.get("killChainId"),
                    "link_id": link.get("linkId"),
                    "link_name": link.get("linkTaskName"),
                    "absolute_time": sc.get("time"),
                    "type": sc.get("type"),
                })

# Platform Tasks (压缩)
for pe in PLAN["platformExecutions"]["platformExecutions"]:
    pid = pe.get("platformId")
    for tk in pe.get("platformTasks", []):
        timing = tk.get("timing") or {}
        related = tk.get("relatedKillChain") or {}
        weapons = ";".join(
            f"{w.get('name')}x{w.get('quantity')}"
            for w in tk.get("weapons", []) or []
            if w.get("name")
        )
        RESOLVED["platform_tasks"].append({
            "platform_id": pid,
            "task_id": tk.get("platformTaskId"),
            "task_name": tk.get("platformTaskName"),
            "task_type": tk.get("platformTaskType"),
            "kill_chain": related.get("killChainId"),
            "link_id":   related.get("relatedLinkId"),
            "targets": ";".join(tk.get("target") or []),
            "timing_start": timing.get("startTime"),
            "timing_end":   timing.get("endTime"),
            "weapons": weapons,
        })

# 写
out_path = STAGING / "02_resolved.json"
out_path.write_text(json.dumps(RESOLVED, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"  written: {out_path}")
print(f"  units:   {len(RESOLVED['units'])}")
print(f"  targets: {len(RESOLVED['targets_blue'])}")
print(f"  weapons: {len(RESOLVED['weapons'])}")
print(f"  waypoints: {len(RESOLVED['waypoints'])}")
print(f"  timings: {len(RESOLVED['timings'])}")
print(f"  platform_tasks: {len(RESOLVED['platform_tasks'])}")