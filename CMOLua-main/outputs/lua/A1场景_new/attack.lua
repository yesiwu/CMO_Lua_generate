-- ============================================================
-- attack.lua — 红方第一轮饱和打击
-- 来源：替代方案 B 打击分配
-- 武器 DBID：YJ-20 → YJ-83(541) | YJ-18(2868)
-- ============================================================

Tool_EmulateNoConsole(true)

local LOG       = "[CMO]"
local SIDE_RED  = "红方"
local SIDE_BLUE = "蓝方"

-- ============================================================
-- 第一轮打击分配表
-- { 攻击方单位名, 目标单位名, 武器DBID, 数量, 武器标签 }
-- ============================================================
local STRIKE = {
    -- Red 052D-1 → Blue FFG-1: YJ-83 ×4
    { "Red-052D-1", "Blue-FFG-1",  541, 4, "YJ-83" },
    -- Red 052D-2 → Blue DDG-2: YJ-83 ×6
    { "Red-052D-2", "Blue-DDG-2",  541, 6, "YJ-83" },
    -- Red 052D-3 → Blue LPD-1: YJ-18 ×6
    { "Red-052D-3", "Blue-LPD-1",  2868, 6, "YJ-18" },
    -- Red 055-1 → Blue DDG-1: YJ-83 ×8
    { "Red-055-1",  "Blue-DDG-1",  541, 8, "YJ-83" },
    -- Red 055-2 → Blue AOR-1: YJ-18 ×8
    { "Red-055-2",  "Blue-AOR-1",  2868, 8, "YJ-18" },
}

-- ============================================================
-- 从 contact 列表查找目标 GUID
-- ============================================================
local function findContactGuid(unitGuid)
    local pok, contacts = pcall(ScenEdit_GetContacts, { side = SIDE_RED })
    if not (pok and contacts) then return nil end
    for _, c in ipairs(contacts) do
        if c.actualunitid == unitGuid then return c.guid end
    end
    return nil
end

-- ============================================================
-- 单次打击（contact 优先 → BOL 兜底）
-- ============================================================
local function fireAt(atkName, tgtName, wpnDbid, qty, wpnLabel)
    local atk = ScenEdit_GetUnit({ side = SIDE_RED, name = atkName })
    local tgt = ScenEdit_GetUnit({ side = SIDE_BLUE, name = tgtName })
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
            latitude = tgt.latitude, longitude = tgt.longitude,
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

-- ============================================================
-- 统计
-- ============================================================
local function countByWeapon(strike)
    local counts = {}
    for _, s in ipairs(strike) do
        local label = s[5]
        counts[label] = (counts[label] or 0) + s[4]
    end
    return counts
end

-- ============================================================
-- 执行
-- ============================================================
local weaponCounts = countByWeapon(STRIKE)
local total = 0
for w, n in pairs(weaponCounts) do total = total + n end

print(LOG .. " ================================================")
print(LOG .. " === 红方第一轮饱和打击开始 ===")
print(LOG .. " 打击平台: Red 052D-1/2/3, Red 055-1/2")
print(LOG .. " 目标:     Blue DDG-1/2, Blue FFG-1, Blue LPD-1, Blue AOR-1")
print(LOG .. " 武器:     YJ-83 ×" .. (weaponCounts["YJ-83"] or 0)
    .. " | YJ-18 ×" .. (weaponCounts["YJ-18"] or 0))
print(LOG .. " 总计:     " .. total .. " 枚反舰导弹")
print(LOG .. " 红方模式: OMNI（全知全能，contact 攻击正常可用）")
print(LOG .. " ================================================")

local successCount = 0
for _, s in ipairs(STRIKE) do
    if fireAt(s[1], s[2], s[3], s[4], s[5]) then
        successCount = successCount + 1
    end
end

print(LOG .. " === 第一轮打击完毕: " .. successCount .. "/" .. #STRIKE .. " 成功 ===")
print(LOG .. " YJ-83 发射: " .. (weaponCounts["YJ-83"] or 0) .. " 枚")
print(LOG .. " YJ-18  发射: " .. (weaponCounts["YJ-18"]  or 0) .. " 枚")
print(LOG .. " attack.lua 执行完毕")
