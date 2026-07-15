-- ============================================================
-- all.lua  红蓝 7V4 辽宁舰协同反舰场景  生成自 JSON 作战方案
-- 黄金模板: json/7V3.lua   分段: main -> clear -> reload -> attack-ship -> attack-air
-- ============================================================

print("\n========================================")
print("[all] 红蓝 7V4 辽宁舰协同反舰场景 (JSON 驱动自动生成)")
print("========================================")

_SIDE_RED  = "红方"
_SIDE_BLUE = "蓝方"

_SETTLE_SHIP = 30   -- 舰艇首发沉降延时(秒)
_SETTLE_AIR  = 150    -- 舰载机起飞+航路+contact 沉降延时(秒)

-- ============================================================
-- MANIFEST (从 JSON 生成)
-- ============================================================
local MANIFEST_SHIPS = {
    {name="Red-055-1", dbid=3883, lat=24.8324, lon=128.5830, heading=135, speed=20, prof="Veteran"},
    {name="Red-055-2", dbid=3883, lat=26.0000, lon=130.0000, heading=135, speed=20, prof="Veteran"},
    {name="Red-052D-1", dbid=4936, lat=21.1437, lon=123.4510, heading=115, speed=20, prof="Veteran"},
    {name="Red-052D-2", dbid=4936, lat=18.2035, lon=123.9880, heading=50, speed=20, prof="Veteran"},
    {name="红方辽宁舰", dbid=2007, lat=25.0000, lon=130.0000, heading=90, speed=20, prof="Veteran"},
}
local MANIFEST_AIRCRAFT = {
    {name="J-15-RED-01", dbid=2496, base="红方辽宁舰", prof="Veteran", loadoutid=9682},
    {name="J-15-RED-02", dbid=2496, base="红方辽宁舰", prof="Veteran", loadoutid=9682},
}
local MANIFEST_BLUE = {
    {name="DDG 113-1", dbid=4299, lat=21.5419, lon=129.9125, heading=294, speed=0, prof="Veteran"},
    {name="DDG 113-2", dbid=4299, lat=22.0000, lon=131.0000, heading=294, speed=0, prof="Veteran"},
    {name="Blue-DBID-2862", dbid=2862, lat=21.6100, lon=130.1791, heading=294, speed=0, prof="Veteran"},
    {name="Blue-DBID-3551", dbid=3551, lat=21.4200, lon=130.1713, heading=293, speed=0, prof="Veteran"},
}

local function getUnit(side, name)
    local ok, u = pcall(ScenEdit_GetUnit, {side=side, name=name})
    if ok and u and u.guid then return u end
    return nil
end


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
    }) do
        clearUnitWeapons(_SIDE_RED, name)
    end
    print("[clear] 完成.")
end


-- ============================================================
-- 第3段: reload
-- ============================================================
do
    print("\n===== [reload] 装弹 =====")
    local SHIPS_RELOAD = {
    }
    for _, s in ipairs(SHIPS_RELOAD) do
        _errnum_ = 0
        local ok = pcall(ScenEdit_AddReloadsToUnit, {
            side=_SIDE_RED, unitname=s.name, wpn_dbid=s.wpn, number=s.qty,
        })
        print(("[reload] %s x%d ok=%s err=%s"):format(s.name, s.qty, tostring(ok), tostring(_errmsg_)))
    end
    local AIRCRAFT_RELOAD = {
        {name="J-15-RED-01", qty=4, wpn=2137},
        {name="J-15-RED-02", qty=4, wpn=2137},
    }
    for _, a in ipairs(AIRCRAFT_RELOAD) do
        _errnum_ = 0
        local ok = pcall(ScenEdit_AddReloadsToUnit, {
            side=_SIDE_RED, unitname=a.name, wpn_dbid=a.wpn, number=a.qty,
        })
        print(("[reload] %s x%d ok=%s err=%s"):format(a.name, a.qty, tostring(ok), tostring(_errmsg_)))
    end
    print("[reload] 完成.")
end


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


-- ============================================================
-- 第4段: attack-ship  舰艇真延时打击
-- ============================================================
do
    print("\n===== [attack-ship] 舰艇真延时打击 =====")
    scheduleFire("Red-055-1", "DDG 113-1", 7, _SETTLE_SHIP + 0, "ship_0_Red-055-1")
    scheduleFire("Red-055-2", "DDG 113-2", 6, _SETTLE_SHIP + 2, "ship_1_Red-055-2")
    scheduleFire("Red-052D-1", "Blue-DBID-3551", 8, _SETTLE_SHIP + 4, "ship_2_Red-052D-1")
    scheduleFire("Red-052D-2", "Blue-DBID-2862", 5, _SETTLE_SHIP + 6, "ship_3_Red-052D-2")
    print("[attack-ship] 完成调度.")
end


-- ============================================================
-- 第5段: attack-air  舰载机 起飞 + 航路 + 打击 + 返航
-- ============================================================
do
    print("\n===== [attack-air] 舰载机起飞打击 =====")
    local SORTIES = {
        {name="J-15-RED-01", target="Blue-DBID-3551", qty=4, base="红方辽宁舰", mid={lat=23.2100,lon=130.0856}, approach={lat=22.4940,lon=130.1199}},
        {name="J-15-RED-02", target="Blue-DBID-2862", qty=4, base="红方辽宁舰", mid={lat=23.3050,lon=130.0896}, approach={lat=22.6270,lon=130.1254}},
    }

    for _, s in ipairs(SORTIES) do
        local u = getUnit(_SIDE_RED, s.name)
        if not u then
            print("[attack-air] [WARN] 找不到 " .. s.name .. ", 跳过")
        else
            _errnum_ = 0
            pcall(ScenEdit_SetUnit, {side=_SIDE_RED, unitname=s.name, timetoready_minutes=0})
            _errnum_ = 0
            local okL = pcall(ScenEdit_SetUnit, {side=_SIDE_RED, unitname=s.name, launch=true})
            _errnum_ = 0
            local okC = pcall(ScenEdit_SetUnit, {
                side=_SIDE_RED, unitname=s.name,
                course = { {latitude=s.mid.lat, longitude=s.mid.lon},
                           {latitude=s.approach.lat, longitude=s.approach.lon} },
                altitude = 8000, throttle = "Cruise",
            })
            print(("[attack-air] %s 起飞 launch=%s 航路=%s -> 目标 %s"):format(
                s.name, tostring(okL), tostring(okC), s.target))

            local body = ("fireAt(%q,%q,0,%d)"):format(s.name, s.target, s.qty)
            local tag = "air_fire_" .. s.name
            scheduleLua(body, _SETTLE_AIR, tag)
            print(("[attack-air] [调度] T+%ds  %s -> %s  qty=%d (自动选弹)"):format(_SETTLE_AIR, s.name, s.target, s.qty))

            local rtbBody = table.concat({
                ("ScenEdit_SetUnit({side=%q, unitname=%q, base=%q})\n"):format(_SIDE_RED, s.name, s.base),
                ("ScenEdit_SetUnit({side=%q, unitname=%q, rtb=true})\n"):format(_SIDE_RED, s.name),
            })
            scheduleLua(rtbBody, _SETTLE_AIR + 120, "air_rtb_" .. s.name)
            print(("[attack-air] [调度] T+%ds  %s 返航"):format(_SETTLE_AIR + 120, s.name))
        end
    end
    print("[attack-air] 完成调度.")
end


print("\n========================================")
print("[all] 全部完成.")
print("下一步: 在 CMO 中按下播放, 让游戏推进时间 -> 触发真延时打击")
print(("    舰艇约 %ds 后发射; 舰载机约 %ds 后到达并打击"):format(_SETTLE_SHIP, _SETTLE_AIR))
print("========================================")
