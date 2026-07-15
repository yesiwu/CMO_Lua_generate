-- ============================================================
-- 打击脚本：055发射13枚YJ-18攻击DDG-113
-- ============================================================

local LOG_PREFIX = "[CMO]"
local function log(level, msg) print(LOG_PREFIX .. " [" .. level .. "] " .. msg) end
local function info(msg) log("INFO",    msg) end
local function warn(msg) log("WARNING", msg) end
local function err(msg)  log("ERROR",   msg) end
local function ok(msg)   log("SUCCESS", msg) end

-- ---------- 配置区 ----------
local CFG_SIDE_RED  = "红方"
local CFG_SIDE_BLUE = "蓝方"
local CFG_BLUE_AUTODETECTABLE = true   -- 必须为true，红方才能稳定获得contact
local CFG_ALLOW_UNIT_GUID     = true   -- 允许直接使用单位GUID攻击

-- 打击清单：攻击方, 目标, 武器DBID, 数量
local STRIKE = {
    { "055-南昌舰", "DDG-113", 2868, 13 },  -- 发射13枚YJ-18攻击DDG-113
}

-- ---------- 工具函数 ----------
local function forceBlueAutodetectable(name)
    local u = ScenEdit_GetUnit({side = CFG_SIDE_BLUE, name = name})
    if not (u and u.guid) then return false end
    return pcall(ScenEdit_SetUnit, {guid = u.guid, autodetectable = true})
end

local function dumpContacts(sideName)
    info("=== 调试：检查红方contacts ===")
    -- 方法1：ScenEdit_GetContacts
    local methods = {
        {name = "ScenEdit_GetContacts({side=...})", fn = function() return ScenEdit_GetContacts({side = sideName}) end},
        {name = "ScenEdit_GetContacts({Side=...})", fn = function() return ScenEdit_GetContacts({Side = sideName}) end},
        {name = "VP_GetSide().contacts", fn = function()
            local s = VP_GetSide({Side = sideName})
            return s and s.contacts
        end},
    }
    for _, m in ipairs(methods) do
        local ok2, r = pcall(m.fn)
        if ok2 and r and type(r) == "table" then
            info(m.name .. " -> " .. #r .. " contacts")
            for i, c in ipairs(r) do
                info("  [" .. i .. "] guid=" .. tostring(c.guid or c.Guid) 
                    .. " name=" .. tostring(c.name or c.Name)
                    .. " actualunitid=" .. tostring(c.actualunitid or c.actualUnitID))
            end
        else
            warn(m.name .. " -> " .. tostring(ok2 and "nil/empty" or tostring(r)))
        end
    end
end

local function collectContacts(sideName)
    local out, seen = {}, {}
    -- 尝试多种方式收集contacts
    local calls = {
        function() return ScenEdit_GetContacts({side = sideName}) end,
        function() return ScenEdit_GetContacts({Side = sideName}) end,
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
    local ok2, s = pcall(VP_GetSide, {Side = sideName})
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

local function findContactForTarget(sideName, tgt, tgtName)
    if not (tgt and tgt.guid) then return nil end
    pcall(ScenEdit_SetSideOptions, {side = sideName, awareness = "OMNI"})
    local cs = collectContacts(sideName)
    for _, c in ipairs(cs) do
        local cg = c.guid or c.Guid
        if not cg then goto continue end
        local function sameGuid(a, b)
            return a and b and tostring(a):lower() == tostring(b):lower()
        end
        if sameGuid(c.actualunitid, tgt.guid)
            or sameGuid(c.actualUnitID, tgt.guid)
            or sameGuid(c.actualunitguid, tgt.guid)
            or sameGuid(c.actualUnitGuid, tgt.guid)
            or sameGuid(c.actualunit, tgt.guid)
            or sameGuid(c.actualUnit, tgt.guid) then
            print(LOG_PREFIX .. " [INFO] matched contact for " .. tgtName .. " by GUID: " .. cg)
            return cg
        end
        if (c.name or c.Name or "") == tgtName then
            print(LOG_PREFIX .. " [INFO] matched contact for " .. tgtName .. " by name: " .. cg)
            return cg
        end
        ::continue::
    end
    return nil
end

local function fireAt(attackerName, targetName, wpnDbid, qty)
    local atk = ScenEdit_GetUnit({side = CFG_SIDE_RED, name = attackerName})
    local tgt = ScenEdit_GetUnit({side = CFG_SIDE_BLUE, name = targetName})

    if not (atk and atk.guid) then
        print(LOG_PREFIX .. " [ERROR] 找不到攻击方 " .. attackerName); return false end
    if not (tgt and tgt.guid) then
        print(LOG_PREFIX .. " [ERROR] 找不到目标 " .. targetName); return false end

    info("攻击方: " .. attackerName .. " (guid=" .. atk.guid .. ")")
    info("目标: " .. targetName .. " (guid=" .. tgt.guid .. ")")

    -- 关键：每次发射前强制设autodetectable
    if CFG_BLUE_AUTODETECTABLE then
        pcall(ScenEdit_SetUnit, {guid = tgt.guid, autodetectable = true})
    end

    local contactGuid = findContactForTarget(CFG_SIDE_RED, tgt, targetName)

    _errnum_ = 0
    local r
    if contactGuid then
        -- 方法1：通过contact GUID攻击
        r = ScenEdit_AttackContact(atk.guid, contactGuid,
                {mode = 1, weapon = wpnDbid, qty = qty})
        print(LOG_PREFIX .. " [INFO] " .. attackerName .. " → contact 攻击 " .. targetName)
    elseif CFG_ALLOW_UNIT_GUID then
        -- 方法2：直接使用单位GUID攻击（OMNI模式下可用）
        print(LOG_PREFIX .. " [WARNING] 未找到contact，尝试直接使用单位GUID攻击...")
        r = ScenEdit_AttackContact(atk.guid, tgt.guid,
                {mode = 1, weapon = wpnDbid, qty = qty})
        print(LOG_PREFIX .. " [INFO] " .. attackerName .. " → unit-GUID 攻击 " .. targetName)
    else
        if CFG_ALLOW_UNIT_GUID then
            print(LOG_PREFIX .. " [ERROR] " .. attackerName
                .. " 无contact且禁用UNIT_GUID，取消发射: " .. targetName)
        else
            print(LOG_PREFIX .. " [ERROR] " .. attackerName
                .. " 无contact且UNIT_GUID已禁用，取消发射: " .. targetName)
        end
        return false
    end

    if r and (_errnum_ or 0) == 0 then
        print(LOG_PREFIX .. " [OK] " .. attackerName .. " 发射 " .. qty
            .. "x [YJ-18 dbid=" .. wpnDbid .. "] → " .. targetName)
        return true
    else
        print(LOG_PREFIX .. " [ERROR] " .. attackerName .. " 攻击 " .. targetName
            .. " 失败: " .. tostring(_errmsg_))
        return false
    end
end

-- ---------- 执行打击 ----------
print("")
print("========================================")
print("       055 vs DDG-113 打击开始")
print("========================================")
print("")

-- 调试：显示contact状态
dumpContacts(CFG_SIDE_RED)

print(LOG_PREFIX .. " === 下达打击指令 ===")
local success_count = 0
local fail_count = 0
for _, s in ipairs(STRIKE) do 
    if fireAt(s[1], s[2], s[3], s[4]) then
        success_count = success_count + 1
    else
        fail_count = fail_count + 1
    end
end
print(LOG_PREFIX .. " === 打击指令下达完毕 ===")
print("")
print("========================================")
print("打击结果: 成功=" .. success_count .. " 失败=" .. fail_count)
print("========================================")
