
-- PHASE 6 FIXTURE: candidate_01 — 护航压制后双机突击航母
-- ============================================================
-- all_舰机协同.lua — 红方 5V3（辽宁舰+J-15×2+055+052D×2 vs CVN-70 编队）
-- 一个脚本完成：main → clear → reload → 舰艇打击 → J-15起飞+打击+返航
--
-- 【已验证的关键点】
--  1) contact 用 VP_GetSide().contacts 获取（GetContacts 在本版本报错）
--  2) 真延时触发器：脚本只预约，按【播放】游戏推进后才执行
--  3) 飞机挂载用 ScenEdit_SetLoadout，不把 AddReloadsToUnit 当作飞机装弹
--  4) 起飞按 isOperating 状态轮询，升空后才设置航路
--  5) 攻击按实际距离轮询，不再依赖固定 150 秒猜测
--
-- 【运行方法】整段粘进 CMO 控制台 → 按【播放】让游戏推进
-- ============================================================

print("\n========================================")
print("[all] Phase 6 candidate_01：护航压制后双机突击航母")
print("========================================")

_SIDE_RED  = "红方"
_SIDE_BLUE = "蓝方"

_SETTLE_SHIP = 30   -- 军舰首发延迟（秒）

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

-- 关键调用统一检查：pcall=true 仅表示 Lua 没抛异常，不表示 CMO 操作成功。
local function cmoCall(label, fn, args)
    _errnum_ = 0
    _errmsg_ = ""
    local ok, result = pcall(fn, args)
    local errnum = tonumber(_errnum_) or 0
    local errmsg = tostring(_errmsg_ or "")
    local success = ok and result ~= nil and result ~= false and errnum == 0
    print(("[CMO-CALL] %s success=%s pcall=%s errnum=%s errmsg=%s"):format(
        label, tostring(success), tostring(ok), tostring(errnum), errmsg))
    return success, result, errmsg
end

local function printAirState(prefix, u)
    if not u then
        print(prefix .. " unit=nil")
        return
    end
    print(("%s name=%s guid=%s operating=%s ready_s=%s loadout=%s condition=%s state=%s"):format(
        prefix,
        tostring(u.name), tostring(u.guid), tostring(u.isOperating),
        tostring(u.readytime_v), tostring(u.loadoutdbid),
        tostring(u.condition), tostring(u.unitstate)))
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
        local u = getUnit(_SIDE_RED, a.name)
        if not u then
            local added, result = cmoCall("AddAircraft/" .. a.name, ScenEdit_AddUnit, {
                type="Air", side=_SIDE_RED, unitname=a.name, dbid=a.dbid,
                loadoutid=a.loadoutid, base=a.base, proficiency=a.prof,
            })
            if added then u = result or getUnit(_SIDE_RED, a.name) end
        else
            print("[main] " .. a.name .. " 已存在")
        end

        if not u then
            print("[main] [FATAL] " .. a.name .. " 创建失败；不再降级为裸机")
        elseif not u.isOperating then
            -- 对已存在的飞机也重新校正基地、挂载和准备时间。
            cmoCall("SetBase/" .. a.name, ScenEdit_SetUnit, {
                guid=u.guid, base=a.base,
            })
            local loaded = cmoCall("SetLoadout/" .. a.name, ScenEdit_SetLoadout, {
                unitname=u.guid,
                LoadoutID=a.loadoutid,
                TimeToReady_Minutes=0,
                IgnoreMagazines=true, -- 演示脚本：忽略母舰弹药库；生产场景应改为 false 并配置弹药库
            })
            if not loaded then
                print("[main] [FATAL] " .. a.name .. " 挂载失败；请核对 DB 版本、机型 DBID 与 LoadoutID")
            end
            cmoCall("ReadyNow/" .. a.name, ScenEdit_SetUnit, {
                guid=u.guid, timetoready_minutes=0,
            })
            u = getUnit(_SIDE_RED, a.name)
            printAirState("[main] [AIR-STATE]", u)
        else
            printAirState("[main] [AIR-STATE already airborne]", u)
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
    -- 飞机不能用 ScenEdit_AddReloadsToUnit 当作挂载装填。
    -- 飞机挂载已经在 main 段通过 ScenEdit_SetLoadout 设置。
    for _, a in ipairs(MANIFEST_AIRCRAFT) do
        local u = getUnit(_SIDE_RED, a.name)
        printAirState("[reload] [AIR-LOADOUT]", u)
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
    _errmsg_ = ""
    local okAttack, r = pcall(ScenEdit_AttackContact, atk.guid, contactGuid, opts)
    local errnum = tonumber(_errnum_) or 0
    local success = okAttack and r ~= nil and r ~= false and errnum == 0
    print(("[CMO] [FIRE] %s → %s mode=%s qty=%s contact=%s success=%s err=%s"):format(
        attackerName, targetName, tostring(opts.mode), tostring(qty),
        tostring(contactGuid), tostring(success), tostring(_errmsg_ or "")))
    return success
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
    -- Phase 6 candidate_01：三艘舰艇分别压制CG-59与两艘DDG，双J-15延后起飞并集中打击CVN-70。
    scheduleFire("红方055南昌舰", "蓝方DDG-113-1约翰芬恩", 8, T0, "055_DDG1")
    scheduleFire("红方052D-1昆明舰", "蓝方CG-59普林斯顿", 8, T0 + 3, "052D1_CG")
    scheduleFire("红方052D-2南京舰", "蓝方DDG-113-2约翰芬恩", 5, T0 + 6, "052D2_DDG2")
    print("[attack-ship] 完成调度。")
end

-- ============================================================
-- 第5段：J-15 起飞 + 打击 + 返航（状态驱动修复版）
-- ============================================================

-- 起飞轮询：不再把 pcall=true 当作“已经起飞”。
function airLaunchPoll(name, target, midLat, midLon, appLat, appLon, attempt)
    local u = getUnit(_SIDE_RED, name)
    if not u then
        print("[attack-air] [FATAL] 找不到 " .. tostring(name))
        return
    end

    printAirState(("[attack-air] [LAUNCH-POLL %d]"):format(attempt), u)

    if u.isOperating then
        local routed = cmoCall("Route/" .. name, ScenEdit_SetUnit, {
            guid=u.guid,
            course={
                {latitude=midLat, longitude=midLon},
                {latitude=appLat, longitude=appLon},
            },
            altitude=8000,
            throttle="Cruise",
        })
        if not routed then
            print("[attack-air] [ERROR] " .. name .. " 已升空，但航路设置失败")
            return
        end
        print("[attack-air] [AIRBORNE] " .. name .. " 已升空并进入攻击航路")
        local body = ("airAttackPoll(%q,%q,%d)"):format(name, target, 1)
        scheduleLua(body, 30, "air_attack_poll_" .. name .. "_1")
        return
    end

    if attempt > 24 then
        print("[attack-air] [FATAL] " .. name .. " 6分钟内仍未升空；请查看 condition/ready_s/errmsg")
        return
    end

    -- 每轮都再次归零准备时间并请求起飞；CMO 会在甲板条件允许时执行。
    cmoCall("ReadyRetry/" .. name, ScenEdit_SetUnit, {
        guid=u.guid, timetoready_minutes=0,
    })
    cmoCall("Launch/" .. name, ScenEdit_SetUnit, {
        guid=u.guid, launch=true,
    })

    local nextAttempt = attempt + 1
    local body = ("airLaunchPoll(%q,%q,%.8f,%.8f,%.8f,%.8f,%d)"):format(
        name, target, midLat, midLon, appLat, appLon, nextAttempt)
    scheduleLua(body, 15, "air_launch_poll_" .. name .. "_" .. tostring(nextAttempt))
end

-- 攻击轮询：按实际距离判断，不再假定 T+150 秒已经飞到射程。
function airAttackPoll(name, target, attempt)
    local u = getUnit(_SIDE_RED, name)
    local tgt = getUnit(_SIDE_BLUE, target)
    if not u then
        print("[attack-air] [FATAL] 攻击轮询找不到 " .. tostring(name))
        return
    end
    if not tgt then
        print("[attack-air] [STOP] 目标不存在或已被摧毁：" .. tostring(target))
        scheduleLua(("ScenEdit_SetUnit({guid=%q,rtb=true})"):format(u.guid), 5,
            "air_rtb_no_target_" .. name)
        return
    end
    if not u.isOperating then
        print("[attack-air] [ERROR] " .. name .. " 尚未处于飞行状态，停止攻击轮询")
        return
    end

    local okRange, rangeNm = pcall(Tool_Range, u.guid, tgt.guid)
    if not okRange then rangeNm = nil end
    print(("[attack-air] [RANGE %d] %s → %s range_nm=%s"):format(
        attempt, name, target, tostring(rangeNm)))

    -- 80 海里是保守触发门槛；真正能否发射仍由当前挂载、WRA和目标状态决定。
    if rangeNm and tonumber(rangeNm) <= 80 then
        local fired = fireAt(name, target, 0, 4)
        if fired then
            print("[attack-air] [ATTACK-ORDERED] " .. name .. " 已提交攻击命令")
            local rtbBody = table.concat({
                ("ScenEdit_SetUnit({guid=%q,base=%q})\n"):format(u.guid, "红方辽宁舰"),
                ("ScenEdit_SetUnit({guid=%q,rtb=true})\n"):format(u.guid),
                ("print('[CMO] [RTB] %s 返航')"):format(name),
            })
            scheduleLua(rtbBody, 600, "air_rtb_" .. name)
            return
        end
    end

    if attempt >= 35 then
        print("[attack-air] [FATAL] " .. name .. " 35分钟内未形成有效攻击，命令返航")
        scheduleLua(("ScenEdit_SetUnit({guid=%q,rtb=true})"):format(u.guid), 5,
            "air_rtb_timeout_" .. name)
        return
    end

    local nextAttempt = attempt + 1
    local body = ("airAttackPoll(%q,%q,%d)"):format(name, target, nextAttempt)
    scheduleLua(body, 60, "air_attack_poll_" .. name .. "_" .. tostring(nextAttempt))
end

do
    print("\n===== [attack-air] J-15 起飞→打击→返航（状态驱动） =====")

    local SORTIES = {
        {
            name="J-15-1", target="蓝方CVN-70卡尔文森",
            mid={lat=23.6000, lon=129.9000}, approach={lat=22.3000, lon=129.9000},
        },
        {
            name="J-15-2", target="蓝方CVN-70卡尔文森",
            mid={lat=23.7500, lon=130.1500}, approach={lat=22.4000, lon=130.0500},
        },
    }

    for _, s in ipairs(SORTIES) do
        local u = getUnit(_SIDE_RED, s.name)
        if not u then
            print("[attack-air] [FATAL] 找不到 " .. s.name .. "，不调度")
        elseif tonumber(u.loadoutdbid or 0) == 0 then
            print("[attack-air] [FATAL] " .. s.name .. " 当前是裸机/无挂载，禁止起飞")
        else
            printAirState("[attack-air] [PRECHECK]", u)
            local body = ("airLaunchPoll(%q,%q,%.8f,%.8f,%.8f,%.8f,1)"):format(
                s.name, s.target, s.mid.lat, s.mid.lon,
                s.approach.lat, s.approach.lon)
            scheduleLua(body, 90, "air_launch_poll_" .. s.name .. "_1")
            print("[attack-air] [调度] T+90s 开始起飞轮询：" .. s.name)
        end
    end

    print("[attack-air] 完成调度。")
end

print("\n========================================")
print("[all] 全部完成。")
print("★★★ 现在请在 CMO 界面按【播放】让游戏推进时间 ★★★")
print(("    军舰约 %ds 发射；J-15 在 T+90s 开始起飞轮询，升空后按实际距离进入攻击"):format(_SETTLE_SHIP))
print("    看日志 [CMO] [FIRE] success=true 确认攻击命令；[CMO] [RTB] 确认返航")
print("========================================")

-- ============================================================
-- CMO 官方内置评分：每个单位被毁时触发一次 Points 动作。
-- 原始 6v4.lua 不包含本段；本副本专供批处理和官方分数CSV导出。
-- ============================================================
do
    print("\n===== [cmo-score] 注册官方毁伤计分事件 =====")

    local SCORE_RULES = {
        {side=_SIDE_BLUE, name="蓝方CVN-70卡尔文森",   points= 200, label="击毁蓝方CVN-70"},
        {side=_SIDE_BLUE, name="蓝方CG-59普林斯顿",     points= 100, label="击毁蓝方CG-59"},
        {side=_SIDE_BLUE, name="蓝方DDG-113-1约翰芬恩", points=  75, label="击毁蓝方DDG-113-1"},
        {side=_SIDE_BLUE, name="蓝方DDG-113-2约翰芬恩", points=  75, label="击毁蓝方DDG-113-2"},
        {side=_SIDE_RED,  name="红方辽宁舰",            points=-200, label="红方辽宁舰被毁"},
        {side=_SIDE_RED,  name="红方055南昌舰",          points=-100, label="红方055南昌舰被毁"},
        {side=_SIDE_RED,  name="红方052D-1昆明舰",       points= -75, label="红方052D-1昆明舰被毁"},
        {side=_SIDE_RED,  name="红方052D-2南京舰",       points= -75, label="红方052D-2南京舰被毁"},
        {side=_SIDE_RED,  name="J-15-1",                points= -20, label="红方J-15-1被毁"},
        {side=_SIDE_RED,  name="J-15-2",                points= -20, label="红方J-15-2被毁"},
    }

    local function installScoreRule(index, rule)
        local unit = getUnit(rule.side, rule.name)
        if not unit or not unit.guid then
            print("[cmo-score] [FATAL] 未找到计分单位：" .. rule.name)
            return
        end

        local tag = string.format("CMO_SCORE_%02d", index)
        local eventName = "Event " .. tag
        local triggerName = "Trigger " .. tag
        local actionName = "Action " .. tag

        pcall(ScenEdit_SetEvent, eventName, {mode="remove"})
        pcall(ScenEdit_SetTrigger, {mode="remove", type="UnitDestroyed", name=triggerName})
        pcall(ScenEdit_SetAction, {mode="remove", type="Points", name=actionName})

        local triggerOk = cmoCall("ScoreTrigger/" .. rule.name, ScenEdit_SetTrigger, {
            mode="add", type="UnitDestroyed", name=triggerName,
            TargetFilter={TargetSide=rule.side, SpecificUnitID=unit.guid},
        })
        local actionOk = cmoCall("ScoreAction/" .. rule.name, ScenEdit_SetAction, {
            mode="add", type="Points", name=actionName,
            SideID=_SIDE_RED, PointChange=rule.points,
        })
        local eventOk = pcall(ScenEdit_SetEvent, eventName, {
            mode="add", IsActive=true, IsRepeatable=false,
        })
        local linkTriggerOk = pcall(ScenEdit_SetEventTrigger, eventName, {mode="add", name=triggerName})
        local linkActionOk = pcall(ScenEdit_SetEventAction, eventName, {mode="add", name=actionName})
        print(("[cmo-score] %s points=%d trigger=%s action=%s event=%s linkT=%s linkA=%s"):format(
            rule.label, rule.points, tostring(triggerOk), tostring(actionOk), tostring(eventOk),
            tostring(linkTriggerOk), tostring(linkActionOk)))
    end

    for index, rule in ipairs(SCORE_RULES) do installScoreRule(index, rule) end
    print("[cmo-score] 完成：10个UnitDestroyed触发器 + 10个官方Points动作。")
end