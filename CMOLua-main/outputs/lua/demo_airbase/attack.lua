-- attack.lua — 演示：蓝方 F/A-18C 对红方机场发起对面打击
--
-- 武器 DBID（MCP 查询）：
--   SLAM-ER   DBID=2869   远程对面/反舰巡航导弹
--
-- 打击目标：红方机场-跑道
-- 攻击平台：FA18C-001, FA18C-002（来自 main.lua）
-- =====================================================================

Tool_EmulateNoConsole(true)

local LOG       = "[CMO]"
local SIDE_RED  = "红方"
local SIDE_BLUE = "蓝方"

-- =====================================================================
-- 武器 DBID
-- =====================================================================
local WPN_SLAMER = 2869   -- SLAM-ER（对地攻击）

-- =====================================================================
-- 打击分配表
-- { 攻击方, 目标, 武器DBID, 数量 }
-- =====================================================================
local STRIKE = {
    -- FA18C-001 ×4 SLAM-ER → 红方跑道
    { "FA18C-001", "红方机场-跑道", WPN_SLAMER, 4, "SLAM-ER" },
    -- FA18C-002 ×4 SLAM-ER → 红方大机库
    { "FA18C-002", "红方机场-大机库", WPN_SLAMER, 4, "SLAM-ER" },
}

-- =====================================================================
-- 从 contact 列表查找目标 GUID
-- =====================================================================
local function findContactGuid(targetGuid)
    local pok, contacts = pcall(ScenEdit_GetContacts, { side = SIDE_BLUE })
    if not (pok and contacts) then return nil end
    for _, c in ipairs(contacts) do
        if c.actualunitid == targetGuid then return c.guid end
    end
    return nil
end

-- =====================================================================
-- 单次打击（contact 优先 → BOL 坐标兜底）
-- =====================================================================
local function fireAt(atkName, tgtName, wpnDbid, qty, wpnLabel)
    local atk = ScenEdit_GetUnit({ side = SIDE_BLUE, name = atkName })
    local tgt = ScenEdit_GetUnit({ side = SIDE_RED,  name = tgtName })
    if not (atk and atk.guid) then
        print(LOG .. " [ERROR] 找不到攻击方: " .. atkName); return false end
    if not (tgt and tgt.guid) then
        print(LOG .. " [ERROR] 找不到目标: " .. tgtName); return false end

    local contactGuid = findContactGuid(tgt.guid)
    _errnum_ = 0
    local r
    if contactGuid then
        r = ScenEdit_AttackContact(atk.guid, contactGuid, {
            mode = 1, weapon = wpnDbid, qty = qty })
        print(LOG .. " [INFO] " .. atkName .. " → contact → " .. tgtName)
    else
        print(LOG .. " [WARN] " .. atkName
            .. " 未探测到 " .. tgtName .. "，改用 BOL 朝坐标发射")
        r = ScenEdit_AttackContact(atk.guid, "BOL", {
            latitude  = tgt.latitude,
            longitude = tgt.longitude,
            mode = 1, weapon = wpnDbid, qty = qty })
    end

    if r and (_errnum_ or 0) == 0 then
        print(LOG .. " [OK] " .. atkName .. " → "
            .. qty .. "x [" .. wpnLabel .. "] → " .. tgtName)
        return true
    else
        print(LOG .. " [ERROR] " .. atkName .. " 攻击 " .. tgtName
            .. " 失败: " .. tostring(_errmsg_))
        return false
    end
end

-- =====================================================================
-- 统计
-- =====================================================================
local function countByWeapon(strike)
    local counts = {}
    for _, s in ipairs(strike) do
        local label = s[5]
        counts[label] = (counts[label] or 0) + s[4]
    end
    return counts
end

-- =====================================================================
-- 执行
-- =====================================================================
local weaponCounts = countByWeapon(STRIKE)
local total = 0
for w, n in pairs(weaponCounts) do total = total + n end

print(LOG .. " ================================================")
print(LOG .. " === 蓝方对面打击开始 ===")
print(LOG .. " 打击平台: FA18C-001, FA18C-002")
print(LOG .. " 目标:     红方机场-跑道, 红方机场-大机库")
print(LOG .. " 武器:     SLAM-ER ×" .. (weaponCounts["SLAM-ER"] or 0))
print(LOG .. " 总计:     " .. total .. " 枚巡航导弹")
print(LOG .. " ================================================")

local successCount = 0
for _, s in ipairs(STRIKE) do
    if fireAt(s[1], s[2], s[3], s[4], s[5]) then
        successCount = successCount + 1
    end
end

print(LOG .. " === 打击完毕: " .. successCount .. "/" .. #STRIKE .. " 成功 ===")
print(LOG .. " attack.lua 执行完毕")
