-- ============================================================
-- attack.lua: 南海 4V4 真延时打击（TOT 事件驱动）
-- 红方 055-1   发射 13 枚 YJ-18 -> DDG-113-1   startDelay=0
-- 红方 055-2   发射 13 枚 YJ-18 -> DDG-113-2   startDelay=0
-- 红方 052D-1  发射  8 枚 YJ-18 -> CVN-70      startDelay=10
-- 红方 052D-2  发射  5 枚 YJ-18 -> CG-59       startDelay=20
-- contact_settle_delay = 15 秒
-- 每枚弹 = 1 个独立 Time Trigger + LuaScript(qty=1)
-- ============================================================

-- ---------- 全局配置（事件沙箱可访问） ----------
_SIDE_RED              = "红方"
_SIDE_BLUE             = "蓝方"
_BLUE_AUTODETECTABLE   = true
_CONTACT_SETTLE_DELAY  = 15
_CONTACT_RETRY_DELAY   = 5
_CONTACT_RETRY_COUNT   = 12
_ALLOW_BOL_FALLBACK    = false
_CONTACT_CACHE         = {}

local CFG = {
    -- { 攻击方,  目标,        武器DBID, 数量, 首发延迟, 枚间隔 }
    { "055-1",  "DDG-113-1", 2868, 13,  0, 1 },
    { "055-2",  "DDG-113-2", 2868, 13,  0, 1 },
    { "052D-1", "CVN-70",    2868,  8, 10, 1 },
    { "052D-2", "CG-59",     2868,  5, 20, 1 },
}

local LOG_PREFIX = "[CMO]"
local function log(level, msg) print(LOG_PREFIX .. " [" .. level .. "] " .. tostring(msg)) end
local function info(msg) log("INFO",    msg) end
local function warn(msg) log("WARNING", msg) end
local function err(msg)  log("ERROR",   msg) end
local function ok(msg)   log("SUCCESS", msg) end

-- ---------- 工具函数 ----------
local function sameGuid(a, b)
    return a and b and tostring(a):lower() == tostring(b):lower()
end

local function forceBlueAutodetectable(name)
    local u = ScenEdit_GetUnit({side = _SIDE_BLUE, name = name})
    if not (u and u.guid) then return false end
    return pcall(ScenEdit_SetUnit, {guid = u.guid, autodetectable = true})
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
            info("Matched contact by GUID: " .. tgtName .. " contact=" .. cg)
            return cg
        end
    end

    for _, c in ipairs(cs) do
        local cg = c.guid or c.Guid
        local nm = contactName(c)
        if cg and tgtName and (nm == tgtName or nm:find(tgtName, 1, true)) then
            _CONTACT_CACHE[cacheKey] = cg
            warn("Matched contact by name: " .. tgtName .. " contact=" .. cg)
            return cg
        end
    end
    return nil
end

-- ============================================================
-- 全局 fireAt（事件脚本沙箱调用）
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
    for attempt = 1, 3 do
        contactGuid = findContactForTarget(tgt, targetName)
        if contactGuid then
            print(LOG_PREFIX .. " [INFO] Attempt " .. attempt .. "/3: 找到 contact " .. contactGuid)
            break
        end
        if attempt < 3 then
            print(LOG_PREFIX .. " [WARNING] Attempt " .. attempt .. "/3: 无 contact，2s 重试...")
            local _t = ScenEdit_CurrentTime()
            while ScenEdit_CurrentTime() < _t + 2 do end
        end
    end

    local r
    if contactGuid then
        _errnum_ = 0
        r = ScenEdit_AttackContact(atk.guid, contactGuid, {
            mode = "1", weapon = wpnDbid, qty = qty,
        })
        print(LOG_PREFIX .. " [INFO] " .. attackerName
            .. " -> CONTACT 攻击 " .. targetName .. " contact=" .. contactGuid)
    elseif _ALLOW_BOL_FALLBACK then
        _errnum_ = 0
        r = ScenEdit_AttackContact(atk.guid, tgt.guid, {
            mode = "1", weapon = wpnDbid, qty = qty,
            latitude  = tgt.latitude,
            longitude = tgt.longitude,
        })
        print(LOG_PREFIX .. " [INFO] " .. attackerName .. " -> BOL 攻击 " .. targetName)
    else
        print(LOG_PREFIX .. " [ERROR] " .. attackerName
            .. " 无 contact 且禁用 BOL，取消发射")
        return false
    end

    if r then
        print(LOG_PREFIX .. " [SUCCESS] " .. attackerName .. " 发射 " .. qty
            .. "x [YJ-18 dbid=" .. wpnDbid .. "] -> " .. targetName)
        return true
    else
        print(LOG_PREFIX .. " [ERROR] " .. attackerName .. " 攻击 " .. targetName
            .. " 失败: " .. tostring(_errmsg_))
        return false
    end
end

-- ---------- 时间换算：仿真秒 → .NET Ticks ----------
local function totTicks(addSeconds)
    local t = ScenEdit_CurrentTime()
    local offSet = 62135596801
    return string.format("%.0f", (t + offSet + addSeconds) * 1e7)
end

-- ---------- 单枚调度 ----------
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
        ok(("调度 %s -> %s | 真实触发 +%ds | %s"):format(
            atkName, tgtName, delay, tag))
        return true
    else
        err(("调度失败 %s -> %s @+%ds (errmsg=%s)"):format(
            atkName, tgtName, delay, tostring(_errmsg_)))
        return false
    end
end

-- ---------- 齐射调度 ----------
function scheduleSalvo()
    info("调度逐枚定时发射（TOT）...")
    local nowT = ScenEdit_CurrentTime()
    info("仿真基准时间 = " .. tostring(nowT))

    local sched, failc = 0, 0
    for i, s in ipairs(CFG) do
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
    ok(("TOT 调度完成：成功 %d 枚，失败 %d 枚"):format(sched, failc))
end

-- ---------- 入口 ----------
print("")
print("========================================")
print("       南海 4V4 真延时打击 (TOT)")
print("       contact_settle_delay = 15 秒")
print("========================================")
print("")

scheduleSalvo()

print("")
print("齐射时序（含 15s contact 稳定期）：")
print("  055-1  -> DDG-113-1  13 枚 首发 +15s (0+15)   末枚 +27s")
print("  055-2  -> DDG-113-2  13 枚 首发 +15s (0+15)   末枚 +27s")
print("  052D-1 -> CVN-70      8 枚 首发 +25s (10+15)  末枚 +32s")
print("  052D-2 -> CG-59       5 枚 首发 +35s (20+15)  末枚 +39s")
print("")
print("说明：必须【推进游戏时间】，Time 触发器才会触发；暂停不发射。")
print("")
ok("attack.lua 执行完毕")