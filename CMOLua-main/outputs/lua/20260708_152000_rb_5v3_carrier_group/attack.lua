-- ============================================================
-- attack.lua: 真延时打击（TOT 事件驱动）
-- 一次性完成：真延时调度齐射
-- 真延时 contact_settle_delay = 15 秒
-- 数据来源: JSON red_blue_5v3_liaoning.json
-- ============================================================

print("[CMO] [INFO] ============ attack.lua 开始 ============")

-- ============================================================
-- 工具与全局（与 all.lua 完全一致）
-- ============================================================
local LOG_PREFIX = "[CMO]"
local function log(level, msg) print(LOG_PREFIX .. " [" .. level .. "] " .. tostring(msg)) end
local function info(msg) log("INFO",    msg) end
local function warn(msg) log("WARNING", msg) end
local function err(msg)  log("ERROR",   msg) end
local function ok(msg)   log("SUCCESS", msg) end

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

local function totTicks(addSeconds)
    local t = ScenEdit_CurrentTime()
    local offSet = 62135596801
    return string.format("%.0f", (t + offSet + addSeconds) * 1e7)
end

-- ============================================================
-- 配置常量
-- ============================================================
local CFG = {
    dbid_yj18  = 2868,
    dbid_yj83k = 2137,
    side_red   = "红方",
    side_blue  = "蓝方",
}

-- STRIKE: {攻击方, 目标, 武器DBID, 数量, 首发延时, 枚间隔(ripple)}
-- 全 T=0（contact_settle=15s）
-- JSON §killWebs §platformExecutions：
--   055:  13×YJ-18 → DDG-113-1(#8) + DDG-113-2(#5)
--   052D-1: 8×YJ-18  → CVN-70
--   052D-2: 5×YJ-18  → CG-59
--   J-15-1: 4×YJ-83K → DDG-113-1
--   J-15-2: 4×YJ-83K → CG-59
local STRIKE = {
    { "红方055南昌舰",    "蓝方DDG-113-1约翰芬恩", CFG.dbid_yj18, 8,  0, 1 },
    { "红方055南昌舰",    "蓝方DDG-113-2约翰芬恩", CFG.dbid_yj18, 5,  0, 1 },
    { "红方052D-1昆明舰", "蓝方CVN-70卡尔文森",   CFG.dbid_yj18, 8,  0, 1 },
    { "红方052D-2南京舰", "蓝方CG-59普林斯顿",    CFG.dbid_yj18, 5,  0, 1 },
    { "J-15-1",          "蓝方DDG-113-1约翰芬恩", CFG.dbid_yj83k, 4, 0, 1 },
    { "J-15-2",          "蓝方CG-59普林斯顿",     CFG.dbid_yj83k, 4, 0, 1 },
}

-- ============================================================
-- 全局配置 (fireAt 沙箱需要)
-- ============================================================
_SIDE_RED              = CFG.side_red
_SIDE_BLUE             = CFG.side_blue
_BLUE_AUTODETECTABLE   = true
_CONTACT_SETTLE_DELAY  = 15
_CONTACT_RETRY_DELAY   = 5
_CONTACT_RETRY_COUNT   = 12
_ALLOW_BOL_FALLBACK    = false
_CONTACT_CACHE         = {}

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
-- fireAt（全局函数，事件脚本沙箱调用）
-- ============================================================
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
    for attempt = 1, _CONTACT_RETRY_COUNT do
        contactGuid = findContactForTarget(tgt, targetName)
        if contactGuid then
            print(LOG_PREFIX .. " [INFO] Attempt " .. attempt .. "/" .. _CONTACT_RETRY_COUNT .. ": 找到 contact " .. contactGuid)
            break
        end
        if attempt < _CONTACT_RETRY_COUNT then
            print(LOG_PREFIX .. " [WARNING] Attempt " .. attempt .. "/" .. _CONTACT_RETRY_COUNT .. ": 无 contact, " .. _CONTACT_RETRY_DELAY .. "s 重试...")
            local _t = ScenEdit_CurrentTime()
            while ScenEdit_CurrentTime() < _t + _CONTACT_RETRY_DELAY do end
        end
    end

    local wname = (wpnDbid == CFG.dbid_yj18) and "YJ-18" or "YJ-83K"
    local r
    if contactGuid then
        _errnum_ = 0
        r = ScenEdit_AttackContact(atk.guid, contactGuid, {
            mode = "1", weapon = wpnDbid, qty = qty,
        })
        print(LOG_PREFIX .. " [INFO] " .. attackerName .. " -> CONTACT 攻击 " .. targetName)
    elseif _ALLOW_BOL_FALLBACK then
        _errnum_ = 0
        r = ScenEdit_AttackContact(atk.guid, tgt.guid, {
            mode = "1", weapon = wpnDbid, qty = qty,
            latitude  = tgt.latitude, longitude = tgt.longitude,
        })
    else
        print(LOG_PREFIX .. " [ERROR] " .. attackerName .. " 无 contact, 取消发射")
        return false
    end

    if r then
        print(LOG_PREFIX .. " [SUCCESS] " .. attackerName .. " 发射 " .. qty
            .. "x [" .. wname .. " dbid=" .. wpnDbid .. "] -> " .. targetName)
        return true
    else
        print(LOG_PREFIX .. " [ERROR] " .. attackerName .. " 失败: " .. tostring(_errmsg_))
        return false
    end
end

-- ============================================================
-- 单枚调度
-- ============================================================
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

-- ============================================================
-- TOT 调度
-- ============================================================
print("========================================")
print("       真延时打击调度")
print("       contact_settle_delay = 15 秒")
print("========================================")

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
print("齐射时序 (含 15s contact 稳定期):")
print("  红方055南昌舰    -> 蓝方DDG-113-1约翰芬恩  8 枚  首发 +15s   末枚 +22s")
print("  红方055南昌舰    -> 蓝方DDG-113-2约翰芬恩  5 枚  首发 +15s   末枚 +19s")
print("  红方052D-1昆明舰 -> 蓝方CVN-70卡尔文森    8 枚  首发 +15s   末枚 +22s")
print("  红方052D-2南京舰 -> 蓝方CG-59普林斯顿     5 枚  首发 +15s   末枚 +19s")
print("  J-15-1          -> 蓝方DDG-113-1约翰芬恩  4 枚  首发 +15s   末枚 +18s")
print("  J-15-2          -> 蓝方CG-59普林斯顿      4 枚  首发 +15s   末枚 +18s")
print("")
print("共发射: 34 枚 (26×YJ-18 + 8×YJ-83K)")
print("说明: 必须【推进游戏时间】才会触发; 暂停不发射")
ok("attack.lua 执行完毕")
