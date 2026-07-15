-- ============================================================
-- attack.lua  — 红方打击脚本
-- 打击方案（MCP 武器 DBID）:
--   YJ-21 = 4058  |  YJ-18 = 2868
--
-- 打击清单:
--   Red-052D-Alpha  → 蓝方 DDG-113       : YJ-21 ×4
--   Red-052D-Beta   → 蓝方 CVN-70        : YJ-21 ×6
--   Red-055-Alpha   → 蓝方 CG-59         : YJ-18 ×7
-- ============================================================

Tool_EmulateNoConsole(true)

local LOG        = '[CMO]'
local SIDE_RED   = '红方'
local SIDE_BLUE  = '蓝方'

-- ============================================================
-- 打击任务表
-- { 攻击方,           目标名,        武器DBID, 数量, 武器标签 }
-- ============================================================
local STRIKE_PLAN = {
    { "Red-052D-Alpha", "DDG-113",    4058, 4, "YJ-21" },
    { "Red-052D-Beta",  "Blue-CVN70", 4058, 6, "YJ-21" },
    { "Red-055-Alpha", "Blue-CG59",   2868, 7, "YJ-18" },
}

-- ============================================================
-- 辅助函数：从红方 contact 列表中查找目标 unit GUID
-- ============================================================
local function findContactGuid(unitGuid)
    local pok, contacts = pcall(ScenEdit_GetContacts, {side = SIDE_RED})
    if not (pok and contacts) then return nil end
    for _, c in ipairs(contacts) do
        if c.actualunitid == unitGuid then
            return c.guid
        end
    end
    return nil
end

-- ============================================================
-- 辅助函数：执行单次打击（contact 优先 → BOL 兜底）
-- ============================================================
local function fireAt(attackerName, targetName, wpnDbid, qty, wpnLabel)
    local atk = ScenEdit_GetUnit({side = SIDE_RED, name = attackerName})
    local tgt = ScenEdit_GetUnit({side = SIDE_BLUE, name = targetName})

    if not (atk and atk.guid) then
        print(LOG .. ' [ERROR] 找不到攻击方: ' .. attackerName)
        return false
    end
    if not (tgt and tgt.guid) then
        print(LOG .. ' [ERROR] 找不到目标: ' .. targetName)
        return false
    end

    -- 优先：contact 精确打击
    local contactGuid = findContactGuid(tgt.guid)
    _errnum_ = 0

    local r
    if contactGuid then
        -- 红方全知模式，目标已在 contact 列表中
        r = ScenEdit_AttackContact(atk.guid, contactGuid, {
            mode   = 1,
            weapon = wpnDbid,
            qty    = qty,
        })
        print(LOG .. ' [INFO] ' .. attackerName .. ' → contact 精确打击 → ' .. targetName)
    else
        -- 降级：BOL 朝坐标发射（武器自行搜索导引头）
        print(LOG .. ' [WARNING] ' .. attackerName
            .. ' 未探测到 ' .. targetName .. '，改用 BOL 朝坐标发射')
        r = ScenEdit_AttackContact(atk.guid, 'BOL', {
            latitude  = tgt.latitude,
            longitude = tgt.longitude,
            mode      = 1,
            weapon    = wpnDbid,
            qty       = qty,
        })
    end

    if r and (_errnum_ or 0) == 0 then
        print(LOG .. ' [OK] ' .. attackerName .. ' 发射 '
            .. qty .. 'x [' .. wpnLabel .. '] → ' .. targetName)
        return true
    else
        print(LOG .. ' [ERROR] ' .. attackerName .. ' 攻击 ' .. targetName
            .. ' 失败: ' .. tostring(_errmsg_))
        return false
    end
end

-- ============================================================
-- 执行打击
-- ============================================================
print(LOG .. ' === 红方打击开始 ===')

local successCount = 0
for _, s in ipairs(STRIKE_PLAN) do
    local ok = fireAt(s[1], s[2], s[3], s[4], s[5])
    if ok then successCount = successCount + 1 end
end

print(LOG .. ' === 打击完毕: ' .. successCount .. '/' .. #STRIKE_PLAN .. ' 成功 ===')
print(LOG .. ' 备注: 红方为全知模式，contact 攻击正常可用')
print(LOG .. '       若某些目标不在 contact 中，将自动降级为 BOL 模式')
print(LOG .. ' attack.lua 执行完毕')
