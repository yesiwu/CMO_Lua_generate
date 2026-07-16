-- ============================================================
-- all.lua: 南海 1V1 4步合一一键脚本
-- 执行顺序: main.lua -> clear.lua -> reload.lua -> attack.lua
-- 一次性完成: 建单位 -> 清弹 -> 装弹 -> 真延时调度齐射
-- 真延时 contact_settle_delay = 15 秒
-- 红方: 055-1  (OMNI, EMCON=Active)
-- 蓝方: DDG-113-1  (autodetectable, EMCON=Active)
-- 055-1 装弹 16 枚 YJ-18，发射 13 枚 -> DDG-113-1
-- ============================================================

print("[CMO] [INFO] ============ 1V1 all.lua 开始 ============")
print("[CMO] [INFO] STEP 1/4 main.lua  -> 建单位")
print("[CMO] [INFO] STEP 2/4 clear.lua -> 清弹")
print("[CMO] [INFO] STEP 3/4 reload.lua-> 装弹")
print("[CMO] [INFO] STEP 4/4 attack.lua-> 真延时打击 (TOT, contact_settle_delay=15s)")
print("")

-- ============================================================
-- 工具与全局 (4 文件合并)
-- ============================================================
local LOG_PREFIX = "[CMO]"
local function log(level, msg) print(LOG_PREFIX .. " [" .. level .. "] " .. tostring(msg)) end
local function info(msg) log("INFO",    msg) end
local function warn(msg) log("WARNING", msg) end
local function err(msg)  log("ERROR",   msg) end
local function ok(msg)   log("SUCCESS", msg) end

local function clampHeading(h)
    if type(h) ~= "number" then return 0 end
    return ((h % 360) + 360) % 360
end

local function sideExists(name)
    return pcall(VP_GetSide, { Side = name })
end

local function ensureSide(name, color)
    if sideExists(name) then
        info("阵营已存在: " .. name)
        return true
    end
    local ok2 = pcall(ScenEdit_AddSide, { name = name, color = color })
    if ok2 then ok("阵营创建成功: " .. name) end
    return ok2
end

local function setHostile(from, to)
    pcall(ScenEdit_SetSidePosture, from, to, "H")
end

local function findUnit(side, name)
    local ok2, s = pcall(VP_GetSide, { Side = side })
    if not ok2 or not (s and s.units) then return nil end
    for _, u in ipairs(s.units) do
        if u.name == name then return u end
    end
    return nil
end

local function safeAddUnit(props)
    local ok2, r = pcall(ScenEdit_AddUnit, props)
    if not ok2 then err("AddUnit 失败: " .. tostring(r)); return nil end
    return r
end

local function createOrReuse(side, name, props)
    local exist = findUnit(side, name)
    if exist then
        info(side .. "/" .. name .. " 已存在，复用")
        return exist
    end
    local u = safeAddUnit(props)
    if u then ok("[" .. side .. "] " .. name .. " dbid=" .. tostring(props.dbid)) end
    return u
end

local function forceBlueAutodetectable(side, name)
    local u = ScenEdit_GetUnit({ side = side, name = name })
    if not (u and u.guid) then return false end
    return pcall(ScenEdit_SetUnit, { guid = u.guid, autodetectable = true })
end

local function sameGuid(a, b)
    return a and b and tostring(a):lower() == tostring(b):lower()
end

local function addContact(dst, seen, c)
    if type(c) ~= "table" then return end
    local cg = c.guid or c.Guid
    if not cg then return end
    local key = tostring(cg)
    if seen[key] then return end
    seen[key] = true
    dst[#dst + 1] = c
end

local function collectContactsFromTable(dst, seen, t, depth)
    if type(t) ~= "table" or depth > 3 then return end
    addContact(dst, seen, t)
    for _, v in pairs(t) do
        if type(v) == "table" then
            collectContactsFromTable(dst, seen, v, depth + 1)
        end
    end
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
            collectContactsFromTable(out, seen, r, 0)
        end
    end
    local ok2, s = pcall(VP_GetSide, { Side = sideName })
    if ok2 and s and type(s.contacts) == "table" then
        collectContactsFromTable(out, seen, s.contacts, 0)
    end
    return out
end

local function contactName(c)
    return tostring(c.name or c.Name or c.actualunitname or c.actualUnitName or "")
end

local function clearUnitWeapons(side, name)
    local u = ScenEdit_GetUnit({ side = side, name = name })
    if not u or not u.guid then
        warn("找不到 " .. side .. "/" .. name)
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

local function dumpAmmo(side, name)
    local u = ScenEdit_GetUnit({ side = side, name = name })
    if not u then return end
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
    ok(name .. " 待发弹合计 = " .. total)
end

local function totTicks(addSeconds)
    local t = ScenEdit_CurrentTime()
    return string.format("%.0f", (t + 62135596801) * 1e7)
end

-- ============================================================
-- 配置常量
-- ============================================================
local CFG = {
    dbid_055    = 3883,
    dbid_ddg113 = 4299,
    dbid_yj18   = 2868,

    lat_055    = 15.0, lon_055    = 112.5,
    lat_ddg113 = 19.0, lon_ddg113 = 117.5,

    side_red  = "红方",
    side_blue = "蓝方",
    blue_autodetectable = true,
}

local AMMO_LIST = {
    { unitname = "055-1", wpn_dbid = CFG.dbid_yj18, number = 16 },
}

local STRIKE = {
    { "055-1", "DDG-113-1", 2868, 13, 0, 1 },
}

-- ============================================================
-- 全局配置 (fireAt 沙箱需要)
-- ============================================================
_SIDE_RED             = CFG.side_red
_SIDE_BLUE            = CFG.side_blue
_BLUE_AUTODETECTABLE  = true
_CONTACT_SETTLE_DELAY = 15
-- BatchRunner 的 Lua 回调不会自动推进仿真时间；找不到 contact 时
-- 使用坐标 BOL，避免在回调中忙等 ScenEdit_CurrentTime()。
_ALLOW_BOL_FALLBACK   = true
_CONTACT_CACHE        = {}

local function findContactForTarget(tgt, tgtName)
    if not (tgt and tgt.guid) then return nil end
    local cacheKey = tostring(tgt.guid)
    if _CONTACT_CACHE[cacheKey] then return _CONTACT_CACHE[cacheKey] end

    pcall(ScenEdit_SetSideOptions, { side = _SIDE_RED, awareness = "OMNI" })
    local cs = collectContacts(_SIDE_RED)
    info(_SIDE_RED .. " contact count = " .. tostring(#cs))

    for _, c in ipairs(cs) do
        local cg = c.guid or c.Guid
        if cg and (
            sameGuid(c.actualunitid,    tgt.guid)
            or sameGuid(c.actualUnitID, tgt.guid)
            or sameGuid(c.actualunitguid, tgt.guid)
            or sameGuid(c.actualUnitGuid, tgt.guid)
            or sameGuid(c.actualunit,    tgt.guid)
            or sameGuid(c.actualUnit,    tgt.guid)
            or sameGuid(c.actual_guid,   tgt.guid)
            or sameGuid(c.actualGuid,    tgt.guid)
        ) then
            _CONTACT_CACHE[cacheKey] = cg
            info("Matched contact by GUID: " .. tgtName)
            return cg
        end
    end

    for _, c in ipairs(cs) do
        local cg = c.guid or c.Guid
        local nm = contactName(c)
        if cg and tgtName and (nm == tgtName or nm:find(tgtName, 1, true)) then
            _CONTACT_CACHE[cacheKey] = cg
            warn("Matched contact by name: " .. tgtName)
            return cg
        end
    end
    return nil
end

-- ============================================================
-- STEP 1: main.lua — 创建单位
-- ============================================================
print("========================================")
print("       STEP 1/4: 建单位")
print("========================================")

ensureSide(CFG.side_blue, "128,128,255")
ensureSide(CFG.side_red,  "255,64,64")
setHostile(CFG.side_red,  CFG.side_blue)
setHostile(CFG.side_blue, CFG.side_red)

-- 蓝方目标
createOrReuse(CFG.side_blue, "DDG-113-1", {
    side = CFG.side_blue, type = "Ship", name = "DDG-113-1",
    dbid = CFG.dbid_ddg113,
    latitude = CFG.lat_ddg113, longitude = CFG.lon_ddg113,
    heading = clampHeading(200), speed = 0,
    proficiency = "Veteran",
    autodetectable = CFG.blue_autodetectable,
})

pcall(ScenEdit_SetDoctrine, { side = CFG.side_blue }, {
    weapon_control_status_air        = 0,
    weapon_control_status_subsurface = 2,
    weapon_control_status_surface   = 2,
})
ok("蓝方 Doctrine: Air=Free, Surface/Subsurface=Hold")

-- 蓝方 EMCON
local blueU = findUnit(CFG.side_blue, "DDG-113-1")
if blueU and blueU.guid then
    pcall(ScenEdit_SetEMCON, "Unit", blueU.guid, "Radar=Active;Sonar=Active;OECM=Active")
end
ok("蓝方 EMCON=Active")

-- 蓝方 autodetectable 双保险
if CFG.blue_autodetectable then
    if forceBlueAutodetectable(CFG.side_blue, "DDG-113-1") then
        ok("DDG-113-1 autodetectable=true")
    end
end

-- 红方单位
createOrReuse(CFG.side_red, "055-1", {
    side = CFG.side_red, type = "Ship", name = "055-1",
    dbid = CFG.dbid_055,
    latitude = CFG.lat_055, longitude = CFG.lon_055,
    heading = clampHeading(45), speed = 20, proficiency = "Veteran",
})

-- 红方 EMCON
local redU = findUnit(CFG.side_red, "055-1")
if redU and redU.guid then
    pcall(ScenEdit_SetEMCON, "Unit", redU.guid, "Radar=Active;Sonar=Active;OECM=Active")
end
ok("红方 EMCON=Active")

-- 红方 OMNI
do
    _errnum_ = 0
    local a = ScenEdit_SetSideOptions({ side = CFG.side_red, awareness = "OMNI" })
    if (_errnum_ or 0) == 0 then
        ok("红方 awareness = " .. tostring(a and a.awareness or "OMNI"))
    else
        warn("OMNI 失败: " .. tostring(_errmsg_))
    end
end

pcall(ScenEdit_SetDoctrine, { side = CFG.side_red }, {
    weapon_control_status_air        = 0,
    weapon_control_status_surface    = 0,
    weapon_control_status_subsurface = 0,
})
ok("红方 Doctrine: WCS=Free")
ok("STEP 1 完成: 单位已就绪")

-- ============================================================
-- STEP 2: clear.lua — 清弹
-- ============================================================
print("")
print("========================================")
print("       STEP 2/4: 清弹")
print("========================================")

clearUnitWeapons(CFG.side_red, "055-1")

print("=== 清空后自检 ===")
dumpAmmo(CFG.side_red, "055-1")
ok("STEP 2 完成: 弹已清空")

-- ============================================================
-- STEP 3: reload.lua — 装弹
-- ============================================================
print("")
print("========================================")
print("       STEP 3/4: 装弹 (YJ-18 x16)")
print("========================================")

for _, a in ipairs(AMMO_LIST) do
    local ok2 = pcall(ScenEdit_AddReloadsToUnit, {
        side = CFG.side_red, unitname = a.unitname,
        wpn_dbid = a.wpn_dbid, number = a.number,
    })
    if ok2 then
        ok("+ " .. a.number .. "x [YJ-18 dbid=" .. a.wpn_dbid .. "] -> " .. a.unitname)
    else
        warn("补给失败: " .. a.unitname)
    end
end

print("=== 装弹自检 ===")
dumpAmmo(CFG.side_red, "055-1")
ok("STEP 3 完成: 弹药已就绪")

-- ============================================================
-- STEP 4: attack.lua — 真延时打击 (TOT 事件驱动)
-- ============================================================
print("")
print("========================================")
print("       STEP 4/4: 真延时打击")
print("       contact_settle_delay = 15 秒")
print("========================================")

function fireAt(attackerName, targetName, wpnDbid, qty)
    local atk = ScenEdit_GetUnit({side = _SIDE_RED,  name = attackerName})
    local tgt = ScenEdit_GetUnit({side = _SIDE_BLUE, name = targetName})

    if not (atk and atk.guid) then
        print(LOG_PREFIX .. " [ERROR] 找不到攻击方 " .. attackerName); return false end
    if not (tgt and tgt.guid) then
        print(LOG_PREFIX .. " [ERROR] 找不到目标 " .. targetName); return false end

    if _BLUE_AUTODETECTABLE then
        pcall(ScenEdit_SetUnit, {guid = tgt.guid, autodetectable = true})
    end

    local contactGuid
    for attempt = 1, 3 do
        contactGuid = findContactForTarget(tgt, targetName)
        if contactGuid then
            print(LOG_PREFIX .. " [INFO] Attempt " .. attempt .. "/3: 找到 contact " .. contactGuid)
            break
        end
        if attempt < 3 then
            -- 不等待仿真时间：当前函数可能运行在暂停的 CMO 事件回调中。
            print(LOG_PREFIX .. " [WARNING] Attempt " .. attempt .. "/3: 无 contact，立即重试...")
        end
    end

    local r
    if contactGuid then
        _errnum_ = 0
        r = ScenEdit_AttackContact(atk.guid, contactGuid, {
            mode = "1", weapon = wpnDbid, qty = qty,
        })
        print(LOG_PREFIX .. " [INFO] " .. attackerName .. " -> CONTACT 攻击 " .. targetName)
    elseif _ALLOW_BOL_FALLBACK then
        _errnum_ = 0
        r = ScenEdit_AttackContact(atk.guid, "BOL", {
            mode = "1", weapon = wpnDbid, qty = qty,
            latitude = tgt.latitude, longitude = tgt.longitude,
        })
    else
        print(LOG_PREFIX .. " [ERROR] " .. attackerName .. " 无 contact, 取消发射")
        return false
    end

    if r then
        print(LOG_PREFIX .. " [SUCCESS] " .. attackerName .. " 发射 " .. qty
            .. "x [YJ-18] -> " .. targetName)
        return true
    else
        print(LOG_PREFIX .. " [ERROR] " .. attackerName .. " 失败: " .. tostring(_errmsg_))
        return false
    end
end

local function scheduleOne(atkName, tgtName, wpn, delay, tag)
    delay = delay + _CONTACT_SETTLE_DELAY

    local evName = "Event " .. tag
    local trName = "Trig "  .. tag
    local acName = "Act "   .. tag
    local fireTime = totTicks(delay)

    local script =
        ("fireAt(%q,%q,%d,1)\n"):format(atkName, tgtName, wpn) ..
        ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(evName) ..
        ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(acName) ..
        ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(trName)

    _errnum_ = 0
    local okTr = pcall(ScenEdit_SetTrigger, {mode="add", type="Time", name=trName, Time=fireTime})
    local okAc = pcall(ScenEdit_SetAction,  {mode="add", type="LuaScript", name=acName, ScriptText=script})
    local okEv = pcall(ScenEdit_SetEvent,   evName, {mode="add", IsActive=true, IsRepeatable=false})
    pcall(ScenEdit_SetEventTrigger, evName, {mode="add", name=trName})
    pcall(ScenEdit_SetEventAction,  evName, {mode="add", name=acName})

    if okTr and okAc and okEv then
        ok(("调度 %s -> %s | +%ds | %s"):format(atkName, tgtName, delay, tag))
        return true
    else
        err(("调度失败 %s -> %s (errmsg=%s)"):format(atkName, tgtName, tostring(_errmsg_)))
        return false
    end
end

local nowT = ScenEdit_CurrentTime()
local sched, failc = 0, 0
for i, s in ipairs(STRIKE) do
    local atkName, tgtName, wpn, qty, startDelay, interval =
        s[1], s[2], s[3], s[4], s[5] or 0, s[6] or 1
    for k = 1, qty do
        local delay = startDelay + (k - 1) * interval
        local tag = ("TOT_%d_%d_%d"):format(i, k, nowT)
        if scheduleOne(atkName, tgtName, wpn, delay, tag) then
            sched = sched + 1
        else
            failc = failc + 1
        end
    end
end
ok(("TOT 调度完成: 成功 %d 枚, 失败 %d 枚"):format(sched, failc))

print("")
print("齐射时序（含 15s contact 稳定期）：")
print("  055-1  -> DDG-113-1  13 枚  首发 +15s  末枚 +27s")
print("")
print("共发射: 13 枚 YJ-18")
print("说明: 必须【推进游戏时间】才会触发; 暂停不发射")
print("")
ok("STEP 4 完成: 真延时齐射已调度")
ok("all.lua 执行完毕 (建单位 -> 清弹 -> 装弹 -> 真延时打击)")
