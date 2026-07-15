-- ============================================================
-- 打击脚本: 055发射13枚YJ-18攻击DDG-113
-- ============================================================

local CFG_SIDE_RED  = "红方"
local CFG_SIDE_BLUE = "蓝方"
local CFG_BLUE_AUTODETECTABLE = true   -- 必须为 true，红方才能获得 contact
local CFG_ALLOW_UNIT_GUID     = true   -- 允许直接使用单位GUID攻击（OMNI模式下可用）

local LOG = "[CMO]"

-- ---------- 配置区 ----------
local NAME_055  = "055-Nanchang"    -- 攻击方，必须与 main.lua 一致
local NAME_DDG  = "DDG-113-JohnFinn" -- 目标，必须与 main.lua 一致
local YJ18_DBID = 2868               -- YJ-18 DBID (用户指定)
local FIRE_QTY  = 13                 -- 发射13枚

-- 打击清单
local STRIKE = {
    { NAME_055, NAME_DDG, YJ18_DBID, FIRE_QTY },
}

-- ---------- 工具函数 ----------
local function forceBlueAutodetectable(name)
    local u = ScenEdit_GetUnit({side = CFG_SIDE_BLUE, name = name})
    if not (u and u.guid) then return false end
    return pcall(ScenEdit_SetUnit, {guid = u.guid, autodetectable = true})
end

local function collectContacts(sideName)
    local out, seen = {}, {}
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
            print(LOG .. " [INFO] matched contact for " .. tgtName .. " by GUID: " .. cg)
            return cg
        end
        if (c.name or c.Name or "") == tgtName then
            print(LOG .. " [INFO] matched contact for " .. tgtName .. " by name: " .. cg)
            return cg
        end
        ::continue::
    end
    return nil
end

-- ---------- 打击函数 ----------
local function fireAt(attackerName, targetName, wpnDbid, qty)
    local atk = ScenEdit_GetUnit({side = CFG_SIDE_RED, name = attackerName})
    local tgt = ScenEdit_GetUnit({side = CFG_SIDE_BLUE, name = targetName})

    if not (atk and atk.guid) then
        print(LOG .. " [ERROR] 找不到攻击方 " .. attackerName); return false end
    if not (tgt and tgt.guid) then
        print(LOG .. " [ERROR] 找不到目标 " .. targetName); return false end

    -- 关键：每次发射前强制设 autodetectable
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
        print(LOG .. " [INFO] " .. attackerName .. " → contact 攻击 " .. targetName)
    elseif CFG_ALLOW_UNIT_GUID then
        -- 方法2：直接使用单位GUID攻击（OMNI模式下可用）
        print(LOG .. " [WARNING] 未找到contact，尝试直接使用单位GUID攻击...")
        r = ScenEdit_AttackContact(atk.guid, tgt.guid,
                {mode = 1, weapon = wpnDbid, qty = qty})
        print(LOG .. " [INFO] " .. attackerName .. " → unit-GUID 攻击 " .. targetName)
    else
        print(LOG .. " [ERROR] " .. attackerName
            .. " 无contact且禁用UNIT_GUID，取消发射: " .. targetName)
        return false
    end

    if r and (_errnum_ or 0) == 0 then
        print(LOG .. " [OK] " .. attackerName .. " 发射 " .. qty
            .. "x [YJ-18 dbid=" .. wpnDbid .. "] → " .. targetName)
        return true
    else
        print(LOG .. " [ERROR] " .. attackerName .. " 攻击 " .. targetName
            .. " 失败: " .. tostring(_errmsg_))
        return false
    end
end

-- ---------- 执行打击 ----------
print(LOG .. " === 下达打击指令 ===")
local success_count = 0
local fail_count = 0
for _, s in ipairs(STRIKE) do
    if fireAt(s[1], s[2], s[3], s[4]) then
        success_count = success_count + 1
    else
        fail_count = fail_count + 1
    end
end
print(LOG .. " === 打击指令下达完毕 ===")
print(LOG .. " 成功=" .. success_count .. " 失败=" .. fail_count)
print(LOG .. " 剩余弹药可在 reload 后继续使用")
