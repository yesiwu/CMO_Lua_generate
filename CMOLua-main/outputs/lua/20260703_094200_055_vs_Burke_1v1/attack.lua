-- ============================================================
-- attack.lua - 055发射13枚YJ-18攻击Burke
-- 使用方式: 运行 main.lua → clear.lua → reload.lua 后再运行本脚本
-- ============================================================

local LOG_PREFIX = "[CMO-ATTACK]"
local function log(level, msg) print(LOG_PREFIX .. " [" .. level .. "] " .. msg) end
local function info(msg) log("INFO", msg) end
local function ok(msg) log("SUCCESS", msg) end
local function warn(msg) log("WARNING", msg) end
local function err(msg) log("ERROR", msg) end

-- ---------- 配置区 ----------
local CFG_SIDE_RED = "红方"
local CFG_SIDE_BLUE = "蓝方"
local CFG_BLUE_AUTODETECTABLE = true   -- 必须为true，红方才能稳定获得contact
local CFG_ALLOW_BOL_FALLBACK = false   -- 对移动舰艇建议false

local DBID_YJ18 = 2868                   -- YJ-18（用户提供）
local NAME_055 = "055-Nanchang"          -- 必须与main.lua的name一致！
local NAME_BURKE = "DDG-51-Burke"        -- 必须与main.lua的name一致！
local STRIKE_QTY = 13                    -- 发射13枚

-- 辅助函数
local function sameGuid(a, b)
    return a and b and tostring(a):lower() == tostring(b):lower()
end

-- ---------- 收集Contact函数 ----------
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

-- ---------- 查找目标Contact ----------
local function findContactForTarget(sideName, tgt, tgtName)
    if not (tgt and tgt.guid) then return nil end
    pcall(ScenEdit_SetSideOptions, {side = sideName, awareness = "OMNI"})
    local cs = collectContacts(sideName)
        for _, c in ipairs(cs) do
            local cg = c.guid or c.Guid
            if not cg then
                -- skip this contact
            elseif sameGuid(c.actualunitid, tgt.guid)
                or sameGuid(c.actualUnitID, tgt.guid)
                or sameGuid(c.actualunitguid, tgt.guid)
                or sameGuid(c.actualUnitGuid, tgt.guid)
                or sameGuid(c.actualunit, tgt.guid)
                or sameGuid(c.actualUnit, tgt.guid) then
                info("matched contact for " .. tgtName .. " by GUID: " .. cg)
                return cg
            elseif (c.name or c.Name or "") == tgtName then
                info("matched contact for " .. tgtName .. " by name: " .. cg)
                return cg
            end
        end
    return nil
end

-- ---------- 打击函数 ----------
local function fireAt(attackerName, targetName, wpnDbid, qty)
    local atk = ScenEdit_GetUnit({side = CFG_SIDE_RED, name = attackerName})
    local tgt = ScenEdit_GetUnit({side = CFG_SIDE_BLUE, name = targetName})

    if not (atk and atk.guid) then
        err("找不到攻击方 " .. attackerName); return false end
    if not (tgt and tgt.guid) then
        err("找不到目标 " .. targetName); return false end

    -- 关键：每次发射前强制设autodetectable
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
            warn(attackerName .. " 无contact，降级BOL朝坐标发射")
            r = ScenEdit_AttackContact(atk.guid, "BOL", {
                    latitude = tgt.latitude, longitude = tgt.longitude,
                    mode = 1, weapon = wpnDbid, qty = qty,
                })
        else
            err(attackerName .. " 无contact且BOL已禁用，取消发射: " .. targetName)
            return false
        end
    end

    if r and (_errnum_ or 0) == 0 then
        ok(attackerName .. " 发射 " .. qty .. "x [YJ-18:" .. wpnDbid .. "] → " .. targetName)
        return true
    else
        err(attackerName .. " 攻击 " .. targetName .. " 失败: " .. tostring(_errmsg_))
        return false
    end
end

-- ---------- 执行打击 ----------
print("")
print("=================================================")
print("  下达打击指令")
print("=================================================")

info("攻击方: " .. NAME_055)
info("目标: " .. NAME_BURKE)
info("武器: YJ-18 (DBID " .. DBID_YJ18 .. ")")
info("数量: " .. STRIKE_QTY .. "枚")
print("")

local success = fireAt(NAME_055, NAME_BURKE, DBID_YJ18, STRIKE_QTY)

print("")
if success then
    ok("打击指令已下达!")
else
    err("打击指令下达失败!")
end
print("=================================================")
print("")
