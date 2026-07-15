-- ==========================================================================
-- attack.lua — STEP 4/4 — 消耗与诱歼作战方案 (真延时打击, TOT 事件驱动)
--   对 manifest.STRIKE 中每条记录:
--     1) 计算每个独立导弹的事件触发时间 (startDelay + (k-1) * interval + contact_settle_delay)
--     2) 创建 Time Trigger
--     3) 创建 LuaScript Action: fireAt(attacker, target, wpn, qty=1) 后清除触发器
--     4) 把 Trigger + Action 关联到 Event
--   真延时要求: qty=N 必须拆成 N 个独立 Trigger,每个 fireAt 调用 qty=1
-- ==========================================================================

print("[CMO] [INFO] ============ attack.lua 开始 (TOT 事件驱动) ============")

dofile("manifest.lua")

-- ==========================================================================
-- 工具
-- ==========================================================================
local LOG_PREFIX = "[CMO]"
local function log(level, msg) print(LOG_PREFIX .. " [" .. level .. "] " .. tostring(msg)) end
local function info(msg)  log("INFO",    msg) end
local function warn(msg)  log("WARNING", msg) end
local function err(msg)   log("ERROR",   msg) end
local function ok(msg)    log("SUCCESS", msg) end

-- 全局变量 (fireAt 沙箱需要, 不能 upvalue)
_SIDE_RED             = CFG_SCENARIO.side_red
_SIDE_BLUE            = CFG_SCENARIO.side_blue
_BLUE_AUTODETECTABLE  = CFG_SCENARIO.blue_autodetectable
_CONTACT_SETTLE_DELAY = tonumber(CFG_SCENARIO.contact_settle_delay) or 15
_ALLOW_BOL_FALLBACK   = false
_CONTACT_CACHE        = {}

-- ==========================================================================
-- GUID 比较 / Contact 收集
-- ==========================================================================
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
    -- 多种 API 调用形式尝试
    local calls = {
        function() return ScenEdit_GetContacts({ side = sideName }) end,
        function() return ScenEdit_GetContacts({ Side = sideName }) end,
        function() return ScenEdit_GetContacts(sideName) end,
    }
    for _, fn in ipairs(calls) do
        local r2, r = pcall(fn)
        if r2 and type(r) == "table" then
            collectContactsFromTable(out, seen, r, 0)
        end
    end
    -- 加上 VP_GetSide().contacts
    local r2, s = pcall(VP_GetSide, { Side = sideName })
    if r2 and s and type(s.contacts) == "table" then
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

    -- 强制确保红方 OMNI (重复保险)
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

    -- Fallback: 按名字
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

-- ==========================================================================
-- fireAt (全局函数, 不能 local)
-- ==========================================================================
function fireAt(attackerName, targetName, wpnDbid, qty)
    local atk = ScenEdit_GetUnit({side = _SIDE_RED,  name = attackerName})
    local tgt = ScenEdit_GetUnit({side = _SIDE_BLUE, name = targetName})

    if not (atk and atk.guid) then
        err("找不到攻击方 " .. attackerName); return false end
    if not (tgt and tgt.guid) then
        err("找不到目标 " .. targetName); return false end

    if _BLUE_AUTODETECTABLE then
        pcall(ScenEdit_SetUnit, {guid = tgt.guid, autodetectable = true})
    end

    local contactGuid
    for attempt = 1, 3 do
        contactGuid = findContactForTarget(tgt, targetName)
        if contactGuid then
            info("Attempt " .. attempt .. "/3: 找到 contact " .. contactGuid)
            break
        end
        if attempt < 3 then
            warn("Attempt " .. attempt .. "/3: 无 contact, 2s 重试...")
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
        info(attackerName .. " -> CONTACT 攻击 " .. targetName)
    elseif _ALLOW_BOL_FALLBACK then
        _errnum_ = 0
        r = ScenEdit_AttackContact(atk.guid, tgt.guid, {
            mode = "1", weapon = wpnDbid, qty = qty,
            latitude = tgt.latitude, longitude = tgt.longitude,
        })
    else
        err(attackerName .. " 无 contact, 取消发射")
        return false
    end

    if r then
        ok(attackerName .. " 发射 " .. qty .. "x [wpn=" .. wpnDbid .. "] -> " .. targetName)
        return true
    else
        err(attackerName .. " 失败: " .. tostring(_errmsg_))
        return false
    end
end

-- ==========================================================================
-- TOT 时间戳换算 (CMO 用 .NET ticks: 100ns since 0001-01-01)
-- ==========================================================================
local function totTicks(addSeconds)
    local t = ScenEdit_CurrentTime()
    return string.format("%.0f", (t + 62135596801) * 1e7)
end

-- ==========================================================================
-- scheduleOne: 调度 1 枚弹的事件触发
--   delay 已包含 _CONTACT_SETTLE_DELAY (脚本头部)
-- ==========================================================================
local function scheduleOne(atkName, tgtName, wpn, delay, tag)
    delay = delay + _CONTACT_SETTLE_DELAY

    local evName = "Event " .. tag
    local trName = "Trig "  .. tag
    local acName = "Act "   .. tag
    local fireTime = totTicks(delay)

    -- Lua 脚本: 调用全局 fireAt(...,qty=1) 后清除自己
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

-- ==========================================================================
-- 主调度循环: STRIKE 中每条 -> 拆 qty 个独立触发器
-- ==========================================================================
print()
print("[CMO] ---------- 调度 " .. #STRIKE .. " 条 STRIKE ----------")

local total_sched, total_fail = 0, 0
local total_missiles = 0

for i, s in ipairs(STRIKE) do
    print()
    info(("STRIKE[%d] %s -> %s | wpn=%d | qty=%d | delay=%ds | interval=%ds")
        :format(i, s.attacker, s.target, s.wpn_dbid, s.qty, s.startDelay, s.interval))

    for k = 1, s.qty do
        local delay = s.startDelay + (k - 1) * s.interval
        local tag = ("TOT_%d_%d_%s"):format(i, k, s.tag or "?")
        if scheduleOne(s.attacker, s.target, s.wpn_dbid, delay, tag) then
            total_sched = total_sched + 1
            total_missiles = total_missiles + 1
        else
            total_fail = total_fail + 1
        end
    end
end

print()
print("=" .. string.rep("=", 60))
print("齐射时序汇总 (含 15s contact 稳定期):")
for i, s in ipairs(STRIKE) do
    local first = s.startDelay + _CONTACT_SETTLE_DELAY
    local last  = s.startDelay + (s.qty - 1) * s.interval + _CONTACT_SETTLE_DELAY
    print(string.format("  [%d] %-10s -> %-12s  %d 枚  首发 +%ds  末枚 +%ds",
        i, s.attacker, s.target or "?", s.qty, first, last))
end
print()

if total_fail == 0 then
    ok(("STRIKE 调度完成: %d/%d 触发器成功 | %d 枚导弹")
        :format(total_sched, total_sched + total_fail, total_missiles))
else
    warn(("STRIKE 部分失败: %d 成功, %d 失败"):format(total_sched, total_fail))
end

print()
print("[CMO] ============ attack.lua 完成 ============")
print("[CMO] [INFO] 必须在 CMO 中推进游戏时间才会触发 (暂停不发射)")
print(string.format("[CMO] [INFO] 最早发射: T+%ds, 最晚发射: T+%ds",
    STRIKE[1].startDelay + _CONTACT_SETTLE_DELAY,
    STRIKE[#STRIKE].startDelay + (STRIKE[#STRIKE].qty - 1) * STRIKE[#STRIKE].interval + _CONTACT_SETTLE_DELAY))