-- ============================================================
-- attack.lua — 红方 055 发射 13 枚 YJ-18 打击蓝方 CVN-70
-- 地点: 南海
--
-- 使用方式: main.lua + reload.lua 执行后，在 CMO Lua 控制台执行本脚本
-- ============================================================

Tool_EmulateNoConsole(true)

-- ============================================================
-- 配置区
-- ============================================================
local CFG_SIDE_RED  = "红方"
local CFG_SIDE_BLUE = "蓝方"
local CFG_BLUE_AUTODETECTABLE = true   -- 必须为 true，红方才能稳定获得 contact
local CFG_ALLOW_BOL_FALLBACK   = false  -- 对移动舰艇建议 false

-- 打击清单: {攻击方单位名, 目标单位名, 武器DBID, 数量}
local STRIKE = {
    {"055-Nanchang", "CVN-70", 2868, 13},  -- 发射 13 枚 YJ-18
}

-- ============================================================
-- 日志工具
-- ============================================================
local LOG = "[CMO]"

-- ============================================================
-- 强制设 Blue autodetectable
-- ============================================================
local function forceBlueAutodetectable(name)
    local u = ScenEdit_GetUnit({side = CFG_SIDE_BLUE, name = name})
    if not (u and u.guid) then return false end
    return pcall(ScenEdit_SetUnit, {guid = u.guid, autodetectable = true})
end

-- ============================================================
-- 收集 contact 列表（兼容多种调用方式）
-- ============================================================
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

-- ============================================================
-- 查找目标对应的 contact
-- ============================================================
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

-- ============================================================
-- 执行打击
-- ============================================================
local function fireAt(attackerName, targetName, wpnDbid, qty)
    local atk = ScenEdit_GetUnit({side = CFG_SIDE_RED, name = attackerName})
    local tgt = ScenEdit_GetUnit({side = CFG_SIDE_BLUE, name = targetName})

    if not (atk and atk.guid) then
        print(LOG .. " [ERROR] 找不到攻击方 " .. attackerName); return false end
    if not (tgt and tgt.guid) then
        print(LOG .. " [ERROR] 找不到目标 " .. targetName); return false end

    -- 关键: 每次发射前强制设 autodetectable
    if CFG_BLUE_AUTODETECTABLE then
        pcall(ScenEdit_SetUnit, {guid = tgt.guid, autodetectable = true})
    end

    -- 再次确保红方全知
    pcall(ScenEdit_SetSideOptions, {side = CFG_SIDE_RED, awareness = "OMNI"})

    local contactGuid = findContactForTarget(CFG_SIDE_RED, tgt, targetName)

    _errnum_ = 0
    local r
    if contactGuid then
        r = ScenEdit_AttackContact(atk.guid, contactGuid,
                {mode = 1, weapon = wpnDbid, qty = qty})
        print(LOG .. " [INFO] " .. attackerName .. " → contact 攻击 " .. targetName)
    else
        if CFG_ALLOW_BOL_FALLBACK then
            print(LOG .. " [WARNING] " .. attackerName
                .. " 无 contact，降级 BOL 朝坐标发射")
            r = ScenEdit_AttackContact(atk.guid, "BOL", {
                    latitude = tgt.latitude, longitude = tgt.longitude,
                    mode = 1, weapon = wpnDbid, qty = qty,
                })
        else
            print(LOG .. " [ERROR] " .. attackerName
                .. " 无 contact 且 BOL 已禁用，取消发射: " .. targetName)
            return false
        end
    end

    if r and (_errnum_ or 0) == 0 then
        print(LOG .. " [OK] " .. attackerName .. " 发射 " .. qty
            .. "x [YJ-18 DBID=" .. wpnDbid .. "] → " .. targetName)
        return true
    else
        print(LOG .. " [ERROR] " .. attackerName .. " 攻击 " .. targetName
            .. " 失败: " .. tostring(_errmsg_))
        return false
    end
end

-- ============================================================
-- 主执行
-- ============================================================
print(LOG .. " === 下达打击指令 ===")
local success = 0
local failed = 0
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
local tgt = ScenEdit_GetUnit({side = CFG_SIDE_BLUE, name = "CVN-70"})
if tgt then
    print(LOG .. " CVN-70 位置: " .. string.format("%.4f", tgt.latitude) .. ", " .. string.format("%.4f", tgt.longitude))
    print(LOG .. " CVN-70 航向: " .. tgt.heading .. "°  航速: " .. tgt.speed .. " 节")
end
