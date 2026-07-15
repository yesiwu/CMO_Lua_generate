-- ============================================================
-- attack.lua — 055 发射 YJ-18 打击 CVN-70
-- ============================================================

Tool_EmulateNoConsole(true)

local LOG = "[CMO]"
local DBID_YJ18 = 2868

-- ============================================================
-- 配置
-- ============================================================
local CFG_SIDE_RED   = "红方"
local CFG_SIDE_BLUE = "蓝方"
local STRIKE = {
    {"055-Nanchang", "CVN-70", DBID_YJ18, 13},  -- 发射 13 枚 YJ-18
}

-- ============================================================
-- 工具函数
-- ============================================================
local function forceBlueAutodetectable(name)
    local ok, u = pcall(ScenEdit_GetUnit, {side = CFG_SIDE_BLUE, name = name})
    if not (ok and u and u.guid) then return false end
    return pcall(ScenEdit_SetUnit, {guid = u.guid, autodetectable = true})
end

local function collectContacts(sideName)
    local out, seen = {}, {}
    -- 尝试多种参数格式
    local calls = {
        {ScenEdit_GetContacts, {side = sideName}},
        {ScenEdit_GetContacts, {Side = sideName}},
        {ScenEdit_GetContacts, sideName},
    }
    for _, call in ipairs(calls) do
        local fn, arg = call[1], call[2]
        local ok, r = pcall(fn, arg)
        if ok and type(r) == "table" then
            for _, c in ipairs(r) do
                local cg = c.guid or c.Guid
                if cg and not seen[cg] then
                    seen[cg] = true
                    out[#out + 1] = c
                end
            end
        end
    end
    return out
end

local function findContactGuid(sideName, tgtGuid, tgtName)
    if not tgtGuid then return nil end
    local cs = collectContacts(sideName)
    for _, c in ipairs(cs) do
        local actualId = c.actualunitid or c.actualUnitID or c.actualunitguid or c.actualUnitGuid
        if actualId and tostring(actualId):lower() == tostring(tgtGuid):lower() then
            print(LOG .. " [INFO] matched contact for " .. tgtName .. ": " .. tostring(c.guid))
            return c.guid
        end
    end
    return nil
end

-- ============================================================
-- 执行打击
-- ============================================================
local function fireAt(attackerName, targetName, wpnDbid, qty)
    -- 获取攻击方
    local okAtk, atk = pcall(ScenEdit_GetUnit, {side = CFG_SIDE_RED, name = attackerName})
    if not (okAtk and atk and atk.guid) then
        print(LOG .. " [ERROR] 找不到攻击方: " .. attackerName)
        return false
    end
    
    -- 获取目标
    local okTgt, tgt = pcall(ScenEdit_GetUnit, {side = CFG_SIDE_BLUE, name = targetName})
    if not (okTgt and tgt and tgt.guid) then
        print(LOG .. " [ERROR] 找不到目标: " .. targetName)
        return false
    end
    
    -- 强制设置蓝方 autodetectable
    forceBlueAutodetectable(targetName)
    
    -- 强制红方 OMNI
    pcall(ScenEdit_SetSideOptions, {side = CFG_SIDE_RED, awareness = "OMNI"})
    
    -- 查找 contact
    local contactGuid = findContactGuid(CFG_SIDE_RED, tgt.guid, targetName)
    
    -- 执行攻击
    local okAttack, result
    if contactGuid then
        print(LOG .. " [攻击] " .. attackerName .. " → " .. targetName .. " (via contact)")
        okAttack, result = pcall(ScenEdit_AttackContact, atk.guid, contactGuid, {mode = 1, weapon = wpnDbid, qty = qty})
    else
        -- 降级到 BOL (朝坐标发射)
        print(LOG .. " [攻击] " .. attackerName .. " → " .. targetName .. " (via BOL)")
        okAttack, result = pcall(ScenEdit_AttackContact, atk.guid, "BOL", {
            latitude = tgt.latitude,
            longitude = tgt.longitude,
            mode = 1,
            weapon = wpnDbid,
            qty = qty
        })
    end
    
    if okAttack then
        print(LOG .. " [OK] " .. attackerName .. " 发射 " .. qty .. "x YJ-18 → " .. targetName)
        return true
    else
        print(LOG .. " [ERROR] 攻击失败: " .. tostring(result))
        return false
    end
end

-- ============================================================
-- 主执行
-- ============================================================
print(LOG .. " === 下达打击指令 ===")

-- 先确保设置
forceBlueAutodetectable("CVN-70")
pcall(ScenEdit_SetSideOptions, {side = CFG_SIDE_RED, awareness = "OMNI"})

-- 执行打击
local success, failed = 0, 0
for _, s in ipairs(STRIKE) do
    if fireAt(s[1], s[2], s[3], s[4]) then
        success = success + 1
    else
        failed = failed + 1
    end
end

print(LOG .. " === 打击指令下达完毕 ===")
print(LOG .. " 成功: " .. success .. " | 失败: " .. failed)

-- 显示目标状态
local okTgt, tgt = pcall(ScenEdit_GetUnit, {side = CFG_SIDE_BLUE, name = "CVN-70"})
if okTgt and tgt then
    print(LOG .. " CVN-70 位置: " .. string.format("%.4f", tgt.latitude) .. ", " .. string.format("%.4f", tgt.longitude))
end
