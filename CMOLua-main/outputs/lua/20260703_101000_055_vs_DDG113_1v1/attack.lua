-- ============================================================
-- attack.lua: 055发射13枚YJ-18攻击DDG-113
-- 修复版：深度遍历contact，使用字符串mode
-- ============================================================

local CFG_SIDE_RED  = "红方"
local CFG_SIDE_BLUE = "蓝方"
local CFG_BLUE_AUTODETECTABLE = true
local CFG_ALLOW_UNIT_GUID     = true   -- OMNI模式下允许直接用单位GUID攻击

-- 打击清单（单位名必须与 main.lua 创建时完全一致）
local STRIKE = {
    -- { 攻击方, 目标, 武器DBID, 数量 }
    { "055-Nanchang", "DDG-113", 2868, 13 },
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
    local u = ScenEdit_GetUnit({side = CFG_SIDE_BLUE, name = name})
    if not (u and u.guid) then return false end
    return pcall(ScenEdit_SetUnit, {guid = u.guid, autodetectable = true})
end

-- 深度遍历contact（关键修复）
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

    info(sideName .. " contact count = " .. tostring(#out))
    return out
end

local function contactName(c)
    return tostring(c.name or c.Name or c.actualunitname or c.actualUnitName or "")
end

local function findContactForTarget(sideName, tgt, tgtName)
    if not (tgt and tgt.guid) then return nil end

    -- 刷新 OMNI
    pcall(ScenEdit_SetSideOptions, { side = sideName, awareness = "OMNI" })

    local contacts = collectContacts(sideName)

    -- 通过 actual unit GUID 匹配
    for _, c in ipairs(contacts) do
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
        ) then
            info("Matched contact by actual unit GUID: " .. tgtName .. " contact=" .. cg)
            return cg
        end
    end

    -- Fallback: 通过名称匹配
    for _, c in ipairs(contacts) do
        local cg = c.guid or c.Guid
        local nm = contactName(c)
        if cg and tgtName and (nm == tgtName or nm:find(tgtName, 1, true)) then
            warn("Matched contact by name: " .. tgtName .. " contact=" .. cg)
            return cg
        end
    end

    return nil
end

-- ---------- 全局打击函数 ----------
function fireAt(attackerName, targetName, wpnDbid, qty)
    local atk = ScenEdit_GetUnit({side = CFG_SIDE_RED, name = attackerName})
    local tgt = ScenEdit_GetUnit({side = CFG_SIDE_BLUE, name = targetName})

    if not (atk and atk.guid) then
        print(LOG_PREFIX .. " [ERROR] 找不到攻击方 " .. attackerName); return false end
    if not (tgt and tgt.guid) then
        print(LOG_PREFIX .. " [ERROR] 找不到目标 " .. targetName); return false end

    -- 每次发射前强制设 autodetectable
    if CFG_BLUE_AUTODETECTABLE then
        pcall(ScenEdit_SetUnit, {guid = tgt.guid, autodetectable = true})
    end

    local contactGuid = findContactForTarget(CFG_SIDE_RED, tgt, targetName)

    local r
    if contactGuid then
        -- 方法1：通过 contact GUID 攻击（使用字符串 mode="1"）
        _errnum_ = 0
        r = ScenEdit_AttackContact(atk.guid, contactGuid, {
            mode = "1",
            weapon = wpnDbid,
            qty = qty,
        })
        print(LOG_PREFIX .. " [INFO] " .. attackerName .. " -> CONTACT 攻击 " .. targetName .. " contact=" .. contactGuid)
    elseif CFG_ALLOW_UNIT_GUID then
        -- 方法2：直接使用单位 GUID 攻击（OMNI 模式下可用）
        print(LOG_PREFIX .. " [WARNING] 未找到 contact，尝试直接使用单位 GUID 攻击...")
        _errnum_ = 0
        r = ScenEdit_AttackContact(atk.guid, tgt.guid, {
            mode = "1",
            weapon = wpnDbid,
            qty = qty,
        })
        print(LOG_PREFIX .. " [INFO] " .. attackerName .. " -> UNIT-GUID 攻击 " .. targetName)
    else
        print(LOG_PREFIX .. " [ERROR] " .. attackerName
            .. " 无 contact 且禁用 UNIT_GUID，取消发射: " .. targetName)
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

-- ---------- 执行打击 ----------
print("")
print("========================================")
print("       055 vs DDG-113 打击开始")
print("========================================")
print("")

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
print(LOG_PREFIX .. " 剩余弹药可在 reload 后继续使用")
print("")
ok("attack.lua 执行完毕")
