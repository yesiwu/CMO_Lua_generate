-- ============================================================
-- all_舰机协同.lua — 红方 5V3（辽宁舰+J-15×2+055+052D×2 vs CVN-70 编队）
-- 一个脚本完成：main → clear → reload → 舰艇打击 → J-15起飞+打击+返航
--
-- 【已验证的关键点】
--  1) contact 用 VP_GetSide().contacts 获取（GetContacts 在本版本报错）
--  2) 真延时触发器：脚本只预约，按【播放】游戏推进后才执行
--  3) 飞机起飞三步：timetoready=0 → launch=true → 设航路+高度
--  4) 攻击用 mode="0" 自动选弹（比强制 dbid 稳）
--  5) 飞机 settle=35s（起飞+爬升+飞到射程比军舰慢），军舰 settle=30s
--
-- 【运行方法】整段粘进 CMO 控制台 → 按【播放】让游戏推进
-- ============================================================

print("\n========================================")
print("[all] 红方5V3 舰机协同（完整版）")
print("========================================")

_SIDE_RED  = "红方"
_SIDE_BLUE = "蓝方"

_SETTLE_SHIP = 30   -- 军舰首发延迟（秒）
_SETTLE_AIR  = 150   -- 飞机首发延迟（秒）——起飞+爬升+飞到射程更慢

-- ============================================================
-- MANIFEST
-- ============================================================
local MANIFEST_SHIPS = {
    {name="红方055南昌舰",    dbid=3883, lat=24.8324, lon=128.5830, heading=135, speed=20, prof="Veteran"},
    {name="红方052D-1昆明舰", dbid=2296, lat=21.1437, lon=123.4510, heading=115, speed=20, prof="Veteran"},
    {name="红方052D-2南京舰", dbid=3586, lat=18.2035, lon=123.9880, heading=50,  speed=20, prof="Veteran"},
    {name="红方辽宁舰",        dbid=2007, lat=25.0000, lon=130.0000, heading=90,  speed=20, prof="Veteran"},
}
local MANIFEST_AIRCRAFT = {
    {name="J-15-1", dbid=2496, base="红方辽宁舰", prof="Veteran", loadoutid=9682},
    {name="J-15-2", dbid=2496, base="红方辽宁舰", prof="Veteran", loadoutid=9682},
}
local MANIFEST_BLUE = {
    {name="蓝方CVN-70卡尔文森",   dbid=3551, lat=21.5419, lon=129.9125, heading=294, speed=0, prof="Veteran"},
    {name="蓝方CG-59普林斯顿",     dbid=2862, lat=21.6100, lon=130.1791, heading=295, speed=0, prof="Veteran"},
    {name="蓝方DDG-113-1约翰芬恩", dbid=4299, lat=21.4200, lon=130.1713, heading=293, speed=0, prof="Veteran"},
    {name="蓝方DDG-113-2约翰芬恩", dbid=4299, lat=21.6000, lon=130.2000, heading=293, speed=0, prof="Veteran"},
}

local function getUnit(side, name)
    local ok, u = pcall(ScenEdit_GetUnit, {side=side, name=name})
    if ok and u and u.guid then return u end
    return nil
end

-- ============================================================
-- 第1段：main
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
                print("[main] " .. a.name .. " [裸机后备] ok=" .. tostring(ok) .. " err=" .. tostring(_errmsg_))
            else
                print("[main] " .. a.name .. " ok=" .. tostring(ok) .. " err=" .. tostring(_errmsg_))
            end
        else
            print("[main] " .. a.name .. " 已存在")
        end
    end

    print("[main] 完成。")
end

-- ============================================================
-- 第2段：clear
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
        print(("[clear] %s: 减载归零 %d 条 (失败 %d)"):format(name, done, fail))
        return fail == 0
    end
    for _, name in ipairs({ "红方055南昌舰", "红方052D-1昆明舰", "红方052D-2南京舰" }) do
        clearUnitWeapons("红方", name)
    end
    print("[clear] 完成。")
end

-- ============================================================
-- 第3段：reload
-- ============================================================
do
    print("\n===== [reload] 装弹 =====")
    local SHIPS_RELOAD = {
        {name="红方055南昌舰",    qty=16, wpn=2868},
        {name="红方052D-1昆明舰",  qty=16, wpn=2868},
        {name="红方052D-2南京舰",  qty=10, wpn=2868},
    }
    for _, s in ipairs(SHIPS_RELOAD) do
        _errnum_ = 0
        local ok = pcall(ScenEdit_AddReloadsToUnit, {
            side="红方", unitname=s.name, wpn_dbid=s.wpn, number=s.qty,
        })
        print(("[reload] %s x%d ok=%s err=%s"):format(s.name, s.qty, tostring(ok), tostring(_errmsg_)))
    end
    local AIRCRAFT_RELOAD = {
        {name="J-15-1", qty=4, wpn=2137},
        {name="J-15-2", qty=4, wpn=2137},
    }
    for _, a in ipairs(AIRCRAFT_RELOAD) do
        _errnum_ = 0
        local ok = pcall(ScenEdit_AddReloadsToUnit, {
            side="红方", unitname=a.name, wpn_dbid=a.wpn, number=a.qty,
        })
        print(("[reload] %s x%d ok=%s err=%s"):format(a.name, a.qty, tostring(ok), tostring(_errmsg_)))
    end
    print("[reload] 完成。")
end

-- ============================================================
-- 全局：时间戳 + 发射函数 + 调度（供舰艇与飞机共用）
-- ============================================================
function totTicks(addSeconds)
    return string.format("%.0f", (ScenEdit_CurrentTime() + addSeconds) * 1e7 + 621355968000000000)
end

-- fireAt：mode="0" 自动选弹（wpnDbid 传 0 或 nil 即自动）
function fireAt(attackerName, targetName, wpnDbid, qty)
    local atk = ScenEdit_GetUnit({side="红方", name=attackerName})
    local tgt = ScenEdit_GetUnit({side="蓝方", name=targetName})
    if not (atk and atk.guid) then
        print(("[CMO] [ERROR] fireAt 找不到攻击方 %s"):format(tostring(attackerName))); return false end
    if not (tgt and tgt.guid) then
        print(("[CMO] [ERROR] fireAt 找不到目标 %s"):format(tostring(targetName))); return false end

    pcall(ScenEdit_SetUnit, {guid=tgt.guid, autodetectable=true})
    pcall(ScenEdit_SetSideOptions, {side="红方", awareness="OMNI"})

    -- 取 contact（本版本可用的方式）
    local contactGuid = nil
    local ok, s = pcall(VP_GetSide, {Side="红方"})
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
        print(("[CMO] [ERROR] %s 无 %s 的 contact（游戏推进不足？加大 settle）"):format(attackerName, targetName))
        return false
    end

    -- mode="0" 自动选弹；只有传了正整数 wpnDbid 才指定弹种
    local opts
    if wpnDbid and tonumber(wpnDbid) and tonumber(wpnDbid) > 0 then
        opts = { mode="1", weapon=tonumber(wpnDbid), qty=qty }
    else
        opts = { mode="0" }
    end
    _errnum_ = 0
    local r = ScenEdit_AttackContact(atk.guid, contactGuid, opts)
    print(("[CMO] [FIRE] %s → %s qty=%s contact=%s result=%s"):format(
        attackerName, targetName, tostring(qty), tostring(contactGuid), tostring(r ~= nil and r ~= false)))
    return r and true or false
end

-- 通用：调度一段 Lua 到未来执行
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

-- 调度一次攻击（自动选弹）
local function scheduleFire(atkName, tgtName, qty, delay, tag)
    local body = ("fireAt(%q,%q,0,%d)"):format(atkName, tgtName, qty)
    scheduleLua(body, delay, tag)
    print(("[attack] [调度] T+%ds  %s → %s  qty=%d (自动选弹)"):format(delay, atkName, tgtName, qty))
end

-- ============================================================
-- 第4段：舰艇打击（真延时）
-- ============================================================
do
    print("\n===== [attack-ship] 舰艇真延时齐射 =====")
    local T0 = _SETTLE_SHIP
    scheduleFire("红方055南昌舰",    "蓝方DDG-113-1约翰芬恩", 8, T0,     "055_DDG1")
    scheduleFire("红方055南昌舰",    "蓝方DDG-113-2约翰芬恩", 5, T0 + 3, "055_DDG2")
    scheduleFire("红方052D-1昆明舰", "蓝方CVN-70卡尔文森",   8, T0,     "052D1_CVN")
    scheduleFire("红方052D-2南京舰", "蓝方CG-59普林斯顿",    5, T0,     "052D2_CG")
    print("[attack-ship] 完成调度。")
end

-- ============================================================
-- 第5段：J-15 起飞 + 打击 + 返航
--   航路：从辽宁舰直接朝目标方向（中途点 + 接近点）
-- ============================================================
do
    print("\n===== [attack-air] J-15 起飞→打击→返航 =====")

    -- 每架飞机的：目标、航路（朝目标方向的简单两点航路）
    local SORTIES = {
        {
            name="J-15-1", target="蓝方DDG-113-1约翰芬恩",
            mid={lat=23.5680, lon=130.0685}, approach={lat=22.3150, lon=130.1285},
        },
        {
            name="J-15-2", target="蓝方CG-59普林斯顿",
            mid={lat=23.6440, lon=130.0716}, approach={lat=22.4575, lon=130.1343},
        },
    }

    for _, s in ipairs(SORTIES) do
        local u = getUnit(_SIDE_RED, s.name)
        if not u then
            print("[attack-air] [WARN] 找不到 " .. s.name .. "，跳过")
        else
            -- 起飞三步（立即执行，让飞机尽快升空）
            -- 1) 归零准备时间
            _errnum_ = 0
            pcall(ScenEdit_SetUnit, {side=_SIDE_RED, unitname=s.name, timetoready_minutes=0})
            -- 2) 起飞
            _errnum_ = 0
            local okL = pcall(ScenEdit_SetUnit, {side=_SIDE_RED, unitname=s.name, launch=true})
            -- 3) 设航路 + 巡航高度
            _errnum_ = 0
            local okC = pcall(ScenEdit_SetUnit, {
                side=_SIDE_RED, unitname=s.name,
                course = { {latitude=s.mid.lat, longitude=s.mid.lon},
                           {latitude=s.approach.lat, longitude=s.approach.lon} },
                altitude = 8000, throttle = "Cruise",
            })
            print(("[attack-air] %s 起飞 launch=%s 航路=%s → 目标 %s"):format(
                s.name, tostring(okL), tostring(okC), s.target))

            -- 打击（延时，等飞机飞到射程 + contact 生成）；自动选弹
            local body = ("fireAt(%q,%q,0,4)"):format(s.name, s.target)
            scheduleLua(body, _SETTLE_AIR, "air_fire_" .. s.name)
            print(("[attack-air] [调度] T+%ds  %s → %s  qty=4 (自动选弹)"):format(_SETTLE_AIR, s.name, s.target))

            -- 返航（打击后再等一段，设 base 再 rtb）
            local rtbBody = table.concat({
                ("ScenEdit_SetUnit({side=%q, unitname=%q, base=%q})\n"):format(_SIDE_RED, s.name, "红方辽宁舰"),
                ("ScenEdit_SetUnit({side=%q, unitname=%q, rtb=true})\n"):format(_SIDE_RED, s.name),
                ("print('[CMO] [RTB] %s 返航')"):format(s.name),
            })
            scheduleLua(rtbBody, _SETTLE_AIR + 120, "air_rtb_" .. s.name)
            print(("[attack-air] [调度] T+%ds  %s 返航"):format(_SETTLE_AIR + 120, s.name))
        end
    end
    print("[attack-air] 完成调度。")
end

print("\n========================================")
print("[all] 全部完成。")
print("★★★ 现在请在 CMO 界面按【播放】让游戏推进时间 ★★★")
print(("    军舰约 %ds 发射；J-15 约 %ds 起飞后飞向目标，到射程后发射"):format(_SETTLE_SHIP, _SETTLE_AIR))
print("    看日志 [CMO] [FIRE] result=true 确认发射；[CMO] [RTB] 确认返航")
print("========================================")
