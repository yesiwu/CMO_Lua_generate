# """
# 第二层是 ScenarioIR。它是全系统最关键的中间表示。不要直接把 JSON 转 Lua，而是先转成统一结构：
# ScenarioIR
#   metadata: 场景名称、时间、类型、安全等级
#   sides: 红方、蓝方、中立方
#   units: 单位层级、所属阵营、军兵种、单位类型、战斗效能
#   equipments: 装备名称、类型、坐标、挂载、状态、所属单位
#   installations: 设施、指挥所、机场、雷达站等
#   environment: 天气、海况、区域范围
#   missions: 巡逻、打击、防空、侦察、电子压制等任务
#   phases: T+0、T+30、T+40 等阶段
#   kill_chains: 侦察 → 压制 → 打击 → 评估
#   events: 触发器、动作、时间条件
#   victory_conditions: 成功/失败判据
#   unknown_fields: 无法理解但不能丢弃的原始字段
# """
# """
# 这个文件负责三件事：

# 把原始 JSON 转成统一的 ScenarioIR；
# 把单位、装备、事件、阶段、杀伤链抽出来；
# 把 IR 渲染成人能看的 scene_contract.md。
# """

from __future__ import annotations

import json
import hashlib
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple


JsonObj = Dict[str, Any]


RECOGNIZED_TOP_LEVEL_KEYS = {
    "ScenarioInfo",
    "Options",
    "WarPower",
    "Installations",
    "basicInfo",
    "intentAnalysis",
    "situationAssessment",
    "combatPhases",
    "killChains",
    "events",
    "victoryConditions",
    "Mission",
    "missions",
    "referencePoints",
    "ReferencePoints",
}


def stable_json_hash(data: Any) -> str:
    text = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def first_present(d: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
    for key in keys:
        if isinstance(d, dict) and key in d:
            return d[key]
    return default


def to_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


def normalize_location(raw: Any, source_path: str, warnings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    兼容两类坐标字段：
    1. Latitude / Longitude / Altitude
    2. lat / lon / alt
    """
    if not isinstance(raw, dict):
        warnings.append({
            "type": "invalid_location",
            "path": source_path,
            "message": "Location 字段不是对象，无法解析坐标。",
            "severity": "medium",
        })
        return {
            "latitude": None,
            "longitude": None,
            "altitude": None,
            "coordinate_system": None,
            "source_path": source_path,
        }

    lat = first_present(raw, ["Latitude", "latitude", "lat"])
    lon = first_present(raw, ["Longitude", "longitude", "lon"])
    alt = first_present(raw, ["Altitude", "altitude", "alt"], 0)
    coordinate_system = first_present(raw, ["CoordinateSystemType", "coordinateSystemType"], None)

    lat_n = to_number(lat)
    lon_n = to_number(lon)
    alt_n = to_number(alt)

    if lat_n is None or lon_n is None:
        warnings.append({
            "type": "missing_coordinate",
            "path": source_path,
            "message": f"坐标缺失或无法解析：lat={lat!r}, lon={lon!r}",
            "severity": "high",
        })
    else:
        if not (-90 <= lat_n <= 90):
            warnings.append({
                "type": "invalid_latitude_range",
                "path": source_path,
                "message": f"纬度超出范围：{lat_n}",
                "severity": "high",
            })
        if not (-180 <= lon_n <= 180):
            warnings.append({
                "type": "invalid_longitude_range",
                "path": source_path,
                "message": f"经度超出范围：{lon_n}",
                "severity": "high",
            })

    return {
        "latitude": lat_n,
        "longitude": lon_n,
        "altitude": alt_n,
        "coordinate_system": coordinate_system,
        "source_path": source_path,
    }


def infer_side_name(force_side_id: Any, explicit_name: Any = None) -> str:
    if explicit_name:
        return str(explicit_name)

    text = str(force_side_id or "").upper()
    if "RED" in text:
        return "红方"
    if "BLUE" in text:
        return "蓝方"
    if "NEUTRAL" in text:
        return "中立方"
    return "未知阵营"


def extract_metadata(raw: JsonObj) -> Dict[str, Any]:
    info = raw.get("ScenarioInfo", {}) if isinstance(raw.get("ScenarioInfo"), dict) else {}

    return {
        "scenario_id": info.get("ScenarioId"),
        "scenario_name": info.get("ScenarioName"),
        "scenario_type": info.get("ScenarioType"),
        "scenario_purpose": info.get("ScenarioPurpose"),
        "start_time": info.get("ScenarioStartTime"),
        "description": info.get("ScenarioDescription"),
        "operational_background": info.get("OperationalBackground"),
        "operational_determination": info.get("OperationalDetermination"),
        "security_classification": info.get("SecurityClassification"),
        "version": info.get("Version"),
        "source_path": "ScenarioInfo",
    }


def extract_units_and_equipments(raw: JsonObj) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    warnings: List[Dict[str, Any]] = []
    units: List[Dict[str, Any]] = []
    equipments: List[Dict[str, Any]] = []

    war_power = raw.get("WarPower", {})
    force_sides = war_power.get("ForceSides", []) if isinstance(war_power, dict) else []

    if not isinstance(force_sides, list):
        warnings.append({
            "type": "invalid_force_sides",
            "path": "WarPower.ForceSides",
            "message": "WarPower.ForceSides 不是数组。",
            "severity": "high",
        })
        return units, equipments, warnings

    for fs_idx, force_side in enumerate(force_sides):
        if not isinstance(force_side, dict):
            warnings.append({
                "type": "invalid_force_side_item",
                "path": f"WarPower.ForceSides[{fs_idx}]",
                "message": "ForceSide 不是对象。",
                "severity": "medium",
            })
            continue

        fs_id = first_present(force_side, ["ForceSideID", "SideID", "id"])
        fs_name = first_present(force_side, ["ForceSideName", "SideName", "name"])
        units_raw = force_side.get("Unit", [])

        if not isinstance(units_raw, list):
            warnings.append({
                "type": "invalid_unit_list",
                "path": f"WarPower.ForceSides[{fs_idx}].Unit",
                "message": "Unit 字段不是数组。",
                "severity": "high",
            })
            continue

        for unit_idx, unit in enumerate(units_raw):
            if not isinstance(unit, dict):
                continue

            unit_path = f"WarPower.ForceSides[{fs_idx}].Unit[{unit_idx}]"
            unit_id = unit.get("UnitID")
            unit_name = unit.get("UnitName")
            force_side_id = unit.get("ForceSideID") or fs_id
            side_name = infer_side_name(force_side_id, fs_name)

            if not unit_id:
                warnings.append({
                    "type": "missing_unit_id",
                    "path": unit_path,
                    "message": "单位缺少 UnitID。",
                    "severity": "medium",
                })
            if not unit_name:
                warnings.append({
                    "type": "missing_unit_name",
                    "path": unit_path,
                    "message": "单位缺少 UnitName。",
                    "severity": "medium",
                })

            unit_location = normalize_location(
                unit.get("UnitLocation", {}),
                f"{unit_path}.UnitLocation",
                warnings,
            )

            unit_record = {
                "unit_id": unit_id,
                "unit_name": unit_name,
                "side": side_name,
                "force_side_id": force_side_id,
                "unit_type": unit.get("UnitType"),
                "unit_echelon": unit.get("UnitEchelon"),
                "military_service": unit.get("UnitMilitaryService"),
                "parent_unit_id": unit.get("ParentUnitID"),
                "combat_effectiveness": unit.get("CombatEffectiveness"),
                "direction_of_movement": unit.get("DirectionOfMovement"),
                "speed": unit.get("Speed"),
                "location": unit_location,
                "equipment_count": len(unit.get("Equipments", [])) if isinstance(unit.get("Equipments"), list) else 0,
                "source_path": unit_path,
            }
            units.append(unit_record)

            eqs_raw = unit.get("Equipments", [])
            if not isinstance(eqs_raw, list):
                warnings.append({
                    "type": "invalid_equipment_list",
                    "path": f"{unit_path}.Equipments",
                    "message": "Equipments 字段不是数组。",
                    "severity": "medium",
                })
                continue

            for eq_idx, eq in enumerate(eqs_raw):
                if not isinstance(eq, dict):
                    continue

                eq_path = f"{unit_path}.Equipments[{eq_idx}]"
                equipment_id = eq.get("EquipmentID")
                equipment_name = eq.get("EquipmentName")

                if not equipment_id:
                    warnings.append({
                        "type": "missing_equipment_id",
                        "path": eq_path,
                        "message": "装备缺少 EquipmentID。",
                        "severity": "medium",
                    })
                if not equipment_name:
                    warnings.append({
                        "type": "missing_equipment_name",
                        "path": eq_path,
                        "message": "装备缺少 EquipmentName。",
                        "severity": "medium",
                    })

                location = normalize_location(eq.get("Location", {}), f"{eq_path}.Location", warnings)

                components = []
                comp_raw = eq.get("ComponentList", [])
                if isinstance(comp_raw, list):
                    for comp_idx, comp in enumerate(comp_raw):
                        if not isinstance(comp, dict):
                            continue
                        components.append({
                            "component_code": comp.get("gzzbnm"),
                            "component_name": comp.get("componentName"),
                            "quantity_remaining": comp.get("QuantityRemaining"),
                            "source_path": f"{eq_path}.ComponentList[{comp_idx}]",
                        })

                equipments.append({
                    "equipment_id": equipment_id,
                    "equipment_name": equipment_name,
                    "side": side_name,
                    "force_side_id": force_side_id,
                    "parent_unit_id": unit_id,
                    "parent_unit_name": unit_name,
                    "equipment_type": eq.get("EquipmentType"),
                    "equipment_class": eq.get("EquipmentClass"),
                    "equipment_category": eq.get("EquipmentCategory"),
                    "equipment_sub_category": eq.get("EquipmentSubCategory"),
                    "equipment_status": eq.get("EquipmentStatus"),
                    "combat_effectiveness": eq.get("EquipmentCombatEffectiveness"),
                    "on_ground": eq.get("OnGround"),
                    "speed": eq.get("EquipmentSpeed"),
                    "location": location,
                    "components": components,
                    "source_path": eq_path,
                })

    return units, equipments, warnings


def extract_events(raw: JsonObj) -> List[Dict[str, Any]]:
    events_raw = raw.get("events") or raw.get("Events") or {}
    events: List[Dict[str, Any]] = []

    if isinstance(events_raw, dict):
        for event_id, event in events_raw.items():
            if not isinstance(event, dict):
                continue
            events.append({
                "event_id": event_id,
                "event_name": event.get("eventName") or event.get("name"),
                "time_seconds": event.get("timeSeconds"),
                "description": event.get("description"),
                "actions": event.get("actions", []),
                "source_path": f"events.{event_id}",
            })

    elif isinstance(events_raw, list):
        for idx, event in enumerate(events_raw):
            if not isinstance(event, dict):
                continue
            event_id = event.get("eventId") or event.get("id") or f"event_{idx}"
            events.append({
                "event_id": event_id,
                "event_name": event.get("eventName") or event.get("name"),
                "time_seconds": event.get("timeSeconds"),
                "description": event.get("description"),
                "actions": event.get("actions", []),
                "source_path": f"events[{idx}]",
            })

    return events


def extract_combat_phases(raw: JsonObj) -> List[Dict[str, Any]]:
    phases_raw = raw.get("combatPhases") or raw.get("CombatPhases") or []
    phases: List[Dict[str, Any]] = []

    if not isinstance(phases_raw, list):
        return phases

    for idx, phase in enumerate(phases_raw):
        if not isinstance(phase, dict):
            continue
        phases.append({
            "phase_sequence": phase.get("phaseSequence"),
            "phase_name": phase.get("phaseName"),
            "time_window": phase.get("timeWindow"),
            "phase_purpose": phase.get("phasePurpose"),
            "critical_tasks": phase.get("criticalTasks", []),
            "source_path": f"combatPhases[{idx}]",
        })

    return phases


def extract_kill_chains(raw: JsonObj) -> List[Dict[str, Any]]:
    raw_chains = raw.get("killChains") or raw.get("KillChains") or []
    chains: List[Dict[str, Any]] = []

    if not isinstance(raw_chains, list):
        return chains

    for idx, chain in enumerate(raw_chains):
        if not isinstance(chain, dict):
            continue
        links = chain.get("LinkList") or chain.get("links") or []
        chains.append({
            "kill_chain_id": chain.get("killChainId"),
            "kill_chain_name": chain.get("killChainName"),
            "description": chain.get("killChainDescription"),
            "links": links if isinstance(links, list) else [],
            "source_path": f"killChains[{idx}]",
        })

    return chains


def extract_reference_points(raw: JsonObj) -> Dict[str, List[Dict[str, Any]]]:
    rp_raw = raw.get("referencePoints") or raw.get("ReferencePoints") or {}
    result: Dict[str, List[Dict[str, Any]]] = {}

    if not isinstance(rp_raw, dict):
        return result

    for side, points in rp_raw.items():
        if not isinstance(points, list):
            continue
        result[str(side)] = []
        for idx, p in enumerate(points):
            if not isinstance(p, dict):
                continue
            result[str(side)].append({
                "name": p.get("name"),
                "latitude": to_number(p.get("latitude") or p.get("Latitude")),
                "longitude": to_number(p.get("longitude") or p.get("Longitude")),
                "source_path": f"referencePoints.{side}[{idx}]",
            })

    return result


def extract_missions(raw: JsonObj) -> List[Dict[str, Any]]:
    missions_raw = raw.get("Mission") or raw.get("missions") or raw.get("Missions") or []
    missions: List[Dict[str, Any]] = []

    if isinstance(missions_raw, dict):
        iterable = missions_raw.items()
        for key, mission in iterable:
            if not isinstance(mission, dict):
                continue
            missions.append({
                "mission_id": mission.get("missionId") or mission.get("id") or key,
                "mission_name": mission.get("missionName") or mission.get("name"),
                "mission_type": mission.get("missionType") or mission.get("type"),
                "side": mission.get("side"),
                "description": mission.get("description") or mission.get("missionDescription"),
                "raw": mission,
                "source_path": f"Mission.{key}",
            })

    elif isinstance(missions_raw, list):
        for idx, mission in enumerate(missions_raw):
            if not isinstance(mission, dict):
                continue
            missions.append({
                "mission_id": mission.get("missionId") or mission.get("id") or f"mission_{idx}",
                "mission_name": mission.get("missionName") or mission.get("name"),
                "mission_type": mission.get("missionType") or mission.get("type"),
                "side": mission.get("side"),
                "description": mission.get("description") or mission.get("missionDescription"),
                "raw": mission,
                "source_path": f"Mission[{idx}]",
            })

    return missions


def extract_victory_conditions(raw: JsonObj) -> Any:
    return raw.get("victoryConditions") or raw.get("VictoryConditions") or None


def build_summary(units: List[Dict[str, Any]], equipments: List[Dict[str, Any]]) -> Dict[str, Any]:
    unit_by_side = Counter(u.get("side") or "未知阵营" for u in units)
    unit_by_type = Counter(u.get("unit_type") or "未知类型" for u in units)
    eq_by_side = Counter(e.get("side") or "未知阵营" for e in equipments)
    eq_by_category = Counter(e.get("equipment_category") or "未知装备类别" for e in equipments)
    eq_by_type = Counter(e.get("equipment_type") or "未知装备类型" for e in equipments)

    return {
        "unit_count": len(units),
        "equipment_count": len(equipments),
        "unit_count_by_side": dict(unit_by_side),
        "unit_count_by_type": dict(unit_by_type),
        "equipment_count_by_side": dict(eq_by_side),
        "equipment_count_by_category": dict(eq_by_category),
        "top_equipment_types": dict(eq_by_type.most_common(20)),
    }


def build_ir(raw: JsonObj, schema_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    metadata = extract_metadata(raw)
    units, equipments, unit_warnings = extract_units_and_equipments(raw)

    combat_phases = extract_combat_phases(raw)
    kill_chains = extract_kill_chains(raw)
    events = extract_events(raw)
    missions = extract_missions(raw)
    reference_points = extract_reference_points(raw)
    victory_conditions = extract_victory_conditions(raw)

    top_keys = set(raw.keys())
    unknown_top_level_keys = sorted(top_keys - RECOGNIZED_TOP_LEVEL_KEYS)

    warnings = list(unit_warnings)
    if unknown_top_level_keys:
        warnings.append({
            "type": "unknown_top_level_keys",
            "path": "$",
            "message": f"存在未进入第一版 IR 的顶层字段：{unknown_top_level_keys}",
            "severity": "low",
        })

    ir = {
        "ir_version": "0.1",
        "source_hash": stable_json_hash(raw),
        "metadata": metadata,
        "summary": build_summary(units, equipments),
        "units": units,
        "equipments": equipments,
        "combat_phases": combat_phases,
        "kill_chains": kill_chains,
        "events": events,
        "missions": missions,
        "reference_points": reference_points,
        "victory_conditions": victory_conditions,
        "unknown_top_level_keys": unknown_top_level_keys,
        "warnings": warnings,
    }

    if schema_profile:
        ir["schema_profile_hash"] = stable_json_hash(schema_profile)

    return ir


def render_scene_contract(ir: Dict[str, Any], max_items: int = 20) -> str:
    md = ir.get("metadata", {})
    summary = ir.get("summary", {})
    warnings = ir.get("warnings", [])

    lines: List[str] = []

    lines.append(f"# 场景文本合同：{md.get('scenario_name') or '未命名场景'}")
    lines.append("")
    lines.append("> 本文件由 ScenarioIR 自动生成，用于人工审核系统对 JSON 场景的理解是否正确。")
    lines.append("> 注意：本文件不是 Lua 脚本，也不是最终仿真方案；它是后续 Lua 生成前的语义合同。")
    lines.append("")

    lines.append("## 1. 场景基本信息")
    lines.append("")
    lines.append(f"- 场景 ID：{md.get('scenario_id')}")
    lines.append(f"- 场景名称：{md.get('scenario_name')}")
    lines.append(f"- 场景类型：{md.get('scenario_type')}")
    lines.append(f"- 开始时间：{md.get('start_time')}")
    lines.append(f"- 安全等级：{md.get('security_classification')}")
    lines.append(f"- 来源字段：`{md.get('source_path')}`")
    lines.append("")

    if md.get("scenario_purpose"):
        lines.append("### 1.1 场景目的")
        lines.append("")
        lines.append(str(md.get("scenario_purpose")))
        lines.append("")

    if md.get("description"):
        lines.append("### 1.2 原始场景描述")
        lines.append("")
        lines.append(str(md.get("description")))
        lines.append("")

    if md.get("operational_background"):
        lines.append("### 1.3 作战背景")
        lines.append("")
        lines.append(str(md.get("operational_background")))
        lines.append("")

    if md.get("operational_determination"):
        lines.append("### 1.4 作战决心")
        lines.append("")
        lines.append(str(md.get("operational_determination")))
        lines.append("")

    lines.append("## 2. 实体摘要")
    lines.append("")
    lines.append(f"- 单位总数：{summary.get('unit_count', 0)}")
    lines.append(f"- 装备总数：{summary.get('equipment_count', 0)}")
    lines.append(f"- 单位按阵营统计：`{summary.get('unit_count_by_side', {})}`")
    lines.append(f"- 单位按类型统计：`{summary.get('unit_count_by_type', {})}`")
    lines.append(f"- 装备按阵营统计：`{summary.get('equipment_count_by_side', {})}`")
    lines.append(f"- 装备按类别统计：`{summary.get('equipment_count_by_category', {})}`")
    lines.append("")

    lines.append("### 2.1 单位样例")
    lines.append("")
    lines.append("| 阵营 | 单位ID | 单位名称 | 单位类型 | 军兵种 | 装备数 | 来源 |")
    lines.append("|---|---|---|---|---|---:|---|")
    for u in ir.get("units", [])[:max_items]:
        lines.append(
            f"| {u.get('side')} | {u.get('unit_id')} | {u.get('unit_name')} | "
            f"{u.get('unit_type')} | {u.get('military_service')} | "
            f"{u.get('equipment_count')} | `{u.get('source_path')}` |"
        )
    lines.append("")

    lines.append("### 2.2 装备样例")
    lines.append("")
    lines.append("| 阵营 | 装备ID | 装备名称 | 类型 | 类别 | 父单位 | 坐标 | 来源 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for e in ir.get("equipments", [])[:max_items]:
        loc = e.get("location", {})
        coord = f"{loc.get('latitude')}, {loc.get('longitude')}, alt={loc.get('altitude')}"
        lines.append(
            f"| {e.get('side')} | {e.get('equipment_id')} | {e.get('equipment_name')} | "
            f"{e.get('equipment_type')} | {e.get('equipment_category')} / {e.get('equipment_sub_category')} | "
            f"{e.get('parent_unit_name')} | {coord} | `{e.get('source_path')}` |"
        )
    lines.append("")

    lines.append("## 3. 作战阶段")
    lines.append("")
    phases = ir.get("combat_phases", [])
    if not phases:
        lines.append("- 暂未从 JSON 中解析到 combatPhases。")
    for p in phases:
        lines.append(f"- 阶段 {p.get('phase_sequence')}：{p.get('phase_name')}")
        lines.append(f"  - 时间窗口：`{p.get('time_window')}`")
        lines.append(f"  - 目的：{p.get('phase_purpose')}")
        lines.append(f"  - 来源：`{p.get('source_path')}`")
        for task in p.get("critical_tasks", [])[:10]:
            if isinstance(task, dict):
                lines.append(f"  - 关键任务：{task.get('taskName')} —— {task.get('taskDescription')}")
    lines.append("")

    lines.append("## 4. 杀伤链 / 任务链")
    lines.append("")
    chains = ir.get("kill_chains", [])
    if not chains:
        lines.append("- 暂未从 JSON 中解析到 killChains。")
    for c in chains:
        lines.append(f"- {c.get('kill_chain_name')}：{c.get('description')}")
        lines.append(f"  - 来源：`{c.get('source_path')}`")
        for link in c.get("links", [])[:20]:
            if isinstance(link, dict):
                lines.append(
                    f"  - {link.get('linkName')}：目标阵营={link.get('targetSide')}，"
                    f"平台数={len(link.get('platforms', [])) if isinstance(link.get('platforms'), list) else 0}，"
                    f"武器={link.get('weapon')}"
                )
    lines.append("")

    lines.append("## 5. 事件")
    lines.append("")
    events = ir.get("events", [])
    if not events:
        lines.append("- 暂未从 JSON 中解析到 events。")
    for ev in events[:max_items]:
        lines.append(
            f"- {ev.get('event_id')} / {ev.get('event_name')}：T+{ev.get('time_seconds')} 秒，"
            f"{ev.get('description')}，动作数={len(ev.get('actions', [])) if isinstance(ev.get('actions'), list) else 0}"
        )
        lines.append(f"  - 来源：`{ev.get('source_path')}`")
    lines.append("")

    lines.append("## 6. 参考点")
    lines.append("")
    rps = ir.get("reference_points", {})
    if not rps:
        lines.append("- 暂未从 JSON 中解析到 referencePoints。")
    for side, points in rps.items():
        lines.append(f"- {side}：{len(points)} 个参考点")
        for p in points[:10]:
            lines.append(f"  - {p.get('name')}：({p.get('latitude')}, {p.get('longitude')})")
    lines.append("")

    lines.append("## 7. 胜利条件")
    lines.append("")
    if ir.get("victory_conditions") is None:
        lines.append("- 暂未从 JSON 中解析到 victoryConditions。")
    else:
        lines.append("```json")
        lines.append(json.dumps(ir.get("victory_conditions"), ensure_ascii=False, indent=2))
        lines.append("```")
    lines.append("")

    lines.append("## 8. 待确认问题 / 解析警告")
    lines.append("")
    if not warnings:
        lines.append("- 暂无警告。")
    else:
        high = [w for w in warnings if w.get("severity") == "high"]
        medium = [w for w in warnings if w.get("severity") == "medium"]
        low = [w for w in warnings if w.get("severity") == "low"]
        lines.append(f"- 高风险：{len(high)}")
        lines.append(f"- 中风险：{len(medium)}")
        lines.append(f"- 低风险：{len(low)}")
        lines.append("")
        lines.append("| 严重级别 | 类型 | 路径 | 说明 |")
        lines.append("|---|---|---|---|")
        for w in warnings[:max_items * 2]:
            lines.append(
                f"| {w.get('severity')} | {w.get('type')} | `{w.get('path')}` | {w.get('message')} |"
            )
    lines.append("")

    lines.append("## 9. 人工审核建议")
    lines.append("")
    lines.append("审核时请只判断：本合同是否忠实表达 JSON。")
    lines.append("")
    lines.append("- 如果只是措辞不清，请选择“要求修改：表述优化”。")
    lines.append("- 如果漏掉 JSON 中已有信息，请指出对应模块，例如 WarPower / events / killChains。")
    lines.append("- 如果要加入 JSON 中没有的新设定，请标记为“新增需求”，不要直接写入事实层。")
    lines.append("- 如果发现 JSON 本身错误，请走 human_override 机制。")
    lines.append("")

    return "\n".join(lines)


def save_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)