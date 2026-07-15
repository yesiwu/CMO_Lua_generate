-- ============================================================
-- CMO 3v3 红蓝对抗 — 精简版（单位创建 + 清空待发弹 + 弹药补给）
-- 适用: CMO 公开版 / 专业版
-- Lua: 5.4（无全局 unpack；使用 table.unpack）
-- ============================================================

local CFG = {
    cmo_version      = "unknown",
    database_name    = "unknown",
    database_version = "unknown",

    -- 单位 DBID（已修正：4936 → 2296/3586）
    dbid_ddg113   = 4299,    -- DDG 113 John Finn [Arleigh Burke Flight IIA Restart]
    dbid_cg59     = 2862,    -- CG 59 Princeton [Ticonderoga Baseline 3, VLS]
    dbid_cvn70    = 3551,    -- CVN 70 Carl Vinson [Nimitz Class]
    dbid_052d_nj  = 2296,    -- Type 052D Luyang III [172 Kunming] ✅
    dbid_052d_xy  = 3586,    -- Type 052DL Luyang III Mod [156 Zibo] ✅
    dbid_055_nc   = 3883,    -- Type 055 Renhai [101 Nanchang]

    -- 武器 DBID
    dbid_yj21 = 4058,        -- YJ-21 [800kg HE]
    dbid_yj18 = 2868,        -- YJ-18 [3M54E Klub Copy]

    side_red  = "红方",
    side_blue = "蓝方",

    overwrite_existing = false,

    -- 关键：蓝方必须可探测，才能被红方 OMNI 感知到
    blue_autodetectable = true,

    -- contact 等待参数（从 1v1.lua 移植）
    contact_settle_delay = 5,
    contact_retry_delay = 5,
    contact_retry_count = 12,
}

-- ============================================================
-- 工具函数
-- ============================================================
local LOG_PREFIX = "[CMO]"
local function log(level, msg) print(LOG_PREFIX .. " [" .. level .. "] " .. msg) end
local function info(msg) log("INFO",    msg) end
local function warn(msg) log("WARNING", msg) end
local function err(msg)  log("ERROR",   msg) end
local function ok(msg)   log("SUCCESS", msg) end

local function safeAddUnit(props)
    local ok2, r = pcall(ScenEdit_AddUnit, props)
    if not ok2 then
        err("AddUnit 失败: " .. tostring(r))
        return nil
    end
    return r
end

local function findUnit(side, name)
    local ok2, s = pcall(VP_GetSide, { Side = side })
    if not ok2 or not (s and s.units) then return nil end
    for _, u in ipairs(s.units) do
        if u.name == name then return u end
    end
    return nil
end

local function clampHeading(h)
    if type(h) ~= "number" then return 0 end
    return ((h % 360) + 360) % 360
end

local function sideExists(name)
    return pcall(VP_GetSide, { Side = name })
end

local function ensureSide(name, color)
    if sideExists(name) then
        info("阵营 " .. name .. " 已存在")
        return true
    end
    local ok2 = pcall(ScenEdit_AddSide, { name = name, color = color })
    if ok2 then ok("阵营 " .. name .. " 创建成功") end
    return ok2
end

local function setHostile(from, to)
    pcall(ScenEdit_SetSidePosture, from, to, "H")
end

local function createOrReuse(side, name, props)
    local exist = findUnit(side, name)
    if exist then
        if CFG.overwrite_existing then
            pcall(ScenEdit_DeleteUnit, { guid = exist.guid })
            warn(side .. "/" .. name .. " 已存在，已删除重建")
        else
            info(side .. "/" .. name .. " 已存在，复用")
            return exist
        end
    end
    local u = safeAddUnit(props)
    if u then
        ok("[" .. side .. "] " .. name .. " (dbid=" .. props.dbid .. ")")
    end
    return u
end

-- ============================================================
-- 清空单位所有 mount 待发弹（把数量减到 0，但保留武器记录/格子）
-- ============================================================
local function clearUnitWeapons(side, name)
    local u = ScenEdit_GetUnit({ side = side, name = name })
    if not u or not u.guid then
        warn("clearUnitWeapons: 找不到 " .. side .. "/" .. name)
        return false
    end

    local jobs = {}
    for _, m in ipairs(u.mounts or {}) do
        for _, w in ipairs(m.mount_weapons or {}) do
            local cur = tonumber(w.wpn_current) or 0
            if cur > 0 then
                jobs[#jobs + 1] = {
                    dbid = w.wpn_dbid, num = cur, mountid = m.mount_guid,
                }
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
        if (_errnum_ or 0) == 0 then done = done + 1
        else fail = fail + 1 end
    end

    ok(("%s: 减载归零 %d 条 (失败 %d)"):format(name, done, fail))
    return fail == 0
end

-- ============================================================
-- 环境预检
-- ============================================================
info("========================================")
info("CMO 3v3 红蓝对抗脚本 — 精简版")
info("========================================")

ensureSide(CFG.side_blue, "128,128,255")
ensureSide(CFG.side_red,  "255,64,64")
setHostile(CFG.side_red,  CFG.side_blue)
setHostile(CFG.side_blue, CFG.side_red)

for _, side in ipairs({ CFG.side_blue, CFG.side_red }) do
    pcall(ScenEdit_SetDoctrine, { side = side }, {
        weapon_control_status_air        = 0,
        weapon_control_status_surface    = 0,
        weapon_control_status_subsurface = 0,
    })
end
ok("Doctrine WCS = Free")

-- ============================================================
-- 创建蓝方单位
-- ============================================================
info("创建蓝方单位...")
local BLUE_NAMES = {}
for _, cfg in ipairs({
    { name = "DDG 113",         dbid = CFG.dbid_ddg113, latitude = 21.5419, longitude = 129.9125, heading = 294.05 },
    { name = "Blue-DBID-2862",  dbid = CFG.dbid_cg59,   latitude = 21.6100, longitude = 130.1791, heading = 294.58 },
    { name = "Blue-DBID-3551",  dbid = CFG.dbid_cvn70,  latitude = 21.4200, longitude = 130.1713, heading = 293.16 },
}) do
    local u = createOrReuse(CFG.side_blue, cfg.name, {
        side = CFG.side_blue, type = "Ship",
        name = cfg.name, dbid = cfg.dbid,
        latitude = cfg.latitude, longitude = cfg.longitude,
        heading = clampHeading(cfg.heading), speed = 0,
        proficiency = "Veteran",
        autodetectable = CFG.blue_autodetectable,
    })
    -- 额外用 SetUnit 强制设置，确保生效
    if u and u.guid and CFG.blue_autodetectable then
        pcall(ScenEdit_SetUnit, { guid = u.guid, autodetectable = true })
        ok(cfg.name .. " autodetectable=true")
    end
    BLUE_NAMES[#BLUE_NAMES + 1] = cfg.name
end

-- ============================================================
-- 蓝方防御态势：雷达关机（模拟无预警被攻击场景）
-- ============================================================
info("[B] 设置蓝方防御态势...")
for _, name in ipairs({ "DDG 113", "Blue-DBID-2862", "Blue-DBID-3551" }) do
    local u = findUnit(CFG.side_blue, name)
    if u and u.guid then
        pcall(ScenEdit_SetEMCON, "Unit", u.guid, "Radar=Off")
    end
end
pcall(ScenEdit_SetDoctrine, { side = CFG.side_blue }, {
    weapon_control_status_air         = 2,
    weapon_control_status_subsurface  = 2,
    weapon_control_status_surface     = 2,
})
ok("[B] 蓝方 Radar=Off，WCS=全部 Hold（禁止拦截）")

-- 清空蓝方所有待发弹（SM-6 等防空导弹全部卸掉）
info("清空蓝方所有待发弹...")
for _, name in ipairs(BLUE_NAMES) do
    clearUnitWeapons(CFG.side_blue, name)
end

-- ============================================================
-- 创建红方单位
-- ============================================================
info("创建红方单位...")
createOrReuse(CFG.side_red, "Red-052D-1", {
    side = CFG.side_red, type = "Ship",
    name = "Red-052D-1", dbid = CFG.dbid_052d_nj,
    latitude = 21.1437, longitude = 123.451,
    heading = clampHeading(115), speed = 20,
    proficiency = "Veteran",
})
createOrReuse(CFG.side_red, "Red-052D-2", {
    side = CFG.side_red, type = "Ship",
    name = "Red-052D-2", dbid = CFG.dbid_052d_xy,
    latitude = 18.2035, longitude = 123.988,
    heading = clampHeading(50), speed = 20,
    proficiency = "Veteran",
})
createOrReuse(CFG.side_red, "Red-055-1", {
    side = CFG.side_red, type = "Ship",
    name = "Red-055-1", dbid = CFG.dbid_055_nc,
    latitude = 24.8324, longitude = 128.583,
    heading = clampHeading(135), speed = 20,
    proficiency = "Veteran",
})

-- ============================================================
-- 设置红方 Radar=Active
-- ============================================================
info("设置红方 Radar=Active...")
for _, name in ipairs({ "Red-052D-1", "Red-052D-2", "Red-055-1" }) do
    local u = findUnit(CFG.side_red, name)
    if u and u.guid then
        pcall(ScenEdit_SetEMCON, "Unit", u.guid, "Radar=Active")
    end
end
ok("红方 Radar=Active")

-- ============================================================
-- 红方全知（God's Eye View）
-- ============================================================
info("设置红方为全知(OMNI)...")
do
    _errnum_ = 0
    local a = ScenEdit_SetSideOptions({ side = CFG.side_red, awareness = "OMNI" })
    if (_errnum_ or 0) == 0 then
        ok("红方 awareness = " .. tostring(a and a.awareness or "OMNI"))
    else
        warn("设置全知失败: " .. tostring(_errmsg_))
    end
end

-- ============================================================
-- 清空红方待发弹（重装前归零）
-- ============================================================
info("清空红方待发弹...")
for _, name in ipairs({ "Red-052D-1", "Red-052D-2", "Red-055-1" }) do
    clearUnitWeapons(CFG.side_red, name)
end

-- ============================================================
-- 弹药补给
-- ============================================================
info("弹药补给...")

local AMMO = {
    { unitname = "Red-052D-1", wpn_dbid = CFG.dbid_yj18, number = 16 },
    { unitname = "Red-052D-2", wpn_dbid = CFG.dbid_yj18, number = 16 },
    { unitname = "Red-052D-2", wpn_dbid = CFG.dbid_yj18, number = 16 },
    { unitname = "Red-055-1",  wpn_dbid = CFG.dbid_yj18, number = 32 },
}

for _, a in ipairs(AMMO) do
    local ok2 = pcall(ScenEdit_AddReloadsToUnit, {
        side = CFG.side_red, unitname = a.unitname,
        wpn_dbid = a.wpn_dbid, number = a.number,
    })
    if ok2 then
        ok("+ " .. a.number .. "x [" .. a.wpn_dbid .. "] → " .. a.unitname)
    else
        warn("弹药补给失败: " .. a.unitname .. " (dbid=" .. a.wpn_dbid .. ")")
    end
end

-- ============================================================
-- 自检
-- ============================================================
info("自检 Red-055-1 待发弹...")
do
    local u = ScenEdit_GetUnit({ side = CFG.side_red, name = "Red-055-1" })
    if u then
        local total = 0
        for i, m in ipairs(u.mounts or {}) do
            for _, w in ipairs(m.mount_weapons or {}) do
                local c = tonumber(w.wpn_current) or 0
                if c > 0 then
                    info(("  MOUNT %d dbid=%s cur=%d"):format(i, tostring(w.wpn_dbid), c))
                    total = total + c
                end
            end
        end
        ok("Red-055-1 待发弹合计 = " .. total)
    end
end

-- ============================================================
-- Contact 等待与攻击逻辑（从 1v1.lua 移植的完整链路）
-- ============================================================
_CONTACT_CACHE = _CONTACT_CACHE or {}
_CONTACT_RETRY_SEQ = _CONTACT_RETRY_SEQ or 0

local function sameGuid(a, b)
    return a and b and tostring(a):lower() == tostring(b.guid):lower()
end

local function collectContacts(sideName)
    local out, seen = {}, {}
    local calls = {
        function() return ScenEdit_GetContacts({ side = sideName }) end,
        function() return ScenEdit_GetContacts({ Side = sideName }) end,
        function() return ScenEdit_GetContacts(sideName) end,
    }
    for _, fn in ipairs(calls) do
        local ok2, r = pcall(fn)
        if ok2 and type(r) == "table" then
            for _, c in ipairs(r) do
                local cg = c.guid or c.Guid
                if cg and not seen[cg] then
                    seen[cg] = true
                    out[#out + 1] = c
                end
            end
        end
    end
    local ok2, s = pcall(VP_GetSide, { Side = sideName })
    if ok2 and s and type(s.contacts) == "table" then
        for _, c in ipairs(s.contacts) do
            local cg = c.guid or c.Guid
            if cg and not seen[cg] then
                seen[cg] = true
                out[#out + 1] = c
            end
        end
    end
    return out
end

local function findContactForTarget(sideName, tgt)
    local cacheKey = tostring(sideName) .. "|" .. tostring(tgt.guid)
    if _CONTACT_CACHE[cacheKey] then
        return _CONTACT_CACHE[cacheKey]
    end

    pcall(ScenEdit_SetSideOptions, { side = sideName, awareness = "OMNI" })
    local cs = collectContacts(sideName)
    info(tostring(sideName) .. " contact count = " .. #cs)

    for _, c in ipairs(cs) do
        local cg = c.guid or c.Guid
        if not cg then goto continue end
        if sameGuid(c.actualunitid, tgt.guid)
            or sameGuid(c.actualUnitID, tgt.guid)
            or sameGuid(c.actualunitguid, tgt.guid)
            or sameGuid(c.actualUnitGuid, tgt.guid)
            or sameGuid(c.actualunit, tgt.guid)
            or sameGuid(c.actualUnit, tgt.guid) then
            _CONTACT_CACHE[cacheKey] = cg
            ok("matched contact for " .. tgt.name .. " by GUID: " .. tostring(cg))
            return cg
        end
        if (c.name or c.Name or "") == tgt.name then
            _CONTACT_CACHE[cacheKey] = cg
            ok("matched contact for " .. tgt.name .. " by name: " .. tostring(cg))
            return cg
        end
        ::continue::
    end
    return nil
end

local function eventTicks(addSeconds)
    local t = ScenEdit_CurrentTime()
    local offSet = 62135596801
    local newTime = (t + offSet + addSeconds) * 10000000
    return string.format("%.0f", newTime)
end

-- ============================================================
-- 攻击函数（全局，供触发器调用）
-- ============================================================
_SIDE_RED  = CFG.side_red
_SIDE_BLUE = CFG.side_blue

function fireAt(attackerName, targetName, wpnDbid, qty)
    local atk = ScenEdit_GetUnit({ side = _SIDE_RED,  name = attackerName })
    local tgt = ScenEdit_GetUnit({ side = _SIDE_BLUE, name = targetName })

    if not (atk and atk.guid) then
        print("[CMO] [ERROR] 找不到攻击方 " .. attackerName); return false
    end
    if not (tgt and tgt.guid) then
        print("[CMO] [ERROR] 找不到目标 " .. targetName); return false
    end

    -- 强制让目标可探测
    if CFG.blue_autodetectable then
        pcall(ScenEdit_SetUnit, { guid = tgt.guid, autodetectable = true })
    end

    -- 等待 contact 出现
    local contactGuid = findContactForTarget(_SIDE_RED, tgt)
    if not contactGuid then
        print("[CMO] [ERROR] " .. attackerName .. " 未能获得 " .. targetName .. " 的 contact，发射取消")
        return false
    end

    -- 按 contact 发射
    _errnum_ = 0
    local r = ScenEdit_AttackContact(atk.guid, contactGuid,
            { mode = "1", weapon = wpnDbid, qty = qty })

    if r then
        print(("[CMO] [SUCCESS] %s 发射 %d 枚 [%d] → %s (contact=%s)")
            :format(attackerName, qty, wpnDbid, targetName, tostring(contactGuid)))
        return true
    else
        print(("[CMO] [ERROR] %s 攻击 %s 失败 (errmsg=%s)")
            :format(attackerName, targetName, tostring(_errmsg_)))
        return false
    end
end

-- ============================================================
-- 定时齐射调度
-- ============================================================
local SALVO = {
    { "Red-052D-2", "Blue-DBID-3551", CFG.dbid_yj18, 16,  0,  5 },
    { "Red-055-1",  "Blue-DBID-2862", CFG.dbid_yj18, 16,  37, 5 },
    { "Red-052D-1", "DDG 113",        CFG.dbid_yj18, 16,  74, 5 },
}

local function scheduleOne(atkName, tgtName, wpn, delay, tag)
    delay = delay + CFG.contact_settle_delay
    local evName = "Event " .. tag
    local trName = "Trig " .. tag
    local acName = "Act " .. tag
    local fireTime = eventTicks(delay)
    local script =
        ("fireAt(%q,%q,%d,1)\n"):format(atkName, tgtName, wpn) ..
        ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(evName) ..
        ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(acName) ..
        ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(trName)
    _errnum_ = 0
    local okTr = pcall(ScenEdit_SetTrigger, { mode="add", type="Time", name=trName, Time=fireTime })
    local okAc = pcall(ScenEdit_SetAction,  { mode="add", type="LuaScript", name=acName, ScriptText=script })
    local okEv = pcall(ScenEdit_SetEvent, evName, { mode="add", IsActive=true, IsRepeatable=false })
    pcall(ScenEdit_SetEventTrigger, evName, { mode="add", name=trName })
    pcall(ScenEdit_SetEventAction,  evName, { mode="add", name=acName })
    return okTr and okAc and okEv
end

function scheduleSalvo()
    info("调度逐枚定时发射...")
    local nowT = ScenEdit_CurrentTime()
    info("当前仿真时间(基准0) = " .. tostring(nowT))

    local sched, failc = 0, 0
    for i, s in ipairs(SALVO) do
        local atkName, tgtName, wpn, qty, startDelay, interval =
            s[1], s[2], s[3], s[4], s[5], s[6]
        for k = 1, qty do
            local delay = startDelay + (k - 1) * interval
            local tag = "TOT_" .. i .. "_" .. k .. "_" .. tostring(nowT)
            if scheduleOne(atkName, tgtName, wpn, delay, tag) then
                sched = sched + 1
                ok(("调度 %s 第%d枚 @%ds -> %s")
                    :format(atkName, k, delay + CFG.contact_settle_delay, tgtName))
            else
                failc = failc + 1
                err(("调度失败 %s 第%d枚 @%ds (errmsg=%s)")
                    :format(atkName, k, delay + CFG.contact_settle_delay, tostring(_errmsg_)))
            end
        end
    end
    ok(("逐枚调度完成：成功 %d，失败 %d"):format(sched, failc))
end

-- ============================================================
-- 等待 contact 后调度齐射（自动重试）
-- ============================================================
local function waitForTargetContactThenScheduleSalvo(retryLeft)
    if retryLeft == nil then retryLeft = CFG.contact_retry_count end

    local first = SALVO[1]
    if not first then
        err("未配置齐射清单，无法调度"); return false
    end

    local targetName = first[2]
    local tgt = ScenEdit_GetUnit({ side = _SIDE_BLUE, name = targetName })
    if not (tgt and tgt.guid) then
        err("等待 contact 失败：找不到目标 " .. tostring(targetName)); return false
    end
    if CFG.blue_autodetectable then
        pcall(ScenEdit_SetUnit, { guid = tgt.guid, autodetectable = true })
    end

    local contactGuid = findContactForTarget(_SIDE_RED, tgt)
    if contactGuid then
        ok(("已获得 %s 的红方 contact：%s，开始调度齐射")
            :format(targetName, tostring(contactGuid)))
        scheduleSalvo()
        return true
    end

    if retryLeft > 0 then
        _CONTACT_RETRY_SEQ = _CONTACT_RETRY_SEQ + 1
        local tag = "ContactWait_" .. _CONTACT_RETRY_SEQ .. "_" .. tostring(ScenEdit_CurrentTime())
        local evName = "Event " .. tag
        local trName = "Trig " .. tag
        local acName = "Act " .. tag
        local script =
            ("waitForTargetContactThenScheduleSalvo(%d)\n"):format(retryLeft - 1) ..
            ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(evName) ..
            ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(acName) ..
            ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(trName)
        pcall(ScenEdit_SetTrigger, { mode="add", type="Time", name=trName, Time=eventTicks(CFG.contact_retry_delay) })
        pcall(ScenEdit_SetAction,  { mode="add", type="LuaScript", name=acName, ScriptText=script })
        pcall(ScenEdit_SetEvent, evName, { mode="add", IsActive=true, IsRepeatable=false })
        pcall(ScenEdit_SetEventTrigger, evName, { mode="add", name=trName })
        pcall(ScenEdit_SetEventAction,  evName, { mode="add", name=acName })
        warn(("%s 尚无 contact，%ds 后重试，剩余 %d 次")
            :format(targetName, CFG.contact_retry_delay, retryLeft))
        return true
    end

    err(("未调度齐射：%s 没有红方可攻击 contact"):format(targetName))
    return false
end

waitForTargetContactThenScheduleSalvo(CFG.contact_retry_count)

ok("脚本执行完成。齐射只会在获得红方 contact 后调度；延迟的弹需游戏推进时间后才会逐枚发射。")
