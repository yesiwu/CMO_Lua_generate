# -*- coding: utf-8 -*-
"""CMO 作战 JSON -> Lua 脚本通用生成器。

以 json/7V3.lua 为黄金模板，输入满足 json/red_blue_5v3_liaoning1.json
结构的作战方案 JSON，输出一份可直接粘贴到 CMO Lua 控制台执行的 all.lua。

生成的脚本分 5 段:
  1) main        建阵营 + 建单位(红方舰艇/航母/舰载机 + 蓝方目标)
  2) clear       清弹(红方发射过导弹的舰艇, 遍历 mounts + remove=true)
  3) reload      装弹(舰艇 + 舰载机, 只装方案指定弹药)
  4) attack-ship 舰艇真延时打击(Time Trigger 事件驱动)
  5) attack-air  舰载机 起飞 + 航路 + 打击 + 返航

用法:
    python tools/json_to_lua.py <input.json> [output.lua]
或作为库:
    from tools.json_to_lua import generate_cmo_lua
    lua_text = generate_cmo_lua("json/red_blue_5v3_liaoning1.json")
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional, Tuple

# 默认 contact 沉降延时(秒). 可被 JSON 顶层 settle 覆盖.
DEFAULT_SETTLE_SHIP = 30
DEFAULT_SETTLE_AIR = 150

# 被视为"航母/母舰"的 type 关键字(不清弹/不装反舰弹, 只作为舰载机 base).
CARRIER_TYPES = {"CV", "CVN", "CARRIER", "航母", "航空母舰"}

# 被视为"飞机"的 type 关键字(走 Aircraft 分支).
AIRCRAFT_TYPE_HINTS = {"J-15", "J15", "AIRCRAFT", "FIGHTER", "飞机", "舰载机"}


def _q(s: Any) -> str:
    """把字符串转成 Lua 双引号字面量(转义反斜杠与引号)."""
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _num(v: Any, default: float = 0.0) -> float:
    """尽量把值转为数字; 非数字(如'待机场设定')返回 default."""
    if _is_number(v):
        return float(v)
    try:
        return float(str(v).strip())
    except (ValueError, AttributeError):
        return default


def _is_carrier(unit: Dict[str, Any]) -> bool:
    t = str(unit.get("type", "")).upper()
    if t in CARRIER_TYPES:
        return True
    # 兜底: units 中若 aircraftCarried 字段非空, 也按航母处理
    return bool(unit.get("aircraftCarried"))


def _is_aircraft(unit: Dict[str, Any]) -> bool:
    t = str(unit.get("type", "")).upper()
    return any(h.upper() in t for h in AIRCRAFT_TYPE_HINTS) or "AIRCRAFT" in t


def _classify(unit: Dict[str, Any]) -> str:
    """返回 'aircraft' | 'carrier' | 'ship'. 优先 aircraft(舰载机)."""
    if _is_aircraft(unit):
        return "aircraft"
    if _is_carrier(unit):
        return "carrier"
    return "ship"


def _unit_index(plan: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """建 {id: unit} 索引, 给 strikePlan 用."""
    idx: Dict[str, Dict[str, Any]] = {}
    for side_key in ("red", "blue"):
        for u in plan.get("sides", {}).get(side_key, {}).get("units", []):
            uid = u.get("id")
            if uid:
                idx[uid] = u
    return idx


def _blue_target_name(units_idx: Dict[str, Dict[str, Any]], tid: str) -> Optional[str]:
    """从 blue 单位 id 解析其 name (Lua 用 name 不用 id)."""
    u = units_idx.get(tid)
    return u.get("name") if u else None


def _resolve_shooter_name(units_idx: Dict[str, Dict[str, Any]], shooter_id: str) -> Optional[str]:
    u = units_idx.get(shooter_id)
    return u.get("name") if u else None


def _resolve_aircraft_base(units_idx: Dict[str, Dict[str, Any]], aircraft_unit: Dict[str, Any]) -> Optional[str]:
    """优先取 aircraft_unit.base, 再去索引里查 carrier 的 name."""
    base_id = aircraft_unit.get("base")
    if not base_id:
        return None
    base = units_idx.get(base_id)
    return base.get("name") if base else None


# ============================================================================
# 段 1: 顶部 banner + 全局常量
# ============================================================================
def _render_header(plan: Dict[str, Any]) -> str:
    scenario_name = plan.get("scenario", {}).get("name", "作战方案")
    side_red = plan.get("sides", {}).get("red", {}).get("name", "红方")
    side_blue = plan.get("sides", {}).get("blue", {}).get("name", "蓝方")
    settle = plan.get("settle", {})
    settle_ship = int(settle.get("ship", DEFAULT_SETTLE_SHIP))
    settle_air = int(settle.get("air", DEFAULT_SETTLE_AIR))

    return f'''-- ============================================================
-- all.lua  {scenario_name}  生成自 JSON 作战方案
-- 黄金模板: json/7V3.lua   分段: main -> clear -> reload -> attack-ship -> attack-air
-- ============================================================

print("\\n========================================")
print("[all] {scenario_name} (JSON 驱动自动生成)")
print("========================================")

_SIDE_RED  = {_q(side_red)}
_SIDE_BLUE = {_q(side_blue)}

_SETTLE_SHIP = {settle_ship}   -- 舰艇首发沉降延时(秒)
_SETTLE_AIR  = {settle_air}    -- 舰载机起飞+航路+contact 沉降延时(秒)
'''


# ============================================================================
# 段 2: MANIFEST 三张表 + getUnit
# ============================================================================
def _render_manifest(plan: Dict[str, Any]) -> str:
    red_units = plan.get("sides", {}).get("red", {}).get("units", [])
    blue_units = plan.get("sides", {}).get("blue", {}).get("units", [])

    units_idx = _unit_index(plan)
    ships: List[Dict[str, Any]] = []
    aircraft: List[Dict[str, Any]] = []
    for u in red_units:
        cls = _classify(u)
        if cls == "aircraft":
            base_name = _resolve_aircraft_base(units_idx, u) or u.get("base", "")
            u = dict(u)
            u["base_name"] = base_name
            aircraft.append(u)
        else:
            ships.append(u)  # 含航母; clear/reload 段按 type 跳过航母

    def fmt_ship_entry(u: Dict[str, Any]) -> str:
        return (f'    {{name={_q(u.get("name",""))}, dbid={int(u.get("dbid",0))}, '
                f'lat={_num(u.get("latitude")):.4f}, lon={_num(u.get("longitude")):.4f}, '
                f'heading={int(_num(u.get("heading", 0)))}, speed={int(_num(u.get("speed", 0)))}, '
                f'prof={_q(u.get("proficiency", "Veteran"))}}}')

    def fmt_aircraft_entry(u: Dict[str, Any]) -> str:
        return (f'    {{name={_q(u.get("name",""))}, dbid={int(u.get("dbid",0))}, '
                f'base={_q(u.get("base_name",""))}, '
                f'prof={_q(u.get("proficiency", "Veteran"))}, '
                f'loadoutid={int(u.get("loadoutId", 0))}}}')

    def fmt_blue_entry(u: Dict[str, Any]) -> str:
        return (f'    {{name={_q(u.get("name",""))}, dbid={int(u.get("dbid",0))}, '
                f'lat={_num(u.get("latitude")):.4f}, lon={_num(u.get("longitude")):.4f}, '
                f'heading={int(_num(u.get("heading", 0)))}, speed={int(_num(u.get("speed", 0)))}, '
                f'prof={_q(u.get("proficiency", "Veteran"))}}}')

    def _join(entries: List[str]) -> str:
        return "".join(e + ",\n" for e in entries)

    ships_block = _join([fmt_ship_entry(u) for u in ships])
    aircraft_block = _join([fmt_aircraft_entry(u) for u in aircraft])
    blue_block = _join([fmt_blue_entry(u) for u in blue_units])

    return (
        "-- ============================================================\n"
        "-- MANIFEST (从 JSON 生成)\n"
        "-- ============================================================\n"
        "local MANIFEST_SHIPS = {\n" + ships_block + "}\n"
        "local MANIFEST_AIRCRAFT = {\n" + aircraft_block + "}\n"
        "local MANIFEST_BLUE = {\n" + blue_block + "}\n\n"
        "local function getUnit(side, name)\n"
        "    local ok, u = pcall(ScenEdit_GetUnit, {side=side, name=name})\n"
        "    if ok and u and u.guid then return u end\n"
        "    return nil\n"
        "end\n"
    )


# ============================================================================
# 段 3: main do 块 (建阵营 + 建单位). 该段与 MANIFEST 内容无关, 是静态模板.
# ============================================================================
def _render_main() -> str:
    return r'''
-- ============================================================
-- 第1段: main
-- ============================================================
do
    print("\n===== [main] 建阵营 + 建单位 =====")

    pcall(ScenEdit_AddSide, {name=_SIDE_RED,  color="255,0,0"})
    pcall(ScenEdit_AddSide, {name=_SIDE_BLUE, color="0,0,255"})
    pcall(ScenEdit_SetSideOptions, {side=_SIDE_RED, awareness="OMNI"})
    pcall(ScenEdit_SetSidePosture, _SIDE_RED,  _SIDE_BLUE, "H")
    pcall(ScenEdit_SetSidePosture, _SIDE_BLUE, _SIDE_RED,  "H")
    for _, side in ipairs({_SIDE_RED, _SIDE_BLUE}) do
        pcall(ScenEdit_SetDoctrine, {side=side}, {
            weapon_control_status_air="0", weapon_control_status_surface="0",
            weapon_control_status_subsurface="0",
        })
    end

    print("[main] 建红方舰艇...")
    for _, s in ipairs(MANIFEST_SHIPS) do
        if not getUnit(_SIDE_RED, s.name) then
            _errnum_ = 0
            local ok = pcall(ScenEdit_AddUnit, {
                type="Ship", side=_SIDE_RED, name=s.name, dbid=s.dbid,
                latitude=s.lat, longitude=s.lon,
                heading=s.heading, speed=s.speed, proficiency=s.prof,
            })
            print("[main] " .. s.name .. " ok=" .. tostring(ok) .. " err=" .. tostring(_errmsg_))
        else
            print("[main] " .. s.name .. " 已存在")
        end
        local u = getUnit(_SIDE_RED, s.name)
        if u then pcall(ScenEdit_SetEMCON, "Unit", u.guid, "Radar=Active") end
    end

    print("[main] 建蓝方舰艇...")
    for _, s in ipairs(MANIFEST_BLUE) do
        if not getUnit(_SIDE_BLUE, s.name) then
            _errnum_ = 0
            local ok = pcall(ScenEdit_AddUnit, {
                type="Ship", side=_SIDE_BLUE, name=s.name, dbid=s.dbid,
                latitude=s.lat, longitude=s.lon,
                heading=s.heading, speed=s.speed,
                autodetectable=true, proficiency=s.prof,
            })
            print("[main] " .. s.name .. " ok=" .. tostring(ok) .. " err=" .. tostring(_errmsg_))
        else
            print("[main] " .. s.name .. " 已存在")
        end
        local u = getUnit(_SIDE_BLUE, s.name)
        if u then
            pcall(ScenEdit_SetUnit, {guid=u.guid, autodetectable=true})
            pcall(ScenEdit_SetEMCON, "Unit", u.guid, "Radar=Active")
        end
    end

    print("[main] 建红方舰载机...")
    for _, a in ipairs(MANIFEST_AIRCRAFT) do
        if not getUnit(_SIDE_RED, a.name) then
            _errnum_ = 0
            local ok = pcall(ScenEdit_AddUnit, {
                type="Aircraft", side=_SIDE_RED, name=a.name, dbid=a.dbid,
                loadoutid=a.loadoutid, base=a.base, proficiency=a.prof,
            })
            if not ok then
                _errnum_ = 0
                ok = pcall(ScenEdit_AddUnit, {
                    type="Aircraft", side=_SIDE_RED, name=a.name, dbid=a.dbid,
                    base=a.base, proficiency=a.prof,
                })
                print("[main] " .. a.name .. " [裸机回退] ok=" .. tostring(ok) .. " err=" .. tostring(_errmsg_))
            else
                print("[main] " .. a.name .. " ok=" .. tostring(ok) .. " err=" .. tostring(_errmsg_))
            end
        else
            print("[main] " .. a.name .. " 已存在")
        end
    end

    print("[main] 完成.")
end
'''


# ============================================================================
# 数据模型: 从 red units 的 weaponLoad + strikePlan 聚合 装弹/清弹/打击
# ============================================================================
# 常见武器名 -> DBID 兜底表(优先用 JSON 内 weaponDbid 或顶层 weaponDbid 映射).
# 这些 DBID 均已通过 MCP 在 DB3K_504.db3 验证; 新武器请在 JSON 里显式给 weaponDbid.
FALLBACK_WEAPON_DBID = {
    "YJ-18": 2868,
    "YJ-83K": 2137,
}


def _weapon_dbid_lookup(plan: Dict[str, Any]) -> Dict[str, int]:
    """收集 武器名->dbid. 优先级: JSON 顶层 weaponDbid 映射 > 各处 weaponDbid > 兜底表."""
    lut: Dict[str, int] = dict(FALLBACK_WEAPON_DBID)

    def scan(loads: List[Dict[str, Any]]) -> None:
        for wl in loads or []:
            wn = wl.get("weapon")
            wd = wl.get("weaponDbid")
            if wn and _is_number(wd):
                lut[str(wn)] = int(wd)

    for side_key in ("red", "blue"):
        for u in plan.get("sides", {}).get(side_key, {}).get("units", []):
            scan(u.get("weaponLoad", []))
    for sp in plan.get("strikePlan", []):
        wn = sp.get("weapon")
        wd = sp.get("weaponDbid")
        if wn and _is_number(wd):
            lut[str(wn)] = int(wd)

    # JSON 顶层可提供 {"weaponDbid": {"YJ-18": 2868, ...}} 显式覆盖
    top = plan.get("weaponDbid")
    if isinstance(top, dict):
        for wn, wd in top.items():
            if _is_number(wd):
                lut[str(wn)] = int(wd)
    return lut


def _build_reload(plan: Dict[str, Any], wlut: Dict[str, int]):
    """返回 (ship_reload, air_reload, clear_names).
    每项: {name, qty, wpn}. clear_names: 需清弹的红方舰艇 name 列表.
    """
    units_idx = _unit_index(plan)
    ship_reload: List[Dict[str, Any]] = []
    air_reload: List[Dict[str, Any]] = []
    clear_names: List[str] = []

    for u in plan.get("sides", {}).get("red", {}).get("units", []):
        cls = _classify(u)
        if cls == "carrier":
            continue  # 航母不清弹/不装反舰弹
        name = u.get("name", "")
        loads = u.get("weaponLoad", [])
        if not loads:
            continue
        for wl in loads:
            wname = str(wl.get("weapon", ""))
            wd = wl.get("weaponDbid") or wlut.get(wname)
            qty = int(_num(wl.get("loaded", 0)))
            if qty <= 0 or not wd:
                continue
            entry = {"name": name, "qty": qty, "wpn": int(wd)}
            if cls == "aircraft":
                air_reload.append(entry)
            else:
                ship_reload.append(entry)
                if name not in clear_names:
                    clear_names.append(name)
    return ship_reload, air_reload, clear_names


def _render_clear(clear_names: List[str]) -> str:
    names_lua = "".join("        " + _q(n) + ",\n" for n in clear_names)
    head = r'''
-- ============================================================
-- 第2段: clear
-- ============================================================
do
    print("\n===== [clear] 清弹 =====")
    local function clearUnitWeapons(side, name)
        local u = ScenEdit_GetUnit({ side = side, name = name })
        if not u or not u.guid then
            print("[clear] [WARN] 找不到 " .. side .. "/" .. name); return false
        end
        local jobs = {}
        for _, m in ipairs(u.mounts or {}) do
            for _, w in ipairs(m.mount_weapons or {}) do
                local cur = tonumber(w.wpn_current) or 0
                if cur > 0 then
                    jobs[#jobs + 1] = { dbid = w.wpn_dbid, num = cur, mountid = m.mount_guid }
                end
            end
        end
        local done, fail = 0, 0
        for _, j in ipairs(jobs) do
            _errnum_ = 0
            ScenEdit_AddReloadsToUnit({
                guid = u.guid, wpn_dbid = j.dbid,
                mount_guid = j.mountid, number = j.num, remove = true,
            })
            if (_errnum_ or 0) == 0 then done = done + 1 else fail = fail + 1 end
        end
        print(("[clear] %s: 减载归零 %d 项 (失败 %d)"):format(name, done, fail))
        return fail == 0
    end
    for _, name in ipairs({
'''
    tail = r'''    }) do
        clearUnitWeapons(_SIDE_RED, name)
    end
    print("[clear] 完成.")
end
'''
    return head + names_lua + tail


def _render_reload(ship_reload: List[Dict[str, Any]], air_reload: List[Dict[str, Any]]) -> str:
    def fmt(entries: List[Dict[str, Any]]) -> str:
        return "".join(
            "        {name=%s, qty=%d, wpn=%d},\n" % (_q(e["name"]), e["qty"], e["wpn"])
            for e in entries
        )
    ship_block = fmt(ship_reload)
    air_block = fmt(air_reload)
    return (
        "\n-- ============================================================\n"
        "-- 第3段: reload\n"
        "-- ============================================================\n"
        "do\n"
        '    print("\\n===== [reload] 装弹 =====")\n'
        "    local SHIPS_RELOAD = {\n" + ship_block + "    }\n"
        "    for _, s in ipairs(SHIPS_RELOAD) do\n"
        "        _errnum_ = 0\n"
        "        local ok = pcall(ScenEdit_AddReloadsToUnit, {\n"
        "            side=_SIDE_RED, unitname=s.name, wpn_dbid=s.wpn, number=s.qty,\n"
        "        })\n"
        '        print(("[reload] %s x%d ok=%s err=%s"):format(s.name, s.qty, tostring(ok), tostring(_errmsg_)))\n'
        "    end\n"
        "    local AIRCRAFT_RELOAD = {\n" + air_block + "    }\n"
        "    for _, a in ipairs(AIRCRAFT_RELOAD) do\n"
        "        _errnum_ = 0\n"
        "        local ok = pcall(ScenEdit_AddReloadsToUnit, {\n"
        "            side=_SIDE_RED, unitname=a.name, wpn_dbid=a.wpn, number=a.qty,\n"
        "        })\n"
        '        print(("[reload] %s x%d ok=%s err=%s"):format(a.name, a.qty, tostring(ok), tostring(_errmsg_)))\n'
        "    end\n"
        '    print("[reload] 完成.")\n'
        "end\n"
    )


# ============================================================================
# 段: 全局函数 (totTicks / fireAt / scheduleLua / scheduleFire) 静态模板
# ============================================================================
def _render_globals() -> str:
    return r'''
-- ============================================================
-- 全局: 时间戳 + 发射函数 + 调度 (舰艇与飞机共用)
-- ============================================================
function totTicks(addSeconds)
    return string.format("%.0f", (ScenEdit_CurrentTime() + addSeconds) * 1e7 + 621355968000000000)
end

-- fireAt: mode="0" 自动选弹; wpnDbid>0 时用指定弹 mode="1"
function fireAt(attackerName, targetName, wpnDbid, qty)
    local atk = ScenEdit_GetUnit({side=_SIDE_RED, name=attackerName})
    local tgt = ScenEdit_GetUnit({side=_SIDE_BLUE, name=targetName})
    if not (atk and atk.guid) then
        print(("[CMO] [ERROR] fireAt 找不到攻击方 %s"):format(tostring(attackerName))); return false end
    if not (tgt and tgt.guid) then
        print(("[CMO] [ERROR] fireAt 找不到目标 %s"):format(tostring(targetName))); return false end

    pcall(ScenEdit_SetUnit, {guid=tgt.guid, autodetectable=true})
    pcall(ScenEdit_SetSideOptions, {side=_SIDE_RED, awareness="OMNI"})

    local contactGuid = nil
    local ok, s = pcall(VP_GetSide, {Side=_SIDE_RED})
    if ok and s and type(s.contacts) == "table" then
        local tg = tostring(tgt.guid):lower()
        for _, c in ipairs(s.contacts) do
            local aid = c.actualunitid or c.actualUnitID or c.actualunitguid or c.actualUnitGuid
            if aid and tostring(aid):lower() == tg then contactGuid = c.guid or c.Guid; break end
        end
        if not contactGuid then
            for _, c in ipairs(s.contacts) do
                local nm = tostring(c.name or c.Name or "")
                if nm ~= "" and (nm == targetName or nm:find(targetName, 1, true)) then
                    contactGuid = c.guid or c.Guid; break
                end
            end
        end
    end
    if not contactGuid then
        print(("[CMO] [ERROR] %s 对 %s 无 contact(推进时间/加大 settle?)"):format(attackerName, targetName))
        return false
    end

    local opts
    if wpnDbid and tonumber(wpnDbid) and tonumber(wpnDbid) > 0 then
        opts = { mode="1", weapon=tonumber(wpnDbid), qty=qty }
    else
        opts = { mode="0" }
    end
    _errnum_ = 0
    local r = ScenEdit_AttackContact(atk.guid, contactGuid, opts)
    print(("[CMO] [FIRE] %s -> %s qty=%s result=%s"):format(
        attackerName, targetName, tostring(qty), tostring(r ~= nil and r ~= false)))
    return r and true or false
end

function scheduleLua(luaBody, delay, tag)
    local ts = tostring(ScenEdit_CurrentTime()) .. "_" .. tag
    local evName, trName, acName = "Ev_"..ts, "Tr_"..ts, "Ac_"..ts
    local script = table.concat({
        luaBody, "\n",
        ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(evName),
        ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(acName),
        ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(trName),
    })
    pcall(ScenEdit_SetTrigger, {mode="add", type="Time", name=trName, Time=totTicks(delay)})
    pcall(ScenEdit_SetAction,  {mode="add", type="LuaScript", name=acName, ScriptText=script})
    pcall(ScenEdit_SetEvent,   evName, {mode="add", IsActive=true, IsRepeatable=false})
    pcall(ScenEdit_SetEventTrigger, evName, {mode="add", name=trName})
    pcall(ScenEdit_SetEventAction,  evName, {mode="add", name=acName})
end

local function scheduleFire(atkName, tgtName, qty, delay, tag)
    local body = ("fireAt(%q,%q,0,%d)"):format(atkName, tgtName, qty)
    scheduleLua(body, delay, tag)
    print(("[attack] [调度] T+%ds  %s -> %s  qty=%d (自动选弹)"):format(delay, atkName, tgtName, qty))
end
'''


# ============================================================================
# strikePlan -> 打击分派 (通用拆分规则)
# ============================================================================
def _pair_shooters_targets(shooters: List[str], targets: List[str]) -> List[Tuple[str, str]]:
    """把 shooters 与 targets 配对成 (shooter, target) 列表.
    规则:
      - 数量相等   -> 一一对应 (zip)
      - 单 shooter -> 该 shooter 打每个 target
      - 单 target  -> 每个 shooter 打该 target
      - 其它       -> 先 zip, 多出的 shooter 轮流分配到 targets
    """
    if not shooters or not targets:
        return []
    if len(shooters) == len(targets):
        return list(zip(shooters, targets))
    if len(shooters) == 1:
        return [(shooters[0], t) for t in targets]
    if len(targets) == 1:
        return [(s, targets[0]) for s in shooters]
    pairs: List[Tuple[str, str]] = []
    for i, s in enumerate(shooters):
        pairs.append((s, targets[i % len(targets)]))
    return pairs


def _split_qty(total: int, n: int) -> List[int]:
    """把 total 尽量均分成 n 份, 前面的份先拿余数."""
    if n <= 0:
        return []
    base, rem = divmod(total, n)
    return [base + (1 if i < rem else 0) for i in range(n)]


def _build_strikes(plan: Dict[str, Any]):
    """返回 (ship_strikes, air_strikes).
    每项: {atk, tgt, qty, wpn, is_air, base_name}.
    """
    units_idx = _unit_index(plan)
    ship_strikes: List[Dict[str, Any]] = []
    air_strikes: List[Dict[str, Any]] = []

    for sp in plan.get("strikePlan", []):
        shooters_ids = sp.get("shooters") or ([sp["shooter"]] if sp.get("shooter") else [])
        targets_ids = sp.get("targets", [])
        fired = int(_num(sp.get("fired", 0)))
        wpn = sp.get("weaponDbid")
        if wpn is not None:
            wpn = int(wpn)

        shooters = [(_resolve_shooter_name(units_idx, s) or s) for s in shooters_ids]
        targets = [(_blue_target_name(units_idx, t) or t) for t in targets_ids]
        pairs = _pair_shooters_targets(shooters, targets)
        if not pairs or fired <= 0:
            continue
        qtys = _split_qty(fired, len(pairs))

        for (atk_name, tgt_name), q in zip(pairs, qtys):
            if q <= 0:
                continue
            atk_unit = None
            for sid in shooters_ids:
                cand = units_idx.get(sid)
                if cand and cand.get("name") == atk_name:
                    atk_unit = cand
                    break
            is_air = bool(atk_unit and _classify(atk_unit) == "aircraft")
            base_name = ""
            if is_air:
                base_name = _resolve_aircraft_base(units_idx, atk_unit) or atk_unit.get("base", "")
            rec = {"atk": atk_name, "tgt": tgt_name, "qty": q, "wpn": wpn,
                   "is_air": is_air, "base_name": base_name,
                   "tgt_id": None}
            # 记录目标 id 以便航路取坐标
            for tid in targets_ids:
                if (_blue_target_name(units_idx, tid) or tid) == tgt_name:
                    rec["tgt_id"] = tid
                    break
            if is_air:
                air_strikes.append(rec)
            else:
                ship_strikes.append(rec)
    return ship_strikes, air_strikes


def _midpoint(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, float]:
    return {
        "lat": (_num(a.get("latitude")) + _num(b.get("latitude"))) / 2,
        "lon": (_num(a.get("longitude")) + _num(b.get("longitude"))) / 2,
    }


def _approach(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, float]:
    lat = _num(a.get("latitude")) + 0.7 * (_num(b.get("latitude")) - _num(a.get("latitude")))
    lon = _num(a.get("longitude")) + 0.7 * (_num(b.get("longitude")) - _num(a.get("longitude")))
    return {"lat": lat, "lon": lon}


def _render_attack_ship(ship_strikes: List[Dict[str, Any]]) -> str:
    body = []
    for i, s in enumerate(ship_strikes):
        body.append("    scheduleFire(" + _q(s["atk"]) + ", " + _q(s["tgt"])
                    + ", %d, _SETTLE_SHIP + %d, %s)\n"
                    % (s["qty"], i * 2, _q("ship_%d_%s" % (i, s["atk"]))))
    block = "".join(body) if body else "    -- 无舰艇打击项"
    return (
        "\n-- ============================================================\n"
        "-- 第4段: attack-ship  舰艇真延时打击\n"
        "-- ============================================================\n"
        "do\n"
        '    print("\\n===== [attack-ship] 舰艇真延时打击 =====")\n'
        + block +
        '    print("[attack-ship] 完成调度.")\n'
        "end\n"
    )


def _render_attack_air(plan: Dict[str, Any], air_strikes: List[Dict[str, Any]]) -> str:
    if not air_strikes:
        return (
            "\n-- ============================================================\n"
            "-- 第5段: attack-air (无舰载机打击, 跳过)\n"
            "-- ============================================================\n"
        )
    units_idx = _unit_index(plan)
    # 为每个舰载机找它的航母/自身作中线参考, 落到目标前坐标
    red_units = plan.get("sides", {}).get("red", {}).get("units", [])
    carrier_lookup: Dict[str, Dict[str, Any]] = {}
    for u in red_units:
        if _classify(u) == "carrier":
            carrier_lookup[u.get("name", "")] = u

    sorties: List[Dict[str, Any]] = []
    for s in air_strikes:
        tgt_id = s.get("tgt_id")
        tgt_unit = units_idx.get(tgt_id) or {}
        # 起飞机: 找飞机的 base 对应的 carrier
        base_name = s.get("base_name") or ""
        base_unit = carrier_lookup.get(base_name) or {}
        mid = _midpoint(base_unit, tgt_unit) if (base_unit and tgt_unit) else {"lat": 0, "lon": 0}
        approach = _approach(base_unit, tgt_unit) if (base_unit and tgt_unit) else {"lat": 0, "lon": 0}
        sorties.append({
            "name": s["atk"],
            "target": s["tgt"],
            "qty": s["qty"],
            "mid": mid,
            "approach": approach,
            "base": base_name,
        })

    sorties_lua = "".join(
        "        {name=%s, target=%s, qty=%d, base=%s, mid={lat=%.4f,lon=%.4f}, approach={lat=%.4f,lon=%.4f}},\n"
        % (_q(s["name"]), _q(s["target"]), s["qty"], _q(s["base"]),
           s["mid"]["lat"], s["mid"]["lon"],
           s["approach"]["lat"], s["approach"]["lon"])
        for s in sorties
    )

    air_strikes_by_name: Dict[str, Dict[str, Any]] = {}
    for s in air_strikes:
        air_strikes_by_name.setdefault(s["atk"], s)

    body = (
        "    local SORTIES = {\n" + sorties_lua + "    }\n\n"
        "    for _, s in ipairs(SORTIES) do\n"
        "        local u = getUnit(_SIDE_RED, s.name)\n"
        "        if not u then\n"
        '            print("[attack-air] [WARN] 找不到 " .. s.name .. ", 跳过")\n'
        "        else\n"
        "            _errnum_ = 0\n"
        "            pcall(ScenEdit_SetUnit, {side=_SIDE_RED, unitname=s.name, timetoready_minutes=0})\n"
        "            _errnum_ = 0\n"
        "            local okL = pcall(ScenEdit_SetUnit, {side=_SIDE_RED, unitname=s.name, launch=true})\n"
        "            _errnum_ = 0\n"
        "            local okC = pcall(ScenEdit_SetUnit, {\n"
        "                side=_SIDE_RED, unitname=s.name,\n"
        "                course = { {latitude=s.mid.lat, longitude=s.mid.lon},\n"
        "                           {latitude=s.approach.lat, longitude=s.approach.lon} },\n"
        "                altitude = 8000, throttle = \"Cruise\",\n"
        "            })\n"
        '            print(("[attack-air] %s 起飞 launch=%s 航路=%s -> 目标 %s"):format(\n'
        "                s.name, tostring(okL), tostring(okC), s.target))\n\n"
        "            local body = (\"fireAt(%q,%q,0,%d)\"):format(s.name, s.target, s.qty)\n"
        '            local tag = "air_fire_" .. s.name\n'
        "            scheduleLua(body, _SETTLE_AIR, tag)\n"
        '            print(("[attack-air] [调度] T+%ds  %s -> %s  qty=%d (自动选弹)"):format(_SETTLE_AIR, s.name, s.target, s.qty))\n'
        "\n"
        "            local rtbBody = table.concat({\n"
        '                ("ScenEdit_SetUnit({side=%q, unitname=%q, base=%q})\\n"):format(_SIDE_RED, s.name, s.base),\n'
        '                ("ScenEdit_SetUnit({side=%q, unitname=%q, rtb=true})\\n"):format(_SIDE_RED, s.name),\n'
        "            })\n"
        '            scheduleLua(rtbBody, _SETTLE_AIR + 120, "air_rtb_" .. s.name)\n'
        '            print(("[attack-air] [调度] T+%ds  %s 返航"):format(_SETTLE_AIR + 120, s.name))\n'
        "        end\n"
        "    end\n"
        '    print("[attack-air] 完成调度.")\n'
    )
    return (
        "\n-- ============================================================\n"
        "-- 第5段: attack-air  舰载机 起飞 + 航路 + 打击 + 返航\n"
        "-- ============================================================\n"
        "do\n"
        '    print("\\n===== [attack-air] 舰载机起飞打击 =====")\n'
        + body +
        "end\n"
    )


# ============================================================================
# 校验 + 主入口
# ============================================================================
def _validate(plan: Dict[str, Any]) -> List[str]:
    """返回警告列表(不致命). 致命错误直接 raise ValueError."""
    warnings: List[str] = []
    sides = plan.get("sides")
    if not sides or "red" not in sides or "blue" not in sides:
        raise ValueError("JSON 缺少 sides.red / sides.blue")
    units_idx = _unit_index(plan)

    for u in plan.get("sides", {}).get("red", {}).get("units", []):
        if _classify(u) == "aircraft":
            base = _resolve_aircraft_base(units_idx, u)
            if not base:
                warnings.append("舰载机 %s 缺少可解析的 base(母舰), 起飞可能失败" % u.get("name"))
            if not _is_number(u.get("loadoutId")):
                warnings.append("舰载机 %s 缺少 loadoutId, 将走裸机回退" % u.get("name"))
        if not _is_number(u.get("dbid")):
            warnings.append("红方单位 %s 的 dbid 非数值(需 MCP 查询)" % u.get("name"))

    for sp in plan.get("strikePlan", []):
        for tid in sp.get("targets", []):
            if tid not in units_idx:
                warnings.append("strikePlan 目标 id '%s' 在 units 中找不到" % tid)
        sid_list = sp.get("shooters") or ([sp["shooter"]] if sp.get("shooter") else [])
        for sid in sid_list:
            if sid not in units_idx:
                warnings.append("strikePlan 射手 id '%s' 在 units 中找不到" % sid)
    return warnings


def generate_cmo_lua(json_path: str, verbose: bool = True) -> str:
    """读取作战 JSON, 返回完整 all.lua 文本."""
    with open(json_path, "r", encoding="utf-8") as f:
        plan = json.load(f)

    warnings = _validate(plan)
    if verbose and warnings:
        for w in warnings:
            print("[warn] " + w, file=sys.stderr)

    wlut = _weapon_dbid_lookup(plan)
    ship_reload, air_reload, clear_names = _build_reload(plan, wlut)
    ship_strikes, air_strikes = _build_strikes(plan)

    parts = [
        _render_header(plan),
        _render_manifest(plan),
        _render_main(),
        _render_clear(clear_names),
        _render_reload(ship_reload, air_reload),
        _render_globals(),
        _render_attack_ship(ship_strikes),
        _render_attack_air(plan, air_strikes),
        _render_footer(),
    ]
    return "\n".join(parts)


def _render_footer() -> str:
    return (
        '\nprint("\\n========================================")\n'
        'print("[all] 全部完成.")\n'
        'print("下一步: 在 CMO 中按下播放, 让游戏推进时间 -> 触发真延时打击")\n'
        'print(("    舰艇约 %ds 后发射; 舰载机约 %ds 后到达并打击"):format(_SETTLE_SHIP, _SETTLE_AIR))\n'
        'print("========================================")\n'
    )


def main(argv: List[str]) -> int:
    if len(argv) < 2:
        print("用法: python tools/json_to_lua.py <input.json> [output.lua]")
        return 1
    in_path = argv[1]
    out_path = argv[2] if len(argv) >= 3 else None
    lua = generate_cmo_lua(in_path)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(lua)
        print("已写出: " + out_path)
    else:
        sys.stdout.write(lua)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
