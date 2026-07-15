-- ============================================================
-- 打击脚本：055发射12枚YJ-18攻击Burke
-- 场景：南海1v1，055 vs Burke
-- ============================================================

-- ---------- 日志工具 ----------
local LOG_PREFIX = "[CMO-ATTACK]"
local function log(level, msg) print(LOG_PREFIX .. " [" .. level .. "] " .. msg) end
local function info(msg) log("INFO", msg) end
local function warn(msg) log("WARNING", msg) end
local function err(msg) log("ERROR", msg) end
local function ok(msg) log("SUCCESS", msg) end

-- ---------- 配置区 ----------
local CFG_SIDE_RED = "红方"
local CFG_SIDE_BLUE = "蓝方"
local CFG_BLUE_AUTODETECTABLE = true   -- 必须为 true
local CFG_ALLOW_BOL_FALLBACK = false   -- 对移动舰艇建议 false

local STRIKE = {
    -- { 攻击方单位名, 目标单位名, 武器DBID, 数量 }
    { "055-Nanchang", "DDG-51-Burke", 2867, 12 },  -- 12枚YJ-18
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
            info("matched contact for " .. tgtName .. " by GUID: " .. cg)
            return cg
        end
        if (c.name or c.Name or "") == tgtName then
            info("matched contact for " .. tgtName .. " by name: " .. cg)
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
        err("找不到攻击方 " .. attackerName); return false end
    if not (tgt and tgt.guid) then
        err("找不到目标 " .. targetName); return false end

    -- 关键：每次发射前强制设 autodetectable
    if CFG_BLUE_AUTODETECTABLE then
        pcall(ScenEdit_SetUnit, {guid = tgt.guid, autodetectable = true})
    end

    local contactGuid = findContactForTarget(CFG_SIDE_RED, tgt, targetName)

    _errnum_ = 0
    local r
    if contactGuid then
        r = ScenEdit_AttackContact(atk.guid, contactGuid,
                {mode = 1, weapon = wpnDbid, qty = qty})
        info(attackerName .. " → contact 攻击 " .. targetName)
    else
        if CFG_ALLOW_BOL_FALLBACK then
            warn(attackerName .. " 无 contact，降级 BOL 朝坐标发射")
            r = ScenEdit_AttackContact(atk.guid, "BOL", {
                    latitude = tgt.latitude, longitude = tgt.longitude,
                    mode = 1, weapon = wpnDbid, qty = qty,
                })
        else
            err(attackerName .. " 无 contact 且 BOL 已禁用，取消发射: " .. targetName)
            return false
        end
    end

    if r and (_errnum_ or 0) == 0 then
        ok(attackerName .. " 发射 " .. qty .. "x [" .. wpnDbid .. "] YJ-18 → " .. targetName)
        return true
    else
        err(attackerName .. " 攻击 " .. targetName .. " 失败: " .. tostring(_errmsg_))
        return false
    end
end

-- ---------- 执行打击 ----------
info("=== 下达打击指令 ===")
for _, s in ipairs(STRIKE) do fireAt(s[1], s[2], s[3], s[4]) end
info("=== 打击指令下达完毕 ===")
