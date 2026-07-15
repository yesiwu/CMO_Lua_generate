-- ============================================================
-- attack.lua — 真延时 TOT 齐射（事件驱动，逐枚 qty=1）
-- 数据来自 manifest.lua 的 STRIKE
-- 红方全知（OMNI）+ 蓝方 autodetectable=true + contact_settle_delay=15s
-- 严禁 for 同步循环 + qty=N（红线 #9）
-- 必须 ScenEdit_SetTrigger (Time) + LuaScript Action，每枚独立触发器
-- fireAt 必须全局函数（红线 #15）
-- ============================================================

dofile("manifest.lua")

-- ============================================================
-- 全局变量（红线 #15：事件沙箱无法访问 upvalue，必须全局）
-- ============================================================
_SIDE_RED             = "红方"
_SIDE_BLUE            = "蓝方"
_WPN_YJ18             = 2868
_CONTACT_SETTLE_DELAY = 15
_LOG_PREFIX           = "[CMO]"

-- ============================================================
-- §1 工具函数（fireAt 必须为全局）
-- ============================================================

local function sameGuid(a, b)
    return a and b and tostring(a):lower() == tostring(b):lower()
end

local function info(msg)  print(_LOG_PREFIX .. " [INFO] "  .. msg) end
local function warn(msg)  print(_LOG_PREFIX .. " [WARN] "  .. msg) end
local function ok(msg)    print(_LOG_PREFIX .. " [OK] "    .. msg) end
local function err(msg)   print(_LOG_PREFIX .. " [ERROR] " .. msg) end

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
    if type(t) ~= "table" or depth > 5 then return end
    addContact(dst, seen, t)
    for _, v in pairs(t) do
        if type(v) == "table" then
            collectContactsFromTable(dst, seen, v, depth + 1)
        end
    end
end

local function collectContacts(sideName)
    local out, seen = {}, {}
    local ok2, r = pcall(ScenEdit_GetContacts, { side = sideName })
    if ok2 and type(r) == "table" then
        collectContactsFromTable(out, seen, r, 0)
    end
    local ok3, s = pcall(VP_GetSide, { Side = sideName })
    if ok3 and s and type(s.contacts) == "table" then
        collectContactsFromTable(out, seen, s.contacts, 0)
    end
    info(sideName .. " contact count = " .. tostring(#out))
    return out
end

local function contactName(c)
    return tostring(c.name or c.Name or c.actualunitname or c.actualUnitName or "")
end

local function findContactForTarget(sideName, tgt, tgtName)
    if not (tgt and tgt.guid) then return nil end
    pcall(ScenEdit_SetSideOptions, { side = sideName, awareness = "OMNI" })
    local cs = collectContacts(sideName)

    for _, c in ipairs(cs) do
        local cg = c.guid or c.Guid
        if cg and (
            sameGuid(c.actualunitid, tgt.guid)
            or sameGuid(c.actualUnitID, tgt.guid)
            or sameGuid(c.actualunitguid, tgt.guid)
            or sameGuid(c.actualUnitGuid, tgt.guid)
            or sameGuid(c.actualunit, tgt.guid)
            or sameGuid(c.actualUnit, tgt.guid)
            or sameGuid(c.actual_guid, tgt.guid)
            or sameGuid(c.actualGuid, tgt.guid)
        ) then return cg end
    end

    for _, c in ipairs(cs) do
        local cg = c.guid or c.Guid
        local nm = contactName(c)
        if cg and tgtName and (nm == tgtName or nm:find(tgtName, 1, true)) then
            warn("Matched contact by name: " .. tgtName)
            return cg
        end
    end

    return nil
end

-- ============================================================
-- §2 全局打击函数 fireAt（红线 #15：不带 local）
-- ============================================================
function fireAt(attackerName, targetName, wpnDbid, qty)
    local ok2, atk = pcall(ScenEdit_GetUnit, { side = _SIDE_RED, name = attackerName })
    local ok3, tgt = pcall(ScenEdit_GetUnit, { side = _SIDE_BLUE, name = targetName })

    if not ok2 or not atk or not atk.guid then
        err("找不到攻击方 " .. attackerName); return false end
    if not ok3 or not tgt or not tgt.guid then
        err("找不到目标 " .. targetName); return false end

    pcall(ScenEdit_SetUnit, { guid = tgt.guid, autodetectable = true })

    local contactGuid
    for attempt = 1, 3 do
        contactGuid = findContactForTarget(_SIDE_RED, tgt, targetName)
        if contactGuid then
            info(("Attempt %d/3: contact = %s"):format(attempt, tostring(contactGuid)))
            break
        end
        if attempt < 3 then
            warn(("Attempt %d/3: 无 contact，2 秒后重试..."):format(attempt))
        end
    end

    local r
    if contactGuid then
        _errnum_ = 0
        r = ScenEdit_AttackContact(atk.guid, contactGuid, {
            mode   = "1",          -- ★ 字符串 "1"
            weapon = wpnDbid,
            qty    = qty,
        })
        info(("%s -> CONTACT 攻击 %s contact=%s"):format(attackerName, targetName, tostring(contactGuid)))
    else
        _errnum_ = 0
        r = ScenEdit_AttackContact(atk.guid, tgt.guid, {
            mode   = "1",
            weapon = wpnDbid,
            qty    = qty,
        })
        warn(("%s -> UNIT-GUID 攻击 %s (无 contact，OMNI 降级)"):format(attackerName, targetName))
    end

    if r then
        ok(("%s 发射 %d × [%d] -> %s"):format(attackerName, qty, wpnDbid, targetName))
        return true
    else
        err(("%s 攻击 %s 失败 err=%s"):format(attackerName, targetName, tostring(_errmsg_)))
        return false
    end
end

-- ============================================================
-- §3 真延时调度：TOT 逐枚 qty=1
-- ============================================================

-- 仿真时间 -> .NET Ticks（红线 #11）
local function totTicks(addSeconds)
    local t = ScenEdit_CurrentTime()
    local offSet = 62135596801
    return string.format("%.0f", (t + offSet + addSeconds) * 1e7)
end

-- 注册单枚弹的触发器
local function scheduleOne(atkName, tgtName, wpn, delay, tag)
    -- ★ contact_settle_delay 叠加到每枚弹（用户要求 ≥15秒）
    delay = delay + _CONTACT_SETTLE_DELAY

    -- ★ tag 带时间戳（幂等性，避免重跑时 Event 已存在）
    local stamp = tostring(ScenEdit_CurrentTime())
    tag = tag .. "_" .. stamp

    local evName = "Event " .. tag
    local trName = "Trig "  .. tag
    local acName = "Act "   .. tag
    local fireTime = totTicks(delay)

    -- 事件脚本必须自含（沙箱执行）
    local script =
        ("fireAt(%q,%q,%d,1)\n"):format(atkName, tgtName, wpn) ..
        ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(evName) ..
        ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(acName) ..
        ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(trName)

    pcall(ScenEdit_SetTrigger, { mode="add", type="Time", name=trName, Time=fireTime })
    pcall(ScenEdit_SetAction,  { mode="add", type="LuaScript", name=acName, ScriptText=script })
    pcall(ScenEdit_SetEvent,   evName, { mode="add", IsActive=true, IsRepeatable=false })
    pcall(ScenEdit_SetEventTrigger, evName, { mode="add", name=trName })
    pcall(ScenEdit_SetEventAction,  evName, { mode="add", name=acName })

    return true
end

-- ============================================================
-- §4 入口：调度所有 STRIKE
-- ============================================================
info("=== 真延时 TOT 调度开始 ===")

local totalRounds = 0
local totalMissiles = 0
for i, s in ipairs(STRIKE) do
    local atkName   = s.attacker
    local tgtName   = s.target
    local wpn       = s.weapon_dbid
    local qty       = s.quantity or 1
    local startDelay= s.startDelay or 0
    local interval  = s.interval or 1
    local intent    = s.intent or ""

    -- 武器必须为 YJ-18
    if wpn ~= _WPN_YJ18 then
        warn(("STRIKE[%d] 武器 dbid=%d 不是 YJ-18/2868，跳过: %s"):format(
            i, wpn, intent))
        goto continue
    end

    local ok2 = pcall(ScenEdit_GetUnit, { side = _SIDE_RED, name = atkName })
    local ok3 = pcall(ScenEdit_GetUnit, { side = _SIDE_BLUE, name = tgtName })
    if not ok2 or not ok3 then
        warn(("STRIKE[%d] 单位不存在: attacker=%s target=%s, 跳过"):format(i, atkName, tgtName))
        goto continue
    end

    info(("调度 STRIKE[%d] %s -> %s × %d (startDelay=%ds interval=%ds intent=%s)"):format(
        i, atkName, tgtName, qty, startDelay, interval, intent))

    for k = 1, qty do
        local delay = startDelay + (k - 1) * interval
        local tag = ("TOT_%d_%d_%s"):format(i, k, intent:gsub("%s+", "_"):sub(1, 30))
        scheduleOne(atkName, tgtName, wpn, delay, tag)
        totalMissiles = totalMissiles + 1
    end
    totalRounds = totalRounds + 1

    ::continue::
end

ok(("%d 个打击任务，%d 枚 YJ-18 已调度（+ %d 秒 contact 稳定期）"):format(
    totalRounds, totalMissiles, _CONTACT_SETTLE_DELAY))
print(_LOG_PREFIX .. " === attack.lua 完成 ===")
print(_LOG_PREFIX .. " 提示：在 CMO 仿真时间推进到 T+0 时自动开火，无需手动操作")