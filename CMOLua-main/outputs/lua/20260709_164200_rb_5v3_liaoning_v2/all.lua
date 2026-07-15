-- ============================================================
-- all.lua: 红蓝7V4 辽宁舰+J-15×2 vs DDG-113+CG-59+CVN-70
-- 执行顺序: main.lua -> clear.lua -> reload.lua -> attack.lua
-- 一次性完成: 建单位 -> 清弹 -> 装弹 -> 真延时调度齐射
-- 真延时 contact_settle_delay = 15 秒
-- 攻击方: 055-Nanchang / 052D-1 / 052D-2 / J-15-RED-01 / J-15-RED-02 (红方 OMNI)
-- 防御方: DDG-113-1 / CG-59 / CVN-70 (蓝方, autodetectable=true)
-- 数据来源: JSON red_blue_5v3_liaoning.json
-- DBID 来源: 用户指定 + MCP 查询
-- ============================================================

--[[ ============================================================
     第一步: main.lua — 创建红蓝双方单位
     ============================================================ --]]
_SIDE_RED   = "红方"
_SIDE_BLUE  = "蓝方"

-- ---------- 红方全知全能 ----------
ScenEdit_SetSideOptions({side=_SIDE_RED, awareness="OMNI"})

-- ---------- 蓝方单位 autodetectable=true ----------
local BLUE_UNITS = {
    {name="DDG-113-1", dbid=4299, lat=21.5419, lon=129.9125, heading=294.05},
    {name="CG-59",      dbid=2862, lat=21.61,   lon=130.1791, heading=294.58},
    {name="CVN-70",     dbid=3551, lat=21.42,   lon=130.1713, heading=293.16},
}

for _, u in ipairs(BLUE_UNITS) do
    ScenEdit_AddUnit({
        side    = _SIDE_BLUE,
        type    = "Ship",
        name    = u.name,
        dbid    = u.dbid,
        latitude  = u.lat,
        longitude = u.lon,
        heading   = u.heading,
        speed     = 0,
        autodetectable = true,
    })
end
print("[main] 蓝方单位创建完毕（autodetectable=true）")

-- ---------- 红方水面舰艇 ----------
local RED_SHIPS = {
    {name="055-Nanchang", dbid=3883, lat=24.8324, lon=128.5830, heading=135},
    {name="052D-1",       dbid=2296, lat=21.1437, lon=123.4510, heading=115},
    {name="052D-2",       dbid=3586, lat=18.2035, lon=123.9880, heading=50},
}

for _, s in ipairs(RED_SHIPS) do
    ScenEdit_AddUnit({
        side    = _SIDE_RED,
        type    = "Ship",
        name    = s.name,
        dbid    = s.dbid,
        latitude  = s.lat,
        longitude = s.lon,
        heading   = s.heading,
        speed     = 20,
        autodetectable = true,
    })
end
print("[main] 红方水面舰艇创建完毕")

-- ---------- 红方辽宁舰 ----------
local cv = ScenEdit_AddUnit({
    side    = _SIDE_RED,
    type    = "Ship",
    name    = "红方辽宁舰",
    dbid    = 2007,
    latitude  = 25.0,
    longitude = 130.0,
    heading   = 90,
    speed     = 20,
    autodetectable = true,
})
print("[main] 辽宁舰创建完毕（" .. (cv and cv.guid or "nil") .. "）")

-- ---------- 红方 J-15 舰载机（mode="0"，不触发武器清单变更） ----------
-- loadoutId=9682 对应 YJ-83K [C-802AK]（DB 中 J-15 反舰挂载）
ScenEdit_AddUnit({
    side      = _SIDE_RED,
    type      = "Aircraft",
    name      = "J-15-RED-01",
    dbid      = 2496,
    loadoutId = 9682,
    base      = "红方辽宁舰",
    heading   = 90,
    speed     = 300,
    altitude  = 500,
    opts      = {mode="0"},
})
print("[main] J-15-RED-01 创建完毕（loadoutId=9682, opts={mode=0}）")

ScenEdit_AddUnit({
    side      = _SIDE_RED,
    type      = "Aircraft",
    name      = "J-15-RED-02",
    dbid      = 2496,
    loadoutId = 9682,
    base      = "红方辽宁舰",
    heading   = 90,
    speed     = 300,
    altitude  = 500,
    opts      = {mode="0"},
})
print("[main] J-15-RED-02 创建完毕（loadoutId=9682, opts={mode=0}）")

print("[main] ===== 所有单位创建完毕 =====")

--[[ ============================================================
     第二步: clear.lua — 清弹（只清发射过的弹）
     ============================================================ --]]
for _, name in ipairs({"055-Nanchang", "052D-1", "052D-2"}) do
    local u = ScenEdit_GetUnit({side=_SIDE_RED, name=name})
    if u and u.guid then
        local r = ScenEdit_DumpAmmo({unit_guid=u.guid, quantity="all", weaponDbId=2868})
        print("[clear] " .. name .. " 清弹 YJ-18 -> " .. tostring(r))
    else
        print("[clear] [WARN] 找不到 " .. name)
    end
end
print("[clear] ===== 清弹完毕 =====")

--[[ ============================================================
     第三步: reload.lua — 装弹（装填 JSON 指定的弹）
     ============================================================ --]]
local RELOAD_LIST = {
    {name="055-Nanchang", wpn=2868, qty=13},
    {name="052D-1",       wpn=2868, qty=8},
    {name="052D-2",       wpn=2868, qty=5},
}

for _, entry in ipairs(RELOAD_LIST) do
    local u = ScenEdit_GetUnit({side=_SIDE_RED, name=entry.name})
    if u and u.guid then
        local r = ScenEdit_SetAircraftLoadout({
            unit_guid   = u.guid,
            weapon_db_id = entry.wpn,
            loadout_id  = entry.wpn,
            mount_guid  = "",
            quantity    = entry.qty,
        })
        print("[reload] " .. entry.name .. " 装弹 " .. entry.qty .. "x YJ-18 -> " .. tostring(r))
    else
        print("[reload] [WARN] 找不到 " .. entry.name)
    end
end
print("[reload] ===== 装弹完毕 =====")

--[[ ============================================================
     第四步: attack.lua — 真延时打击（TOT 事件驱动）
     contact_settle_delay = 15 秒，红方 awareness=OMNI
     ============================================================ --]]

-- ---------- 全局打击函数（供事件脚本调用） ----------
-- ★ fireAt 必须是全局（红线 #15）
function fireAt(atkName, tgtName, wpnDbid, qty)
    local atk = ScenEdit_GetUnit({side="红方", name=atkName})
    local tgt = ScenEdit_GetUnit({side="蓝方", name=tgtName})
    pcall(ScenEdit_SetUnit, {guid=tgt.guid, autodetectable=true})
    pcall(ScenEdit_SetSideOptions, {side="红方", awareness="OMNI"})

    local contactGuid
    local ok, s = pcall(VP_GetSide, {Side="红方"})
    if ok and s and type(s.contacts)=="table" then
        local tg = tostring(tgt.guid):lower()
        for _, c in ipairs(s.contacts) do
            local aid = c.actualunitid or c.actualUnitID or c.actualunitguid
            if aid and tostring(aid):lower()==tg then contactGuid=c.guid; break end
        end
        if not contactGuid then
            for _, c in ipairs(s.contacts) do
                local nm = tostring(c.name or "")
                if nm~="" and (nm==tgtName or nm:find(tgtName,1,true)) then contactGuid=c.guid; break end
            end
        end
    end
    if not contactGuid then print("无 contact，加大延迟或多推进游戏"); return false end

    _errnum_=0
    return ScenEdit_AttackContact(atk.guid, contactGuid, {mode="1", weapon=wpnDbid, qty=qty}) and true or false
end

-- ---------- TOT 时间换算 ----------
local function totTicks(addSeconds)
    local t = ScenEdit_CurrentTime()
    return string.format("%.0f", (t + 62135596801 + addSeconds) * 1e7)
end

-- ---------- 逐枚调度（每枚独立触发器，qty=1） ----------
local CONTACT_SETTLE = 15   -- contact 稳定等待秒数
local INTERVAL       = 1    -- 每枚间隔秒数

local function scheduleOne(atkName, tgtName, wpnDbid, delay, k)
    local ts = tostring(ScenEdit_CurrentTime()):gsub("[^%d]", "")
    local evName = "E_" .. atkName .. "_" .. tgtName .. "_" .. k .. "_" .. ts
    local trName = "T_" .. atkName .. "_" .. tgtName .. "_" .. k .. "_" .. ts
    local acName = "A_" .. atkName .. "_" .. tgtName .. "_" .. k .. "_" .. ts
    local script = ("fireAt(%q,%q,%d,1)\n"):format(atkName, tgtName, wpnDbid)
        .. ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(evName)
        .. ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(acName)
        .. ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(trName)
    local fireTime = totTicks(delay)
    pcall(ScenEdit_SetTrigger, {mode="add", type="Time", name=trName, Time=fireTime})
    pcall(ScenEdit_SetAction,  {mode="add", type="LuaScript", name=acName, ScriptText=script})
    pcall(ScenEdit_SetEvent, evName, {mode="add", IsActive=true, IsRepeatable=false})
    pcall(ScenEdit_SetEventTrigger, evName, {mode="add", name=trName})
    pcall(ScenEdit_SetEventAction,  evName, {mode="add", name=acName})
end

-- 1) 055-Nanchang -> DDG-113-1  (13 枚 YJ-18)
for k = 1, 13 do
    scheduleOne("055-Nanchang", "DDG-113-1", 2868, CONTACT_SETTLE + (k-1)*INTERVAL, k)
end
print("[attack] 055-Nanchang -> DDG-113-1: 13x YJ-18 调度完毕（T+" .. CONTACT_SETTLE .. "s起）")

-- 2) 052D-1 -> CVN-70  (8 枚 YJ-18)
for k = 1, 8 do
    scheduleOne("052D-1", "CVN-70", 2868, CONTACT_SETTLE + (k-1)*INTERVAL, k)
end
print("[attack] 052D-1 -> CVN-70: 8x YJ-18 调度完毕（T+" .. CONTACT_SETTLE .. "s起）")

-- 3) 052D-2 -> CG-59  (5 枚 YJ-18)
for k = 1, 5 do
    scheduleOne("052D-2", "CG-59", 2868, CONTACT_SETTLE + (k-1)*INTERVAL, k)
end
print("[attack] 052D-2 -> CG-59: 5x YJ-18 调度完毕（T+" .. CONTACT_SETTLE .. "s起）")

-- 4) J-15-RED-01 -> CVN-70  (4 枚 YJ-83K，loadoutId=9682)
--    J-15 使用 opts={mode="0"}，导弹来自挂载，无需手动装弹
for k = 1, 4 do
    scheduleOne("J-15-RED-01", "CVN-70", 2137, CONTACT_SETTLE + (k-1)*INTERVAL, k)
end
print("[attack] J-15-RED-01 -> CVN-70: 4x YJ-83K (dbid=2137) 调度完毕（T+" .. CONTACT_SETTLE .. "s起）")

-- 5) J-15-RED-02 -> CG-59  (4 枚 YJ-83K)
for k = 1, 4 do
    scheduleOne("J-15-RED-02", "CG-59", 2137, CONTACT_SETTLE + (k-1)*INTERVAL, k)
end
print("[attack] J-15-RED-02 -> CG-59: 4x YJ-83K (dbid=2137) 调度完毕（T+" .. CONTACT_SETTLE .. "s起）")

print("[attack] ===== 真延时打击调度完毕 =====")
print("[attack] 汇总: 055(13) + 052D-1(8) + 052D-2(5) + J-15-01(4) + J-15-02(4) = 34 枚")
print("[attack] contact_settle_delay = " .. CONTACT_SETTLE .. "s，红方 awareness=OMNI，蓝方 autodetectable=true")
print("[attack] 执行顺序: main.lua -> clear.lua -> reload.lua -> attack.lua")
