r"""
阶段 1 提取脚本：从 消耗与诱歼作战方案.json 提取 5 张 CSV

输出：
    outputs/staging/20260706_consumption_lure/tables/
        units.csv              - 所有单位（红+蓝）
        targets.csv            - 蓝方目标
        weapons.csv            - 需要查 DBID 的武器
        waypoints.csv          - 红方 platformExecutions[*].route.waypoints
        timings.csv            - combatPhases + killChain LinkList 时间
        extract.log            - 人类可读的提取摘要
        extract_meta.json      - 解码后的中间结构（供阶段 2 消费）

关键约定：
    - 坐标统一存为字符串（保留 JSON 原始精度，避免浮点截断）
    - 平台类别通过 platformClass + platformType 自动推断 Unit.type：
        驱逐舰/护卫舰/补给舰/航母 → Ship
        潜艇 → Submarine
        战斗机/电子战飞机 → Aircraft
    - 类别缺失时存 _raw，阶段 2 我会人工分配

使用：
    python 01_extract.py
"""

import csv
import json
import sys
from pathlib import Path

# ========== 路径 ==========
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
JSON_FILE    = PROJECT_ROOT / "json" / "消耗与诱歼作战方案.json"
STAGING_DIR  = PROJECT_ROOT / "outputs" / "staging" / "20260706_consumption_lure"
TABLES_DIR   = STAGING_DIR / "tables"


# ========== 工具函数 ==========
def safe_str(x, default=""):
    if x is None:
        return default
    return str(x).strip()


def infer_unit_type(platform_class: str, platform_type: str) -> str:
    """根据平台类别推断 CMO Unit.type"""
    cls  = (platform_class or "").lower()
    typ  = (platform_type or "").lower()
    text = cls + "|" + typ
    if "潜" in text or "sub" in text or "ssn" in text or "ssk" in text:
        return "Submarine"
    if "机" in text or "aircraft" in text or "ac_" in text or "ew_" in text:
        return "Aircraft"
    if "驱" in text or "护" in text or "舰" in text or "补" in text or "航母" in text \
       or "ddg" in text or "cvn" in text or "ffg" in text or "ship" in text:
        return "Ship"
    return "_UNKNOWN"


# ========== 提取：单位列表 ==========
def extract_units(plan: dict) -> tuple[list, list]:
    """返回 (units_rows, raw_units)。raw_units 给阶段 2 查 DBID 时用"""
    units_rows = []
    raw_units  = []
    seen = set()  # 去重

    # --- 红方：forceOrganization[].forceSelection[].platformSelection[] ---
    for kw in plan["task"]["killWebs"]:
        for fg in kw.get("forceOrganization", []):
            fg_name = safe_str(fg.get("forceGroupName"))
            for fs in fg.get("forceSelection", []):
                unit_name = safe_str(fs.get("unitName"))
                for ps in fs.get("platformSelection", []):
                    pid = safe_str(ps.get("platformId"))
                    if not pid or pid in seen:
                        continue
                    seen.add(pid)
                    loc = ps.get("platformLocation", {})
                    raw = {
                        "id": pid,
                        "name": safe_str(ps.get("platformName"), pid),
                        "unit_zh": unit_name,
                        "group_name": fg_name,
                        "platform_type": safe_str(ps.get("platformType")),
                        "platform_class": safe_str(ps.get("platformClass")),
                        "platform_category": safe_str(ps.get("platformCategory")),
                        "side": safe_str(ps.get("forceSideName"), "红方"),
                        "lat": safe_str(loc.get("latitude")),
                        "lon": safe_str(loc.get("longitude")),
                        "alt": safe_str(loc.get("altitude"), "0"),
                        "loadList": ps.get("loadList", []) or [],
                    }
                    raw["type"] = infer_unit_type(raw["platform_class"], raw["platform_type"])
                    raw_units.append(raw)

    # --- 蓝方：targets[] ---
    for kw in plan["task"]["killWebs"]:
        for tgt in kw.get("targets", []):
            tid = safe_str(tgt.get("targetID"))
            if not tid or tid in seen:
                continue
            seen.add(tid)
            loc = tgt.get("location", {})
            # 蓝方 affiliation.forceSideName
            aff = tgt.get("affiliation", {})
            raw = {
                "id": tid,
                "name": safe_str(tgt.get("targetName"), tid),
                "unit_zh": safe_str(tgt.get("targetName")),
                "group_name": "蓝方目标",
                "platform_type": "",
                "platform_class": "",
                "platform_category": safe_str(tgt.get("objectType"), "水面装备"),
                "side": safe_str(aff.get("forceSideName"), "蓝方"),
                "lat": safe_str(loc.get("latitude")),
                "lon": safe_str(loc.get("longitude")),
                "alt": safe_str(loc.get("altitude"), "0"),
                "loadList": [],
            }
            # 蓝方目标默认是 Ship
            raw["type"] = "Ship"
            raw_units.append(raw)

    # 转为 CSV 行
    for r in raw_units:
        units_rows.append({
            "id":              r["id"],
            "name":            r["name"],
            "type":            r["type"],
            "dbid_pending":    "",  # 阶段 2 填
            "side":            r["side"],
            "platform_type":   r["platform_type"],
            "platform_class":  r["platform_class"],
            "platform_category": r["platform_category"],
            "lat":             r["lat"],
            "lon":             r["lon"],
            "alt":             r["alt"],
            "loadout_id_pending": "",  # 阶段 2 填（仅 Aircraft）
            "loadlist_count":  len(r["loadList"]),
            "unit_zh_hint":    r["unit_zh"],
            "group_name":      r["group_name"],
        })

    return units_rows, raw_units


# ========== 提取：targets.csv ==========
def extract_targets(plan: dict) -> list:
    """蓝方目标清单"""
    rows = []
    for kw in plan["task"]["killWebs"]:
        for tgt in kw.get("targets", []):
            aff = tgt.get("affiliation", {})
            loc = tgt.get("location", {})
            rows.append({
                "id":            safe_str(tgt.get("targetID")),
                "name_zh":       safe_str(tgt.get("targetName")),
                "side":          safe_str(aff.get("forceSideName"), "蓝方"),
                "object_type":   safe_str(tgt.get("objectType")),
                "affiliation":   safe_str(aff.get("forceSideName")),
                "military_service": safe_str(aff.get("militaryService")),
                "lat":           safe_str(loc.get("latitude")),
                "lon":           safe_str(loc.get("longitude")),
                "alt":           safe_str(loc.get("altitude"), "0"),
                "priority_level": tgt.get("priorityLevel", ""),
                "target_status": safe_str(tgt.get("targetStatus")),
                "phase_seq":     safe_str(tgt.get("phaseSequence")),
                "phase_name":    safe_str(tgt.get("phaseName")),
                "dbid_pending":  "",  # 阶段 2 填
            })
    return rows


# ========== 提取：weapons.csv ==========
def extract_weapons(plan: dict) -> list:
    """所有需要查 DBID 的武器（去重）"""
    seen = set()
    rows = []
    for pe in plan["platformExecutions"]["platformExecutions"]:
        pid = safe_str(pe.get("platformId"))
        for tk in pe.get("platformTasks", []):
            for w in tk.get("weapons", []) or []:
                key = (safe_str(w.get("name")), safe_str(w.get("type")))
                if key in seen or not key[0]:
                    continue
                seen.add(key)
                rows.append({
                    "platform_id":   pid,
                    "weapon_name":   safe_str(w.get("name")),
                    "weapon_type":   safe_str(w.get("type")),
                    "quantity_max":  w.get("quantity", ""),
                    "dbid_pending":  "",   # 阶段 2 填
                    "loadout_alts":  "",   # 阶段 2 填候选
                })
    # 顶层 weapon 引用（来自 killChains LinkList）
    for kw in plan["task"]["killWebs"]:
        for kc in kw.get("killChains", []):
            for link in kc.get("LinkList", []):
                for p in link.get("platforms", []) or []:
                    w = p.get("weapon") or {}
                    name  = safe_str(w.get("weaponName"))
                    wtype = safe_str(w.get("weaponType"))
                    if not name and not wtype:
                        continue
                    key = (name, wtype)
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append({
                        "platform_id":   safe_str(p.get("platformId")),
                        "weapon_name":   name,
                        "weapon_type":   wtype,
                        "quantity_max":  "",
                        "dbid_pending":  "",
                        "loadout_alts":  "",
                    })
    return rows


# ========== 提取：waypoints.csv ==========
def extract_waypoints(plan: dict) -> list:
    rows = []
    for pe in plan["platformExecutions"]["platformExecutions"]:
        pid = safe_str(pe.get("platformId"))
        route = pe.get("route") or {}
        wp_list = route.get("waypoints") or []
        for i, wp in enumerate(wp_list, 1):
            rows.append({
                "platform_id": pid,
                "seq":           i,
                "lat":           safe_str(wp.get("latitude")),
                "lon":           safe_str(wp.get("longitude")),
                "alt":           safe_str(wp.get("altitude")),
                "speed":         safe_str(wp.get("speed")),
            })
        if not wp_list:
            # 用 initialPosition 作为唯一起点
            ip = pe.get("initialPosition") or {}
            if ip.get("coordinates"):
                lat_lon = safe_str(ip.get("coordinates")).split(",")
                if len(lat_lon) == 2:
                    rows.append({
                        "platform_id": pid,
                        "seq": 1,
                        "lat": safe_str(lat_lon[0]).strip(),
                        "lon": safe_str(lat_lon[1]).strip(),
                        "alt": safe_str(ip.get("altitude"), "0"),
                        "speed": safe_str(ip.get("speed"), "0"),
                    })
    return rows


# ========== 提取：timings.csv ==========
def extract_timings(plan: dict) -> list:
    """combatPhases 时间窗 + killChain LinkList startCondition 时间"""
    rows = []

    # combatPhases.timeWindow
    for p in plan["mission"]["combatPhases"]:
        tw = p.get("timeWindow") or {}
        rows.append({
            "kind":           "combatPhase",
            "tag":            "phase_" + safe_str(p.get("phaseSequence")),
            "phase_seq":      safe_str(p.get("phaseSequence")),
            "phase_name":     safe_str(p.get("phaseName")),
            "absolute_start": safe_str(tw.get("startTime")),
            "absolute_end":   safe_str(tw.get("endTime")),
            "duration_iso":   safe_str(tw.get("duration")),
            "relative_start_seconds": "",
            "startCondition_type": "",
            "kill_chain_id":  "",
            "link_id":        "",
        })

    # killChain.LinkList[].startCondition[].time
    for kw in plan["task"]["killWebs"]:
        for kc in kw.get("killChains", []):
            for link in kc.get("LinkList", []):
                for sc in link.get("startCondition", []) or []:
                    rows.append({
                        "kind":           "killChainLinkStart",
                        "tag":            safe_str(link.get("linkId")),
                        "phase_seq":      "",
                        "phase_name":     safe_str(link.get("linkTaskName")),
                        "absolute_start": safe_str(sc.get("time")),
                        "absolute_end":   "",
                        "duration_iso":   safe_str(link.get("expectedDuration")),
                        "relative_start_seconds": "",
                        "startCondition_type": safe_str(sc.get("type")),
                        "kill_chain_id":  safe_str(kc.get("killChainId")),
                        "link_id":        safe_str(link.get("linkId")),
                    })
    return rows


# ========== 提取：platformTasks.csv (bonus) ==========
def extract_platform_tasks(plan: dict) -> list:
    """平台任务清单 - 阶段 3 用"""
    rows = []
    for pe in plan["platformExecutions"]["platformExecutions"]:
        pid = safe_str(pe.get("platformId"))
        for tk in pe.get("platformTasks", []):
            timing = tk.get("timing") or {}
            weapons = tk.get("weapons") or []
            weapon_str = ";".join(
                f"{safe_str(w.get('name'))}x{safe_str(w.get('quantity'))}"
                for w in weapons
            )
            rows.append({
                "platform_id":       pid,
                "task_id":           safe_str(tk.get("platformTaskId")),
                "task_name":         safe_str(tk.get("platformTaskName")),
                "task_type":         safe_str(tk.get("platformTaskType")),
                "related_killChain": safe_str((tk.get("relatedKillChain") or {}).get("killChainId")),
                "related_link":      safe_str((tk.get("relatedKillChain") or {}).get("relatedLinkId")),
                "targets":           ";".join(tk.get("target") or []),
                "timing_start":      safe_str(timing.get("startTime")),
                "timing_end":        safe_str(timing.get("endTime")),
                "weapons":           weapon_str,
            })
    return rows


# ========== 写入 CSV ==========
def write_csv(path: Path, fieldnames: list, rows: list):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        # 写 BOM 兼容 Excel
        f.write("\ufeff")
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


# ========== Main ==========
def main():
    if not JSON_FILE.exists():
        print(f"[X] 找不到 JSON: {JSON_FILE}")
        sys.exit(1)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    plan = json.loads(JSON_FILE.read_text(encoding="utf-8"))

    # 提取
    units_rows, raw_units     = extract_units(plan)
    targets_rows              = extract_targets(plan)
    weapons_rows              = extract_weapons(plan)
    waypoints_rows            = extract_waypoints(plan)
    timings_rows              = extract_timings(plan)
    ptasks_rows               = extract_platform_tasks(plan)

    # 写 CSV
    write_csv(TABLES_DIR / "units.csv",
        ["id", "name", "type", "dbid_pending", "side", "platform_type",
         "platform_class", "platform_category", "lat", "lon", "alt",
         "loadout_id_pending", "loadlist_count", "unit_zh_hint", "group_name"], units_rows)

    write_csv(TABLES_DIR / "targets.csv",
        ["id", "name_zh", "side", "object_type", "affiliation", "military_service",
         "lat", "lon", "alt", "priority_level", "target_status",
         "phase_seq", "phase_name", "dbid_pending"], targets_rows)

    write_csv(TABLES_DIR / "weapons.csv",
        ["platform_id", "weapon_name", "weapon_type", "quantity_max",
         "dbid_pending", "loadout_alts"], weapons_rows)

    write_csv(TABLES_DIR / "waypoints.csv",
        ["platform_id", "seq", "lat", "lon", "alt", "speed"], waypoints_rows)

    write_csv(TABLES_DIR / "timings.csv",
        ["kind", "tag", "phase_seq", "phase_name", "absolute_start", "absolute_end",
         "duration_iso", "relative_start_seconds", "startCondition_type",
         "kill_chain_id", "link_id"], timings_rows)

    write_csv(TABLES_DIR / "platformTasks.csv",
        ["platform_id", "task_id", "task_name", "task_type", "related_killChain",
         "related_link", "targets", "timing_start", "timing_end", "weapons"], ptasks_rows)

    # 写中间 meta（阶段 2 消费更方便）
    meta = {
        "source_json": str(JSON_FILE),
        "planName":    plan["mission"]["basicInfo"]["planName"],
        "side":         plan["mission"]["basicInfo"]["side"],
        "combatTime":   plan["mission"]["basicInfo"]["combatTime"],
        "raw_units":    raw_units,
        "platform_tasks_count": len(ptasks_rows),
    }
    (STAGING_DIR / "extract_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 写日志
    log_lines = []
    log_lines.append("=" * 70)
    log_lines.append(f"阶段 1 提取摘要 — {plan['mission']['basicInfo']['planName']}")
    log_lines.append("=" * 70)
    log_lines.append(f"planName   : {plan['mission']['basicInfo']['planName']}")
    log_lines.append(f"side       : {plan['mission']['basicInfo']['side']}")
    log_lines.append(f"combatTime : {plan['mission']['basicInfo']['combatTime']}")
    log_lines.append("")
    log_lines.append(f"extract_units       : {len(units_rows)} 行 ({len([u for u in raw_units if u['side']=='红方'])} 红 + "
                     f"{len([u for u in raw_units if u['side']=='蓝方'])} 蓝)")
    log_lines.append(f"extract_targets     : {len(targets_rows)} 行")
    log_lines.append(f"extract_weapons     : {len(weapons_rows)} 行 (含 0数量/同型号去重)")
    log_lines.append(f"extract_waypoints   : {len(waypoints_rows)} 行")
    log_lines.append(f"extract_timings     : {len(timings_rows)} 行 ({sum(1 for r in timings_rows if r['kind']=='combatPhase')} phase + "
                     f"{sum(1 for r in timings_rows if r['kind']=='killChainLinkStart')} killChain)")
    log_lines.append(f"extract_platformTasks: {len(ptasks_rows)} 行")
    log_lines.append("")
    log_lines.append("单位类别分布：")
    type_cnt = {}
    for u in raw_units:
        type_cnt[u["type"]] = type_cnt.get(u["type"], 0) + 1
    for k, v in sorted(type_cnt.items()):
        log_lines.append(f"  {k:12s} : {v}")
    log_lines.append("")
    log_lines.append("待查 DBID 的平台类型（阶段 2 必须解决）：")
    types = sorted(set(u["platform_type"] for u in raw_units if u["platform_type"]))
    for t in types:
        log_lines.append(f"  - {t}")
    log_lines.append("")
    log_lines.append("待查 DBID 的武器：")
    for w in weapons_rows:
        log_lines.append(f"  - {w['weapon_name']:20s} (type={w['weapon_type']!r}, qty_max={w['quantity_max']!r})")
    log_lines.append("")
    log_lines.append(f"输出目录: {TABLES_DIR}")

    (STAGING_DIR / "extract.log").write_text("\n".join(log_lines), encoding="utf-8")

    # 打印到 stdout
    print("\n".join(log_lines))


if __name__ == "__main__":
    main()